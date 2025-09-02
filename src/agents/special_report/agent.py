"""Special Report Agent implementation using LangGraph StateGraph."""

import logging
from typing import Literal
from uuid import uuid4

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END

from core.llm import get_model, LLMConfig
from .models import (
    SpecialReportState,
    SpecialReportData,
    SpecialReportSection,
    SectionState,
    SectionStatus,
    SectionContent,
    TiptapDocument,
    RouterDirective,
    ChatAgentOutput
)
from .prompts import (
    SECTION_TEMPLATES,
    SECTION_PROMPTS,
    get_section_order,
    get_next_section,
    get_next_unfinished_section
)
from .tools import (
    get_context,
    get_all_section_status,
    save_section,
    create_tiptap_content,
    extract_plain_text,
    validate_field,
    export_report
)

logger = logging.getLogger(__name__)


async def initialize_node(state: SpecialReportState, config: RunnableConfig) -> SpecialReportState:
    """Initialize the agent state."""
    logger.info("Initialize node - Setting up default values")

    # CRITICAL FIX: Get correct IDs from config instead of using temp IDs
    configurable = config.get("configurable", {})
    
    if "user_id" not in state or not state["user_id"]:
        # Try to get user_id from config first
        if "user_id" in configurable and configurable["user_id"]:
            state["user_id"] = configurable["user_id"]
            logger.info(f"Initialize node - Got user_id from config: {state['user_id']}")
        else:
            logger.error("CRITICAL: Initialize node running without a user_id in both state and config!")
            raise ValueError(
                "Critical system error: No valid user_id found. "
                "This indicates a serious ID chain break that will cause data loss. "
                "Check service.py ID passing logic."
            )
    
    if "thread_id" not in state or not state["thread_id"]:
        # Try to get thread_id from config
        if "thread_id" in configurable and configurable["thread_id"]:
            state["thread_id"] = configurable["thread_id"]
            logger.info(f"Initialize node - Got thread_id from config: {state['thread_id']}")
        else:
            logger.error("CRITICAL: Initialize node running without a thread_id in state or config!")
            raise ValueError(
                "Critical system error: No valid thread_id found. "
                "This indicates a serious ID chain break that will cause data loss. "
                "Check service.py ID passing logic."
            )

    # Ensure all other required fields have default values
    if "current_section" not in state:
        state["current_section"] = SpecialReportSection.TOPIC_SELECTION
    if "router_directive" not in state:
        state["router_directive"] = RouterDirective.NEXT
    if "finished" not in state:
        state["finished"] = False
    if "section_states" not in state:
        state["section_states"] = {}
    if "canvas_data" not in state:
        state["canvas_data"] = SpecialReportData()
    if "short_memory" not in state:
        state["short_memory"] = []
    if "error_count" not in state:
        state["error_count"] = 0
    if "last_error" not in state:
        state["last_error"] = None
    if "is_awaiting_rating" not in state:
        state["is_awaiting_rating"] = False
    if "messages" not in state:
        state["messages"] = []
    
    logger.info(f"Initialize complete - User: {state['user_id']}, Thread: {state['thread_id']}")
    return state


async def router_node(state: SpecialReportState, config: RunnableConfig) -> SpecialReportState:
    """Router node that handles navigation and context loading."""
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
        logger.info(f"DEBUG: Preparing to find next section. Current section states: {state.get('section_states', {})}")
        
        # DEBUG: Log current section and its state before transition
        current_section_id = state["current_section"].value
        logger.info(f"TRANSITION_DEBUG: Leaving section {current_section_id}")
        if current_section_id in state.get("section_states", {}):
            current_state = state["section_states"][current_section_id]
            logger.info(f"TRANSITION_DEBUG: Section {current_section_id} final state - status: {current_state.status}, has_content: {bool(current_state.content)}")
        
        next_section = get_next_unfinished_section(state.get("section_states", {}))
        logger.info(f"DEBUG: get_next_unfinished_section decided the next section is: {next_section}")
        
        if next_section:
            logger.info(f"Moving to next section: {next_section}")
            
            previous_section = state["current_section"]
            state["current_section"] = next_section

            # Only clear short_memory when transitioning to a different section
            if previous_section != next_section:
                state["short_memory"] = []
                logger.info(f"Cleared short_memory for new section {next_section.value}")
            else:
                logger.info(f"Preserved short_memory on same-section NEXT directive for {next_section.value}")

            # Get context for new section
            logger.debug(f"DATABASE_DEBUG: Router calling get_context for section {next_section.value}")
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "thread_id": state["thread_id"],
                "section_id": next_section.value,
            })
            logger.debug(f"DATABASE_DEBUG: get_context returned for section {next_section.value}")
            
            from .models import ContextPacket
            state["context_packet"] = ContextPacket(**context)
            
            # Reset directive to STAY to prevent repeated transitions
            state["router_directive"] = RouterDirective.STAY
        else:
            # All sections complete
            logger.info("All sections complete, setting finished flag")
            state["finished"] = True
    
    elif directive.startswith("modify:"):
        # Jump to specific section
        section_id = directive.split(":", 1)[1].lower()
        try:
            new_section = SpecialReportSection(section_id)
            logger.info(f"Jumping to section: {new_section}")
            prev_section = state.get("current_section")
            state["current_section"] = new_section
            
            # Only clear short_memory when switching to a different section
            if prev_section != new_section:
                state["short_memory"] = []
                logger.info(f"Cleared short_memory for jumped section {new_section.value}")
            else:
                logger.info(f"Preserved short_memory for same-section refresh {new_section.value}")
            
            # Get context for new section
            logger.debug(f"DATABASE_DEBUG: Router calling get_context for modify section {new_section.value}")
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "thread_id": state["thread_id"],
                "section_id": new_section.value,
            })
            logger.debug(f"DATABASE_DEBUG: get_context returned for modify section {new_section.value}")
            
            from .models import ContextPacket
            state["context_packet"] = ContextPacket(**context)
            
            # Reset directive to STAY to prevent repeated transitions
            state["router_directive"] = RouterDirective.STAY
        except ValueError:
            logger.error(f"Invalid section ID: {section_id}")
            state["last_error"] = f"Invalid section ID: {section_id}"
            state["error_count"] += 1
    
    return state


