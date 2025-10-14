"""Generate decision node for Concept Pitch Agent."""

import logging
import re

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from core.llm import LLMConfig, get_model

from ..enums import RouterDirective
from ..models import (
    ChatAgentDecision,
    ChatAgentOutput,
    ConceptPitchState,
)

logger = logging.getLogger(__name__)


async def generate_decision_node(state: ConceptPitchState, config: RunnableConfig) -> ConceptPitchState:
    """
    Decision generation node that analyzes conversation and produces structured decisions.
    
    Responsibilities:
    - Analyze complete conversation including the just-generated reply
    - Generate structured decision data (router_directive, score, section_update, etc.)
    - Update state with agent_output containing complete ChatAgentOutput
    - Set router_directive and other state flags
    """
    logger.info(f"Generate decision node - Section: {state['current_section']}")
    
    # Get the last AI message (the reply we just generated)
    messages = state.get("messages", [])
    if not messages or not isinstance(messages[-1], AIMessage):
        logger.error("DECISION_NODE: No AI reply found to analyze")
        # Set a default decision and continue
        default_decision = ChatAgentDecision(
            router_directive="stay",
            user_satisfaction_feedback=None,
            is_satisfied=None,
            should_save_content=False
        )
        # Create agent_output with empty reply
        state["agent_output"] = ChatAgentOutput(
            reply="",
            **default_decision.model_dump()
        )
        state["router_directive"] = "stay"
        return state
    
    last_ai_reply = messages[-1].content
    
    # Use the modular prompt template from prompts.py
    from ..prompts import format_conversation_for_decision, get_decision_prompt_template
    
    # DEBUG: Log conversation messages before formatting
    logger.info("=== DECISION_NODE_CONVERSATION_HISTORY_DEBUG ===")
    logger.info(f"Messages received: {len(messages)}")
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        content_preview = msg.content[:150] if hasattr(msg, 'content') else str(msg)[:150]
        logger.info(f"  [{i}] {msg_type}: {content_preview}...")
    
    # Format conversation history properly
    conversation_history = format_conversation_for_decision(messages)
    logger.info("=== FORMATTED_CONVERSATION_HISTORY ===")
    logger.info(f"Formatted conversation history:\n{conversation_history}")
    logger.info("=== END_CONVERSATION_HISTORY ===")
    
    # Get current section's complete prompt for context
    current_section_prompt = ""
    if state.get("context_packet"):
        current_section_prompt = state["context_packet"].system_prompt
        logger.info(f"DECISION_NODE: Got section prompt, length: {len(current_section_prompt)}")
    else:
        logger.warning("DECISION_NODE: No context_packet available")
    
    # Use the template with proper formatting, including section prompt
    decision_prompt = get_decision_prompt_template().format(
        current_section=state['current_section'].value,
        last_ai_reply=last_ai_reply,
        conversation_history=conversation_history,
        section_prompt=current_section_prompt
    )

    try:
        # All sections now use unified LLM decision generation
        logger.info("=== CALLING DECISION LLM WITH STRUCTURED OUTPUT ===")
        llm = get_model()
        structured_llm = llm.with_structured_output(ChatAgentDecision, method="function_calling")
        
        # Add token limits to prevent infinite generation
        if hasattr(structured_llm, 'bind'):
            structured_llm = structured_llm.bind(
                max_tokens=LLMConfig.DEFAULT_MAX_TOKENS,
                top_p=LLMConfig.DEFAULT_TOP_P
            )
        
        logger.info("DECISION_DEBUG: About to call LLM")
        # Use non-streaming config with tags to prevent decision data from appearing in user stream
        non_streaming_config = RunnableConfig(
            configurable={"stream": False},
            tags=["internal_decision", "do_not_stream"],
            callbacks=[]
        )
        decision = await structured_llm.ainvoke(
            decision_prompt,
            config=non_streaming_config
        )
        logger.info(f"DECISION_DEBUG: LLM returned decision type: {type(decision)}")
        logger.info(f"DECISION_DEBUG: Decision fields: {decision.__dict__ if hasattr(decision, '__dict__') else decision}")
        
        # Log the new should_save_content field
        if decision.should_save_content:
            logger.info("DECISION_DEBUG: should_save_content is True - content extraction needed in memory_updater")
        else:
            logger.info("DECISION_DEBUG: should_save_content is False - no content to save")
        
        logger.info(f"LLM decision analysis completed: {decision}")

        # DEBUG: Enhanced decision output logging
        logger.info("=== DECISION_OUTPUT_DEBUG ===")
        logger.info(f"🎯 Router directive: {decision.router_directive}")
        logger.info(f"📝 User satisfaction feedback: {decision.user_satisfaction_feedback}")
        logger.info(f"😊 Is satisfied: {decision.is_satisfied}")
        logger.info(f"💾 Should save content: {decision.should_save_content}")

        # Create complete ChatAgentOutput by combining reply + decision
        agent_output = ChatAgentOutput(
            reply=last_ai_reply,
            router_directive=decision.router_directive,
            user_satisfaction_feedback=decision.user_satisfaction_feedback,
            is_satisfied=decision.is_satisfied,
            should_save_content=decision.should_save_content
        )

        # Simplified validation - just track if we're waiting for feedback
        asking_for_feedback = ("satisfied" in agent_output.reply.lower() or 
                              "satisfaction" in agent_output.reply.lower() or 
                              "feedback" in agent_output.reply.lower())
        
        if asking_for_feedback and agent_output.should_save_content:
            state["awaiting_satisfaction_feedback"] = (agent_output.user_satisfaction_feedback is None and 
                                                       agent_output.is_satisfied is None)
            logger.info(f"State updated: awaiting_satisfaction_feedback = {state['awaiting_satisfaction_feedback']}")
        else:
            state["awaiting_satisfaction_feedback"] = False

        # Apply satisfaction-based safety rail
        if agent_output.is_satisfied is not None and not agent_output.is_satisfied:
            logger.info("User not satisfied detected from decision. Forcing 'stay' directive.")
            agent_output.router_directive = "stay"

        # Save to state
        state["temp_agent_output"] = agent_output  # For memory_updater
        state["agent_output"] = agent_output

        # Trust the LLM's router_directive decision based on full context
        state["router_directive"] = agent_output.router_directive

        # Handle section transition immediately if directive is "next"
        if agent_output.router_directive == "next":
            from ..prompts import get_next_section
            from ..enums import SectionID
            from ..tools import get_context
            from ..models import ContextPacket
            
            current_section_id = state["current_section"].value
            logger.info(f"[DECISION] Current section: {current_section_id}")
            
            # Use get_next_section instead of get_next_unfinished_section
            # because we know the current section is complete
            next_section = get_next_section(state["current_section"])
            logger.info(f"[DECISION] Next section: {next_section}")
            
            if next_section:
                logger.info(f"[DECISION] Transitioning from {current_section_id} to {next_section.value}")
                state["current_section"] = next_section
                # Clear short_memory for new section
                state["short_memory"] = []
                logger.info(f"[DECISION] Updated current_section to {next_section.value}")
                
                # Immediately update context_packet for the new section
                canvas_data = state.get("canvas_data")
                canvas_data_dict = canvas_data.model_dump() if canvas_data else {}
                
                context = await get_context.ainvoke({
                    "user_id": state.get("user_id", 1),
                    "thread_id": state.get("thread_id"),
                    "section_id": next_section.value,
                    "canvas_data": canvas_data_dict,
                })
                
                state["context_packet"] = ContextPacket(**context)
                logger.info(f"[DECISION] Updated context_packet for {next_section.value}")
                
                # Generate new reply for the new section immediately
                from ..nodes.generate_reply import generate_reply_node
                logger.info(f"[DECISION] Generating new reply for {next_section.value}")
                state = await generate_reply_node(state, config)
                logger.info(f"[DECISION] Generated new reply for {next_section.value}")
            else:
                logger.info("[DECISION] No next section found, conversation complete")
                state["finished"] = True

        # Log when satisfaction might influence routing for debugging
        if agent_output.is_satisfied is not None:
            logger.info(f"User satisfaction: {agent_output.is_satisfied}, "
                        f"LLM router decision: {agent_output.router_directive}")

        # Safety check: Log warning if satisfaction seems inconsistent with directive
        if agent_output.is_satisfied and agent_output.router_directive == "stay":
            logger.info("User satisfied but staying in section - likely collecting more data")
        elif agent_output.is_satisfied is False and agent_output.router_directive == "next":
            logger.warning("⚠️ Moving to next section despite user not satisfied - verify this is intended")

        # --- MVP Fallback: ensure reply contains clear question -----------------------
        need_question = (
            state["router_directive"] == RouterDirective.STAY
            and agent_output.is_satisfied is None
        )

        if need_question:
            # If reply has neither question mark nor clear instruction words, this is handled in reply node
            has_question = re.search(r"[?？]", agent_output.reply, re.IGNORECASE)
            has_instruction = any(word in agent_output.reply.lower() for word in [
                "please", "provide", "describe", "tell", "share", "what", "how", "when", "where", "why"
            ])
            
            if not has_question and not has_instruction:
                logger.info("DECISION_NODE: Reply lacks clear question/instruction - this should be handled in reply generation")

        # If we expect user input next, mark flag (MVP logic uses need_question)
        state["awaiting_user_input"] = need_question

        logger.info(f"DEBUG_DECISION_NODE: Decision generated successfully: {agent_output}")
        
    except Exception as e:
        logger.error(f"Failed to get structured decision from LLM: {e}")
        default_decision = ChatAgentDecision(
            router_directive="stay",
            user_satisfaction_feedback=None,
            is_satisfied=None,
            should_save_content=False
        )
        agent_output = ChatAgentOutput(
            reply=last_ai_reply,
            **default_decision.model_dump()
        )
        state["agent_output"] = agent_output
        state["router_directive"] = "stay"
        state["awaiting_user_input"] = True

    return state
