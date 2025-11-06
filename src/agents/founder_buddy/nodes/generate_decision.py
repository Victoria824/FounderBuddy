"""Generate decision node for Founder Buddy Agent."""

import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from core.llm import get_model

from ..enums import RouterDirective, SectionID
from ..models import ChatAgentDecision, ChatAgentOutput, FounderBuddyState

logger = logging.getLogger(__name__)


async def generate_decision_node(state: FounderBuddyState, config: RunnableConfig) -> FounderBuddyState:
    """
    Decision generation node that analyzes conversation and produces structured decisions.
    
    Responsibilities:
    - Analyze complete conversation including the just-generated reply
    - Generate structured decision data (router_directive, score, etc.)
    - Update state with agent_output containing complete ChatAgentOutput
    - Set router_directive and other state flags
    """
    context_packet = state.get("context_packet")
    if context_packet and hasattr(context_packet, 'section_id'):
        current_section = context_packet.section_id
        logger.info(f"Generate decision node - Section: {current_section}")
    else:
        current_section = state['current_section']
        logger.info(f"Generate decision node - Section: {current_section} (fallback)")
    
    # Get the last AI message (the reply we just generated)
    messages = state.get("messages", [])
    if not messages or not isinstance(messages[-1], AIMessage):
        logger.error("DECISION_NODE: No AI reply found to analyze")
        default_decision = ChatAgentDecision(
            router_directive="stay",
            user_satisfaction_feedback=None,
            is_satisfied=None,
            should_save_content=False
        )
        state["agent_output"] = ChatAgentOutput(
            reply="",
            **default_decision.model_dump()
        )
        state["router_directive"] = "stay"
        return state
    
    last_ai_reply = messages[-1].content
    
    # Get last user message
    user_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
    last_user_msg = user_messages[-1].content.lower() if user_messages else ""
    
    # Check if we're in the last section (invest_plan)
    is_last_section = current_section == SectionID.INVEST_PLAN if hasattr(current_section, 'value') else str(current_section) == "invest_plan"
    
    # Enhanced satisfaction detection
    satisfaction_words = ["yes", "good", "great", "perfect", "continue", "next", "satisfied", "looks good", "right", "proceed", "done", "finished", "complete"]
    is_satisfied = any(word in last_user_msg for word in satisfaction_words) if last_user_msg else None
    
    # Special handling for completion signals
    completion_words = ["satisfied", "done", "finished", "complete", "good", "right"]
    is_completion_signal = any(word in last_user_msg for word in completion_words) if last_user_msg else False
    
    # Determine router directive
    # If in last section and user is satisfied, we might be done
    # Otherwise, move to next section if satisfied
    if is_last_section and is_completion_signal:
        router_directive = RouterDirective.STAY  # Stay to allow business plan generation
    elif is_satisfied:
        router_directive = RouterDirective.NEXT
    else:
        router_directive = RouterDirective.STAY
    
    # Check if we should save content
    # Save when user seems satisfied or when presenting summary
    should_save_content = is_satisfied is True or "summary" in last_ai_reply.lower() or "总结" in last_ai_reply
    
    decision = ChatAgentDecision(
        router_directive=router_directive.value,
        user_satisfaction_feedback=last_user_msg if last_user_msg else None,
        is_satisfied=is_satisfied,
        should_save_content=should_save_content
    )
    
    # Create agent_output
    state["agent_output"] = ChatAgentOutput(
        reply=last_ai_reply,
        **decision.model_dump()
    )
    
    # Update router_directive
    state["router_directive"] = router_directive.value
    
    logger.info(f"Decision: directive={router_directive.value}, satisfied={is_satisfied}, last_section={is_last_section}")
    
    return state