async def chat_agent_node(state: SpecialReportState, config: RunnableConfig) -> SpecialReportState:
    """Chat agent node that handles section-specific conversations."""
    logger.info(f"Chat agent node - Section: {state['current_section']}")
    
    # Get LLM - no tools for chat agent per design doc
    llm = get_model()
    
    messages = []
    last_human_msg: HumanMessage | None = None

    # Check if we should add summary instruction
    awaiting = state.get("awaiting_user_input", False)
    current_section = state["current_section"]
    section_state = state.get("section_states", {}).get(current_section.value)
    section_has_content = bool(section_state and section_state.content)
    
    # Only add summary reminder if section already has saved content that needs rating
    if section_has_content and not awaiting:
        summary_reminder = (
            "The user has previously worked on this section. "
            "Review the saved content and ask for their satisfaction rating if not already provided."
        )
        messages.append({"role": "system", "content": summary_reminder})
        logger.info(f"SUMMARY_REMINDER: Added reminder to check existing content for section {current_section.value}")

    # Section-specific system prompt from context packet
    if state.get("context_packet"):
        current_section_id = state["current_section"].value
        section_state = state.get("section_states", {}).get(current_section_id)

        if section_state and section_state.content:
            logger.info(f"MEMORY_DEBUG: Found existing content for {current_section_id}. Prioritizing it.")
            try:
                content_dict = section_state.content.content.model_dump()
                plain_text_summary = await extract_plain_text.ainvoke({"tiptap_json": content_dict})

                review_prompt = (
                    "CRITICAL CONTEXT: The user is reviewing a section they have already completed. "
                    "Their previous answers have been saved. Your primary task is to present this saved information back to them if they ask for it. "
                    "DO NOT ask the questions again. "
                    "Here is the exact summary of their previously provided answers:\n\n"
                    f"--- PREVIOUSLY SAVED SUMMARY ---\n{plain_text_summary}\n--- END SUMMARY ---"
                )
                messages.append({"role": "system", "content": review_prompt})
            except Exception as e:
                logger.error(f"MEMORY_DEBUG: Failed to extract plain text from existing state for {current_section_id}: {e}")
                # Fallback to the original prompt if extraction fails
                messages.append({"role": "system", "content": state["context_packet"].system_prompt})
        else:
            # Original behavior: use the default system prompt for the section
            messages.append({"role": "system", "content": state["context_packet"].system_prompt})

    # Recent conversation memory
    messages.extend([
        {"role": "user" if isinstance(msg, HumanMessage) else "assistant", "content": msg.content}
        for msg in state.get("short_memory", [])
    ])

    # Last human message (if any and agent hasn't replied yet)
    if state.get("messages"):
        _last_msg = state["messages"][-1]
        if isinstance(_last_msg, HumanMessage):
            messages.append({"role": "user", "content": _last_msg.content})
            last_human_msg = _last_msg

    try:
        # Use LangChain structured output with function calling for better reliability
        logger.info("🚀 Using LangChain structured output with function calling method")
        
        structured_llm = llm.with_structured_output(ChatAgentOutput, method="function_calling")
        
        logger.info("=== CALLING LLM WITH FUNCTION CALLING METHOD ===")
        llm_output = await structured_llm.ainvoke(messages)

        # DEBUG: Log the COMPLETE LLM output
        logger.info("=== LLM_OUTPUT_DEBUG ===")
        logger.info(f"Full reply: {llm_output.reply}")
        logger.info(f"Router directive: {llm_output.router_directive}")
        logger.info(f"Is requesting rating: {llm_output.is_requesting_rating}")
        logger.info(f"Score: {llm_output.score}")
        logger.info(f"Section update provided: {bool(llm_output.section_update)}")

        # Create the final agent_output for the state
        agent_output = llm_output
        
        # Add a safety rail: if the LLM provides a low score, force a 'stay' directive
        if agent_output.score is not None and agent_output.score < 3:
            logger.info(f"Low score ({agent_output.score}) detected from LLM. Forcing 'stay' directive.")
            agent_output.router_directive = "stay"

        # Set the is_awaiting_rating flag based on the structured output from the LLM
        if agent_output.is_requesting_rating:
            # CRITICAL VALIDATION: If requesting rating, must have section_update
            if not agent_output.section_update:
                logger.error("CRITICAL ERROR: Model requested rating but provided no section_update!")
                
                # Force correction to prevent infinite loops
                agent_output = ChatAgentOutput(
                    reply=(
                        "I notice I haven't properly collected all your information yet. "
                        "Let me continue with the next question."
                    ),
                    router_directive="stay",
                    is_requesting_rating=False,
                    score=None,
                    section_update=None
                )
                logger.info("FORCED CORRECTION: Created new corrected agent output to continue collecting information.")
            
            state["is_awaiting_rating"] = agent_output.is_requesting_rating
            logger.info(f"State updated: is_awaiting_rating set to {agent_output.is_requesting_rating}")
        else:
            state["is_awaiting_rating"] = False

        state["agent_output"] = agent_output

        # Determine router directive based on score
        if agent_output.score is not None:
            if agent_output.score >= 3:
                calculated_directive = RouterDirective.NEXT
            else:
                calculated_directive = RouterDirective.STAY
                
            state["router_directive"] = calculated_directive
        else:
            # Fallback to value supplied by model
            state["router_directive"] = agent_output.router_directive

        # Add AI reply to conversation history
        state["messages"].append(AIMessage(content=agent_output.reply))

        # Update short-term memory
        base_mem = state.get("short_memory", [])
        if last_human_msg is not None:
            base_mem.append(last_human_msg)
        base_mem.append(AIMessage(content=agent_output.reply))
        state["short_memory"] = base_mem

        logger.info(f"DEBUG_CHAT_AGENT: Agent output generated: {state.get('agent_output')}")

    except Exception as e:
        logger.error(f"Failed to get structured output from LLM: {e}")
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


