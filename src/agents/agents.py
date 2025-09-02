from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph
from langgraph.pregel import Pregel

from .value_canvas.agent import graph as value_canvas_agent
from .social_pitch.agent import graph as social_pitch_agent
from .mission_pitch.agent import graph as mission_pitch_agent
from .signature_pitch.agent import graph as signature_pitch_agent
from .special_report.agent import graph as special_report_agent
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
    "social-pitch": Agent(
        description="A Social Pitch creation agent that guides users through building compelling 6-component business introductions",
        graph=social_pitch_agent,
    ),
    "mission-pitch": Agent(
        description="A Mission Pitch creation agent that guides organizations through defining their purpose, vision, and strategic direction",
        graph=mission_pitch_agent,
    ),
    "signature-pitch": Agent(
        description="A Signature Pitch creation agent that helps entrepreneurs craft magnetic 90-second pitches rooted in psychology and storytelling",
        graph=signature_pitch_agent,
    ),
    "special-report": Agent(
        description="A Special Report creation agent that guides users through building comprehensive business reports and analysis",
        graph=special_report_agent,
    ),
}


def get_agent(agent_id: str) -> AgentGraph:
    return agents[agent_id].graph


def get_all_agent_info() -> list[AgentInfo]:
    return [
        AgentInfo(key=agent_id, description=agent.description) for agent_id, agent in agents.items()
    ]
