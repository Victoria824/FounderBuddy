"""Memory updater node for Founder Buddy Agent."""

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from core.logging_config import get_logger

from ..enums import RouterDirective, SectionID, SectionStatus
from ..models import SectionContent, SectionState, TiptapDocument, TiptapParagraphNode, TiptapTextNode, FounderBuddyState

logger = get_logger(__name__)


async def memory_updater_node(state: FounderBuddyState, config: RunnableConfig) -> FounderBuddyState:
    """
    Memory updater node that persists section states.
    
    Responsibilities:
    - Update section_states with latest content
    - Update founder_data with extracted values
    - Manage short_memory size
    - Generate business plan when all sections are complete
    """
    current_section = state.get('current_section')
    logger.info(f"Memory updater node - Section: {current_section.value if current_section else 'unknown'}")
    
    agent_out = state.get("agent_output")
    
    if not agent_out:
        logger.debug("No agent output to process")
        return state
    
    # Decide status based on satisfaction and directive
    def _status_from_output(is_satisfied, directive):
        """Return status string."""
        if directive == RouterDirective.NEXT:
            return SectionStatus.DONE.value
        if is_satisfied is not None and is_satisfied:
            return SectionStatus.DONE.value
        return SectionStatus.IN_PROGRESS.value

    # Update section state if we should save content
    if agent_out.should_save_content:
        current_section_id = current_section.value if current_section else "unknown"
        
        # Get the last AI message content
        messages = state.get("messages", [])
        last_ai_msg = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                last_ai_msg = msg
                break
        
        if last_ai_msg:
            # Create section content
            plain_text = last_ai_msg.content
            
            # Create simple Tiptap document
            tiptap_doc = TiptapDocument(
                type="doc",
                content=[
                    TiptapParagraphNode(
                        type="paragraph",
                        content=[
                            TiptapTextNode(type="text", text=plain_text)
                        ]
                    )
                ]
            )
            
            section_content = SectionContent(
                content=tiptap_doc,
                plain_text=plain_text
            )
            
            # Update or create section state
            section_states = state.get("section_states", {})
            section_state = SectionState(
                section_id=current_section,
                content=section_content,
                satisfaction_status="satisfied" if agent_out.is_satisfied else None,
                status=SectionStatus(_status_from_output(agent_out.is_satisfied, RouterDirective(agent_out.router_directive)))
            )
            
            section_states[current_section_id] = section_state
            state["section_states"] = section_states
            
            logger.info(f"Updated section state for {current_section_id} with status {section_state.status.value}")
    
    # Check if all sections are complete and generate business plan
    section_states = state.get("section_states", {})
    all_sections = [SectionID.MISSION, SectionID.IDEA, SectionID.TEAM_TRACTION, SectionID.INVEST_PLAN]
    
    # Check completion status
    all_complete = all(
        section_id.value in section_states and 
        section_states[section_id.value].status == SectionStatus.DONE
        for section_id in all_sections
    )
    
    # Also check if we're in the last section and user said they're done
    current_section = state.get('current_section')
    is_last_section = current_section == SectionID.INVEST_PLAN if current_section else False
    
    # Check if user indicated they're satisfied/done
    user_done = False
    messages = state.get("messages", [])
    if messages:
        last_user_msg = None
        for msg in reversed(messages):
            from langchain_core.messages import HumanMessage
            if isinstance(msg, HumanMessage):
                last_user_msg = msg.content.lower() if hasattr(msg, 'content') else ""
                break
        
        done_keywords = ["satisfied", "done", "finished", "complete", "good", "right", "proceed", "think i'm satisfied"]
        user_done = any(keyword in str(last_user_msg) for keyword in done_keywords) if last_user_msg else False
    
    # Check if we should generate business plan (set flag for router to handle)
    # 1. All sections are marked as DONE, OR
    # 2. We're in the last section and user said they're satisfied
    should_generate_plan = (
        (all_complete and user_done) or 
        (is_last_section and user_done)
    ) and not state.get("business_plan")
    
    if should_generate_plan:
        logger.info("All sections complete and user satisfied - setting flag to generate business plan")
        state["should_generate_business_plan"] = True
    else:
        state["should_generate_business_plan"] = False
    
    # Manage short_memory size (keep last 10 messages)
    short_memory = state.get("short_memory", [])
    if len(short_memory) > 10:
        state["short_memory"] = short_memory[-10:]
    
    return state

