"""Generate decision node for Value Canvas Agent."""

import logging
import re

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from core.llm import get_model, LLMConfig
from ..models import (
    ValueCanvasState,
    ChatAgentDecision,
    ChatAgentOutput,
)
from ..enums import RouterDirective

logger = logging.getLogger(__name__)


async def generate_decision_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
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
            section_update=None
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
    from ..prompts import get_decision_prompt_template, format_conversation_for_decision
    
    # Format conversation history properly
    conversation_history = format_conversation_for_decision(messages)
    
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
        
        # Validate section_update structure before proceeding
        if decision.section_update is not None:
            logger.info(f"DECISION_DEBUG: section_update type: {type(decision.section_update)}")
            logger.info(f"DECISION_DEBUG: section_update keys: {decision.section_update.keys() if isinstance(decision.section_update, dict) else 'Not a dict'}")
            if isinstance(decision.section_update, dict) and 'content' in decision.section_update:
                logger.info("DECISION_DEBUG: section_update has 'content' key")
            else:
                logger.warning("DECISION_DEBUG: section_update missing 'content' key! Fixing structure...")
                # Fix malformed section_update
                if not isinstance(decision.section_update, dict):
                    decision.section_update = {"content": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Auto-generated content"}]}]}}
                elif 'content' not in decision.section_update:
                    decision.section_update['content'] = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Auto-generated content"}]}]}
                logger.info("DECISION_DEBUG: Fixed section_update structure")
        
        logger.info(f"LLM decision analysis completed: {decision}")

        # DEBUG: Log the decision output
        logger.info("=== DECISION_OUTPUT_DEBUG ===")
        logger.info(f"Router directive: {decision.router_directive}")
        logger.info(f"User satisfaction feedback: {decision.user_satisfaction_feedback}")
        logger.info(f"Is satisfied: {decision.is_satisfied}")
        logger.info(f"Section update provided: {bool(decision.section_update)}")
        if decision.section_update:
            logger.info(f"Section update content keys: {list(decision.section_update.keys())}")

        # Create complete ChatAgentOutput by combining reply + decision
        agent_output = ChatAgentOutput(
            reply=last_ai_reply,
            router_directive=decision.router_directive,
            user_satisfaction_feedback=decision.user_satisfaction_feedback,
            is_satisfied=decision.is_satisfied,
            section_update=decision.section_update
        )

        # Enhanced business logic validation
        # Check if we're asking for satisfaction feedback without providing section update
        asking_for_feedback = ("satisfied" in agent_output.reply.lower() or "satisfaction" in agent_output.reply.lower() or "feedback" in agent_output.reply.lower())
        if asking_for_feedback:
            # CRITICAL VALIDATION: If asking for satisfaction feedback, must have section_update
            if not agent_output.section_update:
                logger.warning("⚠️ Model requested rating but provided no section_update - attempting auto-generation")
                
                # Check if reply contains summary patterns that should trigger section_update
                summary_patterns = [
                    "here's what i gathered", "here's what i've gathered",
                    "here's your summary", "here's the summary",
                    "refined version", "•", "bullet",
                    "name:", "company:", "industry:"
                ]
                
                reply_lower = last_ai_reply.lower()
                has_summary = any(pattern in reply_lower for pattern in summary_patterns)
                
                if has_summary:
                    logger.info("📝 Summary patterns detected, auto-generating section_update")
                    # Use the unified section data extraction
                    from ..prompts import extract_section_data
                    auto_section_update = extract_section_data(conversation_history, state['current_section'].value)
                    agent_output.section_update = auto_section_update
                    logger.info("✅ Successfully auto-generated section_update")
                else:
                    logger.error("CRITICAL ERROR: Model requested rating but no summary content found!")
                    logger.error("This violates the core system prompt rule and will cause data loss.")
                    
                    # Force correction to prevent infinite loops
                    agent_output = ChatAgentOutput(
                        reply=last_ai_reply,
                        router_directive="stay",
                        user_satisfaction_feedback=None,
                        is_satisfied=None,
                        section_update=None
                    )
                    logger.info("🔧 FORCED CORRECTION: Reset to continue collecting information.")
            
            state["awaiting_satisfaction_feedback"] = (agent_output.user_satisfaction_feedback is None and agent_output.is_satisfied is None)
            logger.info(f"State updated: awaiting_satisfaction_feedback set to {state['awaiting_satisfaction_feedback']}")
        else:
            state["awaiting_satisfaction_feedback"] = False

        # Apply satisfaction-based safety rail
        if agent_output.is_satisfied is not None and not agent_output.is_satisfied:
            logger.info(f"User not satisfied detected from decision. Forcing 'stay' directive.")
            agent_output.router_directive = "stay"

        # Save to state
        state["temp_agent_output"] = agent_output  # For memory_updater
        state["agent_output"] = agent_output

        # Determine router directive based on satisfaction, per design doc
        if agent_output.is_satisfied is not None:
            if agent_output.is_satisfied:
                calculated_directive = RouterDirective.NEXT
            else:
                calculated_directive = RouterDirective.STAY
                
            state["router_directive"] = calculated_directive
        else:
            # Fallback to value supplied by model (may be stay/next/modify)
            state["router_directive"] = agent_output.router_directive

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
            section_update=None,
        )
        agent_output = ChatAgentOutput(
            reply=last_ai_reply,
            **default_decision.model_dump()
        )
        state["agent_output"] = agent_output
        state["router_directive"] = "stay"
        state["awaiting_user_input"] = True

    return state