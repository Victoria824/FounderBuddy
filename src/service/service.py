import inspect
import json
import logging
import time
import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core._api import LangChainBetaWarning
from langchain_core.messages import AIMessage, AIMessageChunk, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse  # type: ignore[import-untyped]
from langfuse.callback import CallbackHandler  # type: ignore[import-untyped]
from langgraph.types import Command, Interrupt
from langsmith import Client as LangsmithClient
from starlette.middleware.base import BaseHTTPMiddleware

from agents import DEFAULT_AGENT, AgentGraph, get_agent, get_all_agent_info
from agents.value_canvas.agent import initialize_value_canvas_state
from agents.value_canvas.prompts import SECTION_TEMPLATES
from core import settings
from integrations.dentapp.dentapp_utils import SECTION_ID_MAPPING
from memory import initialize_database, initialize_store
from schema import (
    ChatHistory,
    ChatHistoryInput,
    ChatMessage,
    Feedback,
    FeedbackResponse,
    InvokeResponse,
    ServiceMetadata,
    StreamInput,
    UserInput,
)
from service.utils import (
    convert_message_content_to_string,
    langchain_to_chat_message,
    remove_tool_calls,
)

warnings.filterwarnings("ignore", category=LangChainBetaWarning)
logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming frontend requests with detailed information."""
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID for tracking
        request_id = str(uuid4())[:8]
        start_time = time.time()
        
        # Log request details
        logger.info(f"=== FRONTEND_REQUEST_START: {request_id} ===")
        logger.info(f"FRONTEND_REQUEST: {request.method} {request.url}")
        logger.info(f"FRONTEND_REQUEST: Client IP: {request.client.host if request.client else 'unknown'}")
        logger.info(f"FRONTEND_REQUEST: User-Agent: {request.headers.get('user-agent', 'unknown')}")
        logger.info(f"FRONTEND_REQUEST: Content-Type: {request.headers.get('content-type', 'unknown')}")
        
        # Log all headers (excluding sensitive ones)
        sensitive_headers = {'authorization', 'cookie', 'x-api-key'}
        headers_to_log = {
            k: v for k, v in request.headers.items() 
            if k.lower() not in sensitive_headers
        }
        logger.info(f"FRONTEND_REQUEST: Headers: {headers_to_log}")
        
        # Log query parameters
        if request.query_params:
            logger.info(f"FRONTEND_REQUEST: Query params: {dict(request.query_params)}")
        
        # Log request body for POST/PUT requests, but skip for streaming endpoints
        is_streaming_endpoint = "/stream" in str(request.url.path)
        if request.method in ["POST", "PUT", "PATCH"] and not is_streaming_endpoint:
            try:
                # Use the safer approach for non-streaming endpoints
                body = await request.body()
                if body:
                    # Try to parse as JSON for better logging
                    try:
                        body_json = json.loads(body.decode('utf-8'))
                        # Mask sensitive fields
                        masked_body = mask_sensitive_fields(body_json)
                        logger.info(f"FRONTEND_REQUEST: Body (JSON): {json.dumps(masked_body, ensure_ascii=False)}")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Log as raw text if not JSON
                        body_str = body.decode('utf-8', errors='replace')[:1000]  # Limit size
                        logger.info(f"FRONTEND_REQUEST: Body (raw): {body_str}")
                else:
                    logger.info("FRONTEND_REQUEST: Body: (empty)")
                    
            except Exception as e:
                logger.warning(f"FRONTEND_REQUEST: Could not read body: {e}")
        elif is_streaming_endpoint:
            # For streaming endpoints, just log that we're skipping body logging
            logger.info("FRONTEND_REQUEST: Body: (skipped for streaming endpoint)")
        
        # Process the request
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Log response details
            logger.info(f"=== FRONTEND_RESPONSE_END: {request_id} ===")
            logger.info(f"FRONTEND_RESPONSE: Status: {response.status_code}")
            logger.info(f"FRONTEND_RESPONSE: Processing time: {process_time:.3f}s")
            logger.info(f"FRONTEND_RESPONSE: Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"=== FRONTEND_REQUEST_ERROR: {request_id} ===")
            logger.error(f"FRONTEND_ERROR: {str(e)}")
            logger.error(f"FRONTEND_ERROR: Processing time: {process_time:.3f}s")
            raise


def mask_sensitive_fields(data: dict | list | Any) -> dict | list | Any:
    """Mask sensitive fields in request data for logging."""
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in ['password', 'token', 'secret', 'key', 'auth']):
                masked[key] = "***MASKED***"
            elif isinstance(value, (dict, list)):
                masked[key] = mask_sensitive_fields(value)
            else:
                masked[key] = value
        return masked
    elif isinstance(data, list):
        return [mask_sensitive_fields(item) for item in data]
    else:
        return data


def verify_bearer(
    http_auth: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(HTTPBearer(description="Please provide AUTH_SECRET api key.", auto_error=False)),
    ],
) -> None:
    if not settings.AUTH_SECRET:
        return
    auth_secret = settings.AUTH_SECRET.get_secret_value()
    if not http_auth or http_auth.credentials != auth_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Configurable lifespan that initializes the appropriate database checkpointer and store
    based on settings.
    """
    try:
        # Initialize both checkpointer (for short-term memory) and store (for long-term memory)
        async with initialize_database() as saver, initialize_store() as store:
            # Set up both components
            if hasattr(saver, "setup"):  # ignore: union-attr
                await saver.setup()
            # Only setup store for Postgres as InMemoryStore doesn't need setup
            if hasattr(store, "setup"):  # ignore: union-attr
                await store.setup()

            # Configure agents with both memory components
            agents = get_all_agent_info()
            for a in agents:
                agent = get_agent(a.key)
                # Set checkpointer for thread-scoped memory (conversation history)
                agent.checkpointer = saver
                # Set store for long-term memory (cross-conversation knowledge)
                agent.store = store
            yield
    except Exception as e:
        logger.error(f"Error during database/store initialization: {e}")
        raise


