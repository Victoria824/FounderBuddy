"""Special Report Agent implementation using LangGraph StateGraph."""

import logging
import uuid

from langchain_core.messages import AIMessage

from core.logging_config import get_logger
from .models import SpecialReportState, ContextPacket
from .enums import SpecialReportSection, RouterDirective
from .tools import get_context
from .graph.builder import build_special_report_graph

logger = get_logger(__name__)

# Create the runnable graph
graph = build_special_report_graph()


async def initialize_special_report_state(user_id: int = None, thread_id: str = None) -> SpecialReportState:
    """Initialize a new Special Report state."""
    
    if not user_id:
        user_id = 1
        logger.info(f"Using default user_id: {user_id}")
    else:
        logger.info(f"Using provided user_id: {user_id}")

    if not thread_id:
        thread_id = str(uuid.uuid4())
        logger.info(f"Generated new thread_id: {thread_id}")
    else:
        try:
            uuid.UUID(thread_id)
        except ValueError:
            thread_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, thread_id))
            logger.info(f"Converted non-UUID thread_id to UUID: {thread_id}")
    
    initial_state = SpecialReportState(
        user_id=user_id,
        thread_id=thread_id,
        messages=[],
        current_section=SpecialReportSection.TOPIC_SELECTION,
        router_directive=RouterDirective.NEXT,  # Start by loading first section
    )
    
    # Get initial context
    context = await get_context.ainvoke({
        "user_id": user_id,
        "thread_id": thread_id,
        "section_id": SpecialReportSection.TOPIC_SELECTION.value,
    })
    
    initial_state["context_packet"] = ContextPacket(**context)
    
    # Add welcome message
    welcome_msg = AIMessage(
        content="Welcome! I'm here to help you create your Special Report. "
        "Let's start with topic selection."
    )
    initial_state["messages"].append(welcome_msg)
    
    return initial_state


__all__ = ["graph", "initialize_special_report_state"]