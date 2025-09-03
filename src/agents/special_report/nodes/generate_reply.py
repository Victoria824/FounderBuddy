"""Generate reply node for Special Report Agent."""

import logging

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from core.llm import get_model
from core.logging_config import get_logger
from ..models import SpecialReportState, SectionState
from ..enums import SpecialReportSection, SectionStatus
from ..tools import extract_plain_text
from ..prompts import SECTION_TEMPLATES, get_next_unfinished_section

logger = get_logger(__name__)


async def generate_reply_node(state: SpecialReportState, config: RunnableConfig) -> SpecialReportState:
    """Generate conversational reply without structured output."""
    current_section = state.get('current_section')
    logger.info(f"Generate reply node - Section: {current_section}")
    
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
        messages.append(SystemMessage(content=summary_reminder))
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
                messages.append(SystemMessage(content=review_prompt))
            except Exception as e:
                logger.error(f"MEMORY_DEBUG: Failed to extract plain text from existing state for {current_section_id}: {e}")
                # Fallback to the original prompt if extraction fails
                messages.append(SystemMessage(content=state["context_packet"].system_prompt))
        else:
            # Original behavior: use the default system prompt for the section
            messages.append(SystemMessage(content=state["context_packet"].system_prompt))

    # Recent conversation memory  
    messages.extend(state.get("short_memory", []))
    
    # Check if this is the initial message generation (no human input yet, just basic welcome)
    is_initial_message = False
    current_messages = state.get("messages", [])
    if (len(current_messages) == 1 and 
        isinstance(current_messages[0], AIMessage) and 
        "Welcome! I'm here to help you create your Special Report" in current_messages[0].content):
        is_initial_message = True
        logger.info("INITIAL_MESSAGE: Generating detailed first message to replace basic welcome")
    
    # Last human message (if any and agent hasn't replied yet)
    if state.get("messages") and not is_initial_message:
        _last_msg = state["messages"][-1]
        if isinstance(_last_msg, HumanMessage):
            messages.append(_last_msg)
            last_human_msg = _last_msg

    # --- Pre-LLM Context Injection ---
    # To prevent the LLM from hallucinating the next section's name, we calculate it
    # programmatically and provide it as a direct instruction.
    try:
        temp_states = state.get("section_states", {}).copy()
        current_section_id = state["current_section"].value
        
        if current_section_id not in temp_states:
            temp_states[current_section_id] = SectionState(
                section_id=SpecialReportSection(current_section_id),
                status=SectionStatus.DONE
            )
        else:
            # Assume the current section will be completed in this turn for prediction
            temp_states[current_section_id].status = SectionStatus.DONE

        next_section = get_next_unfinished_section(temp_states)
        
        if next_section:
            next_section_name = SECTION_TEMPLATES.get(next_section.value).name
            instructional_prompt = (
                f"SYSTEM INSTRUCTION: The next section is '{next_section_name}'. "
                "If the user confirms to proceed, you MUST use this exact name in your transition message."
            )
            messages.append(SystemMessage(content=instructional_prompt))
            logger.info(f"Injected next section name into context: '{next_section_name}'")
    except Exception as e:
        logger.warning(f"Could not determine next section for prompt injection: {e}")
    # --- End of Pre-LLM Context Injection ---

    try:
        # Generate conversational response without structured output
        logger.info("🚀 Generating streaming reply without structured output")
        
        # Override stream setting if present in config to prevent streaming in internal generation
        reply_config = RunnableConfig(
            configurable={"stream": False},
            tags=["generate_reply", "no_stream"]
        )
        
        reply_response = await llm.ainvoke(messages, config=reply_config)
        
        # Extract content from response
        if hasattr(reply_response, 'content'):
            reply_content = reply_response.content
        else:
            reply_content = str(reply_response)
        
        logger.info(f"=== REPLY_OUTPUT_DEBUG ===")
        logger.info(f"Raw reply content: {reply_content[:200]}...")
        logger.info(f"Final reply content: {reply_content[:200]}...")
        
        # Store reply in state for decision node to use
        state["current_reply"] = reply_content
        
        # Add AI reply to conversation history
        if is_initial_message:
            # Replace the basic welcome message with the detailed first message
            state["messages"] = [AIMessage(content=reply_content)]
            logger.info("INITIAL_MESSAGE: Replaced basic welcome message with detailed first message")
        else:
            state["messages"].append(AIMessage(content=reply_content))

        # Update short-term memory
        base_mem = state.get("short_memory", [])
        if last_human_msg is not None:
            base_mem.append(last_human_msg)
        base_mem.append(AIMessage(content=reply_content))
        state["short_memory"] = base_mem

        logger.info(f"DEBUG_GENERATE_REPLY: Reply generated successfully")

    except Exception as e:
        logger.error(f"Failed to generate reply: {e}")
        default_reply = "Sorry, I encountered an error generating my response. Could you please try again?"
        state["current_reply"] = default_reply
        state["messages"].append(AIMessage(content=default_reply))
        state["awaiting_user_input"] = True
        state.setdefault("short_memory", []).append(AIMessage(content=default_reply))
    
    return state