app = FastAPI(lifespan=lifespan)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

router = APIRouter(dependencies=[Depends(verify_bearer)])


@router.get("/info")
async def info() -> ServiceMetadata:
    return ServiceMetadata(
        agents=get_all_agent_info(),
        models=[],  # Models are server-managed, not user-selectable
        default_agent=DEFAULT_AGENT,
        default_model=None,  # Model selection is server-internal
    )


async def _handle_input(user_input: UserInput, agent: AgentGraph) -> tuple[dict[str, Any], UUID]:
    """
    Parse user input and handle any required interrupt resumption.
    Returns kwargs for agent invocation and the run_id.
    """
    run_id = uuid4()
    thread_id = user_input.thread_id
    user_id = user_input.user_id

    callbacks = []
    if settings.LANGFUSE_TRACING:
        langfuse_handler = CallbackHandler()
        callbacks.append(langfuse_handler)

    if not thread_id:
        # This is a new conversation - generate new thread_id and let graph initialize naturally
        thread_id = str(uuid4())
        logger.info(f"Generated new thread with ID: {thread_id}")
    else:
        # This is an existing conversation, so we load the state
        logger.info(f"Loading existing thread with ID: {thread_id}")
    
    # Build the configurable dict
    configurable = {
        "thread_id": thread_id,
        "user_id": user_id,
    }
    
    # Pass thread_id to agent
    configurable["thread_id"] = thread_id
    
    # Add user's custom agent config if provided
    if user_input.agent_config:
        if overlap := configurable.keys() & user_input.agent_config.keys():
            raise HTTPException(
                status_code=422,
                detail=f"agent_config contains reserved keys: {overlap}",
            )
        configurable.update(user_input.agent_config)
    
    # Create a configuration for the thread
    config = RunnableConfig(
        configurable=configurable,
        run_id=run_id,
        callbacks=callbacks,
    )

    # Check for interrupts that need to be resumed
    if not user_input.thread_id:
        # 新线程 - 刚初始化状态，不会有中断需要恢复
        # 避免调用aget_state引发graph意外执行
        interrupted_tasks = []
    else:
        # 现有线程 - 检查是否有中断需要恢复
        state = await agent.aget_state(config=config)
        interrupted_tasks = [
            task for task in state.tasks if hasattr(task, "interrupts") and task.interrupts
        ]

    input: Command | dict[str, Any]
    if interrupted_tasks:
        input = Command(resume=user_input.message)
    else:
        input = {"messages": [HumanMessage(content=user_input.message)]}

    kwargs = {
        "input": input,
        "config": config,
    }

    return kwargs, run_id


