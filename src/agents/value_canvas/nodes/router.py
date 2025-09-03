"""Router node for Value Canvas Agent."""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from core.logging_config import get_logger
from ..models import ValueCanvasState, ContextPacket
from ..enums import SectionID, RouterDirective
from ..prompts import get_next_unfinished_section
from ..tools import get_context

logger = get_logger(__name__)

# Router tools
router_tools = [
    get_context,
]

# Create tool node
router_tool_node = ToolNode(router_tools)


async def router_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Router node that handles navigation and context loading.
    
    Responsibilities:
    - Process router directives (stay, next, modify:section_id)
    - Update current_section
    - Call get_context when changing sections
    - Check for completion and set finished flag
    """
    # Check if there's a new user message - if so, reset awaiting_user_input
    msgs = state.get("messages", [])
    if msgs and len(msgs) >= 2:
        last_msg = msgs[-1]
        second_last_msg = msgs[-2]
        # If last message is human and second last is AI, user has responded
        if isinstance(last_msg, HumanMessage) and isinstance(second_last_msg, AIMessage):
            state["awaiting_user_input"] = False

    current_section = state.get('current_section')
    directive = state.get("router_directive", RouterDirective.STAY)
    
    logger.debug(f"[ROUTER] Section: {current_section.value if current_section else 'unknown'}, Directive: {directive}")

    if directive == RouterDirective.STAY:
        # Stay on current section, no context reload needed
        logger.debug("Staying on current section")
        return state
    
    elif directive == RouterDirective.NEXT:
        # Find next unfinished section
        current_section_id = state["current_section"].value
        next_section = get_next_unfinished_section(state.get("section_states", {}))
        
        if next_section:
            logger.section_transition(current_section_id, next_section.value, "next")
            
            previous_section = state["current_section"]
            state["current_section"] = next_section

            # Only clear short_memory when transitioning to a different section
            if previous_section != next_section:
                state["short_memory"] = []
                logger.debug(f"Cleared short_memory for new section")
            else:
                logger.debug(f"Preserved short_memory for same section")

            # Get context for new section
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "thread_id": state["thread_id"],
                "section_id": next_section.value,
                "canvas_data": state["canvas_data"].model_dump(),
            })
            
            state["context_packet"] = ContextPacket(**context)
            
            # Reset directive to STAY to prevent repeated transitions
            state["router_directive"] = RouterDirective.STAY
        else:
            # All sections complete
            logger.info("[COMPLETE] All sections finished")
            state["finished"] = True
    
    elif directive.startswith("modify:"):
        # Jump to specific section
        section_id = directive.split(":", 1)[1].lower()  # handle case-insensitive IDs like "ICP"
        try:
            new_section = SectionID(section_id)
            logger.section_transition(
                prev_section.value if prev_section else "unknown",
                new_section.value,
                "modify"
            )
            prev_section = state.get("current_section")
            state["current_section"] = new_section
            
            # Only clear short_memory when switching to a different section
            if prev_section != new_section:
                state["short_memory"] = []
                logger.debug(f"Cleared short_memory for section jump")
            else:
                logger.debug(f"Preserved short_memory for same-section refresh")
            
            # Get context for new section
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "thread_id": state["thread_id"],
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