"""Mission Pitch Agent implementation using LangGraph StateGraph."""

import logging
import re
from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END, START
from langgraph.graph import StateGraph
# ToolNode no longer needed - tools called directly within nodes

from core.llm import get_model, LLMConfig

from .models import (
    ChatAgentOutput,
    ContextPacket,
    HiddenThemeData,
    PersonalOriginData,
    BusinessOriginData,
    MissionData,
    ThreeYearVisionData,
    BigVisionData,
    RouterDirective,
    SectionContent,
    MissionSectionID,
    SectionState,
    SectionStatus,
    TiptapDocument,
    MissionPitchData,
    MissionPitchState,
)
from .prompts import (
    get_next_unfinished_section,
    SECTION_TEMPLATES,
)
from .tools import (
    create_tiptap_content,
    export_mission_framework,
    extract_plain_text,
    get_all_sections_status,
    get_context,
    save_section,
    validate_field,
)

logger = logging.getLogger(__name__)


# Tools used by specific nodes
router_tools = [
    get_context,
]

memory_updater_tools = [
    save_section,
    get_all_sections_status,
    create_tiptap_content,
    extract_plain_text,
    validate_field,
]

implementation_tools = [
    export_mission_framework,
]

# Tools will be called directly within nodes (following social pitch pattern)


async def initialize_node(state: MissionPitchState, config: RunnableConfig) -> MissionPitchState:
    """
    Initialize node that ensures all required state fields are present.
    This is the first node in the graph to handle LangGraph Studio's incomplete state.
    """
    logger.info("Initialize node - Setting up default values")

    # Get correct IDs from config
    configurable = config.get("configurable", {})
    
    if "user_id" not in state or not state["user_id"]:
        # Try to get user_id from config first
        if "user_id" in configurable and configurable["user_id"]:
            state["user_id"] = configurable["user_id"]
            logger.info(f"Initialize node - Got user_id from config: {state['user_id']}")
        else:
            # Fallback for LangGraph Studio (no config provided)
            state["user_id"] = 1
            logger.warning(f"Initialize node - No user_id in config, using default: {state['user_id']}")
            logger.info("This is likely LangGraph Studio mode - using safe defaults")
    
    if "thread_id" not in state or not state["thread_id"]:
        # Try to get thread_id from config
        if "thread_id" in configurable and configurable["thread_id"]:
            state["thread_id"] = configurable["thread_id"]
            logger.info(f"Initialize node - Got thread_id from config: {state['thread_id']}")
        else:
            # Generate a new thread_id for LangGraph Studio
            import uuid
            state["thread_id"] = str(uuid.uuid4())
            logger.warning(f"Initialize node - No thread_id in config, generated: {state['thread_id']}")
            logger.info("This is likely LangGraph Studio mode - using generated thread_id")
    
    # Ensure all required fields have default values
    if "current_section" not in state:
        state["current_section"] = MissionSectionID.HIDDEN_THEME
        
    if "router_directive" not in state:
        state["router_directive"] = RouterDirective.NEXT
        
    if "finished" not in state:
        state["finished"] = False
        
    if "canvas_data" not in state:
        state["canvas_data"] = MissionPitchData()
        
    if "section_states" not in state:
        state["section_states"] = {}
        
    if "short_memory" not in state:
        state["short_memory"] = []
        
    if "awaiting_user_input" not in state:
        state["awaiting_user_input"] = False
        
    if "is_awaiting_rating" not in state:
        state["is_awaiting_rating"] = False
        
    if "error_count" not in state:
        state["error_count"] = 0
    
    logger.info(f"Initialize node - Final user_id: {state['user_id']}, thread_id: {state['thread_id']}")
    return state