async def memory_updater_node(state: SpecialReportState, config: RunnableConfig) -> SpecialReportState:
    """Memory updater node that persists section states and updates canvas data."""
    logger.info("=== DATABASE_DEBUG: memory_updater_node() ENTRY ===")
    logger.info("DATABASE_DEBUG: Memory updater node processing agent output")
    
    agent_out = state.get("agent_output")
    logger.debug(f"DATABASE_DEBUG: Agent output exists: {bool(agent_out)}")
    if agent_out:
        logger.debug(f"DATABASE_DEBUG: Agent output - section_update: {bool(agent_out.section_update)}, score: {agent_out.score}, router_directive: {agent_out.router_directive}")

    # CRITICAL FIX: Use enum status values, not strings
    def _status_from_output(score, directive):
        """Return status enum to match SectionState model."""
        if directive == RouterDirective.NEXT:
            return SectionStatus.DONE        # Returns enum, not string
        if score is not None and score >= 3:
            return SectionStatus.DONE
        return SectionStatus.IN_PROGRESS

    if agent_out and agent_out.section_update:
        section_id = state["current_section"].value
        logger.info(f"DATABASE_DEBUG: Processing section_update for section {section_id}")
        
        # Save to database using save_section tool
        logger.debug("DATABASE_DEBUG: Calling save_section tool with structured content")
        
        computed_status = _status_from_output(agent_out.score, agent_out.router_directive)
        logger.info(f"DATABASE_DEBUG: Computed status: {computed_status} (type: {type(computed_status)})")
        
        save_result = await save_section.ainvoke({
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
            "section_id": section_id,
            "content": agent_out.section_update['content'] if isinstance(agent_out.section_update, dict) else agent_out.section_update,
            "score": agent_out.score,
            "status": computed_status.value,  # Convert enum to string for database
        })
        logger.debug(f"DATABASE_DEBUG: save_section returned: {bool(save_result)}")
        
        # Update local state
        logger.debug("DATABASE_DEBUG: Updating local section_states with new content")
        if isinstance(agent_out.section_update, dict) and 'content' in agent_out.section_update:
            tiptap_doc = TiptapDocument.model_validate(agent_out.section_update['content'])
        else:
            logger.error(f"Invalid section_update structure: {type(agent_out.section_update)}")
            tiptap_doc = TiptapDocument(type="doc", content=[])
        
        state["section_states"][section_id] = SectionState(
            section_id=SpecialReportSection(section_id),
            content=SectionContent(
                content=tiptap_doc,
                plain_text=None
            ),
            score=agent_out.score,
            status=computed_status,  # Use enum directly
        )

        logger.info(f"DATABASE_DEBUG: ✅ Section {section_id} updated with structured content")

    logger.info("=== DATABASE_DEBUG: memory_updater_node() EXIT ===")
    return state


