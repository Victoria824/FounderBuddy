"""Generate reply node for Founder Buddy Agent."""

import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from core.llm import get_model

from ..enums import SectionStatus
from ..models import FounderBuddyState

logger = logging.getLogger(__name__)


async def generate_reply_node(state: FounderBuddyState, config: RunnableConfig) -> FounderBuddyState:
    """
    Reply generation node that produces streaming conversational responses.
    
    Responsibilities:
    - Generate conversational reply based on context_packet system prompt
    - Support streaming output token by token
    - Add reply to conversation history
    - Update short_memory
    """
    logger.info(f"Generate reply node - Section: {state['current_section']}")
    
    # Check if conversation is finished (business plan generated)
    if state.get("finished", False):
        # Generate a polite message informing user that conversation is complete
        completion_message = """Thank you for using Founder Buddy! 

Your business plan has been generated and is available above. If you'd like to start a new conversation or make changes, please start a new thread.

Is there anything else I can help you with regarding your business plan?"""
        
        ai_message = AIMessage(content=completion_message)
        state["messages"].append(ai_message)
        state["awaiting_user_input"] = True
        
        logger.info("Generated completion message for finished conversation")
        return state
    
    context_packet = state.get('context_packet')
    
    # Get LLM - no tools, no structured output for streaming
    llm = get_model()
    
    messages: list[BaseMessage] = []

    # Section-specific system prompt from context packet
    if state.get("context_packet"):
        messages.append(SystemMessage(content=state["context_packet"].system_prompt))

        # Add progress information
        section_names = {
            "mission": "Mission",
            "idea": "Idea",
            "team_traction": "Team & Traction",
            "invest_plan": "Investment Plan"
        }
        
        completed_sections = []
        for section_id, section_state in state.get("section_states", {}).items():
            if section_state.status == SectionStatus.DONE:
                section_name = section_names.get(section_id, section_id)
                completed_sections.append(section_name)
        
        current_section_name = section_names.get(state["current_section"].value, state["current_section"].value)
        
        progress_info = (
            f"\n\nSYSTEM STATUS:\n"
            f"- Total sections: 4\n"
            f"- Completed: {len(completed_sections)} sections"
        )
        if completed_sections:
            progress_info += f" ({', '.join(completed_sections)})"
        progress_info += f"\n- Currently working on: {current_section_name}\n"
        
        messages.append(SystemMessage(content=progress_info))
        
        # Add clarification for new sections without content
        current_section_id = state["current_section"].value
        section_state = state.get("section_states", {}).get(current_section_id)
        if not section_state or not section_state.content:
            new_section_instruction = (
                f"IMPORTANT: You are now in the {current_section_id} section. "
                "This is a NEW section with no content yet. "
                "Start by following the conversation flow defined in the section prompt. "
                "Do NOT reference or include content from previous sections."
            )
            messages.append(SystemMessage(content=new_section_instruction))

    # Recent conversation memory
    messages.extend(state.get("short_memory", []))

    # Last human message (if any and agent hasn't replied yet)
    if state.get("messages"):
        _last_msg = state["messages"][-1]
        if isinstance(_last_msg, HumanMessage):
            messages.append(_last_msg)

    # Generate reply
    response = await llm.ainvoke(messages)
    
    # Extract content
    reply_content = response.content if hasattr(response, 'content') else str(response)
    
    # Create AI message
    ai_message = AIMessage(content=reply_content)
    
    # Add to messages
    state["messages"].append(ai_message)
    
    # Update short_memory (keep last 10 messages)
    short_memory = state.get("short_memory", [])
    short_memory.append(ai_message)
    if len(short_memory) > 10:
        short_memory = short_memory[-10:]
    state["short_memory"] = short_memory
    
    # Set awaiting_user_input flag
    state["awaiting_user_input"] = True
    
    logger.info(f"Generated reply for section {state['current_section'].value}")
    
    return state

