"""Value Canvas Agent implementation using LangGraph StateGraph."""

import json
import logging
from typing import Any, Dict, List, Literal, Optional, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from core.llm import get_model
from core.settings import settings

from agents.value_canvas_models import (
    ChatAgentOutput,
    ContextPacket,
    RouterDirective,
    SectionID,
    SectionStatus,
    ValueCanvasData,
    ValueCanvasState,
)
from agents.value_canvas_prompts import (
    get_next_section,
    get_next_unfinished_section,
)
from agents.value_canvas_tools import (
    create_tiptap_content,
    export_checklist,
    extract_plain_text,
    get_all_sections_status,
    get_context,
    save_section,
    validate_field,
)

logger = logging.getLogger(__name__)

# Tool setup - Chat Agent has NO tools according to design doc

# Tools used by specific nodes
router_tools = [
    get_context,
]

memory_updater_tools = [
    save_section,
    get_all_sections_status,
    create_tiptap_content,
    extract_plain_text,
    validate_field,  # Moved from chat_agent per design doc
]

implementation_tools = [
    export_checklist,
]

# Create tool nodes
router_tool_node = ToolNode(router_tools)
memory_updater_tool_node = ToolNode(memory_updater_tools)
implementation_tool_node = ToolNode(implementation_tools)


async def initialize_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Initialize node that ensures all required state fields are present.
    This is the first node in the graph to handle LangGraph Studio's incomplete state.
    """
    logger.info("Initialize node - Setting up default values")
    
    # Ensure all required fields have default values
    if "user_id" not in state or not state["user_id"]:
        state["user_id"] = "studio-user"
    if "doc_id" not in state or not state["doc_id"]:
        state["doc_id"] = "studio-doc"
    if "current_section" not in state:
        state["current_section"] = SectionID.INTERVIEW
    if "router_directive" not in state:
        state["router_directive"] = RouterDirective.NEXT
    if "finished" not in state:
        state["finished"] = False
    if "section_states" not in state:
        state["section_states"] = {}
    if "canvas_data" not in state:
        state["canvas_data"] = ValueCanvasData()
    if "short_memory" not in state:
        state["short_memory"] = []
    if "error_count" not in state:
        state["error_count"] = 0
    if "last_error" not in state:
        state["last_error"] = None
    if "messages" not in state:
        state["messages"] = []
    
    logger.info(f"Initialize complete - User: {state['user_id']}, Doc: {state['doc_id']}")
    return state


async def router_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Router node that handles navigation and context loading.
    
    Responsibilities:
    - Process router directives (stay, next, modify:section_id)
    - Update current_section
    - Call get_context when changing sections
    - Check for completion and set finished flag
    """
    # Ensure essential keys exist by injecting default values defined in ValueCanvasState.
    # This lets users start a new thread in LangGraph Studio without manually supplying state.
    state.setdefault("user_id", "studio-user")
    state.setdefault("doc_id", "studio-doc")
    state.setdefault("current_section", SectionID.INTERVIEW)
    state.setdefault("router_directive", RouterDirective.NEXT)
    state.setdefault("finished", False)
    state.setdefault("section_states", {})
    state.setdefault("canvas_data", ValueCanvasData())
    state.setdefault("messages", [])
    state.setdefault("short_memory", [])
    state.setdefault("awaiting_user_input", False)
    
    # Check if there's a new user message - if so, reset awaiting_user_input
    msgs = state.get("messages", [])
    if msgs and len(msgs) >= 2:
        last_msg = msgs[-1]
        second_last_msg = msgs[-2]
        # If last message is human and second last is AI, user has responded
        if isinstance(last_msg, HumanMessage) and isinstance(second_last_msg, AIMessage):
            state["awaiting_user_input"] = False

    logger.info(
        f"Router node - Current section: {state['current_section']}, Directive: {state['router_directive']}"
    )
    
    # Process router directive
    directive = state.get("router_directive", RouterDirective.STAY)
    
    if directive == RouterDirective.STAY:
        # Stay on current section, no context reload needed
        logger.info("Staying on current section")
        return state
    
    elif directive == RouterDirective.NEXT:
        # Find next unfinished section
        next_section = get_next_unfinished_section(state.get("section_states", {}))
        
        if next_section:
            logger.info(f"Moving to next section: {next_section}")
            state["current_section"] = next_section
            
            # Get context for new section
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "doc_id": state["doc_id"],
                "section_id": next_section.value,
                "canvas_data": state["canvas_data"].model_dump(),
            })
            
            state["context_packet"] = ContextPacket(**context)
            
            # Reset directive to STAY to prevent repeated transitions
            state["router_directive"] = RouterDirective.STAY
        else:
            # All sections complete
            logger.info("All sections complete, setting finished flag")
            state["finished"] = True
    
    elif directive.startswith("modify:"):
        # Jump to specific section
        section_id = directive.split(":", 1)[1]
        try:
            new_section = SectionID(section_id)
            logger.info(f"Jumping to section: {new_section}")
            state["current_section"] = new_section
            
            # Get context for new section
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "doc_id": state["doc_id"],
                "section_id": new_section.value,
                "canvas_data": state["canvas_data"].model_dump(),
            })
            
            state["context_packet"] = ContextPacket(**context)
            
            # Reset directive to STAY to prevent repeated transitions
            state["router_directive"] = RouterDirective.STAY
        except ValueError:
            logger.error(f"Invalid section ID: {section_id}")
            state["last_error"] = f"Invalid section ID: {section_id}"
            state["error_count"] += 1
    
    return state