async def implementation_node(state: SpecialReportState, config: RunnableConfig) -> SpecialReportState:
    """Implementation node that generates the final report."""
    logger.info("Implementation node - Generating final deliverables")
    
    try:
        # Export report
        result = await export_report.ainvoke({
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
            "report_data": state["canvas_data"].model_dump(),
        })
        
        # Add completion message
        completion_msg = AIMessage(
            content=f"Congratulations! Your Special Report is complete. "
            f"You can download your report here: {result['url']}"
        )
        state["messages"].append(completion_msg)
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        error_msg = AIMessage(
            content=f"I encountered an error generating your report: {str(e)}. "
            "Your data has been saved and you can try exporting again later."
        )
        state["messages"].append(error_msg)
    
    return state


def route_decision(state: SpecialReportState) -> Literal["implementation", "chat_agent", "halt"]:
    """Determine the next node to go to based on current state."""
    # All sections complete → Implementation
    if state.get("finished", False):
        return "implementation"
    
    # Helper: determine if there's an unresponded user message
    def has_pending_user_input() -> bool:
        msgs = state.get("messages", [])
        if not msgs:
            return False
        last_msg = msgs[-1]
        return isinstance(last_msg, HumanMessage)
    
    directive = state.get("router_directive")
    
    # STAY directive - continue on current section
    if directive == RouterDirective.STAY or (isinstance(directive, str) and directive.lower() == "stay"):
        if has_pending_user_input():
            return "chat_agent"
        if state.get("awaiting_user_input", False):
            return "halt"
        return "halt"
    
    # NEXT/MODIFY directive - section transition  
    elif directive == RouterDirective.NEXT or (isinstance(directive, str) and directive.startswith("modify:")):
        if has_pending_user_input():
            return "chat_agent"
        
        msgs = state.get("messages", [])
        if msgs and isinstance(msgs[-1], AIMessage):
            return "halt"
        
        return "chat_agent"
    
    # Default case - halt to prevent infinite loops
    return "halt"


# Build the graph
def build_special_report_graph():
    """Build the Special Report agent graph."""
    graph = StateGraph(SpecialReportState)
    
    # Add nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("router", router_node)
    graph.add_node("chat_agent", chat_agent_node)
    graph.add_node("memory_updater", memory_updater_node)
    graph.add_node("implementation", implementation_node)
    
    # Add edges
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "router")
    
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
graph = build_special_report_graph()


# Initialize function for new conversations
async def initialize_special_report_state(user_id: int = None, thread_id: str = None) -> SpecialReportState:
    """Initialize a new Special Report state."""
    import uuid
    
    if not user_id:
        user_id = 1
        logger.info(f"Using default user_id: {user_id}")
    else:
        logger.info(f"Using provided user_id: {user_id}")

    if not thread_id:
        thread_id = str(uuid.uuid4())
        logger.info(f"Generated new thread_id: {thread_id}")
    else:
        try:
            uuid.UUID(thread_id)
        except ValueError:
            thread_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, thread_id))
            logger.info(f"Converted non-UUID thread_id to UUID: {thread_id}")
    
    initial_state = SpecialReportState(
        user_id=user_id,
        thread_id=thread_id,
        messages=[],
        current_section=SpecialReportSection.TOPIC_SELECTION,
        router_directive=RouterDirective.NEXT,  # Start by loading first section
    )
    
    # Get initial context
    context = await get_context.ainvoke({
        "user_id": user_id,
        "thread_id": thread_id,
        "section_id": SpecialReportSection.TOPIC_SELECTION.value,
    })
    
    from .models import ContextPacket
    initial_state["context_packet"] = ContextPacket(**context)
    
    # Add welcome message
    welcome_msg = AIMessage(
        content="Welcome! I'm here to help you create your Special Report. "
        "Let's start with topic selection."
    )
    initial_state["messages"].append(welcome_msg)
    
    return initial_state


__all__ = ["graph", "initialize_special_report_state"]