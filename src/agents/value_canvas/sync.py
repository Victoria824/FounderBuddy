"""Section synchronization logic for Value Canvas Agent.

This module handles syncing LangGraph state with manually edited section content
from the database (DentApp API).
"""

import logging
from typing import Any, Type

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from core.llm import get_model
from integrations.dentapp.dentapp_client import get_dentapp_client
from integrations.dentapp.dentapp_utils import (
    AGENT_ID,
    get_section_id_int,
    plain_text_to_tiptap,
    tiptap_to_plain_text,
)

from .enums import SectionID, SectionStatus
from .models import (
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
    ValueCanvasData,
)

logger = logging.getLogger(__name__)


def get_section_model_class(section_id: str) -> Type[BaseModel] | None:
    """
    Get the Pydantic model class for a given section ID.

    Args:
        section_id: Section identifier string

    Returns:
        Pydantic model class for structured data extraction, or None if not found
    """
    section_to_model_map = {
        SectionID.INTERVIEW.value: InterviewData,
        SectionID.ICP.value: ICPData,
        SectionID.ICP_STRESS_TEST.value: ICPData,  # ICP Stress Test saves ICPData
        SectionID.PAIN.value: PainData,
        SectionID.DEEP_FEAR.value: DeepFearData,
        SectionID.PAYOFFS.value: PayoffsData,
        SectionID.SIGNATURE_METHOD.value: SignatureMethodData,
        SectionID.MISTAKES.value: MistakesData,
        SectionID.PRIZE.value: PrizeData,
    }

    return section_to_model_map.get(section_id)


async def extract_data_from_tiptap_text(
    plain_text: str,
    section_id: str,
    model_class: Type[BaseModel]
) -> BaseModel:
    """
    Extract structured data from Tiptap plain text using LLM.

    This is the reverse of the normal flow - instead of extracting from conversation,
    we extract from manually edited Tiptap content.

    Args:
        plain_text: Plain text content extracted from Tiptap JSON
        section_id: Section identifier
        model_class: Pydantic model class for structured extraction

    Returns:
        Extracted structured data as Pydantic model instance
    """
    logger.info(f"=== SYNC_EXTRACT: Extracting structured data from Tiptap text ===")
    logger.info(f"SYNC_EXTRACT: section_id={section_id}")
    logger.debug(f"SYNC_EXTRACT: text_length={len(plain_text)}")

    # Create extraction prompt
    extraction_prompt = f"""Extract structured data from this Value Canvas section content.

Section: {section_id}

Content (manually edited by user):
{plain_text}

Extract all relevant fields according to the data model requirements.
Be accurate and complete in your extraction. This content was manually edited by the user,
so extract exactly what they wrote without making assumptions or additions."""

    # Use LLM with structured output
    llm = get_model()
    structured_llm = llm.with_structured_output(model_class)

    # Use non-streaming config with tags to prevent extraction data from appearing in logs
    non_streaming_config = RunnableConfig(
        configurable={"stream": False},
        tags=["internal_extraction", "do_not_stream", "sync_operation"],
        callbacks=[]
    )

    # Extract data with non-streaming config
    logger.debug("SYNC_EXTRACT: Invoking LLM for extraction...")
    extracted_data = await structured_llm.ainvoke(
        extraction_prompt,
        config=non_streaming_config
    )

    logger.info(f"SYNC_EXTRACT: ✅ Successfully extracted data for {section_id}")
    return extracted_data


