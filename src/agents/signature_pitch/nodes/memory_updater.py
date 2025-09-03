"""Memory updater node for Signature Pitch Agent."""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from core.llm import get_model
from ..models import (
    SignaturePitchState,
    SignaturePitchSectionID,
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

logger = logging.getLogger(__name__)


async def memory_updater_node(state: SignaturePitchState, config: RunnableConfig) -> SignaturePitchState:
    """
    Memory updater node that persists section states and updates canvas data.
    Enhanced with sophisticated two-branch logic from Value Canvas.
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
            section_id=SignaturePitchSectionID(section_id),
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
        
    # Handle cases where agent provides score/status but no structured section_update  
    elif agent_out:
        # BRANCH 2: Process agent output without section_update (when LLM provides score but no content)
        logger.info("SAVE_SECTION_DEBUG: ✅ ENTERING BRANCH 2: Processing agent output without section_update")
        logger.info("DATABASE_DEBUG: Processing agent output without section_update (likely score/status only)")
        
        if state.get("context_packet"):
            score_section_id = state["context_packet"].section_id.value
            logger.debug(f"DATABASE_DEBUG: Processing score/status update for section {score_section_id}")

            # Only proceed if there's satisfaction feedback to save.
            if agent_out.is_satisfied is None:
                logger.info(f"DATABASE_DEBUG: No satisfaction data or section_update for {score_section_id}, skipping save.")
                return state

            # We have satisfaction data, so we MUST save. We need to find the content.
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
                computed_status = _status_from_output(agent_out.is_satisfied, agent_out.router_directive)
                logger.info(f"SAVE_SECTION_DEBUG: ✅ Calling save_section for {score_section_id} with satisfaction and content.")
                
                try:
                    await save_section.ainvoke({
                        "user_id": state["user_id"],
                        "thread_id": state["thread_id"],
                        "section_id": score_section_id,
                        "content": content_to_save,
                        "satisfaction_feedback": agent_out.user_satisfaction_feedback,
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
                    section_id=SignaturePitchSectionID(score_section_id),
                    content=SectionContent(
                        content=tiptap_doc,
                        plain_text=None
                    ),
                    satisfaction_feedback=agent_out.user_satisfaction_feedback,
                    status=computed_status,
                )
                logger.info(f"DATABASE_DEBUG: ✅ Updated/created section state for {score_section_id} with satisfaction {agent_out.is_satisfied}")
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
    state: SignaturePitchState, 
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
        # Import section-specific data models
        from ..sections import (
            ActiveChangeData,
            SpecificWhoData,
            OutcomePrizeData,
            CoreCredibilityData,
            StorySparkData,
            SignatureLineData,
        )
        
        if section_id == SignaturePitchSectionID.ACTIVE_CHANGE.value:
            structured_llm = llm.with_structured_output(ActiveChangeData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract active change data from this content: {plain_text}")
            ])
            
            # Update canvas_data with extracted fields
            canvas_data = state["canvas_data"]
            if extracted_data.active_change:
                canvas_data.active_change = extracted_data.active_change
                
        elif section_id == SignaturePitchSectionID.SPECIFIC_WHO.value:
            structured_llm = llm.with_structured_output(SpecificWhoData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract specific who data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.specific_who:
                canvas_data.specific_who = extracted_data.specific_who
            if extracted_data.target_audience:
                canvas_data.target_audience = extracted_data.target_audience
                
        elif section_id == SignaturePitchSectionID.OUTCOME_PRIZE.value:
            structured_llm = llm.with_structured_output(OutcomePrizeData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract outcome prize data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.outcome_prize:
                canvas_data.outcome_prize = extracted_data.outcome_prize
            if extracted_data.compelling_result:
                canvas_data.compelling_result = extracted_data.compelling_result
                
        elif section_id == SignaturePitchSectionID.CORE_CREDIBILITY.value:
            structured_llm = llm.with_structured_output(CoreCredibilityData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract core credibility data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.core_credibility:
                canvas_data.core_credibility = extracted_data.core_credibility
            if extracted_data.proof_points:
                canvas_data.proof_points = extracted_data.proof_points
                
        elif section_id == SignaturePitchSectionID.STORY_SPARK.value:
            structured_llm = llm.with_structured_output(StorySparkData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract story spark data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.story_spark:
                canvas_data.story_spark = extracted_data.story_spark
            if extracted_data.narrative_hook:
                canvas_data.narrative_hook = extracted_data.narrative_hook
                
        elif section_id == SignaturePitchSectionID.SIGNATURE_LINE.value:
            structured_llm = llm.with_structured_output(SignatureLineData)
            extracted_data = await structured_llm.ainvoke([
                SystemMessage(content=f"Extract signature line data from this content: {plain_text}")
            ])
            
            canvas_data = state["canvas_data"]
            if extracted_data.signature_line:
                canvas_data.signature_line = extracted_data.signature_line
            if extracted_data.ninety_second_pitch:
                canvas_data.ninety_second_pitch = extracted_data.ninety_second_pitch
                
        logger.info(f"Successfully extracted and updated canvas data for section: {section_id}")
        
    except Exception as e:
        logger.warning(f"Failed to extract structured data for section {section_id}: {e}")
        # Continue without structured extraction - the content is still saved
