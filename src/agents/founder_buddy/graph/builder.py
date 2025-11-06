"""Graph builder for Founder Buddy Agent."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph

from ..models import FounderBuddyState
from ..nodes import (
    generate_business_plan_node,
    generate_decision_node,
    generate_reply_node,
    initialize_node,
    memory_updater_node,
    router_node,
)
from .routes import route_after_memory_updater, route_decision


def build_founder_buddy_graph():
    """Build the Founder Buddy agent graph."""
    graph = StateGraph(FounderBuddyState)
    
    # Add nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("router", router_node)
    graph.add_node("generate_reply", generate_reply_node)
    graph.add_node("generate_decision", generate_decision_node)
    graph.add_node("memory_updater", memory_updater_node)
    graph.add_node("generate_business_plan", generate_business_plan_node)
    
    # Add edges
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "router")
    
    # Router can go to reply generation or end
    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "generate_reply": "generate_reply",
            None: END,
        },
    )
    
    # Flow: generate_reply -> generate_decision -> memory_updater -> (conditional) -> router or generate_business_plan
    graph.add_edge("generate_reply", "generate_decision")
    graph.add_edge("generate_decision", "memory_updater")
    
    # After memory_updater, check if we should generate business plan
    graph.add_conditional_edges(
        "memory_updater",
        route_after_memory_updater,
        {
            "generate_business_plan": "generate_business_plan",
            "router": "router",
        },
    )
    
    # Business plan generation ends the conversation
    graph.add_edge("generate_business_plan", END)
    
    # Compile with memory checkpointer
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)

