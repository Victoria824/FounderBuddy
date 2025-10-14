"""Tools for Concept Pitch Agent."""

import logging
from typing import Any

from langchain_core.tools import tool

from core.settings import settings
from integrations.dentapp.dentapp_client import get_dentapp_client
from integrations.dentapp.dentapp_utils import (
    VALUE_CANVAS_AGENT_ID,
    SECTION_ID_MAPPING,
    get_section_id_int,
    log_api_operation,
    plain_text_to_tiptap,
)

from .enums import SectionID, SectionStatus
from .models import ConceptPitchData, SectionContent, TiptapDocument
from .sections import SECTION_TEMPLATES

logger = logging.getLogger(__name__)


@tool
async def get_context(user_id: int, thread_id: str | None, section_id: str, canvas_data: dict) -> dict:
    """
    Get context for a specific Concept Pitch section, including Value Canvas data.
    
    This tool fetches Value Canvas data from the DentApp API to provide context
    for Concept Pitch generation (ICP, Pain, Gain, Prize, Signature Method).
    
    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier (can be None for new conversations)
        section_id: Section identifier (e.g., 'summary_confirmation', 'pitch_generation')
        canvas_data: Current canvas data for template rendering
    
    Returns:
        Context packet with Value Canvas data and system prompt
    """
    logger.info("=== CONCEPT_PITCH_GET_CONTEXT: 🆕 NEW CODE LOADED 🆕 ===")
    logger.info(f"CONCEPT_PITCH_GET_CONTEXT: Section: {section_id}, User: {user_id}, Thread: {thread_id or 'None'}")
    
    # Initialize context with basic section info
    context = {
        "section_id": section_id,
        "status": SectionStatus.PENDING.value,
        "system_prompt": f"System prompt for {section_id}",
        "draft": None,
        "validation_rules": None,
        "value_canvas_data": {},  # Will be populated with Value Canvas data
    }
    
    # Try to get Value Canvas data from DentApp API
    # FORCE ENABLE API - Direct override
    logger.info("=" * 80)
    logger.info("🚨 CRITICAL DEBUG: ENTERING API CHECK SECTION")
    logger.info(f"🚨 settings.USE_DENTAPP_API = {settings.USE_DENTAPP_API}")
    logger.info("=" * 80)
    if True:  # settings.USE_DENTAPP_API:
        logger.info("=== CONCEPT_PITCH_API_CALL: ✅ ENTERED TRUE BRANCH ===")
        try:
            client = get_dentapp_client()
            if client:
                # Get all Value Canvas sections to build complete context
                value_canvas_sections = [
                    "icp", "pain", "payoffs", "signature_method", "prize"
                ]
                
                value_canvas_data = {}
                
                for vc_section in value_canvas_sections:
                    section_id_int = get_section_id_int(vc_section)
                    if section_id_int:
                        logger.info(f"CONCEPT_PITCH_API_CALL: Fetching {vc_section} (ID: {section_id_int})")
                        
                        result = await client.get_section_state(
                            agent_id=VALUE_CANVAS_AGENT_ID,
                            section_id=section_id_int,
                            user_id=user_id
                        )

                        # Check for data in the correct structure: result['data']['content']
                        if result and result.get('data') and result['data'].get('content'):
                            # Handle nested data structure from DentApp API
                            content_raw = result['data']['content']
                            logger.info(f"CONCEPT_PITCH_API_CALL: Raw content for {vc_section}: {type(content_raw)} - {str(content_raw)[:100]}...")

                            # Support both string format and object format
                            if isinstance(content_raw, str):
                                # Plain text format
                                content = content_raw.strip()
                            elif isinstance(content_raw, dict) and 'text' in content_raw:
                                # Object format with text field
                                content = content_raw.get('text', '').strip()
                            else:
                                # Fallback: try to extract any string value
                                content = str(content_raw).strip() if content_raw else ''

                            if content:
                                value_canvas_data[vc_section] = content
                                logger.info(f"CONCEPT_PITCH_API_CALL: ✅ Retrieved {vc_section}: {len(content)} chars")
                            else:
                                logger.warning(f"CONCEPT_PITCH_API_CALL: ⚠️ {vc_section} content is empty after processing")
                        else:
                            logger.warning(f"CONCEPT_PITCH_API_CALL: ⚠️ No data/content for {vc_section}, result: {result}")
                    else:
                        logger.warning(f"CONCEPT_PITCH_API_CALL: Invalid section ID for {vc_section}")
                
                # Also try to get agent context for additional user data
                agent_context = await client.get_agent_context(user_id)
                if agent_context:
                    logger.info("CONCEPT_PITCH_API_CALL: ✅ Retrieved agent context")
                    value_canvas_data["agent_context"] = agent_context
                
                context["value_canvas_data"] = value_canvas_data
                logger.info(f"CONCEPT_PITCH_API_CALL: ✅ Retrieved Value Canvas data for {len(value_canvas_data)} sections")
                
            else:
                logger.warning("CONCEPT_PITCH_API_CALL: DentApp client not available")
                
        except Exception as e:
            logger.warning(f"CONCEPT_PITCH_API_CALL: ⚠️ Failed to fetch Value Canvas data: {e}")
            logger.debug("CONCEPT_PITCH_API_CALL: Using empty Value Canvas data")
    else:
        logger.warning("CONCEPT_PITCH_API_CALL: ⚠️ DentApp API disabled, using mock data")
        # Mock Value Canvas data for local testing
        value_canvas_data = {
            "icp": "Small business owners and entrepreneurs who are launching their first digital product or service",
            "pain": "They struggle with creating a clear, compelling pitch that resonates with their target market. They often spend weeks or months refining their messaging without getting real market feedback, leading to wasted time and resources.",
            "payoffs": "A validated concept pitch that generates genuine interest and referrals from their target audience, allowing them to confidently move forward with product development knowing there's real demand.",
            "signature_method": "The CAOS (Concept As Original Story) framework - a structured approach to creating three different pitch variations (Pain-driven, Gain-driven, and Prize-driven) that can be tested in real conversations to gather authentic market feedback.",
            "prize": "A proven business concept with pre-validated market demand, giving them the confidence to invest time and money into building the right solution, while building a network of early adopters and advocates who are already excited about what's coming.",
        }
        context["value_canvas_data"] = value_canvas_data
        logger.info(f"CONCEPT_PITCH_API_CALL: ✅ Using mock Value Canvas data for {len(value_canvas_data)} sections")
    
    # Get section-specific system prompt from template
    section_template = SECTION_TEMPLATES.get(section_id)
    if section_template:
        # Use the section template's system prompt
        system_prompt = section_template.system_prompt_template
        
        # Inject Value Canvas data into the prompt using template variables
        if context["value_canvas_data"]:
            vc_data = context["value_canvas_data"]
            
            # Add Value Canvas context at the beginning
            value_canvas_context = "\n\nVALUE CANVAS CONTEXT (Use this data to personalize the pitch):\n"
            
            if vc_data.get("icp"):
                value_canvas_context += f"- ICP: {vc_data['icp']}\n"
            
            if vc_data.get("pain"):
                value_canvas_context += f"- Pain: {vc_data['pain']}\n"
            
            if vc_data.get("payoffs"):
                value_canvas_context += f"- Gain: {vc_data['payoffs']}\n"
            
            if vc_data.get("signature_method"):
                value_canvas_context += f"- Signature Method: {vc_data['signature_method']}\n"
            
            if vc_data.get("prize"):
                value_canvas_context += f"- Prize: {vc_data['prize']}\n"
            
            # Append Value Canvas context to the section prompt
            system_prompt = system_prompt + value_canvas_context
            logger.info(f"CONCEPT_PITCH_GET_CONTEXT: ✅ Using section template for {section_id} with Value Canvas context")
        else:
            logger.info(f"CONCEPT_PITCH_GET_CONTEXT: ✅ Using section template for {section_id} (no Value Canvas data)")
        
        context["system_prompt"] = system_prompt
    else:
        # Fallback to generic prompt if section template not found
        logger.warning(f"CONCEPT_PITCH_GET_CONTEXT: ⚠️ No section template found for {section_id}, using fallback")
        context["system_prompt"] = f"System prompt for {section_id}"
    
    logger.info(f"CONCEPT_PITCH_GET_CONTEXT: ✅ Returning context with {len(context['value_canvas_data'])} Value Canvas sections")
    return context


@tool
async def save_section(user_id: int, thread_id: str, section_id: str, content: dict, satisfaction_feedback: str = None, status: str = None) -> dict:
    """Save section content to database."""
    # Placeholder implementation
    return {"success": True, "section_id": section_id}


@tool
async def get_all_sections_status(user_id: int, thread_id: str) -> dict:
    """Get status of all sections."""
    # Placeholder implementation
    return {"sections": {}}


@tool
async def extract_plain_text(content: dict) -> str:
    """Extract plain text from Tiptap content."""
    # Placeholder implementation
    return "Extracted plain text"


@tool
async def validate_field(field_name: str, value: str, validation_rules: list) -> dict:
    """Validate a field against validation rules."""
    # Placeholder implementation
    return {"valid": True, "errors": []}


@tool
async def convert_to_tiptap_json(data: dict, section_id: str) -> dict:
    """Convert data to Tiptap JSON format."""
    # Placeholder implementation
    return {"type": "doc", "content": []}


@tool
async def update_canvas_data(extracted_data: dict, canvas_data: dict, section_id: str) -> dict:
    """Update canvas data with extracted information."""
    # Placeholder implementation
    return canvas_data
