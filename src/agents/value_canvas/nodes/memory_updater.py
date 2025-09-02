"""Memory updater node for Value Canvas Agent."""

import logging

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from core.llm import get_model
from ..models import (
    ValueCanvasState,
    SectionState,
    SectionContent,
    TiptapDocument,
    InterviewData,
    ICPData,
    PainData,
    DeepFearData,
    PayoffsData,
    SignatureMethodData,
    MistakesData,
    PrizeData,
)
from ..enums import SectionID, SectionStatus, RouterDirective
from ..tools import (
    save_section,
    get_all_sections_status,
    create_tiptap_content,
    extract_plain_text,
    validate_field,
)

logger = logging.getLogger(__name__)

# Memory updater tools
memory_updater_tools = [
    save_section,
    get_all_sections_status,
    create_tiptap_content,
    extract_plain_text,
    validate_field,
]

# Create tool node
memory_updater_tool_node = ToolNode(memory_updater_tools)


async def memory_updater_node(state: ValueCanvasState, config: RunnableConfig) -> ValueCanvasState:
    """
    Memory updater node that persists section states and updates canvas data.
    
    Responsibilities:
    - Update section_states with latest content
    - Update canvas_data with extracted values
    - Manage short_memory size
    - Handle database writes
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

    # Decide status based on score and directive
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
        
        # Save to database using save_section tool
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
        
        save_result = await save_section.ainvoke({
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
            "section_id": section_id,
            "content": agent_out.section_update['content'] if isinstance(agent_out.section_update, dict) else agent_out.section_update, # Pass the Tiptap content directly
            "satisfaction_feedback": agent_out.user_satisfaction_feedback,
            "status": computed_status,
        })
        logger.debug(f"DATABASE_DEBUG: save_section returned: {bool(save_result)}")
        
        # Update local state
        logger.debug("DATABASE_DEBUG: Updating local section_states with new content")
        # Parse the section_update content properly
        if isinstance(agent_out.section_update, dict) and 'content' in agent_out.section_update:
            tiptap_doc = TiptapDocument.model_validate(agent_out.section_update['content'])
        else:
            logger.error(f"SAVE_SECTION_DEBUG: Invalid section_update structure: {type(agent_out.section_update)}")
            tiptap_doc = TiptapDocument(type="doc", content=[])
        
        state["section_states"][section_id] = SectionState(
            section_id=SectionID(section_id),
            content=SectionContent(
                content=tiptap_doc,
                plain_text=None  # Will be filled later if needed
            ),
            satisfaction_feedback=agent_out.user_satisfaction_feedback,
            status=_status_from_output(agent_out.is_satisfied, agent_out.router_directive),
        )
        logger.info(f"SAVE_SECTION_DEBUG: ✅ BRANCH 1 COMPLETED: Section {section_id} saved with structured content")

        # ----------------------------------------------------------
        # NEW: Extract Interview basics and update canvas_data
        # This now uses a modern, reliable structured output approach.
        # ----------------------------------------------------------
        # Create a mapping from SectionID to the Pydantic model for structured data extraction
        section_to_model_map = {
            SectionID.INTERVIEW: InterviewData,
            SectionID.ICP: ICPData,
            SectionID.PAIN: PainData,
            SectionID.DEEP_FEAR: DeepFearData,
            SectionID.PAYOFFS: PayoffsData,
            SectionID.SIGNATURE_METHOD: SignatureMethodData,
            SectionID.MISTAKES: MistakesData,
            SectionID.PRIZE: PrizeData,
        }

        current_section = state.get("current_section")
        extraction_model = section_to_model_map.get(current_section)

        if extraction_model:
            try:
                # 1. Extract plain text from the Tiptap JSON content
                plain_text = await extract_plain_text.ainvoke({"tiptap_json": agent_out.section_update['content'] if isinstance(agent_out.section_update, dict) else agent_out.section_update})
                logger.info(f"EXTRACTION_DEBUG: Plain text for {current_section.value} extraction:\\n---\\n{plain_text}\\n---")
                
                # 2. Define a simple prompt for the LLM
                extraction_prompt = f"""
                You are a data extraction specialist. Your task is to accurately extract information from the user's conversation summary and structure it according to the provided format. The context is a "Value Canvas," a business messaging framework.

                Section for Extraction: "{current_section.name}"

                User's Summary:
                ---
                {plain_text}
                ---

                Please extract the data fields based on their descriptions in the target data model. Pay close attention to nuances and ensure all relevant details are captured.
                """
                
                # 3. Get the LLM and bind it to our desired structured output model
                llm = get_model()
                structured_llm = llm.with_structured_output(extraction_model)
                # Add token limits to prevent infinite generation
                if hasattr(structured_llm, 'bind'):
                    structured_llm = structured_llm.bind(max_tokens=2000)
                
                # 4. Invoke the LLM to get a structured Pydantic object directly
                logger.info(f"EXTRACTION_DEBUG: Calling LLM with structured_output for {extraction_model.__name__}.")
                extracted_data = await structured_llm.ainvoke(extraction_prompt)
                logger.info(f"EXTRACTION_DEBUG: Successfully extracted structured data for {current_section.value}: {extracted_data}")

                # 5. Safely update canvas_data with the extracted, validated data
                canvas_data = state.get("canvas_data")
                if canvas_data and extracted_data:
                    # Special handling for SignatureMethodData
                    if current_section == SectionID.SIGNATURE_METHOD and isinstance(extracted_data, SignatureMethodData):
                        # Map SignatureMethodData to ValueCanvasData fields
                        canvas_data.method_name = extracted_data.method_name
                        
                        # Convert principles list to the old format for compatibility
                        if extracted_data.principles:
                            canvas_data.sequenced_principles = [p.name for p in extracted_data.principles if p.name]
                            canvas_data.principle_descriptions = {
                                p.name: p.description for p in extracted_data.principles 
                                if p.name and p.description
                            }
                        
                        logger.info(
                            f"CANVAS_DEBUG: Mapped SignatureMethodData to canvas_data - "
                            f"method_name: {canvas_data.method_name}, "
                            f"principles count: {len(canvas_data.sequenced_principles or [])}"
                        )
                    else:
                        # Standard field mapping for other sections
                        for field, value in extracted_data.model_dump().items():
                            if hasattr(canvas_data, field) and value is not None:
                                setattr(canvas_data, field, value)
                    
                    logger.info(
                        "CANVAS_DEBUG: Updated canvas_data with structured info for section "
                        f"'{current_section.value}'"
                    )
            except Exception as e:
                logger.warning(f"CANVAS_DEBUG: Failed to extract structured data for {current_section.value}: {e}")
            
        logger.info(f"DATABASE_DEBUG: ✅ Section {section_id} updated with structured content")
        
        # Extract plain text and update canvas data
        # This would parse the content and update specific fields in canvas_data
        # For example, if section is ICP, extract icp_nickname, etc.
        
    # Handle cases where agent provides satisfaction feedback/status but no structured section_update  
    elif agent_out:
        logger.info("SAVE_SECTION_DEBUG: ✅ ENTERING BRANCH 2: Processing agent output without section_update")
        logger.info("DATABASE_DEBUG: Processing agent output without section_update (likely satisfaction feedback/status only)")
        
        if state.get("current_section"):
            score_section_id = state["current_section"].value
            logger.debug(f"DATABASE_DEBUG: Processing satisfaction feedback/status update for section {score_section_id}")

            # Only proceed if there's satisfaction feedback to save OR router directive is NEXT.
            # This ensures that when user confirms to proceed to next section (router_directive='next'),
            # we still update the section status even without explicit satisfaction feedback.
            if agent_out.is_satisfied is None and agent_out.router_directive != RouterDirective.NEXT:
                logger.info(f"DATABASE_DEBUG: No satisfaction feedback or section_update for {score_section_id}, and not moving next, skipping save.")
                return state

            # We have satisfaction feedback, so we MUST save. We need to find the content.
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
                    content_to_save = await create_tiptap_content.ainvoke({"text": summary_text})
                else:
                    logger.error(f"SAVE_SECTION_DEBUG: Could not recover summary from message history for {score_section_id}.")

            # 3. If we found content (either from state or recovery), proceed with saving.
            if content_to_save:
                computed_status = _status_from_output(agent_out.is_satisfied, agent_out.router_directive)
                logger.info(f"SAVE_SECTION_DEBUG: ✅ Calling save_section for {score_section_id} with satisfaction feedback and content.")
                
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
                    section_id=SectionID(score_section_id),
                    content=SectionContent(
                        content=tiptap_doc,
                        plain_text=None
                    ),
                    satisfaction_feedback=agent_out.user_satisfaction_feedback,
                    status=computed_status,
                )
                logger.info(f"DATABASE_DEBUG: ✅ Updated/created section state for {score_section_id} with satisfaction feedback {agent_out.is_satisfied}")
            else:
                # 4. If content recovery failed, check if we should still update status
                if agent_out.router_directive == RouterDirective.NEXT:
                    # User wants to proceed, mark section as DONE even without content
                    logger.warning(f"DATABASE_DEBUG: No content found for {score_section_id}, but router_directive is NEXT. Marking as DONE.")
                    
                    computed_status = _status_from_output(agent_out.is_satisfied, agent_out.router_directive)
                    
                    # Create minimal section state with DONE status
                    state.setdefault("section_states", {})[score_section_id] = SectionState(
                        section_id=SectionID(score_section_id),
                        content=SectionContent(
                            content=TiptapDocument(type="doc", content=[]),  # Empty content
                            plain_text=None
                        ),
                        satisfaction_feedback=agent_out.user_satisfaction_feedback,
                        status=computed_status,  # Will be DONE because of router_directive == NEXT
                    )
                    logger.info(f"DATABASE_DEBUG: ✅ Marked section {score_section_id} as DONE without content (router_directive was NEXT)")
                else:
                    # Not moving next and no content, cannot update
                    logger.error(f"DATABASE_DEBUG: ❌ CRITICAL: Aborting save for section {score_section_id} due to missing content.")

        else:
            logger.warning("DATABASE_DEBUG: ⚠️ Cannot update section state as context_packet is missing")

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