async def router_node(state: MissionPitchState, config: RunnableConfig) -> MissionPitchState:
    """
    Router node that handles navigation and context loading.
    """
    logger.info("Router node - Processing navigation")
    
    # Check if there's a new user message - if so, reset awaiting_user_input
    msgs = state.get("messages", [])
    if msgs and len(msgs) >= 2:
        last_msg = msgs[-1]
        second_last_msg = msgs[-2]
        # If last message is human and second last is AI, user has responded
        if isinstance(last_msg, HumanMessage) and isinstance(second_last_msg, AIMessage):
            state["awaiting_user_input"] = False
            logger.info("Router node - User has responded, reset awaiting_user_input")
    
    directive = state.get("router_directive", RouterDirective.STAY)
    logger.info(f"Router node - Directive: {directive}")
    
    if directive == RouterDirective.STAY:
        # Stay on current section, no context reload needed
        logger.info("Router node - Staying on current section")
        return state
    
    elif directive == RouterDirective.NEXT:
        # Find next unfinished section
        logger.info("Router node - Looking for next unfinished section")
        next_section = get_next_unfinished_section(state.get("section_states", {}))
        
        if next_section:
            logger.info(f"Router node - Moving to next section: {next_section}")
            state["current_section"] = next_section
            
            # Get context for new section
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "thread_id": state["thread_id"],
                "section_id": next_section.value,
                "canvas_data": state["canvas_data"].model_dump() if state.get("canvas_data") else None,
            })
            
            state["context_packet"] = ContextPacket(**context)
            state["router_directive"] = RouterDirective.STAY
            
        else:
            logger.info("Router node - All sections completed, finishing")
            state["finished"] = True
    
    elif directive.startswith("modify:"):
        # Jump to specific section
        section_id = directive.split(":", 1)[1]
        logger.info(f"Router node - Jumping to section: {section_id}")
        
        try:
            new_section = MissionSectionID(section_id)
            state["current_section"] = new_section
            
            # Get context for new section
            context = await get_context.ainvoke({
                "user_id": state["user_id"],
                "thread_id": state["thread_id"],
                "section_id": section_id,
                "canvas_data": state["canvas_data"].model_dump() if state.get("canvas_data") else None,
            })
            
            state["context_packet"] = ContextPacket(**context)
            state["router_directive"] = RouterDirective.STAY
            
        except ValueError:
            logger.error(f"Router node - Invalid section ID: {section_id}")
            # Stay on current section if invalid
            state["router_directive"] = RouterDirective.STAY
    
    return state


async def chat_agent_node(state: MissionPitchState, config: RunnableConfig) -> MissionPitchState:
    """
    Chat agent node that handles section-specific conversations.
    This node has NO tools and only does conversation generation.
    """
    logger.info("Chat agent node - Starting conversation generation")
    
    # Get LLM with structured output
    llm = get_model()
    structured_llm = llm.with_structured_output(ChatAgentOutput, method="function_calling")
    
    # Build message context
    messages: list[BaseMessage] = []
    
    # Add system prompt from context packet
    if state.get("context_packet"):
        system_content = state["context_packet"].system_prompt
        messages.append(SystemMessage(content=system_content))
        logger.debug("Chat agent node - Added system prompt from context packet")
    
    # Add conversation history (short memory)
    if state.get("short_memory"):
        messages.extend(state["short_memory"])
        logger.debug(f"Chat agent node - Added {len(state['short_memory'])} messages from short memory")
    
    # Add the last human message from the main conversation
    if state.get("messages"):
        last_msg = state["messages"][-1]
        if isinstance(last_msg, HumanMessage):
            messages.append(last_msg)
            logger.debug("Chat agent node - Added last human message")
    
    # Get structured output from LLM
    try:
        logger.info("Chat agent node - Calling LLM for response generation")
        llm_output = await structured_llm.ainvoke(messages)
        logger.info("Chat agent node - Successfully got structured output from LLM")
        
        # Store the structured output for downstream processing
        state["agent_output"] = llm_output
        
        # Update router directive from LLM output
        state["router_directive"] = llm_output.router_directive
        
        # Add AI response to messages
        state["messages"].append(AIMessage(content=llm_output.reply))
        
        # Update short memory - keep last 10 messages
        all_messages = state.get("messages", [])
        state["short_memory"] = all_messages[-10:] if len(all_messages) > 10 else all_messages
        
        # Set waiting flags
        state["awaiting_user_input"] = True
        state["is_awaiting_rating"] = llm_output.is_requesting_rating
        
        logger.info(f"Chat agent node - Set router directive to: {llm_output.router_directive}")
        
    except Exception as e:
        logger.error(f"Chat agent node - Error during LLM call: {e}")
        state["error_count"] = state.get("error_count", 0) + 1
        state["last_error"] = str(e)
        
        # Create fallback response
        fallback_output = ChatAgentOutput(
            reply="I apologize, but I encountered an error. Please try again.",
            router_directive="stay",
        )
        state["agent_output"] = fallback_output
        state["messages"].append(AIMessage(content=fallback_output.reply))
    
    return state


