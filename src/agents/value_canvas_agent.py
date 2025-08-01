"""Value Canvas Agent implementation using LangGraph StateGraph."""

import json
import logging
from typing import Any, Dict, List, Literal, Optional, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from core.llm import get_model
from core.settings import settings

from agents.value_canvas_models import (
    ChatAgentOutput,
    ContextPacket,
    RouterDirective,
    SectionID,
    SectionStatus,
    ValueCanvasState,
)
from agents.value_canvas_prompts import (
    get_next_section,
    get_next_unfinished_section,
)
from agents.value_canvas_tools import (
    create_tiptap_content,
    export_checklist,
    extract_plain_text,
    get_all_sections_status,
    get_context,
    save_section,
    validate_field,
)

logger = logging.getLogger(__name__)

# Tool setup - Chat Agent has NO tools according to design doc

# Tools used by specific nodes
router_tools = [
    get_context,
]

memory_updater_tools = [
    save_section,
    get_all_sections_status,
    create_tiptap_content,
    extract_plain_text,
    validate_field,  # Moved from chat_agent per design doc
]

implementation_tools = [
    export_checklist,
]

# Create tool nodes
router_tool_node = ToolNode(router_tools)
memory_updater_tool_node = ToolNode(memory_updater_tools)
implementation_tool_node = ToolNode(implementation_tools)


async def router_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Router node that handles navigation and context loading.
    
    Responsibilities:
    - Process router directives (stay, next, modify:section_id)
    - Update current_section
    - Call get_context when changing sections
    - Check for completion and set finished flag
    """
    logger.info(f"Router node - Current section: {state['current_section']}, Directive: {state['router_directive']}")
    
    # Process router directive
    directive = state.get("router_directive", RouterDirective.STAY)
    
    if directive == RouterDirective.STAY:
        # Stay on current section, no context reload needed
        logger.info("Staying on current section")
        return state
    
    elif directive == RouterDirective.NEXT:
        # Find next unfinished section
        next_section = get_next_unfinished_section(state.get("section_states", {}))
        
        if next_section:
            logger.info(f"Moving to next section: {next_section}")
            state["current_section"] = next_section
            
            # Get context for new section
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "doc_id": state["doc_id"],
                "section_id": next_section.value,
                "canvas_data": state["canvas_data"].model_dump(),
            })
            
            state["context_packet"] = ContextPacket(**context)
        else:
            # All sections complete
            logger.info("All sections complete, setting finished flag")
            state["finished"] = True
    
    elif directive.startswith("modify:"):
        # Jump to specific section
        section_id = directive.split(":", 1)[1]
        try:
            new_section = SectionID(section_id)
            logger.info(f"Jumping to section: {new_section}")
            state["current_section"] = new_section
            
            # Get context for new section
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "doc_id": state["doc_id"],
                "section_id": new_section.value,
                "canvas_data": state["canvas_data"].model_dump(),
            })
            
            state["context_packet"] = ContextPacket(**context)
        except ValueError:
            logger.error(f"Invalid section ID: {section_id}")
            state["last_error"] = f"Invalid section ID: {section_id}"
            state["error_count"] += 1
    
    # Reset router directive
    state["router_directive"] = RouterDirective.STAY
    
    return state


async def chat_agent_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Chat agent node that handles section-specific conversations.
    
    Responsibilities:
    - Generate responses based on context_packet system prompt
    - Validate user input
    - Generate section content (Tiptap JSON)
    - Set score and router_directive
    - Output structured ChatAgentOutput
    """
    logger.info(f"Chat agent node - Section: {state['current_section']}")
    
    # Get LLM - no tools for chat agent per design doc
    llm = get_model()
    
    # Build messages
    messages: List[BaseMessage] = []
    
    # Add system prompt from context packet
    if state.get("context_packet"):
        messages.append(SystemMessage(content=state["context_packet"]["system_prompt"]))
    
    # Add conversation history (limited to recent messages)
    messages.extend(state.get("short_memory", [])[-10:])  # Keep last 10 messages
    
    # Add current user message
    if state.get("messages"):
        last_message = state["messages"][-1]
        if isinstance(last_message, HumanMessage):
            messages.append(last_message)
    
    # Generate response
    try:
        response = await llm.ainvoke(messages)
        
        # Parse structured output
        try:
            # Extract JSON from the response
            content = response.content
            if isinstance(content, str):
                # Clean up the content to extract JSON
                # Remove markdown code blocks if present
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]  # Remove ```json
                if content.startswith("```"):
                    content = content[3:]  # Remove ```
                if content.endswith("```"):
                    content = content[:-3]  # Remove trailing ```
                
                # Find JSON object
                start = content.find("{")
                end = content.rfind("}") + 1
                
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    output_data = json.loads(json_str)
                    
                    # Ensure all required fields exist
                    if "reply" not in output_data:
                        output_data["reply"] = "I'm processing your request..."
                    if "router_directive" not in output_data:
                        output_data["router_directive"] = "stay"
                    if "score" not in output_data:
                        output_data["score"] = None
                    if "section_update" not in output_data:
                        output_data["section_update"] = None
                    
                    # Create ChatAgentOutput
                    agent_output = ChatAgentOutput(**output_data)
                    state["agent_output"] = agent_output
                    
                    # Update state based on output
                    state["router_directive"] = agent_output.router_directive
                    
                    # Note: save_section will be handled by memory_updater node according to design doc
                    
                    # Add AI response to messages
                    state["messages"].append(AIMessage(content=agent_output.reply))
                    
                    # Update short memory
                    state["short_memory"] = messages[-8:] + [
                        last_message if isinstance(last_message, HumanMessage) else HumanMessage(content=""),
                        AIMessage(content=agent_output.reply)
                    ]
                else:
                    raise ValueError("No JSON object found in response")
            else:
                raise ValueError("Response content is not a string")
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse structured output: {e}\nResponse: {content}")
            # Create a default response
            default_output = ChatAgentOutput(
                reply="I apologize, but I had trouble formatting my response. Let me try again. Could you please repeat your last message?",
                router_directive="stay",
                score=None,
                section_update=None
            )
            state["agent_output"] = default_output
            state["router_directive"] = "stay"
            state["messages"].append(AIMessage(content=default_output.reply))
            state["short_memory"] = messages[-8:] + [AIMessage(content=default_output.reply)]
            
    except Exception as e:
        logger.error(f"Error in chat agent: {e}")
        state["last_error"] = str(e)
        state["error_count"] += 1
        
        # Add error message
        error_msg = AIMessage(content=f"I encountered an error: {str(e)}. Let me try again.")
        state["messages"].append(error_msg)
    
    return state