@router.post("/{agent_id}/invoke")
@router.post("/invoke")
async def invoke(user_input: UserInput, agent_id: str = DEFAULT_AGENT) -> InvokeResponse:
    """
    Invoke an agent with user input to retrieve a final response.

    If agent_id is not provided, the default agent will be used.
    Use thread_id to persist and continue a multi-turn conversation. run_id kwarg
    is also attached to messages for recording feedback.
    Use user_id to persist and continue a conversation across multiple threads.
    """
    # Log detailed invoke request
    logger.info(f"=== INVOKE_REQUEST: agent_id={agent_id} ===")
    logger.info(f"INVOKE_REQUEST: user_id={user_input.user_id}")
    logger.info(f"INVOKE_REQUEST: thread_id={user_input.thread_id}")
    # Model selection is handled by server configuration
    logger.info(f"INVOKE_REQUEST: message_length={len(user_input.message) if user_input.message else 0}")
    logger.info(f"INVOKE_REQUEST: agent_config={user_input.agent_config}")
    
    # NOTE: Currently this only returns the last message or interrupt.
    # In the case of an agent outputting multiple AIMessages (such as the background step
    # in interrupt-agent, or a tool step in research-assistant), it's omitted. Arguably,
    # you'd want to include it. You could update the API to return a list of ChatMessages
    # in that case.
    agent: AgentGraph = get_agent(agent_id)
    kwargs, run_id = await _handle_input(user_input, agent)
    
    logger.info(f"INVOKE_REQUEST: run_id={run_id}")
    logger.info(f"INVOKE_REQUEST: config_thread_id={kwargs['config']['configurable']['thread_id']}")

    try:
        response_events: list[tuple[str, Any]] = await agent.ainvoke(**kwargs, stream_mode=["updates", "values"])  # type: ignore # fmt: skip
        response_type, response = response_events[-1]
        if response_type == "values":
            # Normal response, the agent completed successfully
            output = langchain_to_chat_message(response["messages"][-1])
        elif response_type == "updates" and "__interrupt__" in response:
            # The last thing to occur was an interrupt
            # Return the value of the first interrupt as an AIMessage
            output = langchain_to_chat_message(
                AIMessage(content=response["__interrupt__"][0].value)
            )
        else:
            raise ValueError(f"Unexpected response type: {response_type}")

        output.run_id = str(run_id)

        # Get the latest state to include section data
        state = await agent.aget_state(config=kwargs["config"])
        if "current_section" in state.values:
            current_section_enum = state.values["current_section"]
            current_section_id = current_section_enum.value  # Use the string value
            section_state = state.values.get("section_states", {}).get(current_section_id)
            section_template = SECTION_TEMPLATES.get(current_section_id)

            section_data = {
                "database_id": SECTION_ID_MAPPING.get(current_section_id),
                "name": section_template.name if section_template else "Unknown Section",
                "status": section_state.status.value if section_state else "pending",
            }
            output.custom_data["section"] = section_data

        invoke_response = InvokeResponse(
            output=output,
            thread_id=kwargs["config"]["configurable"]["thread_id"],
            user_id=kwargs["config"]["configurable"]["user_id"],
        )
        
        # Log successful response
        logger.info(f"=== INVOKE_RESPONSE_SUCCESS: run_id={run_id} ===")
        logger.info(f"INVOKE_RESPONSE: output_type={output.type}")
        logger.info(f"INVOKE_RESPONSE: content_length={len(output.content) if output.content else 0}")
        logger.info(f"INVOKE_RESPONSE: thread_id={invoke_response.thread_id}")
        logger.info(f"INVOKE_RESPONSE: user_id={invoke_response.user_id}")
        logger.info(f"INVOKE_RESPONSE: has_custom_data={bool(output.custom_data)}")
        
        return invoke_response
    except Exception as e:
        logger.error(f"=== INVOKE_ERROR: run_id={run_id} ===")
        logger.error(f"INVOKE_ERROR: {str(e)}")
        logger.error(f"INVOKE_ERROR: agent_id={agent_id}")
        logger.error(f"INVOKE_ERROR: user_id={user_input.user_id}")
        logger.error(f"INVOKE_ERROR: thread_id={user_input.thread_id}")
        raise HTTPException(status_code=500, detail="Unexpected error")


