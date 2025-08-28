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

        # Add progress information based on section_states
        section_names = {
            "hidden_theme": "Hidden Theme",
            "personal_origin": "Personal Origin", 
            "business_origin": "Business Origin",
            "mission": "Mission",
            "three_year_vision": "3-Year Vision",
            "big_vision": "Big Vision",
            "implementation": "Implementation"
        }
        
        completed_sections = []
        for section_id, section_state in state.get("section_states", {}).items():
            if section_state.status == SectionStatus.DONE:
                section_name = section_names.get(section_id, section_id)
                completed_sections.append(section_name)
        
        current_section_name = section_names.get(state["current_section"].value, state["current_section"].value)
        
        progress_info = (
            f"\n\nSYSTEM STATUS:\n"
            f"- Total sections: 7\n"
            f"- Completed: {len(completed_sections)} sections"
        )
        if completed_sections:
            progress_info += f" ({', '.join(completed_sections)})"
        progress_info += f"\n- Currently working on: {current_section_name}\n"
        
        messages.append(SystemMessage(content=progress_info))
    
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
    Enhanced with sophisticated two-branch logic from Value Canvas.
    """
    logger.info("=== DATABASE_DEBUG: memory_updater_node() ENTRY ===")
    logger.info("DATABASE_DEBUG: Memory updater node processing agent output")
    
    agent_out = state.get("agent_output")
    logger.debug(f"DATABASE_DEBUG: Agent output exists: {bool(agent_out)}")
    if agent_out:
        logger.debug(f"DATABASE_DEBUG: Agent output - section_update: {bool(agent_out.section_update)}, score: {agent_out.score}, router_directive: {agent_out.router_directive}")

    # [DIAGNOSTIC] Log state before update
    logger.info(f"DATABASE_DEBUG: section_states BEFORE update: {state.get('section_states', {})}")
    logger.debug(f"DATABASE_DEBUG: Current section: {state.get('current_section')}")
    context_packet = state.get('context_packet')
    logger.debug(f"DATABASE_DEBUG: Context packet section: {context_packet.section_id if context_packet else None}")

    # Decide status based on score and directive
    def _status_from_output(score, directive):
        """Return status *string* to align with get_next_unfinished_section() logic."""
        if directive == RouterDirective.NEXT:
            return SectionStatus.DONE.value  # "done"
        if score is not None and score >= 3:
            return SectionStatus.DONE.value
        return SectionStatus.IN_PROGRESS.value

    # [SAVE_SECTION_DEBUG] Track decision path in memory_updater_node
    logger.info("SAVE_SECTION_DEBUG: memory_updater_node decision analysis:")
    logger.info(f"SAVE_SECTION_DEBUG: - agent_out exists: {bool(agent_out)}")
    if agent_out:
        logger.info(f"SAVE_SECTION_DEBUG: - agent_out.section_update exists: {bool(agent_out.section_update)}")
        logger.info(f"SAVE_SECTION_DEBUG: - agent_out.score: {agent_out.score}")
        logger.info(f"SAVE_SECTION_DEBUG: - agent_out.router_directive: {agent_out.router_directive}")
    else:
        logger.info("SAVE_SECTION_DEBUG: - No agent_out, will not call save_section")
    
    if agent_out and agent_out.section_update:
        # BRANCH 1: Process section_update (when LLM provides structured content)
        section_id = state["current_section"].value
        logger.info(f"SAVE_SECTION_DEBUG: ✅ ENTERING BRANCH 1: Processing section_update for section {section_id}")
        logger.info(f"DATABASE_DEBUG: Processing section_update for section {section_id}")
        logger.debug(f"DATABASE_DEBUG: Section update content type: {type(agent_out.section_update)}")
        
        # DEBUG: Log what content is being saved to which section
        logger.warning(f"CONTENT_DEBUG: About to save content to section {section_id}")
        if isinstance(agent_out.section_update, dict) and 'content' in agent_out.section_update:
            content_dict = agent_out.section_update['content']
            if isinstance(content_dict, dict) and 'content' in content_dict:
                # Try to extract first paragraph text for debugging
                try:
                    first_para = content_dict['content'][0]
                    if isinstance(first_para, dict) and 'content' in first_para:
                        first_text = first_para['content'][0].get('text', 'No text')
                        logger.warning(f"CONTENT_DEBUG: First paragraph starts with: {first_text[:100]}...")
                except Exception:
                    logger.warning("CONTENT_DEBUG: Could not extract content preview")
        
        # Save to database using save_section tool (make non-blocking for DB issues)
        logger.info("SAVE_SECTION_DEBUG: ✅ CALLING save_section with structured content")
        logger.debug("DATABASE_DEBUG: Calling save_section tool with structured content")
        
        # [CRITICAL DEBUG] Log the exact parameters being passed to save_section
        computed_status = _status_from_output(agent_out.score, agent_out.router_directive)
        logger.info("SAVE_SECTION_DEBUG: About to call save_section with:")
        logger.info(f"SAVE_SECTION_DEBUG: - user_id: {state['user_id']}")
        logger.info(f"SAVE_SECTION_DEBUG: - thread_id: {state['thread_id']}")
        logger.info(f"SAVE_SECTION_DEBUG: - section_id: {section_id}")
        logger.info(f"SAVE_SECTION_DEBUG: - score: {agent_out.score} (type: {type(agent_out.score)})")
        logger.info(f"SAVE_SECTION_DEBUG: - status: {computed_status} (type: {type(computed_status)})")
        logger.info(f"SAVE_SECTION_DEBUG: - router_directive was: {agent_out.router_directive} (type: {type(agent_out.router_directive)})")
        
        try:
            save_result = await save_section.ainvoke({
                "user_id": state["user_id"],
                "thread_id": state["thread_id"],
                "section_id": section_id,
                "content": agent_out.section_update['content'] if isinstance(agent_out.section_update, dict) else agent_out.section_update,
                "score": agent_out.score,
                "status": computed_status,
            })
            logger.debug(f"DATABASE_DEBUG: save_section returned: {bool(save_result)}")
        except Exception as e:
            logger.warning(f"DATABASE_DEBUG: save_section failed (expected if DB not configured): {e}")
            # Continue with local state management even if database save fails
        
        # Update local state (this is critical for proper functioning)
        logger.debug("DATABASE_DEBUG: Updating local section_states with new content")
        # Parse the section_update content properly
        if isinstance(agent_out.section_update, dict) and 'content' in agent_out.section_update:
            tiptap_doc = TiptapDocument.model_validate(agent_out.section_update['content'])
        else:
            logger.error(f"SAVE_SECTION_DEBUG: Invalid section_update structure: {type(agent_out.section_update)}")
            tiptap_doc = TiptapDocument(type="doc", content=[])
        
        state["section_states"][section_id] = SectionState(
            section_id=MissionSectionID(section_id),
            content=SectionContent(
                content=tiptap_doc,
                plain_text=None  # Will be filled later if needed
            ),
            score=agent_out.score,
            status=_status_from_output(agent_out.score, agent_out.router_directive),
        )
        logger.info(f"SAVE_SECTION_DEBUG: ✅ BRANCH 1 COMPLETED: Section {section_id} saved with structured content")

        # Extract structured data and update canvas_data using LLM
        try:
            await extract_and_update_canvas_data(state, section_id, agent_out.section_update)
        except Exception as e:
            logger.warning(f"DATABASE_DEBUG: Failed to extract structured data (non-critical): {e}")
        
        logger.info(f"DATABASE_DEBUG: ✅ Section {section_id} updated with structured content")
        
        # Reset consecutive stays counter since we made progress
        state["consecutive_stays"] = 0
        
    # Handle cases where agent provides score/status but no structured section_update  
    elif agent_out:
        # BRANCH 2: Process agent output without section_update (when LLM provides score but no content)
        logger.info("SAVE_SECTION_DEBUG: ✅ ENTERING BRANCH 2: Processing agent output without section_update")
        logger.info("DATABASE_DEBUG: Processing agent output without section_update (likely score/status only)")
        
        if state.get("context_packet"):
            score_section_id = state["context_packet"].section_id.value
            logger.debug(f"DATABASE_DEBUG: Processing score/status update for section {score_section_id}")

            # Only proceed if there's a score to save.
            if agent_out.score is None:
                logger.info(f"DATABASE_DEBUG: No score or section_update for {score_section_id}, skipping save.")
                return state

            # We have a score, so we MUST save. We need to find the content.
            content_to_save = None

            # 1. Try to find content in the current state for the section
            if score_section_id in state.get("section_states", {}) and state["section_states"][score_section_id].content:
                logger.info(f"SAVE_SECTION_DEBUG: Found content for section {score_section_id} in state.")
                # The content in state should now be the correct Tiptap document
                content_to_save = state["section_states"][score_section_id].content.content.model_dump()
            
            # 2. If not in state, recover from previous message history with improved logic
            if not content_to_save:
                logger.warning(f"SAVE_SECTION_DEBUG: Content for {score_section_id} not in state, recovering from history.")
                messages = state.get("messages", [])
                summary_text = None
                # Search backwards through the message history to find the last summary message.
                for msg in reversed(messages):
                    if isinstance(msg, AIMessage):
                        # A summary message typically contains these keywords.
                        content_lower = msg.content.lower()
                        if "summary" in content_lower and ("satisfied" in content_lower or "rate 0-5" in content_lower):
                            summary_text = msg.content
                            logger.info("SAVE_SECTION_DEBUG: Found candidate summary message in history.")
                            break
                
                if summary_text:
                    logger.info("SAVE_SECTION_DEBUG: Recovered summary text, converting to Tiptap format.")
                    try:
                        content_to_save = await create_tiptap_content.ainvoke({"text": summary_text})
                    except Exception as e:
                        logger.error(f"SAVE_SECTION_DEBUG: Failed to convert summary to Tiptap: {e}")
                else:
                    logger.error(f"SAVE_SECTION_DEBUG: Could not recover summary from message history for {score_section_id}.")

            # 3. If we found content (either from state or recovery), proceed with saving.
            if content_to_save:
                computed_status = _status_from_output(agent_out.score, agent_out.router_directive)
                logger.info(f"SAVE_SECTION_DEBUG: ✅ Calling save_section for {score_section_id} with score and content.")
                
                try:
                    await save_section.ainvoke({
                        "user_id": state["user_id"],
                        "thread_id": state["thread_id"],
                        "section_id": score_section_id,
                        "content": content_to_save,
                        "score": agent_out.score,
                        "status": computed_status,
                    })
                except Exception as e:
                    logger.warning(f"DATABASE_DEBUG: save_section failed (expected if DB not configured): {e}")

                # Update local state consistently, whether it existed before or not.
                # Convert content_to_save to TiptapDocument
                if isinstance(content_to_save, dict):
                    tiptap_doc = TiptapDocument.model_validate(content_to_save)
                else:
                    tiptap_doc = content_to_save
                
                state.setdefault("section_states", {})[score_section_id] = SectionState(
                    section_id=MissionSectionID(score_section_id),
                    content=SectionContent(
                        content=tiptap_doc,
                        plain_text=None
                    ),
                    score=agent_out.score,
                    status=computed_status,
                )
                logger.info(f"DATABASE_DEBUG: ✅ Updated/created section state for {score_section_id} with score {agent_out.score}")
            else:
                # 4. If content recovery failed, we must not call save_section with empty content.
                logger.error(f"DATABASE_DEBUG: ❌ CRITICAL: Aborting save for section {score_section_id} due to missing content.")

        else:
            logger.warning("DATABASE_DEBUG: ⚠️ Cannot update section state as context_packet is missing")

    else:
        # No agent output at all - safety mechanism for stuck states
        logger.info("SAVE_SECTION_DEBUG: ❌ No agent_out - applying safety mechanism")
        
        # Safety mechanism: if we're stuck in stay mode without progress, force next
        if state.get("router_directive") == "stay":
            consecutive_stays = state.get("consecutive_stays", 0) + 1
            state["consecutive_stays"] = consecutive_stays
            
            if consecutive_stays >= 3:  # After 3 stays without progress, force next
                logger.warning("Memory updater node - Forcing next due to no progress after multiple stays")
                state["router_directive"] = "next" 
                state["consecutive_stays"] = 0

    # [SAVE_SECTION_DEBUG] Final decision summary
    if not agent_out:
        logger.info("SAVE_SECTION_DEBUG: ❌ FINAL RESULT: No agent_out - save_section was NEVER called")
    elif agent_out.section_update:
        logger.info("SAVE_SECTION_DEBUG: ✅ FINAL RESULT: Had section_update - save_section was called in BRANCH 1")
    elif agent_out:
        logger.info("SAVE_SECTION_DEBUG: ✅ FINAL RESULT: Had agent_out but no section_update - save_section was called in BRANCH 2 (if conditions met)")
    else:
        logger.info("SAVE_SECTION_DEBUG: ❌ FINAL RESULT: Unknown state - save_section may not have been called")
    
    # [DIAGNOSTIC] Log state after update
    logger.info(f"DATABASE_DEBUG: section_states AFTER update: {state.get('section_states', {})}")
    logger.info("=== DATABASE_DEBUG: memory_updater_node() EXIT ===")

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