async def memory_updater_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Memory updater node that persists section states and updates canvas data.
    
    Responsibilities:
    - Update section_states with latest content
    - Update canvas_data with extracted values
    - Manage short_memory size
    - Handle database writes
    """
    logger.info("Memory updater node")
    
    # Update section state if we have agent output with section update
    if state.get("agent_output") and state["agent_output"].section_update:
        section_id = state["current_section"].value
        
        # Save to database using save_section tool
        await save_section.ainvoke({
            "user_id": state["user_id"],
            "doc_id": state["doc_id"],
            "section_id": section_id,
            "content": state["agent_output"].section_update.model_dump(),
            "score": state["agent_output"].score,
            "status": SectionStatus.DONE if state["agent_output"].score and state["agent_output"].score >= 3 else SectionStatus.IN_PROGRESS,
        })
        
        # Update local state
        state["section_states"][section_id] = {
            "section_id": section_id,
            "content": state["agent_output"].section_update.model_dump(),
            "score": state["agent_output"].score,
            "status": SectionStatus.DONE if state["agent_output"].score and state["agent_output"].score >= 3 else SectionStatus.IN_PROGRESS,
        }
        
        # Extract plain text and update canvas data
        # This would parse the content and update specific fields in canvas_data
        # For example, if section is ICP, extract icp_nickname, etc.
        
    # Trim short memory if too long (keep last 20 messages)
    if len(state.get("short_memory", [])) > 20:
        state["short_memory"] = state["short_memory"][-20:]
    
    return state


async def implementation_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Implementation node that generates the final checklist/PDF.
    
    Only runs when all sections are complete.
    """
    logger.info("Implementation node - Generating final deliverables")
    
    try:
        # Export checklist
        result = await export_checklist.ainvoke({
            "user_id": state["user_id"],
            "doc_id": state["doc_id"],
            "canvas_data": state["canvas_data"].model_dump(),
        })
        
        # Add completion message
        completion_msg = AIMessage(
            content=f"Congratulations! Your Value Canvas is complete. "
            f"You can download your implementation checklist here: {result['url']}"
        )
        state["messages"].append(completion_msg)
        
    except Exception as e:
        logger.error(f"Error generating implementation: {e}")
        error_msg = AIMessage(
            content=f"I encountered an error generating your checklist: {str(e)}. "
            "Your Value Canvas data has been saved and you can try exporting again later."
        )
        state["messages"].append(error_msg)
    
    return state



def should_go_to_implementation(state: ValueCanvasState) -> Literal["implementation", "chat_agent"]:
    """Determine if we should go to implementation node."""
    if state.get("finished", False):
        return "implementation"
    return "chat_agent"


# Build the graph
def build_value_canvas_graph():
    """Build the Value Canvas agent graph."""
    graph = StateGraph(ValueCanvasState)
    
    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("chat_agent", chat_agent_node)
    graph.add_node("memory_updater", memory_updater_node)
    graph.add_node("implementation", implementation_node)
    
    # Add edges
    graph.add_edge(START, "router")
    
    # Router can go to chat agent or implementation
    graph.add_conditional_edges(
        "router",
        should_go_to_implementation,
        {
            "chat_agent": "chat_agent",
            "implementation": "implementation",
        }
    )
    
    # Chat agent has no tools, goes directly to memory_updater
    graph.add_edge("chat_agent", "memory_updater")
    
    # Memory updater goes back to router
    graph.add_edge("memory_updater", "router")
    
    # Implementation ends the graph
    graph.add_edge("implementation", END)
    
    return graph.compile()


# Create the runnable graph
graph = build_value_canvas_graph()


# Initialize function for new conversations
async def initialize_value_canvas_state(user_id: str, doc_id: str) -> ValueCanvasState:
    """Initialize a new Value Canvas state."""
    initial_state = ValueCanvasState(
        user_id=user_id,
        doc_id=doc_id,
        messages=[],
        current_section=SectionID.INTERVIEW,
        router_directive=RouterDirective.NEXT,  # Start by loading first section
    )
    
    # Get initial context
    context = await get_context.ainvoke({
        "user_id": user_id,
        "doc_id": doc_id,
        "section_id": SectionID.INTERVIEW.value,
        "canvas_data": {},
    })
    
    initial_state["context_packet"] = ContextPacket(**context)
    
    # Add welcome message
    welcome_msg = AIMessage(
        content="Welcome! I'm here to help you create your Value Canvas - "
        "a powerful framework that will transform your marketing messaging. "
        "Let's start by getting to know you and your business better."
    )
    initial_state["messages"].append(welcome_msg)
    
    return initial_state


__all__ = ["graph", "initialize_value_canvas_state"]