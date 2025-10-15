import inspect
import json

from core.logging_config import get_logger, setup_logging

# Setup logging configuration
setup_logging()
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
from langchain_core.messages import AIMessage, AIMessageChunk, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse  # type: ignore[import-untyped]
from langfuse.callback import CallbackHandler  # type: ignore[import-untyped]
from langgraph.types import Command, Interrupt
from langsmith import Client as LangsmithClient
from starlette.middleware.base import BaseHTTPMiddleware

from agents import DEFAULT_AGENT, AgentGraph, get_agent, get_all_agent_info
from agents.mission_pitch.agent import initialize_mission_pitch_state
from agents.mission_pitch.prompts import SECTION_TEMPLATES as MISSION_PITCH_TEMPLATES
from agents.signature_pitch.agent import initialize_signature_pitch_state
from agents.signature_pitch.prompts import SECTION_TEMPLATES as SIGNATURE_PITCH_TEMPLATES
from agents.social_pitch.agent import initialize_social_pitch_state
from agents.social_pitch.prompts import SECTION_TEMPLATES as SOCIAL_PITCH_TEMPLATES
from agents.special_report.agent import initialize_special_report_state
from agents.special_report.prompts import SECTION_TEMPLATES as SPECIAL_REPORT_TEMPLATES
from agents.value_canvas.agent import initialize_value_canvas_state
from agents.value_canvas.prompts import SECTION_TEMPLATES as VALUE_CANVAS_TEMPLATES
from agents.concept_pitch.agent import initialize_concept_pitch_state
from agents.concept_pitch.prompts import SECTION_TEMPLATES as CONCEPT_PITCH_TEMPLATES
from core import settings
from core.settings import DatabaseType
from integrations.dentapp.dentapp_utils import SECTION_ID_MAPPING, get_section_string_id
from memory import initialize_database, initialize_store, pg_manager
from schema import (
    ChatHistory,
    ChatHistoryInput,
    ChatMessage,
    Feedback,
    FeedbackResponse,
    InvokeResponse,
    RefineSectionInput,
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
logger = get_logger(__name__)


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
        if settings.DATABASE_TYPE == DatabaseType.POSTGRES:
            # Initialize PostgreSQL connection pool
            await pg_manager.setup()
            saver = pg_manager.get_saver()
            store = pg_manager.get_store()
            
            # Configure all agents
            agents = get_all_agent_info()
            for a in agents:
                agent = get_agent(a.key)
                agent.checkpointer = saver
                agent.store = store
            
            logger.info("Application startup complete with PostgreSQL connection pool")
            yield
            
            # Clean up connection pool
            await pg_manager.cleanup()
        else:
            # SQLite or MongoDB - use original logic
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
    from schema import EndpointInfo

    return ServiceMetadata(
        agents=get_all_agent_info(),
        models=[],  # Models are server-managed, not user-selectable
        default_agent=DEFAULT_AGENT,
        default_model=None,  # Model selection is server-internal
        endpoints=[
            EndpointInfo(
                path="/sync_section/{agent_id}/{section_id}",
                method="POST",
                description="Sync LangGraph state with manually edited section content from database. Uses LLM to extract structured data from Tiptap text and updates agent state. Common section IDs: 45=interview, 46=icp, 48=pain, 49=deep_fear, 50=payoffs, 52=signature_method, 53=mistakes, 54=prize.",
                parameters={
                    "agent_id": "Agent identifier (currently only 'value-canvas' supported)",
                    "section_id": "Section ID integer from database (e.g., 48 for pain, 46 for icp, 45 for interview)",
                    "user_id": "User identifier (required query parameter)",
                    "thread_id": "Thread/conversation identifier (required query parameter)"
                },
                example="/sync_section/value-canvas/48?user_id=12&thread_id=3ab280c6-44ee-416d-87f9-73aad616c8ec"
            ),
            EndpointInfo(
                path="/refine_section/{agent_id}/{section_id}",
                method="POST",
                description="Refine section content using AI. Accepts JSON body with user_id, thread_id, and refinement_prompt. Returns refined content (plain text + Tiptap format). Does NOT save to database. Common section IDs: 45=interview, 46=icp, 48=pain, 49=deep_fear, 50=payoffs, 52=signature_method, 53=mistakes, 54=prize.",
                parameters={
                    "agent_id": "Agent identifier - path parameter (currently only 'value-canvas' supported)",
                    "section_id": "Section ID integer from database - path parameter (e.g., 48 for pain, 46 for icp, 45 for interview)",
                    "body.user_id": "User identifier (integer, required in JSON body)",
                    "body.thread_id": "Thread/conversation identifier (string, required in JSON body)",
                    "body.refinement_prompt": "User's refinement instruction (string, can be long text, required in JSON body)"
                },
                example='curl -X POST http://localhost:8080/refine_section/value-canvas/48 -H "Content-Type: application/json" -d \'{"user_id": 12, "thread_id": "3ab280c6-44ee-416d-87f9-73aad616c8ec", "refinement_prompt": "Make it more concise"}\''
            ),
        ]
    )


async def _handle_input(user_input: UserInput, agent: AgentGraph, agent_id: str) -> tuple[dict[str, Any], UUID]:
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

    initial_state = None
    if not thread_id:
        # This is a new conversation, so we need to initialize a new state
        if agent_id == "value-canvas":
            initial_state = await initialize_value_canvas_state(user_id=user_id)
        elif agent_id == "mission-pitch":
            initial_state = await initialize_mission_pitch_state(user_id=user_id)
        elif agent_id == "social-pitch":
            initial_state = await initialize_social_pitch_state(user_id=user_id)
        elif agent_id == "signature-pitch":
            initial_state = await initialize_signature_pitch_state(user_id=user_id)
        elif agent_id == "special-report":
            initial_state = await initialize_special_report_state(user_id=user_id)
        elif agent_id == "concept-pitch":
            initial_state = await initialize_concept_pitch_state(user_id=user_id)
        else:
            raise ValueError(f"Unknown agent: {agent_id}")

        # Get the generated thread_id from initial_state
        # For dict-like states, use .get(), for Pydantic models use direct access
        logger.info(f"DEBUG: initial_state type = {type(initial_state)}")
        logger.info(f"DEBUG: hasattr(initial_state, 'user_id') = {hasattr(initial_state, 'user_id')}")

        if hasattr(initial_state, 'user_id'):
            user_id = initial_state.user_id
            thread_id = initial_state.thread_id
            logger.info(f"DEBUG: Got user_id={user_id}, thread_id={thread_id} from Pydantic model")
        else:
            user_id = initial_state.get("user_id")
            thread_id = initial_state.get("thread_id")
            logger.info(f"DEBUG: Got user_id={user_id}, thread_id={thread_id} from dict")

        logger.info(f"Initialized new thread with ID: {thread_id}")
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
    # Extract current section for HumanMessage metadata
    current_section = None
    if not user_input.thread_id:
        # New thread - freshly initialized state, no interrupts to resume
        # Avoid calling aget_state which might trigger unexpected graph execution
        interrupted_tasks = []
        # Get current_section from initial_state that was just created
        if initial_state:
            if hasattr(initial_state, 'current_section'):
                current_section = initial_state.current_section
            else:
                current_section = initial_state.get("current_section")
    else:
        # Existing thread - check if there are interrupts to resume
        state = await agent.aget_state(config=config)
        interrupted_tasks = [
            task for task in state.tasks if hasattr(task, "interrupts") and task.interrupts
        ]
        # Extract current section from state for HumanMessage metadata
        current_section = state.values.get("current_section") if state.values else None

    input: Command | dict[str, Any]
    if interrupted_tasks:
        input = Command(resume=user_input.message)
    else:
        # Create HumanMessage with section metadata in additional_kwargs
        additional_kwargs = {}
        if current_section:
            # Get the section string ID (e.g., "interview", "icp", "pain")
            section_id_str = current_section.value if hasattr(current_section, 'value') else str(current_section)
            additional_kwargs.update({
                "section_id": section_id_str,
                "agent_name": agent_id,
            })

        input = {"messages": [HumanMessage(content=user_input.message, additional_kwargs=additional_kwargs)]}

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
    
    # Use custom graph for concept-pitch agent
    if agent_id == 'concept-pitch':
        from agents.concept_pitch.agent import initialize_concept_pitch_state, graph as concept_pitch_graph
        
        # Initialize the state using the proper LangGraph state initialization
        init_state = await initialize_concept_pitch_state(
            user_id=user_input.user_id or 1,
            thread_id=user_input.thread_id
        )
        
        # Add the user message to the state
        if user_input.message:
            init_state["messages"].append(HumanMessage(content=user_input.message))
        
        # Build config for the agent
        config = {
            "configurable": {
                "thread_id": init_state["thread_id"],
                "user_id": init_state["user_id"],
            }
        }
        
        # Run the LangGraph agent
        response_events = await concept_pitch_graph.ainvoke(init_state, config=config, stream_mode=["updates", "values"])
        response_type, response = response_events[-1]
        
        if response_type == "values":
            # Normal response, the agent completed successfully
            output = langchain_to_chat_message(response["messages"][-1])
            
            # Extract concept pitch data if available
            concept_pitch_data = {}
            if "concept_pitch" in response:
                concept_pitch_data = response["concept_pitch"]
            
            # Add concept pitch data to custom_data
            if concept_pitch_data:
                output.custom_data["concept_pitch"] = concept_pitch_data
            
        elif response_type == "updates" and "__interrupt__" in response:
            # The last thing to occur was an interrupt
            output = langchain_to_chat_message(
                AIMessage(content=response["__interrupt__"][0].value)
            )
        else:
            raise ValueError(f"Unexpected response type: {response_type}")
        
        # Create response
        invoke_response = InvokeResponse(
            output=output,
            thread_id=init_state["thread_id"],
            user_id=init_state["user_id"],
        )
        
        logger.info(f"=== CONCEPT_PITCH_RESPONSE_SUCCESS ===")
        logger.info(f"CONCEPT_PITCH_RESPONSE: thread_id={init_state['thread_id']}")
        logger.info(f"CONCEPT_PITCH_RESPONSE: user_id={init_state['user_id']}")
        logger.info(f"CONCEPT_PITCH_RESPONSE: response_type={response_type}")
        logger.info(f"CONCEPT_PITCH_RESPONSE: has_concept_pitch={bool(output.custom_data.get('concept_pitch'))}")
        
        return invoke_response
    else:
        agent: AgentGraph = get_agent(agent_id)
        kwargs, run_id = await _handle_input(user_input, agent, agent_id)
    
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
            # Choose the right section templates based on agent_id
            if agent_id == "mission-pitch":
                section_templates = MISSION_PITCH_TEMPLATES
            elif agent_id == "social-pitch":
                section_templates = SOCIAL_PITCH_TEMPLATES
            elif agent_id == "signature-pitch":
                section_templates = SIGNATURE_PITCH_TEMPLATES
            elif agent_id == "special-report":
                section_templates = SPECIAL_REPORT_TEMPLATES
            else:  # default to value_canvas
                section_templates = VALUE_CANVAS_TEMPLATES
            
            section_template = section_templates.get(current_section_id)

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
    # Log stream request summary
    logger.info(f"[STREAM] Start: agent={agent_id}, user={user_input.user_id}, thread={user_input.thread_id[:8] if user_input.thread_id else 'new'}...")
    
    agent: AgentGraph = get_agent(agent_id)
    kwargs, run_id = await _handle_input(user_input, agent, agent_id)
    
    logger.debug(f"Stream run_id: {run_id}")

    # Get the current thread's message history length to filter out historical messages
    try:
        current_state = await agent.aget_state(config=kwargs["config"])
        initial_message_count = len(current_state.values.get("messages", []))
        logger.debug(f"Initial message count: {initial_message_count}")
    except Exception as e:
        logger.debug(f"Could not get initial message count: {e}")
        initial_message_count = 0

    sent_message_count = 0  # Track the number of messages sent to prevent duplicates

    try:
        # Send metadata as the first event in the stream
        thread_id = kwargs["config"]["configurable"]["thread_id"]
        user_id = kwargs["config"]["configurable"]["user_id"]
        
        yield f"data: {json.dumps({'type': 'metadata', 'content': {'thread_id': thread_id, 'user_id': user_id, 'run_id': str(run_id)}})}\n\n"
        
        # Process streamed events from the graph and yield messages over the SSE stream.
        async for stream_event in agent.astream(
            **kwargs, stream_mode=["updates", "messages", "custom"]
        ):
            # Log stream events efficiently
            if isinstance(stream_event, tuple):
                stream_mode, _ = stream_event
                logger.stream_event("received", {"mode": stream_mode})
            else:
                logger.stream_event("received", {"mode": "unknown"})

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
                    
                    # STREAM_FIX: Only send NEW messages (not historical ones)
                    # Use initial_message_count to filter out messages that were already in the thread
                    update_messages = updates.get("messages", [])
                    
                    # Only add messages that are new (beyond the initial count)
                    if len(update_messages) > 0:
                        # If we have an initial count, only take messages after that position
                        if initial_message_count > 0 and len(update_messages) > initial_message_count:
                            new_messages.extend(update_messages[initial_message_count:])
                            logger.debug(f"Sending {len(update_messages[initial_message_count:])} new messages")
                        # If no initial count or this is the first batch, check against sent_message_count
                        elif len(update_messages) > sent_message_count:
                            new_messages.extend(update_messages[sent_message_count:])
                            sent_message_count = len(update_messages)
                            logger.debug(f"Sending {len(new_messages)} new messages")

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
                    # Skip function calling related tuples - these are internal operations, not user messages
                    if key in ['tool_calls', 'additional_kwargs', 'invalid_tool_calls']:
                        logger.debug(f"Skipping function call tuple: {key}")
                        continue
                    # Skip internal extraction field names that might leak from structured output
                    # These are field names from our data models that shouldn't appear in user stream
                    extraction_fields = [
                        # Interview fields
                        'client_name', 'company_name', 'preferred_name', 'industry', 'specialty', 
                        'career_highlight', 'client_outcomes', 'specialized_skills', 'awards_media',
                        'published_content', 'notable_partners',
                        # ICP fields
                        'icp_nickname', 'icp_role_identity', 'icp_context_scale', 'icp_industry_sector_context',
                        'icp_demographics', 'icp_interests', 'icp_values', 'icp_golden_insight',
                        # Pain fields
                        'pain1_symptom', 'pain1_struggle', 'pain1_cost', 'pain1_consequence',
                        'pain2_symptom', 'pain2_struggle', 'pain2_cost', 'pain2_consequence',
                        'pain3_symptom', 'pain3_struggle', 'pain3_cost', 'pain3_consequence',
                        # Deep Fear fields
                        'deep_fear', 'golden_insight',
                        # Payoffs fields
                        'payoff1_objective', 'payoff1_desire', 'payoff1_without', 'payoff1_resolution',
                        'payoff2_objective', 'payoff2_desire', 'payoff2_without', 'payoff2_resolution',
                        'payoff3_objective', 'payoff3_desire', 'payoff3_without', 'payoff3_resolution',
                        # Signature Method fields
                        'method_name', 'sequenced_principles', 'principle_descriptions', 'principles',
                        # Mistakes fields
                        'mistakes',
                        # Prize fields
                        'prize_statement', 'prize_category', 'refined_prize',
                        # Social Pitch fields - NAME
                        'user_name', 'user_position',
                        # Social Pitch fields - SAME
                        'business_category', 'target_customer', 'same_statement',
                        # Social Pitch fields - FAME
                        'fame_tier', 'fame_statement', 'achievement_details',
                        # Social Pitch fields - PAIN
                        'ideal_clients', 'broad_challenge', 'pain_statement',
                        # Social Pitch fields - AIM
                        'current_project_category', 'project_description', 'aim_statement',
                        # Social Pitch fields - GAME
                        'vision_approach', 'bigger_vision', 'game_statement',
                    ]
                    if key in extraction_fields:
                        logger.debug(f"Skipping internal extraction field: {key}")
                        continue
                    # Store parts in temporary dict
                    logger.debug(f"Processing tuple: {key}")
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
                    
                    # Skip messages that appear to be internal data extraction results
                    # These might have content but are from structured output calls
                    if isinstance(message, AIMessage) and message.content:
                        # Check if content looks like field names or extracted data
                        content_lower = message.content.lower() if isinstance(message.content, str) else ""
                        extraction_fields = [
                            # Interview fields
                            'client_name', 'company_name', 'preferred_name', 'industry', 'specialty', 
                            'career_highlight', 'client_outcomes', 'specialized_skills', 'awards_media',
                            'published_content', 'notable_partners',
                            # ICP fields
                            'icp_nickname', 'icp_role_identity', 'icp_context_scale', 'icp_industry_sector_context',
                            'icp_demographics', 'icp_interests', 'icp_values', 'icp_golden_insight',
                            # Pain fields
                            'pain1_symptom', 'pain1_struggle', 'pain1_cost', 'pain1_consequence',
                            'pain2_symptom', 'pain2_struggle', 'pain2_cost', 'pain2_consequence',
                            'pain3_symptom', 'pain3_struggle', 'pain3_cost', 'pain3_consequence',
                            # Deep Fear fields
                            'deep_fear', 'golden_insight',
                            # Payoffs fields
                            'payoff1_objective', 'payoff1_desire', 'payoff1_without', 'payoff1_resolution',
                            'payoff2_objective', 'payoff2_desire', 'payoff2_without', 'payoff2_resolution',
                            'payoff3_objective', 'payoff3_desire', 'payoff3_without', 'payoff3_resolution',
                            # Signature Method fields
                            'method_name', 'sequenced_principles', 'principle_descriptions', 'principles',
                            # Mistakes fields
                            'mistakes',
                            # Prize fields
                            'prize_statement', 'prize_category', 'refined_prize',
                            # Social Pitch fields
                            'user_name', 'user_position', 'business_category', 'target_customer', 
                            'same_statement', 'fame_tier', 'fame_statement', 'achievement_details',
                            'ideal_clients', 'broad_challenge', 'pain_statement', 'current_project_category',
                            'project_description', 'aim_statement', 'vision_approach', 'bigger_vision', 'game_statement',
                        ]
                        if any(field in content_lower for field in extraction_fields):
                            logger.debug(f"Skipping potential extraction data message: {message.content[:50]}...")
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
                # Skip messages with internal tags
                tags = metadata.get("tags", [])
                if any(tag in tags for tag in ["skip_stream", "internal_extraction", "do_not_stream", "internal_decision"]):
                    logger.debug(f"Skipping message with internal tags: {tags}")
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
        import traceback
        logger.error(f"[STREAM ERROR] {str(e)} (run_id={run_id}, agent={agent_id})")
        logger.error(f"[STREAM ERROR TRACEBACK]\n{traceback.format_exc()}")
        yield f"data: {json.dumps({'type': 'error', 'content': 'Internal server error'})}\n\n"
    finally:
        # Always send section data at the end of the stream
        try:
            state = await agent.aget_state(config=kwargs["config"])
            if "current_section" in state.values:
                current_section_enum = state.values["current_section"]
                current_section_id = current_section_enum.value  # Use the string value
                section_state = state.values.get("section_states", {}).get(current_section_id)
                
                # Choose the right section templates based on agent_id
                if agent_id == "mission-pitch":
                    section_templates = MISSION_PITCH_TEMPLATES
                elif agent_id == "social-pitch":
                    section_templates = SOCIAL_PITCH_TEMPLATES
                elif agent_id == "signature-pitch":
                    section_templates = SIGNATURE_PITCH_TEMPLATES
                elif agent_id == "special-report":
                    section_templates = SPECIAL_REPORT_TEMPLATES
                elif agent_id == "concept-pitch":
                    section_templates = CONCEPT_PITCH_TEMPLATES
                else:  # default to value_canvas
                    section_templates = VALUE_CANVAS_TEMPLATES
                
                section_template = section_templates.get(current_section_id)

                section_data = {
                    "database_id": SECTION_ID_MAPPING.get(current_section_id),
                    "name": section_template.name if section_template else "Unknown Section",
                    "status": section_state.status.value if section_state else "pending",
                }
                yield f"data: {json.dumps({'type': 'section', 'content': section_data})}\n\n"
        except Exception as e:
            logger.error(f"Error getting section data: {e}")

        # Log stream completion
        logger.info(f"[STREAM] Complete: agent={agent_id}, thread={kwargs['config']['configurable']['thread_id'][:8]}...")
        
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

        # Check if state exists and has messages
        if not state_snapshot.values:
            logger.warning(f"HISTORY_WARNING: No state found for thread_id={input.thread_id}")
            return ChatHistory(messages=[])

        messages: list[AnyMessage] = state_snapshot.values.get("messages", [])
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
    section_id: int,
    user_id: int,
    thread_id: str | None = None,
):
    """
    Notify agent that a section has been edited and trigger a minimal sync run.

    This endpoint always:
    - Triggers a minimal Agent run to reload latest content for the section
    - Returns an AI prompt (single message) and the latest section status/draft

    Args:
        agent_id: Agent identifier (e.g., "value-canvas")
        section_id: Section ID integer from database (e.g., 48 for pain, 46 for icp)
        user_id: User identifier
        thread_id: Thread/conversation identifier (required)
    """
    # Log section update request
    logger.info(f"=== SECTION_UPDATE_REQUEST: agent_id={agent_id}, section_id={section_id} ===")
    logger.info(f"SECTION_UPDATE_REQUEST: user_id={user_id}")
    logger.info(f"SECTION_UPDATE_REQUEST: thread_id={thread_id}")

    # Convert section_id integer to string identifier for internal use
    section_id_str = get_section_string_id(section_id)
    if not section_id_str:
        raise HTTPException(status_code=422, detail=f"Invalid section_id: {section_id}")

    # Require thread_id to ensure updates are scoped to the correct document/thread
    if not thread_id:
        raise HTTPException(status_code=422, detail="Missing required parameter: thread_id")
    
    # Choose the right section templates based on agent_id
    if agent_id == "mission-pitch":
        section_templates = MISSION_PITCH_TEMPLATES
    elif agent_id == "social-pitch":
        section_templates = SOCIAL_PITCH_TEMPLATES
    elif agent_id == "signature-pitch":
        section_templates = SIGNATURE_PITCH_TEMPLATES
    elif agent_id == "special-report":
        section_templates = SPECIAL_REPORT_TEMPLATES
    elif agent_id == "concept-pitch":
        section_templates = CONCEPT_PITCH_TEMPLATES
    else:  # default to value_canvas
        section_templates = VALUE_CANVAS_TEMPLATES
    
    # Validate section_id
    if section_id_str not in section_templates:
        raise HTTPException(status_code=422, detail=f"Unknown section_id: {section_id}")

    # Trigger a minimal graph run to refresh context
    agent: AgentGraph = get_agent(agent_id)
    notify_msg = (
        f"I just updated section '{section_id_str}' in the UI. "
        f"Please reload the latest content from the database for this section, "
        f"then ask me whether to continue to the next step or refine this section."
    )
    user_input = UserInput(message=notify_msg, user_id=user_id, thread_id=thread_id)
    kwargs, run_id = await _handle_input(user_input, agent, agent_id)

    # Execute once; ignore content and return minimal success
    try:
        await agent.ainvoke(**kwargs, stream_mode=["updates", "values"])  # type: ignore

        # Log successful section update
        logger.info(f"=== SECTION_UPDATE_SUCCESS: agent_id={agent_id}, section_id={section_id} (string_id={section_id_str}) ===")
        logger.info(f"SECTION_UPDATE_SUCCESS: user_id={user_id}")
        logger.info(f"SECTION_UPDATE_SUCCESS: thread_id={thread_id}")

    except Exception as e:
        logger.error(f"=== SECTION_UPDATE_ERROR: agent_id={agent_id}, section_id={section_id} ===")
        logger.error(f"SECTION_UPDATE_ERROR: {str(e)}")
        logger.error(f"SECTION_UPDATE_ERROR: user_id={user_id}")
        logger.error(f"SECTION_UPDATE_ERROR: thread_id={thread_id}")
        raise HTTPException(status_code=500, detail="Agent sync failed")

    return {"success": True}