async def sync_section_from_database(
    user_id: int,
    thread_id: str,
    section_id: str,
    agent_graph: Any  # AgentGraph type
) -> dict[str, Any]:
    """
    Sync a section's LangGraph state with manually edited content from database.

    This function:
    1. Fetches the latest section content from DentApp API (Tiptap format)
    2. Converts Tiptap to plain text
    3. Uses LLM to extract structured data from plain text
    4. Updates LangGraph state (canvas_data + section_states)
    5. Persists changes via checkpoint

    Args:
        user_id: User identifier
        thread_id: Thread/conversation identifier
        section_id: Section identifier
        agent_graph: LangGraph agent instance

    Returns:
        Sync result dictionary with success status and details

    Raises:
        ValueError: If section_id is invalid or no model class found
        Exception: If DentApp API call fails or state update fails
    """
    logger.info(f"=== SYNC_SECTION_START: section_id={section_id}, user={user_id}, thread={thread_id} ===")

    # Validate section and get model class
    model_class = get_section_model_class(section_id)
    if not model_class:
        logger.error(f"SYNC_ERROR: No model class found for section {section_id}")
        raise ValueError(f"Unknown or unsupported section_id: {section_id}")

    logger.debug(f"SYNC: Using model class {model_class.__name__} for section {section_id}")

    # Step 1: Fetch latest content from DentApp API
    logger.info("SYNC: Step 1/5 - Fetching content from DentApp API")
    dentapp_client = get_dentapp_client()

    if not dentapp_client:
        logger.error("SYNC_ERROR: DentApp API client not available")
        raise Exception("DentApp API is not configured")

    section_id_int = get_section_id_int(section_id)
    if section_id_int is None:
        logger.error(f"SYNC_ERROR: Cannot map section_id {section_id} to integer")
        raise ValueError(f"Invalid section_id: {section_id}")

    logger.debug(f"SYNC: Calling get_section_state(agent_id={AGENT_ID}, section_id={section_id_int}, user_id={user_id})")
    api_result = await dentapp_client.get_section_state(
        agent_id=AGENT_ID,
        section_id=section_id_int,
        user_id=user_id
    )

    if not api_result:
        logger.error("SYNC_ERROR: DentApp API returned no data")
        raise Exception(f"Failed to fetch section data from DentApp API")

    # Extract content from nested data structure
    # DentApp API returns: {"data": {"content": {"text": "actual content"}}}
    data = api_result.get('data', {})
    content_obj = data.get('content', {})

    # Handle both string and object formats
    if isinstance(content_obj, str):
        raw_content = content_obj
    elif isinstance(content_obj, dict):
        raw_content = content_obj.get('text', '')
    else:
        raw_content = ''

    if not raw_content or not raw_content.strip():
        logger.warning(f"SYNC_WARNING: Section {section_id} has no content in database")
        return {
            "success": False,
            "error": "Section has no content to sync",
            "section_id": section_id
        }

    logger.info(f"SYNC: ✅ Fetched content from database (length: {len(raw_content)})")

    # Step 2: Convert Tiptap to plain text (if needed)
    logger.info("SYNC: Step 2/5 - Converting to plain text")
    # The DentApp API stores plain text, not Tiptap JSON
    plain_text = raw_content
    logger.debug(f"SYNC: Plain text length: {len(plain_text)}")

    # Also convert to Tiptap format for section_states
    tiptap_content = plain_text_to_tiptap(plain_text)
    logger.debug("SYNC: Converted plain text to Tiptap format")

    # Step 3: Extract structured data using LLM
    logger.info("SYNC: Step 3/5 - Extracting structured data with LLM")
    extracted_data = await extract_data_from_tiptap_text(
        plain_text=plain_text,
        section_id=section_id,
        model_class=model_class
    )

    logger.info(f"SYNC: ✅ Extracted structured data")
    logger.debug(f"SYNC: Extracted data: {extracted_data.model_dump() if hasattr(extracted_data, 'model_dump') else extracted_data}")

    # Step 4: Get current state
    logger.info("SYNC: Step 4/5 - Getting current LangGraph state")
    config = RunnableConfig(
        configurable={
            "thread_id": thread_id,
            "user_id": user_id
        }
    )

    current_state = await agent_graph.aget_state(config)
    logger.debug(f"SYNC: Retrieved state for thread {thread_id}")

    # Step 5: Update state
    logger.info("SYNC: Step 5/5 - Updating LangGraph state")

    # Get current canvas_data
    canvas_data = current_state.values.get("canvas_data", {})

    # Convert to dict if it's a Pydantic model
    if hasattr(canvas_data, 'model_dump'):
        canvas_data_dict = canvas_data.model_dump()
    else:
        canvas_data_dict = dict(canvas_data) if canvas_data else {}

    # Update canvas_data with extracted fields
    extracted_dict = extracted_data.model_dump() if hasattr(extracted_data, 'model_dump') else extracted_data

    # Special handling for SignatureMethod section
    if section_id == "signature_method":
        if 'method_name' in extracted_dict:
            canvas_data_dict['method_name'] = extracted_dict['method_name']
        if 'principles' in extracted_dict and extracted_dict['principles']:
            principles = extracted_dict['principles']
            canvas_data_dict['sequenced_principles'] = [
                p['name'] for p in principles if 'name' in p
            ]
            canvas_data_dict['principle_descriptions'] = {
                p['name']: p['description']
                for p in principles
                if 'name' in p and 'description' in p
            }
    else:
        # Standard field mapping for other sections
        for field, value in extracted_dict.items():
            if value is not None:
                canvas_data_dict[field] = value

    logger.debug(f"SYNC: Updated canvas_data with {len(extracted_dict)} fields")

    # Create updated section_state
    tiptap_doc = TiptapDocument.model_validate(tiptap_content)
    updated_section_state = SectionState(
        section_id=SectionID(section_id),
        content=SectionContent(
            content=tiptap_doc,
            plain_text=plain_text
        ),
        status=SectionStatus.DONE,  # Mark as done since it has content
        satisfaction_status=None  # User edited manually, no satisfaction feedback
    )

    # Get current section_states
    section_states = current_state.values.get("section_states", {})
    if isinstance(section_states, dict):
        section_states_dict = dict(section_states)
    else:
        section_states_dict = {}

    section_states_dict[section_id] = updated_section_state

    # Use update_state to persist changes
    logger.debug("SYNC: Calling agent.aupdate_state() to persist changes")
    await agent_graph.aupdate_state(
        config=config,
        values={
            "canvas_data": canvas_data_dict,
            "section_states": section_states_dict
        }
    )

    logger.info(f"=== SYNC_SECTION_SUCCESS: section_id={section_id} ===")
    logger.info(f"SYNC_SUCCESS: Updated canvas_data and section_states for {section_id}")

    return {
        "success": True,
        "section_id": section_id,
        "user_id": user_id,
        "thread_id": thread_id,
        "extracted_fields": list(extracted_dict.keys()),
        "content_length": len(plain_text)
    }
