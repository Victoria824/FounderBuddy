"""Generate reply node for Mission Pitch Agent."""

import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agents.message_utils import create_ai_message_with_metadata
from core.llm import get_model

from ..enums import SectionStatus
from ..models import MissionPitchState

logger = logging.getLogger(__name__)


async def generate_reply_node(state: MissionPitchState, config: RunnableConfig) -> MissionPitchState:
    """
    Reply generation node that produces streaming conversational responses.
    
    Responsibilities:
    - Generate conversational reply based on context_packet system prompt
    - Support streaming output token by token
    - Add reply to conversation history
    - Update short_memory
    """
    logger.info(f"Generate reply node - Section: {state['current_section']}")
    
    # Get LLM - no tools, no structured output for streaming
    llm = get_model()
    
    messages: list[BaseMessage] = []
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
        messages.append(SystemMessage(content=summary_reminder))
        logger.info(f"SUMMARY_REMINDER: Added reminder to check existing content for section {current_section.value}")

    # Section-specific system prompt from context packet
    if state.get("context_packet"):
        # Prioritize displaying existing section content if available
        current_section_id = state["current_section"].value
        section_state = state.get("section_states", {}).get(current_section_id)

        if section_state and section_state.content:
            logger.info(f"MEMORY_DEBUG: Found existing content for {current_section_id}. Prioritizing it.")
            try:
                # Extract plain text from existing content for context
                content_dict = section_state.content.content.model_dump()
                # Simple extraction - get text content from Tiptap structure
                plain_text_summary = ""
                if 'content' in content_dict:
                    for paragraph in content_dict['content']:
                        if paragraph.get('type') == 'paragraph' and 'content' in paragraph:
                            for text_node in paragraph['content']:
                                if text_node.get('type') == 'text':
                                    plain_text_summary += text_node.get('text', '') + " "

                review_prompt = (
                    "CRITICAL CONTEXT: The user is reviewing a section they have already completed. "
                    "Their previous answers have been saved. Your primary task is to present this saved information back to them if they ask for it. "
                    "DO NOT ask the interview questions again. "
                    "Here is the exact summary of their previously provided answers:\n\n"
                    f"--- PREVIOUSLY SAVED SUMMARY ---\n{plain_text_summary.strip()}\n--- END SUMMARY ---"
                )
                messages.append(SystemMessage(content=review_prompt))
            except Exception as e:
                logger.error(f"MEMORY_DEBUG: Failed to extract plain text from existing state for {current_section_id}: {e}")
                # Fallback to the original prompt if extraction fails
                messages.append(SystemMessage(content=state["context_packet"].system_prompt))
        else:
            # Original behavior: use the default system prompt for the section
            messages.append(SystemMessage(content=state["context_packet"].system_prompt))

        # Add progress information based on section_states
        section_names = {
            "hidden_theme": "Hidden Theme",
            "personal_origin": "Personal Origin", 
            "business_origin": "Business Origin",
            "mission": "Mission",
            "three_year_vision": "3-Year Vision",
            "big_vision": "Big Vision",
            "implementation": "Implementation"
        }
        
        completed_sections = []
        for section_id, section_state in state.get("section_states", {}).items():
            if section_state.status == SectionStatus.DONE:
                section_name = section_names.get(section_id, section_id)
                completed_sections.append(section_name)
        
        current_section_name = section_names.get(state["current_section"].value, state["current_section"].value)
        
        progress_info = (
            f"\n\nSYSTEM STATUS:\n"
            f"- Total sections: 7\n"
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
                "Do NOT generate section_update until you have collected actual data for THIS section. "
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
            last_human_msg = _last_msg

    # Override JSON output requirement with a simple instruction
    messages.append(SystemMessage(
        content="OVERRIDE: Generate a natural conversational response. "
                "Do NOT output JSON format. Just provide your direct reply to the user."
    ))

    try:
        # DEBUG: Log LLM input
        logger.info("=== LLM_REPLY_INPUT_DEBUG ===")
        logger.info(f"Current section: {state['current_section']}")
        logger.info(f"Total messages count: {len(messages)}")
        
        # Use standard LLM for streaming response (no structured output)
        logger.info("🚀 Generating streaming reply without structured output")
        
        # Generate the reply
        reply_message = await llm.ainvoke(messages)
        reply_content = reply_message.content

        # DEBUG: Log the reply content
        logger.info("=== REPLY_OUTPUT_DEBUG ===")
        logger.info(f"Raw reply content: {reply_content[:200]}...")

        # Defensive programming: Check if LLM still returned JSON
        if "```json" in reply_content or reply_content.strip().startswith("{"):
            logger.info("🔧 Reply contains JSON, attempting to extract reply field")
            try:
                import json
                # Clean markdown code blocks if present
                cleaned = reply_content.replace("```json", "").replace("```", "").strip()
                
                # Try to parse as JSON
                response_data = json.loads(cleaned)
                if isinstance(response_data, dict) and "reply" in response_data:
                    reply_content = response_data["reply"]
                    logger.info("✅ Successfully extracted reply from JSON output")
                else:
                    logger.warning("⚠️ JSON found but no 'reply' field, using raw content")
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Failed to parse JSON reply: {e}, using raw content")
            except Exception as e:
                logger.warning(f"⚠️ Error processing JSON reply: {e}, using raw content")

        # Final reply content
        logger.info(f"Final reply content: {reply_content[:200]}...")

        # Store reply in state for decision node to use
        state["current_reply"] = reply_content

        # Add AI reply to conversation history with section metadata
        ai_message = create_ai_message_with_metadata(
            content=reply_content,
            section_id=state["current_section"].value,
            agent_name="mission-pitch"
        )
        state["messages"].append(ai_message)

        # Update short-term memory by appending new messages
        base_mem = state.get("short_memory", [])
        if last_human_msg is not None:
            base_mem.append(last_human_msg)
        base_mem.append(ai_message)
        state["short_memory"] = base_mem

        logger.info("DEBUG_REPLY_NODE: Reply generated successfully")
        
    except Exception as e:
        logger.error(f"Failed to generate reply: {e}")
        default_reply = "Sorry, I encountered an error generating my response. Could you rephrase your question?"
        state["current_reply"] = default_reply
        error_message = create_ai_message_with_metadata(
            content=default_reply,
            section_id=state["current_section"].value,
            agent_name="mission-pitch"
        )
        state["messages"].append(error_message)
        state.setdefault("short_memory", []).append(error_message)
    
    return state