@router.post("/sync_section/{agent_id}/{section_id}")
async def sync_section(
    agent_id: str,
    section_id: int,
    user_id: int,
    thread_id: str,
):
    """
    Sync LangGraph state with manually edited section content from database.

    This endpoint:
    1. Fetches the latest section content from DentApp API (Tiptap format)
    2. Converts Tiptap to plain text
    3. Uses LLM to extract structured data from the edited text
    4. Updates LangGraph state (canvas_data + section_states)
    5. Persists changes via checkpoint

    This is designed for when users manually edit section content in the frontend
    and we need to sync the structured state with their changes.

    Args:
        agent_id: Agent identifier (e.g., "value-canvas")
        section_id: Section ID integer from database (e.g., 48 for pain, 46 for icp)
        user_id: User identifier
        thread_id: Thread/conversation identifier

    Returns:
        Sync result with success status and details
    """
    # Log sync request
    logger.info(f"=== SYNC_SECTION_REQUEST: agent_id={agent_id}, section_id={section_id} ===")
    logger.info(f"SYNC_SECTION_REQUEST: user_id={user_id}")
    logger.info(f"SYNC_SECTION_REQUEST: thread_id={thread_id}")

    # Convert section_id integer to string identifier for internal use
    section_id_str = get_section_string_id(section_id)
    if not section_id_str:
        raise HTTPException(status_code=422, detail=f"Invalid section_id: {section_id}")

    # Validate required parameters
    if not thread_id:
        raise HTTPException(status_code=422, detail="Missing required parameter: thread_id")

    # Only value-canvas agent is supported for now
    if agent_id != "value-canvas":
        raise HTTPException(
            status_code=422,
            detail=f"Sync not yet supported for agent: {agent_id}. Currently only 'value-canvas' is supported."
        )

    # Get agent
    try:
        agent: AgentGraph = get_agent(agent_id)
    except Exception as e:
        logger.error(f"SYNC_ERROR: Failed to get agent {agent_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # Import sync function (only for value-canvas)
    try:
        from agents.value_canvas.sync import sync_section_from_database
    except ImportError as e:
        logger.error(f"SYNC_ERROR: Failed to import sync module: {e}")
        raise HTTPException(status_code=500, detail="Sync module not available")

    # Execute sync
    try:
        result = await sync_section_from_database(
            user_id=user_id,
            thread_id=thread_id,
            section_id=section_id_str,
            agent_graph=agent
        )

        # Log successful sync
        logger.info(f"=== SYNC_SECTION_SUCCESS: agent_id={agent_id}, section_id={section_id} (string_id={section_id_str}) ===")
        logger.info(f"SYNC_SECTION_SUCCESS: extracted_fields={result.get('extracted_fields', [])}")
        logger.info(f"SYNC_SECTION_SUCCESS: content_length={result.get('content_length', 0)}")

        return result

    except ValueError as e:
        logger.error(f"=== SYNC_SECTION_VALIDATION_ERROR: {str(e)} ===")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"=== SYNC_SECTION_ERROR: agent_id={agent_id}, section_id={section_id} ===")
        logger.error(f"SYNC_SECTION_ERROR: {str(e)}")
        logger.error(f"SYNC_SECTION_ERROR: user_id={user_id}")
        logger.error(f"SYNC_SECTION_ERROR: thread_id={thread_id}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/refine_section/{agent_id}/{section_id}")