async def message_generator(
    user_input: StreamInput, agent_id: str = DEFAULT_AGENT
) -> AsyncGenerator[str, None]:
    """
    Generate a stream of messages from the agent.

    This is the workhorse method for the /stream endpoint.
    """
    # Log detailed stream request
    logger.info(f"=== STREAM_REQUEST: agent_id={agent_id} ===")
    logger.info(f"STREAM_REQUEST: user_id={user_input.user_id}")
    logger.info(f"STREAM_REQUEST: thread_id={user_input.thread_id}")
    # Model selection is handled by server configuration
    logger.info(f"STREAM_REQUEST: stream_tokens={user_input.stream_tokens}")
    logger.info(f"STREAM_REQUEST: message_length={len(user_input.message) if user_input.message else 0}")
    
    agent: AgentGraph = get_agent(agent_id)
    kwargs, run_id = await _handle_input(user_input, agent)
    
    logger.info(f"STREAM_REQUEST: run_id={run_id}")
    logger.info(f"STREAM_REQUEST: config_thread_id={kwargs['config']['configurable']['thread_id']}")

    sent_message_count = 0  # Track the number of messages sent to prevent duplicates

    try:
        # Process streamed events from the graph and yield messages over the SSE stream.
        async for stream_event in agent.astream(
            **kwargs, stream_mode=["updates", "messages", "custom"]
        ):
            # [STREAM_DEBUG] Log every raw event from the graph stream
            logger.info(f"STREAM_DEBUG: Raw Event Received: {repr(stream_event)}")

            if not isinstance(stream_event, tuple):
                continue
            stream_mode, event = stream_event
            new_messages = []
            if stream_mode == "updates":
                for node, updates in event.items():
                    # A simple approach to handle agent interrupts.
                    # In a more sophisticated implementation, we could add
                    # some structured ChatMessage type to return the interrupt value.
                    if node == "__interrupt__":
                        interrupt: Interrupt
                        for interrupt in updates:
                            new_messages.append(AIMessage(content=interrupt.value))
                        continue
                    updates = updates or {}
                    
                    # Only process new messages we haven't sent before
                    update_messages = updates.get("messages", [])
                    if len(update_messages) > sent_message_count:
                        new_messages.extend(update_messages[sent_message_count:])
                        sent_message_count = len(update_messages)

            if stream_mode == "custom":
                new_messages = [event]

            # LangGraph streaming may emit tuples: (field_name, field_value)
            # e.g. ('content', <str>), ('tool_calls', [ToolCall,...]), ('additional_kwargs', {...}), etc.
            # We accumulate only supported fields into `parts` and skip unsupported metadata.
            # More info at: https://langchain-ai.github.io/langgraph/cloud/how-tos/stream_messages/
            processed_messages = []
            current_message: dict[str, Any] = {}
            for message in new_messages:
                if isinstance(message, tuple):
                    key, value = message
                    # DEBUG: Log all tuple events to identify what we're missing
                    logger.info(f"🔍 TUPLE_EVENT: key='{key}', value_type={type(value).__name__}")
                    # Skip function calling related tuples - these are internal operations, not user messages
                    if key in ['tool_calls', 'additional_kwargs', 'invalid_tool_calls']:
                        logger.info(f"🚫 SKIPPING function call tuple: {key}")
                        continue
                    # Store parts in temporary dict
                    logger.info(f"✅ KEEPING tuple: {key}")
                    current_message[key] = value
                else:
                    # Add complete message if we have one in progress
                    if current_message:
                        # Only process messages that contain content (user-facing messages)
                        if 'content' in current_message:
                            processed_messages.append(_create_ai_message(current_message))
                        current_message = {}
                    processed_messages.append(message)

            # Add any remaining message parts
            if current_message:
                # Only process messages that contain content (user-facing messages)
                if 'content' in current_message:
                    processed_messages.append(_create_ai_message(current_message))

            for message in processed_messages:
                # TEMP DEBUG: print the raw message structure to diagnose content KeyError
                logger.info(f"🪵 RAW_MESSAGE: {repr(message)}")
                
                try:
                    # FIX: Skip processing for internal, content-less messages from structured_output calls
                    if isinstance(message, AIMessage) and not message.content:
                        if message.tool_calls or message.invalid_tool_calls:
                            logger.info(f"🚫 SKIPPING internal tool_call message: {repr(message)}")
                            continue

                    logger.info(f"🔧 CONVERTING message type: {type(message).__name__}")
                    chat_message = langchain_to_chat_message(message)
                    logger.info(f"✅ CONVERSION SUCCESS for {type(message).__name__}")
                    chat_message.run_id = str(run_id)
                except Exception as e:
                    logger.error(f"❌ CONVERSION FAILED: {e}")
                    logger.error(f"❌ FAILED MESSAGE TYPE: {type(message).__name__}")
                    logger.error(f"❌ FAILED MESSAGE CONTENT: {repr(message)}")
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Unexpected error'})}\n\n"
                    continue
                # LangGraph re-sends the input message, which feels weird, so drop it
                if chat_message.type == "human" and chat_message.content == user_input.message:
                    continue
                yield f"data: {json.dumps({'type': 'message', 'content': chat_message.model_dump()})}\n\n"

            if stream_mode == "messages":
                if not user_input.stream_tokens:
                    continue
                msg, metadata = event
                if "skip_stream" in metadata.get("tags", []):
                    continue
                # Only process AIMessageChunk for token streaming
                if not isinstance(msg, AIMessageChunk):
                    continue
                content = remove_tool_calls(msg.content)
                if content:
                    # Empty content in the context of OpenAI usually means
                    # that the model is asking for a tool to be invoked.
                    # So we only print non-empty content.
                    yield f"data: {json.dumps({'type': 'token', 'content': convert_message_content_to_string(content)})}\n\n"
    except Exception as e:
        logger.error(f"=== STREAM_ERROR: run_id={run_id} ===")
        logger.error(f"STREAM_ERROR: {str(e)}")
        logger.error(f"STREAM_ERROR: agent_id={agent_id}")
        logger.error(f"STREAM_ERROR: user_id={user_input.user_id}")
        logger.error(f"STREAM_ERROR: thread_id={user_input.thread_id}")
        yield f"data: {json.dumps({'type': 'error', 'content': 'Internal server error'})}\n\n"
    finally:
        # Always send section data at the end of the stream
        try:
            state = await agent.aget_state(config=kwargs["config"])
            if "current_section" in state.values:
                current_section_enum = state.values["current_section"]
                current_section_id = current_section_enum.value  # Use the string value
                section_state = state.values.get("section_states", {}).get(current_section_id)
                section_template = SECTION_TEMPLATES.get(current_section_id)

                section_data = {
                    "database_id": SECTION_ID_MAPPING.get(current_section_id),
                    "name": section_template.name if section_template else "Unknown Section",
                    "status": section_state.status.value if section_state else "pending",
                }
                yield f"data: {json.dumps({'type': 'section', 'content': section_data})}\n\n"
        except Exception as e:
            logger.error(f"Error getting section data: {e}")

        # Log stream completion
        logger.info(f"=== STREAM_COMPLETE: run_id={run_id} ===")
        logger.info(f"STREAM_COMPLETE: agent_id={agent_id}")
        logger.info(f"STREAM_COMPLETE: thread_id={kwargs['config']['configurable']['thread_id']}")
        
        yield "data: [DONE]\n\n"