async def memory_updater_node(state: MissionPitchState, config: RunnableConfig) -> MissionPitchState:
    """
    Memory updater node that persists section states and updates canvas data.
    """
    logger.info("Memory updater node - Processing section updates")
    
    agent_out = state.get("agent_output")
    if not agent_out or not agent_out.section_update:
        logger.info("Memory updater node - No section update to process")
        
        # Safety mechanism: if we're stuck in stay mode without progress, force next
        if state.get("router_directive") == "stay":
            consecutive_stays = state.get("consecutive_stays", 0) + 1
            state["consecutive_stays"] = consecutive_stays
            
            if consecutive_stays >= 3:  # After 3 stays without progress, force next
                logger.warning("Memory updater node - Forcing next due to no progress after multiple stays")
                state["router_directive"] = "next" 
                state["consecutive_stays"] = 0
        
        return state
    
    section_id = state["current_section"].value
    logger.info(f"Memory updater node - Processing update for section: {section_id}")
    
    try:
        # Determine section status based on score
        score = agent_out.score
        computed_status = SectionStatus.PENDING
        
        if score is not None:
            if score >= 3:
                computed_status = SectionStatus.DONE
                logger.info(f"Memory updater node - Section marked as DONE (score: {score})")
            else:
                computed_status = SectionStatus.IN_PROGRESS
                logger.info(f"Memory updater node - Section marked as IN_PROGRESS (score: {score})")
        elif agent_out.section_update:
            computed_status = SectionStatus.IN_PROGRESS
            logger.info("Memory updater node - Section marked as IN_PROGRESS (has content)")
        
        # Save to database
        await save_section.ainvoke({
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
            "section_id": section_id,
            "content": agent_out.section_update['content'],
            "score": score,
            "status": computed_status.value,
        })
        
        # Convert section_update content to TiptapDocument for validation
        tiptap_doc = TiptapDocument(**agent_out.section_update['content'])
        
        # Update local state
        state["section_states"][section_id] = SectionState(
            section_id=MissionSectionID(section_id),
            content=SectionContent(content=tiptap_doc),
            score=score,
            status=computed_status,
        )
        
        # Extract structured data and update canvas_data using LLM
        await extract_and_update_canvas_data(state, section_id, agent_out.section_update)
        
        # Reset consecutive stays counter since we made progress
        state["consecutive_stays"] = 0
        
        logger.info("Memory updater node - Successfully processed section update")
        
    except Exception as e:
        logger.error(f"Memory updater node - Error processing section update: {e}")
        state["error_count"] = state.get("error_count", 0) + 1
        state["last_error"] = str(e)
    
    return state