async def chat_agent_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Chat agent node that handles section-specific conversations.
    
    Responsibilities:
    - Generate responses based on context_packet system prompt
    - Validate user input
    - Generate section content (Tiptap JSON)
    - Set score and router_directive
    - Output structured ChatAgentOutput
    """
    logger.info(f"Chat agent node - Section: {state['current_section']}")
    
    # Get LLM - no tools for chat agent per design doc
    llm = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    
    messages: List[BaseMessage] = []
    last_human_msg: Optional[HumanMessage] = None

    # 1) Hard system instruction per design doc – MUST output pure JSON.
    json_schema_instruction = (
        "You are Value Canvas Chat Agent. Respond ONLY with valid JSON matching this schema: "
        '{"reply": "string", "router_directive": "stay|next|modify:<section_id>", '
        '"score": "integer|null", "section_update": "object|null"} '
        "Do NOT output markdown, code fences, or any extra commentary."
    )
    messages.append(SystemMessage(content=json_schema_instruction))
    # If awaiting rating (router stays and user just provided info), instruct LLM to produce summary first
    if state.get("awaiting_user_input", False):
        summary_instruction = (
            "When responding, begin with a concise summary (in 3-5 bullet points) of the user's latest answers for the current section, "
            "then ask them to rate their satisfaction with the summary on a 0-5 scale."
        )
        messages.append(SystemMessage(content=summary_instruction))

    # 2) Section-specific system prompt from context packet
    if state.get("context_packet"):
        messages.append(SystemMessage(content=state["context_packet"].system_prompt))

    # 3) Recent conversation memory
    messages.extend(state.get("short_memory", [])[-10:])

    # 4) Last human message (if any and agent hasn't replied yet)
    if state.get("messages"):
        _last_msg = state["messages"][-1]
        if isinstance(_last_msg, HumanMessage):
            messages.append(_last_msg)
            last_human_msg = _last_msg

    try:
        max_attempts = 1
        output_data = None
        # Force OpenAI to return JSON in one shot
        openai_args = {"response_format": {"type": "json_object"}}
        
        for attempt in range(max_attempts):
            response = await llm.ainvoke(messages, **openai_args)
            content = response.content if hasattr(response, "content") else response

            # Attempt to parse JSON as below (reuse existing logic in local helper)
            def _extract_json(text: str):
                txt = text.strip()
                if txt.startswith("```json"):
                    txt = txt[7:]
                if txt.startswith("```"):
                    txt = txt[3:]
                if txt.endswith("```"):
                    txt = txt[:-3]
                start = txt.find("{")
                end = txt.rfind("}") + 1
                if start >= 0 and end > start:
                    return txt[start:end]
                return None

            json_str = _extract_json(content) if isinstance(content, str) else None
            if json_str:
                try:
                    output_data = json.loads(json_str)
                    parsed_successfully = True
                    break
                except json.JSONDecodeError:
                    pass

        if not parsed_successfully:
            raise ValueError("Failed to get valid JSON from LLM after retries")

        # Ensure mandatory keys present
        output_data.setdefault("reply", "I'm processing your request...")
        output_data.setdefault("router_directive", "stay")
        output_data.setdefault("score", None)
        output_data.setdefault("section_update", None)

        agent_output = ChatAgentOutput(**output_data)

        # Determine router directive based on score, per design doc
        if agent_output.score is not None:
            calculated_directive = (
                RouterDirective.NEXT if agent_output.score >= 3 else RouterDirective.STAY
            )
            state["router_directive"] = calculated_directive
            
            # If score-based logic says NEXT but LLM didn't generate transition message,
            # override the reply to be a transition message
            if (calculated_directive == RouterDirective.NEXT and 
                "move on" not in agent_output.reply.lower() and 
                "next section" not in agent_output.reply.lower()):
                agent_output.reply = "Great! Let's move on to the next section."
        else:
            # Fallback to value supplied by model (may be stay/next/modify)
            state["router_directive"] = agent_output.router_directive

        state["agent_output"] = agent_output

        # If we expect user input next, mark flag
        state["awaiting_user_input"] = (state["router_directive"] == RouterDirective.STAY)

        # Add AI reply to conversation history
        state["messages"].append(AIMessage(content=agent_output.reply))

        # Update short-term memory (last 10 exchanges)
        base_mem = state.get("short_memory", [])[-8:]
        if last_human_msg is not None:
            base_mem.append(last_human_msg)
        base_mem.append(AIMessage(content=agent_output.reply))
        state["short_memory"] = base_mem

    except Exception as e:
        logger.error(f"Failed to parse structured output: {e}\nResponse: {response.content if 'response' in locals() else ''}")
        default_output = ChatAgentOutput(
            reply="Sorry, I encountered a formatting error. Could you rephrase?",
            router_directive="stay",
            score=None,
            section_update=None,
        )
        state["agent_output"] = default_output
        state["router_directive"] = "stay"
        state["messages"].append(AIMessage(content=default_output.reply))
        state["awaiting_user_input"] = True
        state.setdefault("short_memory", []).append(AIMessage(content=default_output.reply))
    return state


async def memory_updater_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Memory updater node that persists section states and updates canvas data.
    
    Responsibilities:
    - Update section_states with latest content
    - Update canvas_data with extracted values
    - Manage short_memory size
    - Handle database writes
    """
    logger.info("Memory updater node")
    
    agent_out = state.get("agent_output")

    # Decide status based on score and directive
    def _status_from_output(score, directive):
        """Return status *string* to align with get_next_unfinished_section() logic."""
        if directive == RouterDirective.NEXT:
            return SectionStatus.DONE.value  # "done"
        if score is not None and score >= 3:
            return SectionStatus.DONE.value
        return SectionStatus.IN_PROGRESS.value

    if agent_out and agent_out.section_update:
        section_id = state["current_section"].value
        
        # Save to database using save_section tool
        await save_section.ainvoke({
            "user_id": state["user_id"],
            "doc_id": state["doc_id"],
            "section_id": section_id,
            "content": agent_out.section_update.model_dump(),
            "score": agent_out.score,
            "status": _status_from_output(agent_out.score, agent_out.router_directive),
        })
        
        # Update local state
        state["section_states"][section_id] = {
            "section_id": section_id,
            "content": agent_out.section_update.model_dump(),
            "score": agent_out.score,
            "status": _status_from_output(agent_out.score, agent_out.router_directive),
        }
        
        # Extract plain text and update canvas data
        # This would parse the content and update specific fields in canvas_data
        # For example, if section is ICP, extract icp_nickname, etc.
        
    # Even if there is no section_update (评分轮)，也要更新分数与状态
    if agent_out and not agent_out.section_update:
        section_id = state["current_section"].value
        state["section_states"].setdefault(section_id, {})
        state["section_states"][section_id]["score"] = agent_out.score
        state["section_states"][section_id]["status"] = _status_from_output(agent_out.score, agent_out.router_directive)

    return state


