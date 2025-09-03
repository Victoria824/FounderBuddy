"""Generate reply node for Value Canvas Agent."""

import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from core.llm import get_model
from ..models import ValueCanvasState
from ..enums import SectionID, SectionStatus
from ..tools import extract_plain_text

logger = logging.getLogger(__name__)


async def generate_reply_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Reply generation node that produces streaming conversational responses.
    
    Responsibilities:
    - Generate conversational reply based on context_packet system prompt
    - Support streaming output token by token
    - Add reply to conversation history
    - Update short_memory
    """
    logger.info(f"Generate reply node - Section: {state['current_section']}")
    
    # DEBUG: Log recent message history
    # Create a new context packet for this turn
    context_packet = state.get('context_packet')
    logger.info(
        f"DEBUG_REPLY_NODE: Context Packet received: {context_packet}"
    )

    # Get LLM - no tools, no structured output for streaming
    llm = get_model()
    
    messages: list[BaseMessage] = []
    last_human_msg: HumanMessage | None = None

    # FIRST_TURN_GUARD removed - Let LLM handle conversation flow intelligently
    # based on section-specific prompt instructions

    # Check if we should add summary instruction
    # Add summary instruction when:
    # 1. We're not already awaiting user input
    # 2. User hasn't provided a rating
    # 3. We have collected enough information in the conversation (check short_memory)
    awaiting = state.get("awaiting_user_input", False)
    current_section = state["current_section"]
    section_state = state.get("section_states", {}).get(current_section.value)
    section_has_content = bool(section_state and section_state.content)
    
    # Only add summary reminder if section already has saved content that needs rating
    # EXCEPTION: Don't enter review mode for Interview section - let it complete its 8-step flow
    if section_has_content and not awaiting and current_section != SectionID.INTERVIEW:
        # This is for sections that were previously saved but need rating
        summary_reminder = (
            "The user has previously worked on this section. "
            "Review the saved content and ask for their satisfaction rating if not already provided."
        )
        messages.append(SystemMessage(content=summary_reminder))
        logger.info(f"SUMMARY_REMINDER: Added reminder to check existing content for section {current_section.value}")

    # 2) Section-specific system prompt from context packet
    if state.get("context_packet"):
        # NEW: Prioritize displaying existing section content if available
        current_section_id = state["current_section"].value
        section_state = state.get("section_states", {}).get(current_section_id)

        if section_state and section_state.content and current_section != SectionID.INTERVIEW:
            logger.info(f"MEMORY_DEBUG: Found existing content for {current_section_id}. Prioritizing it.")
            try:
                # Use the plain_text version if available, otherwise extract it.
                # Note: content in section_states is now a SectionContent object.
                content_dict = section_state.content.content.model_dump()
                plain_text_summary = await extract_plain_text.ainvoke({"tiptap_json": content_dict})

                review_prompt = (
                    "CRITICAL CONTEXT: The user is reviewing a section they have already completed. "
                    "Their previous answers have been saved. Your primary task is to present this saved information back to them if they ask for it. "
                    "DO NOT ask the interview questions again. "
                    "Here is the exact summary of their previously provided answers. You MUST use this information:\n\n"
                    f"--- PREVIOUSLY SAVED SUMMARY ---\n{plain_text_summary}\n--- END SUMMARY ---"
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
            "interview": "Interview",
            "icp": "Ideal Client Persona (ICP)",
            "pain": "The Pain",
            "deep_fear": "Deep Fear",
            "payoffs": "The Payoffs",
            "signature_method": "Signature Method",
            "mistakes": "Mistakes",
            "prize": "Prize"
        }
        
        completed_sections = []
        for section_id, section_state in state.get("section_states", {}).items():
            if section_state.status == SectionStatus.DONE:
                section_name = section_names.get(section_id, section_id)
                completed_sections.append(section_name)
        
        current_section_name = section_names.get(state["current_section"].value, state["current_section"].value)
        
        progress_info = (
            f"\n\nSYSTEM STATUS:\n"
            f"- Total sections: 9\n"
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

    # 3) Recent conversation memory
    # Keep all messages from short_memory.
    messages.extend(state.get("short_memory", []))

    # 4) Last human message (if any and agent hasn't replied yet)
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
        logger.info("Last 2 messages:")
        for i, msg in enumerate(messages[-2:]):
            msg_type = type(msg).__name__
            content_preview = msg.content[:200] if hasattr(msg, 'content') else str(msg)[:200]
            logger.info(f"  [{i}] {msg_type}: {content_preview}...")
        
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

        # Add AI reply to conversation history
        state["messages"].append(AIMessage(content=reply_content))

        # Update short-term memory by appending new messages
        base_mem = state.get("short_memory", [])
        if last_human_msg is not None:
            base_mem.append(last_human_msg)
        base_mem.append(AIMessage(content=reply_content))
        state["short_memory"] = base_mem

        logger.info(f"DEBUG_REPLY_NODE: Reply generated successfully")
        
    except Exception as e:
        logger.error(f"Failed to generate reply: {e}")
        default_reply = "Sorry, I encountered an error generating my response. Could you rephrase your question?"
        state["messages"].append(AIMessage(content=default_reply))
        state.setdefault("short_memory", []).append(AIMessage(content=default_reply))
    
    return state