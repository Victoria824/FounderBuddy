"""Generate reply node for Concept Pitch Agent."""

import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from core.llm import get_model

from ..enums import SectionStatus
from ..models import ConceptPitchState

logger = logging.getLogger(__name__)


async def generate_reply_node(state: ConceptPitchState, config: RunnableConfig) -> ConceptPitchState:
    """
    Reply generation node that produces streaming conversational responses.
    
    Responsibilities:
    - Generate conversational reply based on context_packet system prompt
    - Support streaming output token by token
    - Add reply to conversation history
    - Update short_memory
    """
    logger.info(f"Generate reply node - Section: {state['current_section']}")
    
    # Create a new context packet for this turn
    context_packet = state.get('context_packet')
    logger.info(
        f"DEBUG_REPLY_NODE: Context Packet received: {context_packet}"
    )

    # Get LLM - no tools, no structured output for streaming
    llm = get_model()
    
    messages: list[BaseMessage] = []
    last_human_msg: HumanMessage | None = None

    # Section-specific system prompt from context packet
    if state.get("context_packet"):
        # Always use the default system prompt for the section
        messages.append(SystemMessage(content=state["context_packet"].system_prompt))

        # Add progress information based on section_states
        section_names = {
            "summary_confirmation": "Summary Confirmation",
            "pitch_generation": "Pitch Generation",
            "pitch_selection": "Pitch Selection",
            "refinement": "Refinement",
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
            f"- Total sections: 5\n"
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
    # Keep all messages from short_memory.
    messages.extend(state.get("short_memory", []))

    # Last human message (if any and agent hasn't replied yet)
    if state.get("messages"):
        _last_msg = state["messages"][-1]
        if isinstance(_last_msg, HumanMessage):
            messages.append(_last_msg)
            last_human_msg = _last_msg

    # Override JSON output requirement with a simple instruction
    if state["current_section"].value == "summary_confirmation":
        # For summary confirmation, use strict format enforcement
        messages.append(SystemMessage(
            content="CRITICAL: You MUST output the EXACT opening script from the system prompt. "
                    "Do NOT ask questions, do NOT request information, do NOT add greetings. "
                    "Output ONLY the exact format specified in the system prompt, replacing {{placeholders}} with actual data."
        ))
    else:
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

        logger.info("DEBUG_REPLY_NODE: Reply generated successfully")
        
    except Exception as e:
        logger.error(f"Failed to generate reply: {e}")
        default_reply = "Sorry, I encountered an error generating my response. Could you rephrase your question?"
        state["messages"].append(AIMessage(content=default_reply))
        state.setdefault("short_memory", []).append(AIMessage(content=default_reply))
    
    return state