def _create_ai_message(parts: dict) -> AIMessage:
    sig = inspect.signature(AIMessage)
    valid_keys = set(sig.parameters)
    filtered = {k: v for k, v in parts.items() if k in valid_keys}
    # Ensure content field is always present (AIMessage requires it)
    if 'content' not in filtered:
        filtered['content'] = ""
    return AIMessage(**filtered)


def _sse_response_example() -> dict[int | str, Any]:
    return {
        status.HTTP_200_OK: {
            "description": "Server Sent Event Response",
            "content": {
                "text/event-stream": {
                    "example": "data: {'type': 'token', 'content': 'Hello'}\n\ndata: {'type': 'token', 'content': ' World'}\n\ndata: [DONE]\n\n",
                    "schema": {"type": "string"},
                }
            },
        }
    }


@router.post(
    "/{agent_id}/stream",
    response_class=StreamingResponse,
    responses=_sse_response_example(),
)
@router.post("/stream", response_class=StreamingResponse, responses=_sse_response_example())
async def stream(user_input: StreamInput, agent_id: str = DEFAULT_AGENT) -> StreamingResponse:
    """
    Stream an agent's response to a user input, including intermediate messages and tokens.

    If agent_id is not provided, the default agent will be used.
    Use thread_id to persist and continue a multi-turn conversation. run_id kwarg
    is also attached to all messages for recording feedback.
    Use user_id to persist and continue a conversation across multiple threads.

    Set `stream_tokens=false` to return intermediate messages but not token-by-token.
    """
    return StreamingResponse(
        message_generator(user_input, agent_id),
        media_type="text/event-stream",
    )


