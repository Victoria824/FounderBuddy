"""Graph builder for Special Report Agent."""

from langgraph.constants import END, START
from langgraph.graph import StateGraph

from core.logging_config import get_logger
from ..models import SpecialReportState
from ..nodes import (
    initialize_node,
    router_node,
    generate_reply_node,
    generate_decision_node,
    memory_updater_node,
    implementation_node,
)
from .routes import route_decision

logger = get_logger(__name__)


def build_special_report_graph():
    """Build the Special Report agent graph with dual-node reply generation."""
    graph = StateGraph(SpecialReportState)
    
    # Add nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("router", router_node)
    graph.add_node("generate_reply", generate_reply_node)
    graph.add_node("generate_decision", generate_decision_node)
    graph.add_node("memory_updater", memory_updater_node)
    graph.add_node("implementation", implementation_node)
    
    # Add edges
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "router")
    
    # Router conditional edges
    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "generate_reply": "generate_reply",
            "implementation": "implementation",
            None: END,
        },
    )
    
    # Main processing flow: Reply → Decision → Memory → Router
    graph.add_edge("generate_reply", "generate_decision")
    graph.add_edge("generate_decision", "memory_updater")
    graph.add_edge("memory_updater", "router")
    
    # Implementation ends the graph
    graph.add_edge("implementation", END)
    
    return graph.compile()