"""Memory updater node for Special Report Agent."""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from core.llm import get_model
from core.logging_config import get_logger
from ..models import (
    SpecialReportState,
    SpecialReportSection,
    SectionState,
    SectionContent,
    SectionStatus,
    TiptapDocument,
    RouterDirective,
)
from ..tools import (
    save_section,
    create_tiptap_content,
    extract_plain_text,
)

logger = get_logger(__name__)


async def memory_updater_node(state: SpecialReportState, config: RunnableConfig) -> SpecialReportState:
    """
    Memory updater node that persists section states and updates canvas data.
    Enhanced with satisfaction-based state management pattern from Value Canvas.
    """
    logger.info("=== DATABASE_DEBUG: memory_updater_node() ENTRY ===")
    logger.info("DATABASE_DEBUG: Memory updater node processing agent output")
    
    agent_out = state.get("agent_output")
    logger.debug(f"DATABASE_DEBUG: Agent output exists: {bool(agent_out)}")
    if agent_out:
        logger.debug(f"DATABASE_DEBUG: Agent output - section_update: {bool(agent_out.section_update)}, is_satisfied: {agent_out.is_satisfied}, router_directive: {agent_out.router_directive}")

    # [DIAGNOSTIC] Log state before update
    logger.info(f"DATABASE_DEBUG: section_states BEFORE update: {state.get('section_states', {})}")
    logger.debug(f"DATABASE_DEBUG: Current section: {state.get('current_section')}")
    context_packet = state.get('context_packet')
    logger.debug(f"DATABASE_DEBUG: Context packet section: {context_packet.section_id if context_packet else None}")

    # Decide status based on satisfaction and directive
    def _status_from_output(is_satisfied, directive):
        """Return status *string* to align with get_next_unfinished_section() logic."""
        if directive == RouterDirective.NEXT:
            return SectionStatus.DONE.value  # "done"
        if is_satisfied is not None and is_satisfied:
            return SectionStatus.DONE.value
        return SectionStatus.IN_PROGRESS.value

    # [SAVE_SECTION_DEBUG] Track decision path in memory_updater_node
    logger.info("SAVE_SECTION_DEBUG: memory_updater_node decision analysis:")
    logger.info(f"SAVE_SECTION_DEBUG: - agent_out exists: {bool(agent_out)}")
    if agent_out:
        logger.info(f"SAVE_SECTION_DEBUG: - agent_out.section_update exists: {bool(agent_out.section_update)}")
        logger.info(f"SAVE_SECTION_DEBUG: - agent_out.is_satisfied: {agent_out.is_satisfied}")
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
        computed_status = _status_from_output(agent_out.is_satisfied, agent_out.router_directive)
        logger.info("SAVE_SECTION_DEBUG: About to call save_section with:")
        logger.info(f"SAVE_SECTION_DEBUG: - user_id: {state['user_id']}")
        logger.info(f"SAVE_SECTION_DEBUG: - thread_id: {state['thread_id']}")
        logger.info(f"SAVE_SECTION_DEBUG: - section_id: {section_id}")
        logger.info(f"SAVE_SECTION_DEBUG: - is_satisfied: {agent_out.is_satisfied} (type: {type(agent_out.is_satisfied)})")
        logger.info(f"SAVE_SECTION_DEBUG: - status: {computed_status} (type: {type(computed_status)})")
        logger.info(f"SAVE_SECTION_DEBUG: - router_directive was: {agent_out.router_directive} (type: {type(agent_out.router_directive)})")
        
        try:
            save_result = await save_section.ainvoke({
                "user_id": state["user_id"],
                "thread_id": state["thread_id"],
                "section_id": section_id,
                "content": agent_out.section_update['content'] if isinstance(agent_out.section_update, dict) else agent_out.section_update,
                "satisfaction_feedback": agent_out.user_satisfaction_feedback,
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
            section_id=SpecialReportSection(section_id),
            content=SectionContent(
                content=tiptap_doc,
                plain_text=None  # Will be filled later if needed
            ),
            satisfaction_feedback=agent_out.user_satisfaction_feedback,
            status=_status_from_output(agent_out.is_satisfied, agent_out.router_directive),
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
        
    # Handle cases where agent provides satisfaction feedback but no structured section_update  
    elif agent_out:
        # BRANCH 2: Process agent output without section_update (when LLM provides satisfaction but no content)
        logger.info("SAVE_SECTION_DEBUG: ✅ ENTERING BRANCH 2: Processing agent output without section_update")
        logger.info("DATABASE_DEBUG: Processing agent output without section_update (likely satisfaction only)")
        
        if state.get("context_packet"):
            score_section_id = state["context_packet"].section_id.value
            logger.debug(f"DATABASE_DEBUG: Processing satisfaction update for section {score_section_id}")

            # Only proceed if there's satisfaction feedback to save OR router directive is NEXT.
            if agent_out.is_satisfied is None and agent_out.router_directive != RouterDirective.NEXT:
                logger.debug(f"No satisfaction feedback for {score_section_id}, skipping save")
                return state

            # We have satisfaction feedback, so we MUST save. We need to find the content.
            content_to_save = None

            # 1. Try to find content in the current state for the section
            if score_section_id in state.get("section_states", {}) and state["section_states"][score_section_id].content:
                logger.debug(f"Found existing content for {score_section_id}")
                # The content in state should now be the correct Tiptap document
                content_to_save = state["section_states"][score_section_id].content.content.model_dump()
            
            # 2. If not in state, recover from previous message history with improved logic
            if not content_to_save:
                logger.debug(f"Recovering content for {score_section_id} from history")
                messages = state.get("messages", [])
                summary_text = None
                # Search backwards through the message history to find the last summary message.
                for msg in reversed(messages):
                    if isinstance(msg, AIMessage):
                        # A summary message typically contains these keywords.
                        content_lower = msg.content.lower()
                        if "summary" in content_lower and ("satisfied" in content_lower or "rate 0-5" in content_lower):
                            summary_text = msg.content
                            logger.debug("Found summary message in history")
                            break
                
                if summary_text:
                    logger.debug("Converting recovered text to Tiptap format")
                    content_to_save = await create_tiptap_content.ainvoke({"text": summary_text})
                else:
                    logger.error(f"Could not recover summary for {score_section_id}")

            # 3. If we found content (either from state or recovery), proceed with saving.
            if content_to_save:
                computed_status = _status_from_output(agent_out.is_satisfied, agent_out.router_directive)
                
                await save_section.ainvoke({
                    "user_id": state["user_id"],
                    "thread_id": state["thread_id"],
                    "section_id": score_section_id,
                    "content": content_to_save,
                    "satisfaction_feedback": agent_out.user_satisfaction_feedback,
                    "status": computed_status,
                })

                # Update local state consistently, whether it existed before or not.
                # Convert content_to_save to TiptapDocument
                if isinstance(content_to_save, dict):
                    tiptap_doc = TiptapDocument.model_validate(content_to_save)
                else:
                    tiptap_doc = content_to_save
                
                state.setdefault("section_states", {})[score_section_id] = SectionState(
                    section_id=SpecialReportSection(score_section_id),
                    content=SectionContent(
                        content=tiptap_doc,
                        plain_text=None
                    ),
                    satisfaction_feedback=agent_out.user_satisfaction_feedback,
                    status=computed_status,
                )
            else:
                # 4. If content recovery failed, check if we should still update status
                if agent_out.router_directive == RouterDirective.NEXT:
                    # User wants to proceed, mark section as DONE even without content
                    logger.debug(f"Marking {score_section_id} as DONE (router_directive=NEXT)")
                    
                    computed_status = _status_from_output(agent_out.is_satisfied, agent_out.router_directive)
                    
                    # Create minimal section state with DONE status
                    state.setdefault("section_states", {})[score_section_id] = SectionState(
                        section_id=SpecialReportSection(score_section_id),
                        content=SectionContent(
                            content=TiptapDocument(type="doc", content=[]),  # Empty content
                            plain_text=None
                        ),
                        satisfaction_feedback=agent_out.user_satisfaction_feedback,
                        status=computed_status,  # Will be DONE because of router_directive == NEXT
                    )
                else:
                    # Not moving next and no content, cannot update
                    logger.error(f"Cannot save {score_section_id}: missing content")

        else:
            logger.warning("Cannot update section state: missing context")

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
    state: SpecialReportState, 
    section_id: str, 
    section_update: dict
) -> None:
    """Extract structured data from section content and update canvas_data."""
    logger.info(f"Extracting structured data for section: {section_id}")
    
    # Get plain text from tiptap content
    plain_text = await extract_plain_text.ainvoke({"tiptap_json": section_update['content']})
    
    # Extract data based on section type
    llm = get_model()
    
    try:
        if section_id == SpecialReportSection.TOPIC_SELECTION.value:
            # Import section-specific data models locally to avoid circular imports
            from ..sections.topic_selection.models import TopicSelectionData
            structured_llm = llm.with_structured_output(TopicSelectionData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract topic selection data from this content: {plain_text}")
            ])
            
            # Update canvas_data with extracted fields
            canvas_data = state["canvas_data"]
            if extracted_data.selected_topic:
                canvas_data.topic_data.selected_topic = extracted_data.selected_topic
            if extracted_data.subtitle:
                canvas_data.topic_data.subtitle = extracted_data.subtitle
                
        elif section_id == SpecialReportSection.CONTENT_DEVELOPMENT.value:
            from ..sections.content_development.models import ContentDevelopmentData
            structured_llm = llm.with_structured_output(ContentDevelopmentData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract content development data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.key_stories:
                canvas_data.content_data.personal_stories = extracted_data.key_stories[:5]
            if extracted_data.main_framework:
                canvas_data.content_data.visual_frameworks = [extracted_data.main_framework]
            if extracted_data.proof_elements:
                canvas_data.content_data.proof_points = extracted_data.proof_elements[:10]
            if extracted_data.action_steps:
                canvas_data.content_data.immediate_actions = extracted_data.action_steps[:10]
                
        elif section_id == SpecialReportSection.REPORT_STRUCTURE.value:
            from ..sections.report_structure.models import ReportStructureData
            structured_llm = llm.with_structured_output(ReportStructureData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract report structure data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.attract_content:
                canvas_data.report_structure.attract_content = extracted_data.attract_content
            if extracted_data.disrupt_content:
                canvas_data.report_structure.disrupt_content = extracted_data.disrupt_content
            if extracted_data.inform_content:
                canvas_data.report_structure.inform_content = extracted_data.inform_content
            if extracted_data.recommend_content:
                canvas_data.report_structure.recommend_content = extracted_data.recommend_content
            if extracted_data.overcome_content:
                canvas_data.report_structure.overcome_content = extracted_data.overcome_content
            if extracted_data.reinforce_content:
                canvas_data.report_structure.reinforce_content = extracted_data.reinforce_content
            if extracted_data.invite_content:
                canvas_data.report_structure.invite_content = extracted_data.invite_content
        
        logger.info(f"Successfully extracted and updated canvas data for section: {section_id}")
        
    except Exception as e:
        logger.warning(f"Failed to extract structured data for section {section_id}: {e}")
        # Continue without structured extraction - the content is still saved