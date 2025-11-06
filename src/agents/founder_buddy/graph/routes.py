"""Routing logic for Founder Buddy Agent graph."""

from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage

from ..enums import RouterDirective
from ..models import FounderBuddyState


def route_after_memory_updater(state: FounderBuddyState) -> Literal["generate_business_plan", "router"]:
    """Route after memory_updater to determine if we should generate business plan."""
    # Check if we should generate business plan
    if state.get("should_generate_business_plan", False):
        return "generate_business_plan"
    return "router"


def route_decision(state: FounderBuddyState) -> Literal["generate_reply"] | None:
    """Determine the next node to go to based on current state."""
    # Check if there's a new user message even if finished
    msgs = state.get("messages", [])
    has_new_user_message = msgs and isinstance(msgs[-1], HumanMessage)
    
    # If finished but user sent a new message, we should still respond
    # (though typically business plan generation ends the conversation)
    if state.get("finished", False):
        # If there's a new user message, generate a polite response
        if has_new_user_message:
            # Allow one more reply to inform user that conversation is complete
            return "generate_reply"
        return None
    
    # Helper: determine if there's an unresponded user message
    def has_pending_user_input() -> bool:
        if not msgs:
            return False
        last_msg = msgs[-1]
        return isinstance(last_msg, HumanMessage)
    
    directive = state.get("router_directive")
    
    # STAY directive - continue on current section
    if directive == RouterDirective.STAY or (isinstance(directive, str) and directive.lower() == "stay"):
        if has_pending_user_input():
            return "generate_reply"
        
        if state.get("awaiting_user_input", False):
            return None
        
        if msgs and isinstance(msgs[-1], AIMessage):
            last_msg_content = msgs[-1].content.lower()
            if any(phrase in last_msg_content for phrase in ["perfect! now let's", "great! let's", "ready to dive"]):
                return "generate_reply"
        
        return None
    
    # NEXT/MODIFY directive - section transition
    elif directive == RouterDirective.NEXT or (isinstance(directive, str) and directive.startswith("modify:")):
        if has_pending_user_input():
            return "generate_reply"
        
        return "generate_reply"
    
    # Default case - halt
    return None

