from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph
from langgraph.pregel import Pregel

from agents.value_canvas.agent import graph as value_canvas_agent
from schema import AgentInfo

DEFAULT_AGENT = "value-canvas"

# Type alias to handle LangGraph's different agent patterns
# - @entrypoint functions return Pregel
# - StateGraph().compile() returns CompiledStateGraph
AgentGraph = CompiledStateGraph | Pregel


@dataclass
class Agent:
    description: str
    graph: AgentGraph


agents: dict[str, Agent] = {
    "value-canvas": Agent(
        description="A Value Canvas creation agent that guides users through building powerful marketing frameworks",
        graph=value_canvas_agent,
    ),
}


def get_agent(agent_id: str) -> AgentGraph:
    return agents[agent_id].graph


def get_all_agent_info() -> list[AgentInfo]:
    return [
        AgentInfo(key=agent_id, description=agent.description) for agent_id, agent in agents.items()
    ]