async def refine_section(
    agent_id: str,
    section_id: int,
    request: RefineSectionInput,
):
    """
    Refine section content using AI based on user's instruction.

    This endpoint:
    1. Fetches current LangGraph state to get canvas_data
    2. Gets rendered section prompt with all dependencies
    3. Fetches current section content from DentApp API
    4. Constructs refinement prompt with clear structure
    5. Calls OpenAI LLM to generate refined content
    6. Returns refined content (does NOT save to database)

    Frontend workflow:
    1. User clicks "Refine" button
    2. Frontend calls this endpoint
    3. Refined content is displayed for user review
    4. If user accepts, frontend saves to DentApp API and calls /sync_section

    Args:
        agent_id: Agent identifier (e.g., "value-canvas") - path parameter
        section_id: Section ID integer from database (e.g., 48 for pain, 46 for icp) - path parameter
        request: Request body containing user_id, thread_id, and refinement_prompt

    Returns:
        Refinement result with refined content in both plain text and Tiptap format
    """
    # Extract parameters from request body
    user_id = request.user_id
    thread_id = request.thread_id
    refinement_prompt = request.refinement_prompt

    # Log refine request
    logger.info(f"=== REFINE_SECTION_REQUEST: agent_id={agent_id}, section_id={section_id} ===")
    logger.info(f"REFINE_SECTION_REQUEST: user_id={user_id}")
    logger.info(f"REFINE_SECTION_REQUEST: thread_id={thread_id}")
    logger.info(f"REFINE_SECTION_REQUEST: refinement_prompt={refinement_prompt[:100]}...")

    # Convert section_id integer to string identifier for internal use
    section_id_str = get_section_string_id(section_id)
    if not section_id_str:
        raise HTTPException(status_code=422, detail=f"Invalid section_id: {section_id}")

    # Validate refinement_prompt is not just whitespace
    if not refinement_prompt.strip():
        raise HTTPException(status_code=422, detail="refinement_prompt cannot be empty or whitespace only")

    # Only value-canvas agent is supported for now
    if agent_id != "value-canvas":
        raise HTTPException(
            status_code=422,
            detail=f"Refine not yet supported for agent: {agent_id}. Currently only 'value-canvas' is supported."
        )

    # Get agent
    try:
        agent: AgentGraph = get_agent(agent_id)
    except Exception as e:
        logger.error(f"REFINE_ERROR: Failed to get agent {agent_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # Import refine function (only for value-canvas)
    try:
        from agents.value_canvas.refine import refine_section_content
    except ImportError as e:
        logger.error(f"REFINE_ERROR: Failed to import refine module: {e}")
        raise HTTPException(status_code=500, detail="Refine module not available")

    # Execute refinement
    try:
        result = await refine_section_content(
            user_id=user_id,
            thread_id=thread_id,
            section_id=section_id_str,
            refinement_prompt=refinement_prompt,
            agent_graph=agent
        )

        # Log successful refinement
        logger.info(f"=== REFINE_SECTION_SUCCESS: agent_id={agent_id}, section_id={section_id} (string_id={section_id_str}) ===")
        logger.info(f"REFINE_SECTION_SUCCESS: refined_content_length={len(result.get('refined_content', {}).get('plain_text', ''))}")

        return result

    except ValueError as e:
        logger.error(f"=== REFINE_SECTION_VALIDATION_ERROR: {str(e)} ===")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"=== REFINE_SECTION_ERROR: agent_id={agent_id}, section_id={section_id} ===")
        logger.error(f"REFINE_SECTION_ERROR: {str(e)}")
        logger.error(f"REFINE_SECTION_ERROR: user_id={user_id}")
        logger.error(f"REFINE_SECTION_ERROR: thread_id={thread_id}")
        raise HTTPException(status_code=500, detail=f"Refine failed: {str(e)}")


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
