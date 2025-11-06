"""Router node for Founder Buddy Agent."""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from core.logging_config import get_logger

from ..enums import RouterDirective, SectionID
from ..models import ContextPacket, FounderBuddyState
from ..prompts import get_next_unfinished_section
from ..tools import get_context

logger = get_logger(__name__)

# Router tools
router_tools = [
    get_context,
]

# Create tool node
router_tool_node = ToolNode(router_tools)


async def router_node(state: FounderBuddyState, config: RunnableConfig) -> FounderBuddyState:
    """
    Router node that handles navigation and context loading.
    
    Responsibilities:
    - Process router directives (stay, next, modify:section_id)
    - Update current_section
    - Call get_context when changing sections
    - Check for completion and set finished flag
    """
    # If business plan is generated or conversation is finished, don't route to new sections
    if state.get("finished", False) or state.get("business_plan"):
        logger.info("[ROUTER] Business plan generated or conversation finished - staying in current state")
        state["router_directive"] = RouterDirective.STAY
        return state
    
    msgs = state.get("messages", [])
    if msgs and len(msgs) >= 2:
        last_msg = msgs[-1]
        second_last_msg = msgs[-2]
        if isinstance(last_msg, HumanMessage) and isinstance(second_last_msg, AIMessage):
            state["awaiting_user_input"] = False

    current_section = state.get('current_section')
    directive = state.get("router_directive", RouterDirective.STAY)
    
    logger.debug(f"[ROUTER] Section: {current_section.value if current_section else 'unknown'}, Directive: {directive}")

    if directive == RouterDirective.STAY:
        logger.debug("Staying on current section")
        
        if not state.get("context_packet"):
            logger.debug("[ROUTER] Loading context_packet for current section")
            current_section_id = state["current_section"].value
            
            founder_data = state.get("founder_data")
            founder_data_dict = founder_data.model_dump() if founder_data else {}
            
            context = await get_context.ainvoke({
                "user_id": state.get("user_id", 1),
                "thread_id": state.get("thread_id"),
                "section_id": current_section_id,
                "founder_data": founder_data_dict,
            })
            
            state["context_packet"] = ContextPacket(**context)
            logger.debug(f"[ROUTER] Loaded context_packet for {current_section_id}")
        
        return state
    
    elif directive == RouterDirective.NEXT:
        current_section_id = state["current_section"].value
        logger.debug(f"[ROUTER] Current section: {current_section_id}, directive: {directive}")
        
        from ..prompts import get_next_section
        next_section = get_next_section(state["current_section"])
        
        if next_section:
            logger.info(f"[ROUTER] Transitioning from {current_section_id} to {next_section.value}")
            
            previous_section = state["current_section"]
            state["current_section"] = next_section

            if previous_section != next_section:
                state["short_memory"] = []
                logger.debug("Cleared short_memory for new section")
            
            state["router_directive"] = RouterDirective.STAY
            
            founder_data = state.get("founder_data")
            founder_data_dict = founder_data.model_dump() if founder_data else {}
            
            context = await get_context.ainvoke({
                "user_id": state.get("user_id", 1),
                "thread_id": state.get("thread_id"),
                "section_id": next_section.value,
                "founder_data": founder_data_dict,
            })
            
            state["context_packet"] = ContextPacket(**context)
            logger.debug(f"[ROUTER] Loaded context_packet for {next_section.value}")
        else:
            # All sections complete
            logger.info("[ROUTER] All sections complete, finishing")
            state["finished"] = True
            state["router_directive"] = RouterDirective.STAY
        
        return state
    
    elif isinstance(directive, str) and directive.startswith("modify:"):
        target_section_id = directive.split(":", 1)[1]
        logger.info(f"[ROUTER] Modify directive: jumping to {target_section_id}")
        
        try:
            target_section = SectionID(target_section_id)
            state["current_section"] = target_section
            state["router_directive"] = RouterDirective.STAY
            
            founder_data = state.get("founder_data")
            founder_data_dict = founder_data.model_dump() if founder_data else {}
            
            context = await get_context.ainvoke({
                "user_id": state.get("user_id", 1),
                "thread_id": state.get("thread_id"),
                "section_id": target_section_id,
                "founder_data": founder_data_dict,
            })
            
            state["context_packet"] = ContextPacket(**context)
            logger.debug(f"[ROUTER] Loaded context_packet for {target_section_id}")
        except ValueError:
            logger.error(f"[ROUTER] Invalid section ID: {target_section_id}")
            state["router_directive"] = RouterDirective.STAY
        
        return state
    
    return state

