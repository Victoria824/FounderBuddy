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
    if state.get("finished", False) or state.get("business_plan"):
        # Check if business plan message already exists in messages
        messages = state.get("messages", [])
        has_business_plan_message = any(
            isinstance(msg, AIMessage) and 
            ("business plan generated" in msg.content.lower() or "🎉" in msg.content)
            for msg in messages
        )
        
        if not has_business_plan_message:
            # Business plan was generated but message not sent yet - send it now
            business_plan = state.get("business_plan", "")
            if business_plan:
                final_message = f"""# 🎉 Business Plan Generated

Thank you for completing all sections! Below is your complete business plan based on our conversation:

---

{business_plan}

---

**Next Steps:**
1. Review this business plan carefully
2. Adjust and refine based on your actual situation
3. Begin executing the action items outlined in the plan

Best of luck with your venture! 🚀"""
                ai_message = AIMessage(content=final_message)
                state["messages"].append(ai_message)
                logger.info("Added business plan message to conversation")
        
        # Generate a polite message informing user that conversation is complete
        completion_message = """Thank you for using Founder Buddy! 

Your business plan has been generated and is available above. If you'd like to start a new conversation or make changes, please start a new thread.

Is there anything else I can help you with regarding your business plan?"""
        
        ai_message = AIMessage(content=completion_message)
        state["messages"].append(ai_message)
        state["awaiting_user_input"] = True
        
        logger.info("Generated completion message for finished conversation")
        return state
    
    # Check if user just confirmed the final summary - skip generating reply
    # Let memory_updater route to business plan generation instead
    messages = state.get("messages", [])
    if messages and len(messages) >= 2:
        last_msg = messages[-1]
        second_last_msg = messages[-2]
        
        if isinstance(last_msg, HumanMessage) and isinstance(second_last_msg, AIMessage):
            user_content = last_msg.content.lower()
            ai_content = second_last_msg.content.lower()
            
            # Check if user confirmed summary (expanded list)
            satisfaction_words = ["yes", "good", "great", "perfect", "right", "correct", "sounds good", "looks good", "that's right", "exactly", "yep", "yeah"]
            user_confirmed = any(word in user_content for word in satisfaction_words)
            
            # Check if AI showed summary (expanded detection)
            # Match patterns like "Does this feel right", "Does this summary feel right", "Here's a summary", etc.
            ai_showed_summary = (
                "summary" in ai_content or 
                "does this feel right" in ai_content or
                "does this summary" in ai_content or
                "here's a summary" in ai_content or
                "here is a summary" in ai_content or
                "summary of your" in ai_content or
                "feel right to you" in ai_content or
                "does this summary feel right" in ai_content
            )
            
            # Check if we're in the last section
            from ..enums import SectionID
            current_section = state.get("current_section")
            is_last_section = current_section == SectionID.INVEST_PLAN if current_section else False
            
            # Log for debugging
            logger.info(f"Checking skip conditions: is_last_section={is_last_section}, ai_showed_summary={ai_showed_summary}, user_confirmed={user_confirmed}")
            logger.info(f"User message: {user_content[:100]}")
            logger.info(f"AI message: {ai_content[:200]}")
            
            # If user confirmed summary in last section, skip generating reply
            # This allows memory_updater to route to business plan generation
            if is_last_section and ai_showed_summary and user_confirmed:
                logger.info("User confirmed final summary - skipping reply generation to allow business plan generation")
                logger.info(f"Conditions: is_last_section={is_last_section}, ai_showed_summary={ai_showed_summary}, user_confirmed={user_confirmed}")
                # Don't generate a reply, just return state
                # The memory_updater will handle routing to business plan generation
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