@router.post("/feedback")
async def feedback(feedback: Feedback) -> FeedbackResponse:
    """
    Record feedback for a run to LangSmith.

    This is a simple wrapper for the LangSmith create_feedback API, so the
    credentials can be stored and managed in the service rather than the client.
    See: https://api.smith.langchain.com/redoc#tag/feedback/operation/create_feedback_api_v1_feedback_post
    """
    # Log feedback request
    logger.info(f"=== FEEDBACK_REQUEST: run_id={feedback.run_id} ===")
    logger.info(f"FEEDBACK_REQUEST: key={feedback.key}")
    logger.info(f"FEEDBACK_REQUEST: score={feedback.score}")
    logger.info(f"FEEDBACK_REQUEST: has_kwargs={bool(feedback.kwargs)}")
    
    try:
        client = LangsmithClient()
        kwargs = feedback.kwargs or {}
        client.create_feedback(
            run_id=feedback.run_id,
            key=feedback.key,
            score=feedback.score,
            **kwargs,
        )
        
        logger.info(f"=== FEEDBACK_SUCCESS: run_id={feedback.run_id} ===")
        return FeedbackResponse()
    except Exception as e:
        logger.error(f"=== FEEDBACK_ERROR: run_id={feedback.run_id} ===")
        logger.error(f"FEEDBACK_ERROR: {str(e)}")
        raise


