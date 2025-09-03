"""Memory updater node for Value Canvas Agent."""

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from core.llm import get_model
from core.logging_config import get_logger, log_node_entry, log_node_exit
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

logger = get_logger(__name__)

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
    current_section = state.get('current_section')
    log_node_entry(logger, "memory_updater", current_section.value if current_section else "unknown")
    
    agent_out = state.get("agent_output")
    context_packet = state.get('context_packet')
    
    # Log agent output summary in one line
    if agent_out:
        logger.agent_output(
            section=current_section.value if current_section else "unknown",
            has_update=bool(agent_out.section_update),
            is_satisfied=agent_out.is_satisfied,
            directive=str(agent_out.router_directive)
        )

    # Decide status based on score and directive
    def _status_from_output(is_satisfied, directive):
        """Return status *string* to align with get_next_unfinished_section() logic."""
        if directive == RouterDirective.NEXT:
            return SectionStatus.DONE.value  # "done"
        if is_satisfied is not None and is_satisfied:
            return SectionStatus.DONE.value
        return SectionStatus.IN_PROGRESS.value

    # Decision tracking only in debug mode
    if not agent_out:
        logger.debug("No agent output to process")
    
    if agent_out and agent_out.section_update:
        section_id = state["current_section"].value
        logger.memory_update(section_id, "processing section_update")
        
        computed_status = _status_from_output(agent_out.is_satisfied, agent_out.router_directive)
        
        save_result = await save_section.ainvoke({
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
            "section_id": section_id,
            "content": agent_out.section_update['content'] if isinstance(agent_out.section_update, dict) else agent_out.section_update, # Pass the Tiptap content directly
            "satisfaction_feedback": agent_out.user_satisfaction_feedback,
            "status": computed_status,
        })
        # Log save operation
        logger.save_operation(
            section=section_id,
            status="satisfied" if agent_out.is_satisfied else "in_progress",
            has_content=True
        )
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
                logger.debug(f"Extracting structured data from {current_section.value}")
                
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
                # IMPORTANT: Use a non-streaming config to prevent internal extraction from appearing in user stream
                # We use a special tag to mark this as internal so it can be filtered out
                non_streaming_config = RunnableConfig(
                    configurable={"stream": False},
                    tags=["internal_extraction", "do_not_stream"]
                )
                extracted_data = await structured_llm.ainvoke(extraction_prompt, config=non_streaming_config)
                logger.debug(f"Successfully extracted structured data for {current_section.value}")

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
                        
                        logger.debug(f"Mapped SignatureMethodData: {len(canvas_data.sequenced_principles or [])} principles")
                    else:
                        # Standard field mapping for other sections
                        for field, value in extracted_data.model_dump().items():
                            if hasattr(canvas_data, field) and value is not None:
                                setattr(canvas_data, field, value)
                    
                    logger.memory_update(current_section.value, "canvas_data updated")
            except Exception as e:
                logger.warning(f"Failed to extract structured data for {current_section.value}: {e}")
        
        # Extract plain text and update canvas data
        # This would parse the content and update specific fields in canvas_data
        # For example, if section is ICP, extract icp_nickname, etc.
        
    # Handle cases where agent provides satisfaction feedback/status but no structured section_update  
    elif agent_out:
        logger.debug("Processing satisfaction feedback without section_update")
        
        if state.get("current_section"):
            score_section_id = state["current_section"].value
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
                # Log save operation
                logger.save_operation(
                    section=score_section_id,
                    status="satisfied" if agent_out.is_satisfied else "pending",
                    has_content=True
                )
                
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
            else:
                # 4. If content recovery failed, check if we should still update status
                if agent_out.router_directive == RouterDirective.NEXT:
                    # User wants to proceed, mark section as DONE even without content
                    logger.debug(f"Marking {score_section_id} as DONE (router_directive=NEXT)")
                    
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
                    logger.save_operation(score_section_id, "done", has_content=False)
                else:
                    # Not moving next and no content, cannot update
                    logger.error(f"Cannot save {score_section_id}: missing content")

        else:
            logger.warning("Cannot update section state: missing context")

    log_node_exit(logger, "memory_updater", current_section.value if current_section else "unknown")

    return state