async def extract_and_update_canvas_data(
    state: MissionPitchState, 
    section_id: str, 
    section_update: dict
) -> None:
    """Extract structured data from section content and update canvas_data."""
    logger.info(f"Extracting structured data for section: {section_id}")
    
    # Get plain text from tiptap content
    plain_text = await extract_plain_text.ainvoke(section_update['content'])
    
    # Extract data based on section type
    llm = get_model()
    
    try:
        if section_id == MissionSectionID.HIDDEN_THEME.value:
            structured_llm = llm.with_structured_output(HiddenThemeData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract hidden theme data from this content: {plain_text}")
            ])
            
            # Update canvas_data with extracted fields
            canvas_data = state["canvas_data"]
            if extracted_data.theme_rant:
                canvas_data.theme_rant = extracted_data.theme_rant
            if extracted_data.theme_1sentence:
                canvas_data.theme_1sentence = extracted_data.theme_1sentence
            if extracted_data.theme_confidence:
                canvas_data.theme_confidence = extracted_data.theme_confidence
                
        elif section_id == MissionSectionID.PERSONAL_ORIGIN.value:
            structured_llm = llm.with_structured_output(PersonalOriginData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract personal origin data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.personal_origin_age:
                canvas_data.personal_origin_age = extracted_data.personal_origin_age
            if extracted_data.personal_origin_setting:
                canvas_data.personal_origin_setting = extracted_data.personal_origin_setting
            if extracted_data.personal_origin_key_moment:
                canvas_data.personal_origin_key_moment = extracted_data.personal_origin_key_moment
            if extracted_data.personal_origin_link_to_theme:
                canvas_data.personal_origin_link_to_theme = extracted_data.personal_origin_link_to_theme
                
        elif section_id == MissionSectionID.BUSINESS_ORIGIN.value:
            structured_llm = llm.with_structured_output(BusinessOriginData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract business origin data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.business_origin_pattern:
                canvas_data.business_origin_pattern = extracted_data.business_origin_pattern
            if extracted_data.business_origin_story:
                canvas_data.business_origin_story = extracted_data.business_origin_story
            if extracted_data.business_origin_evidence:
                canvas_data.business_origin_evidence = extracted_data.business_origin_evidence
                
        elif section_id == MissionSectionID.MISSION.value:
            structured_llm = llm.with_structured_output(MissionData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract mission data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.mission_statement:
                canvas_data.mission_statement = extracted_data.mission_statement
                
        elif section_id == MissionSectionID.THREE_YEAR_VISION.value:
            structured_llm = llm.with_structured_output(ThreeYearVisionData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract 3-year vision data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.three_year_milestone:
                canvas_data.three_year_milestone = extracted_data.three_year_milestone
            if extracted_data.three_year_metrics:
                canvas_data.three_year_metrics = extracted_data.three_year_metrics
                
        elif section_id == MissionSectionID.BIG_VISION.value:
            structured_llm = llm.with_structured_output(BigVisionData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract big vision data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.big_vision:
                canvas_data.big_vision = extracted_data.big_vision
            if extracted_data.big_vision_selfless_test_passed:
                canvas_data.big_vision_selfless_test_passed = extracted_data.big_vision_selfless_test_passed
                
        # Add similar blocks for other sections (values, impact, stakeholders, goals, metrics)
        
        logger.info(f"Successfully extracted and updated canvas data for section: {section_id}")
        
    except Exception as e:
        logger.warning(f"Failed to extract structured data for section {section_id}: {e}")
        # Continue without structured extraction - the content is still saved


async def implementation_node(state: MissionPitchState, config: RunnableConfig) -> MissionPitchState:
    """
    Implementation node that generates final mission framework exports.
    """
    logger.info("Implementation node - Generating mission framework")
    
    try:
        # Generate mission framework export
        framework_content = await export_mission_framework.ainvoke({
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
            "canvas_data": state["canvas_data"].model_dump(),
        })
        
        # Create implementation response
        response_content = f"Your complete Mission Framework has been generated:\\n\\n{framework_content}"
        
        state["messages"].append(AIMessage(content=response_content))
        state["finished"] = True
        
        logger.info("Implementation node - Successfully generated mission framework")
        
    except Exception as e:
        logger.error(f"Implementation node - Error generating framework: {e}")
        fallback_response = "I apologize, but there was an error generating your mission framework. Please try again."
        state["messages"].append(AIMessage(content=fallback_response))
        state["error_count"] = state.get("error_count", 0) + 1
        state["last_error"] = str(e)
    
    return state


def route_decision(state: MissionPitchState) -> Literal["chat_agent", "implementation", "halt"]:
    """
    Determine the next node to go to based on current state.
    Adapted from value-canvas sophisticated routing logic.
    """
    # 1. All sections complete → Implementation
    if state.get("finished", False):
        logger.info("Graph control - Mission completed, moving to implementation")
        return "implementation"
    
    # Also check if we have no unfinished sections (alternative completion check)
    next_section = get_next_unfinished_section(state.get("section_states", {}))
    if not next_section:
        logger.info("Graph control - No unfinished sections remaining, moving to implementation")
        return "implementation"
    
    # Helper: determine if there's an unresponded user message
    def has_pending_user_input() -> bool:
        msgs = state.get("messages", [])
        if not msgs:
            return False
        last_msg = msgs[-1]
        from langchain_core.messages import HumanMessage
        # If last message is from user, agent hasn't replied yet
        return isinstance(last_msg, HumanMessage)
    
    directive = state.get("router_directive")
    logger.info(f"Graph control - Router directive: {directive}, Has pending input: {has_pending_user_input()}")
    
    # 2. STAY directive - continue on current section
    if directive == RouterDirective.STAY or (isinstance(directive, str) and directive.lower() == "stay"):
        # If the user has replied since last AI message, forward to Chat Agent.
        if has_pending_user_input():
            logger.info("Graph control - User has new input, going to chat_agent")
            return "chat_agent"

        # If AI is still waiting for user response, halt and wait for next run (prevent repeated questions).
        if state.get("awaiting_user_input", False):
            logger.info("Graph control - AI awaiting user input, halting")
            return "halt"

        # Otherwise, halt directly (typically when just initialized).
        logger.info("Graph control - No pending input and not awaiting, halting")
        return "halt"
    
    # 3. NEXT/MODIFY directive - section transition  
    elif directive == RouterDirective.NEXT or (isinstance(directive, str) and directive.startswith("modify:")):
        # For NEXT/MODIFY directives, we need to let the router handle the transition
        # and then ask the first question for the new section
        
        # If there's a pending user input, it means user has acknowledged the transition
        # Let router process the directive and then go to chat_agent for new section
        if has_pending_user_input():
            logger.info("Graph control - Pending user input with NEXT/MODIFY directive, going to chat_agent")
            return "chat_agent"
        
        # If Chat Agent just set NEXT directive but user hasn't responded yet, halt and wait
        from langchain_core.messages import AIMessage
        msgs = state.get("messages", [])
        if msgs and isinstance(msgs[-1], AIMessage):
            logger.info("Graph control - AI just set NEXT/MODIFY, waiting for user response")
            return "halt"
        
        # Default case - go to chat_agent to ask first question of current section
        logger.info("Graph control - NEXT/MODIFY directive, going to chat_agent for new section")
        return "chat_agent"
    
    # 4. Default case - halt to prevent infinite loops
    logger.info("Graph control - Default case, halting to prevent loops")
    return "halt"


def should_continue(state: MissionPitchState) -> Literal["router"]:
    """
    Simple continuation function - always return to router for decision making.
    """
    logger.info("Graph control - Returning to router")
    return "router"


# Create the StateGraph
workflow = StateGraph(MissionPitchState)

# Add nodes
workflow.add_node("initialize", initialize_node)
workflow.add_node("router", router_node)
workflow.add_node("chat_agent", chat_agent_node)
workflow.add_node("memory_updater", memory_updater_node)
workflow.add_node("implementation", implementation_node)

# Add edges
workflow.add_edge(START, "initialize")
workflow.add_edge("initialize", "router")

# Router makes decisions about where to go
workflow.add_conditional_edges(
    "router",
    route_decision,
    {
        "chat_agent": "chat_agent",
        "implementation": "implementation",
        "halt": END,
        END: END,
    }
)

workflow.add_edge("chat_agent", "memory_updater")
workflow.add_conditional_edges(
    "memory_updater",
    should_continue,
    {
        "router": "router",
    }
)
workflow.add_edge("implementation", END)

# Compile the graph
graph = workflow.compile()


async def initialize_mission_pitch_state(user_id: int, thread_id: str | None = None) -> MissionPitchState:
    """
    Initialize a new Mission Pitch state with the given user and thread IDs.
    
    Args:
        user_id: User ID
        thread_id: Thread ID (optional, will be generated if not provided)
    
    Returns:
        Initialized Mission Pitch state
    """
    import uuid
    
    if not thread_id:
        thread_id = str(uuid.uuid4())
    
    initial_state = MissionPitchState(
        user_id=user_id,
        thread_id=thread_id,
        current_section=MissionSectionID.HIDDEN_THEME,
        router_directive=RouterDirective.NEXT,
        finished=False,
        canvas_data=MissionPitchData(),
        section_states={},
        short_memory=[],
        awaiting_user_input=False,
        is_awaiting_rating=False,
        error_count=0,
        messages=[],
    )
    
    # Get initial context
    context = await get_context.ainvoke({
        "user_id": user_id,
        "thread_id": thread_id,
        "section_id": MissionSectionID.HIDDEN_THEME.value,
        "canvas_data": {},
    })
    
    initial_state["context_packet"] = ContextPacket(**context)
    
    # Add welcome message
    welcome_msg = AIMessage(
        content="Welcome! I'm here to help you discover and articulate your Mission Pitch - "
        "a powerful framework that will clarify your purpose and vision. "
        "Let's start by exploring your Hidden Theme."
    )
    initial_state["messages"].append(welcome_msg)
    
    return initial_state




__all__ = ["graph", "initialize_mission_pitch_state"]