@router.post("/history")
def history(input: ChatHistoryInput) -> ChatHistory:
    """
    Get chat history.
    """
    # Log history request
    logger.info(f"=== HISTORY_REQUEST: thread_id={input.thread_id} ===")
    
    # TODO: Hard-coding DEFAULT_AGENT here is wonky
    agent: AgentGraph = get_agent(DEFAULT_AGENT)
    try:
        state_snapshot = agent.get_state(
            config=RunnableConfig(configurable={"thread_id": input.thread_id})
        )
        messages: list[AnyMessage] = state_snapshot.values["messages"]
        chat_messages: list[ChatMessage] = [langchain_to_chat_message(m) for m in messages]
        
        # Log successful history response
        logger.info(f"=== HISTORY_SUCCESS: thread_id={input.thread_id} ===")
        logger.info(f"HISTORY_SUCCESS: message_count={len(chat_messages)}")
        
        return ChatHistory(messages=chat_messages)
    except Exception as e:
        logger.error(f"=== HISTORY_ERROR: thread_id={input.thread_id} ===")
        logger.error(f"HISTORY_ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="Unexpected error")


@router.get("/section_states/{agent_id}/{section_id}")
async def notify_section_update(
    agent_id: str,
    section_id: str,
    user_id: int,
    thread_id: str | None = None,
):
    """
    Notify agent that a section has been edited and trigger a minimal sync run.

    This endpoint always:
    - Triggers a minimal Agent run to reload latest content for the section
    - Returns an AI prompt (single message) and the latest section status/draft
    """
    # Log section update request
    logger.info(f"=== SECTION_UPDATE_REQUEST: agent_id={agent_id}, section_id={section_id} ===")
    logger.info(f"SECTION_UPDATE_REQUEST: user_id={user_id}")
    logger.info(f"SECTION_UPDATE_REQUEST: thread_id={thread_id}")
    
    # Require thread_id to ensure updates are scoped to the correct document/thread
    if not thread_id:
        raise HTTPException(status_code=422, detail="Missing required parameter: thread_id")
    # Validate section_id
    if section_id not in SECTION_TEMPLATES:
        raise HTTPException(status_code=422, detail=f"Unknown section_id: {section_id}")

    # Trigger a minimal graph run to refresh context
    agent: AgentGraph = get_agent(agent_id)
    notify_msg = (
        f"I just updated section '{section_id}' in the UI. "
        f"Please reload the latest content from the database for this section, "
        f"then ask me whether to continue to the next step or refine this section."
    )
    user_input = UserInput(message=notify_msg, user_id=user_id, thread_id=thread_id)
    kwargs, run_id = await _handle_input(user_input, agent)

    # Execute once; ignore content and return minimal success
    try:
        await agent.ainvoke(**kwargs, stream_mode=["updates", "values"])  # type: ignore
        
        # Log successful section update
        logger.info(f"=== SECTION_UPDATE_SUCCESS: agent_id={agent_id}, section_id={section_id} ===")
        logger.info(f"SECTION_UPDATE_SUCCESS: user_id={user_id}")
        logger.info(f"SECTION_UPDATE_SUCCESS: thread_id={thread_id}")
        
    except Exception as e:
        logger.error(f"=== SECTION_UPDATE_ERROR: agent_id={agent_id}, section_id={section_id} ===")
        logger.error(f"SECTION_UPDATE_ERROR: {str(e)}")
        logger.error(f"SECTION_UPDATE_ERROR: user_id={user_id}")
        logger.error(f"SECTION_UPDATE_ERROR: thread_id={thread_id}")
        raise HTTPException(status_code=500, detail="Agent sync failed")

    return {"success": True}


@app.get("/health")
async def health_check():
    """Health check endpoint."""

    health_status = {"status": "ok"}

    if settings.LANGFUSE_TRACING:
        try:
            langfuse = Langfuse()
            health_status["langfuse"] = "connected" if langfuse.auth_check() else "disconnected"
        except Exception as e:
            logger.error(f"Langfuse connection error: {e}")
            health_status["langfuse"] = "disconnected"

    return health_status


app.include_router(router)
