"""Memory updater node for Value Canvas Agent."""

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from core.llm import get_model
from core.logging_config import get_logger, log_node_entry, log_node_exit

from ..enums import RouterDirective, SectionID, SectionStatus
from ..models import (
    DeepFearData,
    ICPData,
    InterviewData,
    MistakesData,
    PainData,
    PayoffsData,
    PrizeData,
    SectionContent,
    SectionState,
    SignatureMethodData,
    TiptapDocument,
    ValueCanvasState,
)
from ..tools import (
    create_tiptap_content,
    extract_plain_text,
    get_all_sections_status,
    save_section,
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
            has_update=agent_out.should_save_content,
            is_satisfied=agent_out.is_satisfied,
            directive=str(agent_out.router_directive)
        )

    # Decide status based on satisfaction and directive
    def _status_from_output(is_satisfied, directive):
        """Return status *string* to align with get_next_unfinished_section() logic."""
        if directive == RouterDirective.NEXT:
            return SectionStatus.DONE.value  # "done"
        if is_satisfied is not None and is_satisfied:
            return SectionStatus.DONE.value
        return SectionStatus.IN_PROGRESS.value

    if not agent_out:
        logger.debug("No agent output to process")
        return state
    
    # NEW LOGIC: Check should_save_content flag instead of section_update
    if agent_out and agent_out.should_save_content:
        section_id = state["current_section"].value
        logger.memory_update(section_id, "extracting and saving content")
        
        # Extract content using LLM instead of relying on section_update
        from ..prompts import extract_section_data_with_llm
        
        # Get the appropriate model for this section
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
        
        extraction_model = section_to_model_map.get(state["current_section"])
        extracted_data = None  # Initialize for later use
        tiptap_content = None
        
        if extraction_model:
            try:
                # Extract data using LLM
                extracted_data = await extract_section_data_with_llm(
                    messages=state.get("messages", []),
                    section=section_id,
                    model_class=extraction_model
                )
                
                # Convert to Tiptap format
                tiptap_content = await create_tiptap_content.ainvoke({
                    "text": str(extracted_data)  # Convert dict to string for Tiptap formatting
                })
                
                computed_status = _status_from_output(agent_out.is_satisfied, agent_out.router_directive)
                
                # Save to database
                await save_section.ainvoke({
                    "user_id": state["user_id"],
                    "thread_id": state["thread_id"],
                    "section_id": section_id,
                    "content": tiptap_content,
                    "satisfaction_feedback": agent_out.user_satisfaction_feedback,
                    "status": computed_status,
                })
                
                logger.info(f"Successfully extracted and saved {section_id} data")
            except Exception as e:
                logger.error(f"Failed to extract data for {section_id}: {e}")
                computed_status = _status_from_output(agent_out.is_satisfied, agent_out.router_directive)
        else:
            logger.warning(f"No extraction model found for section {section_id}")
            computed_status = _status_from_output(agent_out.is_satisfied, agent_out.router_directive)
        # Log save operation
        logger.save_operation(
            section=section_id,
            status="satisfied" if agent_out.is_satisfied else "in_progress",
            has_content=True
        )
        
        # Parse the extracted content for state update
        if tiptap_content and isinstance(tiptap_content, dict):
            tiptap_doc = TiptapDocument.model_validate(tiptap_content)
        else:
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

        # Update canvas_data with the extracted data we already have
        if extracted_data:
            canvas_data = state.get("canvas_data")
            if canvas_data:
                try:
                    # Convert extracted_data to dict if it's a Pydantic model
                    if hasattr(extracted_data, 'model_dump'):
                        extracted_dict = extracted_data.model_dump()
                    else:
                        extracted_dict = extracted_data
                    
                    # Special handling for SignatureMethodData
                    if state["current_section"] == SectionID.SIGNATURE_METHOD:
                        # Map SignatureMethodData to ValueCanvasData fields
                        if 'method_name' in extracted_dict:
                            canvas_data.method_name = extracted_dict['method_name']
                        
                        # Convert principles list to the old format for compatibility
                        if 'principles' in extracted_dict and extracted_dict['principles']:
                            principles = extracted_dict['principles']
                            canvas_data.sequenced_principles = [p['name'] for p in principles if 'name' in p]
                            canvas_data.principle_descriptions = {
                                p['name']: p['description'] for p in principles 
                                if 'name' in p and 'description' in p
                            }
                    else:
                        # Standard field mapping for other sections
                        for field, value in extracted_dict.items():
                            if hasattr(canvas_data, field) and value is not None:
                                setattr(canvas_data, field, value)
                    
                    logger.memory_update(section_id, "canvas_data updated")
                except Exception as e:
                    logger.warning(f"Failed to update canvas_data for {section_id}: {e}")
    # Handle router directive changes even without content to save
    elif agent_out and agent_out.router_directive == RouterDirective.NEXT:
        # User wants to proceed to next section, update status even without content
        if state.get("current_section"):
            current_section_id = state["current_section"].value
            # Mark section as DONE even without content when moving to next
            computed_status = _status_from_output(agent_out.is_satisfied, agent_out.router_directive)
            
            # Create minimal section state with DONE status
            state.setdefault("section_states", {})[current_section_id] = SectionState(
                section_id=SectionID(current_section_id),
                content=SectionContent(
                    content=TiptapDocument(type="doc", content=[]),  # Empty content
                    plain_text=None
                ),
                satisfaction_feedback=agent_out.user_satisfaction_feedback,
                status=computed_status,  # Will be DONE because of router_directive == NEXT
            )
            logger.save_operation(current_section_id, "done", has_content=False)

        else:
            logger.warning("Cannot update section state: missing context")

    log_node_exit(logger, "memory_updater", current_section.value if current_section else "unknown")

    return state