async def implementation_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Implementation node that generates the final checklist/PDF.
    
    Only runs when all sections are complete.
    """
    logger.info("Implementation node - Generating final deliverables")
    
    try:
        # Export checklist
        result = await export_checklist.ainvoke({
            "user_id": state["user_id"],
            "doc_id": state["doc_id"],
            "canvas_data": state["canvas_data"].model_dump(),
        })
        
        # Add completion message
        completion_msg = AIMessage(
            content=f"Congratulations! Your Value Canvas is complete. "
            f"You can download your implementation checklist here: {result['url']}"
        )
        state["messages"].append(completion_msg)
        
    except Exception as e:
        logger.error(f"Error generating implementation: {e}")
        error_msg = AIMessage(
            content=f"I encountered an error generating your checklist: {str(e)}. "
            "Your Value Canvas data has been saved and you can try exporting again later."
        )
        state["messages"].append(error_msg)
    
    return state



def route_decision(state: ValueCanvasState) -> Literal["implementation", "chat_agent", "halt"]:
    """Determine the next node to go to based on current state."""
    # 1. All sections complete → Implementation
    if state.get("finished", False):
        return "implementation"
    
    # Helper: determine if there's an unresponded user message
    def has_pending_user_input() -> bool:
        msgs = state.get("messages", [])
        if not msgs:
            return False
        last_msg = msgs[-1]
        from langchain_core.messages import HumanMessage, AIMessage  # local import to avoid circular
        # If last message is from user, agent hasn't replied yet
        return isinstance(last_msg, HumanMessage)
    
    directive = state.get("router_directive")
    
    # 2. STAY directive - continue on current section
    if directive == RouterDirective.STAY or (isinstance(directive, str) and directive.lower() == "stay"):
        # If the user has replied since last AI message, forward to Chat Agent.
        if has_pending_user_input():
            return "chat_agent"

        # 如果 AI 还在等用户回复，则停机等待下一次 run（防止重复提问）。
        if state.get("awaiting_user_input", False):
            return "halt"

        # 否则直接 halt（通常刚初始化时会走到这）。
        return "halt"
    
    # 3. NEXT/MODIFY directive - section transition  
    elif directive == RouterDirective.NEXT or (isinstance(directive, str) and directive.startswith("modify:")):
        # For NEXT/MODIFY directives, we need to let the router handle the transition
        # and then ask the first question for the new section
        
        # If there's a pending user input, it means user has acknowledged the transition
        # Let router process the directive and then go to chat_agent for new section
        if has_pending_user_input():
            return "chat_agent"
        
        # If Chat Agent just set NEXT directive but user hasn't responded yet, halt and wait
        msgs = state.get("messages", [])
        if msgs and isinstance(msgs[-1], AIMessage):
            return "halt"
        
        # Default case - go to chat_agent to ask first question of current section
        return "chat_agent"
    
    # 4. Default case - halt to prevent infinite loops
    return "halt"


# Build the graph
def build_value_canvas_graph():
    """Build the Value Canvas agent graph."""
    graph = StateGraph(ValueCanvasState)
    
    # Add nodes
    # initialize_node removed per design; router is now first node
    # graph.add_node("initialize", initialize_node)
    graph.add_node("router", router_node)
    graph.add_node("chat_agent", chat_agent_node)
    graph.add_node("memory_updater", memory_updater_node)
    graph.add_node("implementation", implementation_node)
    
    # Add edges
    graph.add_edge(START, "router")
    
    # Router can go to chat agent or implementation
    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "chat_agent": "chat_agent",
            "implementation": "implementation",
            "halt": END,
        }
    )
    
    # Chat agent has no tools, goes directly to memory_updater
    graph.add_edge("chat_agent", "memory_updater")
    
    # Memory updater goes back to router
    graph.add_edge("memory_updater", "router")
    
    # Implementation ends the graph
    graph.add_edge("implementation", END)
    
    return graph.compile()


# Create the runnable graph
graph = build_value_canvas_graph()


# Initialize function for new conversations
async def initialize_value_canvas_state(user_id: str, doc_id: str) -> ValueCanvasState:
    """Initialize a new Value Canvas state."""
    initial_state = ValueCanvasState(
        user_id=user_id,
        doc_id=doc_id,
        messages=[],
        current_section=SectionID.INTERVIEW,
        router_directive=RouterDirective.NEXT,  # Start by loading first section
    )
    
    # Get initial context
    context = await get_context.ainvoke({
        "user_id": user_id,
        "doc_id": doc_id,
        "section_id": SectionID.INTERVIEW.value,
        "canvas_data": {},
    })
    
    initial_state["context_packet"] = ContextPacket(**context)
    
    # Add welcome message
    welcome_msg = AIMessage(
        content="Welcome! I'm here to help you create your Value Canvas - "
        "a powerful framework that will transform your marketing messaging. "
        "Let's start by getting to know you and your business better."
    )
    initial_state["messages"].append(welcome_msg)
    
    return initial_state


__all__ = ["graph", "initialize_value_canvas_state"]