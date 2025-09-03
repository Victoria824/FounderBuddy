"""Routing logic for Special Report Agent graph."""

from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage

from core.logging_config import get_logger
from ..models import SpecialReportState
from ..enums import RouterDirective

logger = get_logger(__name__)


def route_decision(state: SpecialReportState) -> Literal["implementation", "generate_reply"] | None:
    """Determine the next node to go to based on current state."""
    # All sections complete → Implementation
    if state.get("finished", False):
        return "implementation"
    
    # Helper: determine if there's an unresponded user message
    def has_pending_user_input() -> bool:
        msgs = state.get("messages", [])
        if not msgs:
            return False
        last_msg = msgs[-1]
        return isinstance(last_msg, HumanMessage)
    
    # Helper: check if this is the initial basic welcome message that needs to be replaced
    def needs_detailed_first_message() -> bool:
        msgs = state.get("messages", [])
        if not msgs:
            return True
        # Check if we only have the basic welcome message from initialization
        if len(msgs) == 1 and isinstance(msgs[0], AIMessage):
            content = msgs[0].content
            # Basic welcome message content check
            if "Welcome! I'm here to help you create your Special Report" in content and "Let's start" in content:
                return True
        return False
    
    directive = state.get("router_directive")
    
    # STAY directive - continue on current section
    if directive == RouterDirective.STAY or (isinstance(directive, str) and directive.lower() == "stay"):
        if has_pending_user_input():
            return "generate_reply"
        if state.get("awaiting_user_input", False):
            return None
        return None
    
    # NEXT/MODIFY directive - section transition  
    elif directive == RouterDirective.NEXT or (isinstance(directive, str) and directive.startswith("modify:")):
        # Special case: Initial message generation when starting conversation
        if needs_detailed_first_message():
            return "generate_reply"
            
        if has_pending_user_input():
            return "generate_reply"
        
        msgs = state.get("messages", [])
        if msgs and isinstance(msgs[-1], AIMessage):
            # Don't halt if we need to replace the basic welcome message
            if not needs_detailed_first_message():
                return None
        
        return "generate_reply"
    
    # Default case - halt to prevent infinite loops
    return None