"""Tools for Social Pitch Agent."""

import logging
import uuid
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from core.settings import settings
from integrations.dentapp.dentapp_client import get_dentapp_client
from integrations.dentapp.dentapp_utils import (
    get_section_id_int,
    log_api_operation,
    plain_text_to_tiptap,
    tiptap_to_plain_text,
)

from .models import (
    SectionID,
    SectionStatus,
    TiptapDocument,
)
from .prompts import BASE_RULES, SECTION_TEMPLATES

logger = logging.getLogger(__name__)

# Social Pitch uses agent ID 3
SOCIAL_PITCH_AGENT_ID = 3

# Section ID mapping for Social Pitch agent
SOCIAL_PITCH_SECTION_MAPPING = {
    "name": None,      # Will be set by environment config
    "same": None,      # Will be set by environment config  
    "fame": None,      # Will be set by environment config
    "pain": None,      # Will be set by environment config
    "aim": None,       # Will be set by environment config
    "game": None,      # Will be set by environment config
}


def get_social_pitch_section_id_int(section_id_str: str) -> int | None:
    """
    Convert Social Pitch section ID string to DentApp API section_id integer.
    Maps Social Pitch sections to their dedicated section IDs.
    
    Args:
        section_id_str: Section ID from the agent (e.g., "name", "same")
        
    Returns:
        Integer section_id for DentApp API, or None if not found
    """
    # Social Pitch specific mapping - need to handle "pain" differently for Social Pitch
    if section_id_str == "pain":
        # Use sp_pain mapping for Social Pitch pain section
        section_id_str = "sp_pain"
    
    # Try to use the dynamic configuration from dentapp_utils
    try:
        return get_section_id_int(section_id_str)
    except:
        # Fallback mapping for Social Pitch sections
        fallback_mapping = {
            "name": 17,      # GSD config fallback
            "same": 18,
            "fame": 19, 
            "sp_pain": 20,   # Social Pitch pain
            "aim": 21,
            "game": 22,
        }
        
        section_id_int = fallback_mapping.get(section_id_str)
        if section_id_int is None:
            logger.error(f"Unknown Social Pitch section ID: {section_id_str}")
        return section_id_int


@tool
async def get_context(
    user_id: int,
    thread_id: str,
    section_id: str,
    pitch_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get context packet for a specific Social Pitch section.
    
    This tool fetches section data from the database and generates
    the appropriate system prompt based on the section template.
    
    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier
        section_id: Section identifier (e.g., 'name', 'same')
        pitch_data: Current pitch data for template rendering
    
    Returns:
        Context packet with system prompt and draft content
    """
    logger.info("=== DATABASE_DEBUG: get_context() ENTRY (Social Pitch) ===")
    logger.info(f"DATABASE_DEBUG: Section: {section_id}, User: {user_id}, Thread: {thread_id}")
    logger.debug(f"DATABASE_DEBUG: User ID type: {type(user_id)}, Thread ID type: {type(thread_id)}")
    logger.debug(f"DATABASE_DEBUG: Pitch data provided: {bool(pitch_data)}")
    
    # Get section template
    template = SECTION_TEMPLATES.get(section_id)
    if not template:
        raise ValueError(f"Unknown Social Pitch section ID: {section_id}")
    
    # Generate system prompt
    base_prompt = BASE_RULES
    section_prompt = template.system_prompt_template
    
    # Render template with pitch data if provided
    if pitch_data is None:
        pitch_data = {}

    # Allow partial rendering: missing keys will be replaced with empty string
    import re
    def _replace_placeholder(match):
        key = match.group(1)
        return str(pitch_data.get(key, "")) if isinstance(pitch_data, dict) else ""

    # Only replace simple placeholders like {identifier}, keep other braces unchanged
    section_prompt = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", _replace_placeholder, section_prompt)
    
    system_prompt = f"{base_prompt}\\n\\n---\\n\\n{section_prompt}"
    
    # Fetch draft from database
    logger.debug("DATABASE_DEBUG: Starting database fetch for existing Social Pitch section state...")
    draft = None
    status = "pending"
    
    # Try DentApp API first (if enabled)
    if settings.USE_DENTAPP_API:
        logger.info("=== TOOLS_API_CALL: get_context() using DentApp API (Social Pitch) ===")
        logger.info(f"TOOLS_API_CALL: section_id='{section_id}', user_id='{user_id}', thread_id='{thread_id}'")
        try:
            # Convert section_id for DentApp API
            section_id_int = get_social_pitch_section_id_int(section_id)
            
            if section_id_int is None:
                logger.error(f"TOOLS_API_CALL: ❌ Invalid Social Pitch section_id: {section_id}")
                raise ValueError(f"Unknown Social Pitch section ID: {section_id}")
            
            logger.info(f"TOOLS_API_CALL: Mapped section_id '{section_id}' -> {section_id_int}")
            log_api_operation("get_context", user_id=user_id, section_id=section_id, 
                            user_id_int=user_id, section_id_int=section_id_int)
            
            # Call DentApp API
            logger.info(f"TOOLS_API_CALL: Calling get_section_state(agent_id={SOCIAL_PITCH_AGENT_ID}, section_id={section_id_int}, user_id={user_id})")
            dentapp_client = get_dentapp_client()
            async with dentapp_client as client:
                result = await client.get_section_state(
                    agent_id=SOCIAL_PITCH_AGENT_ID,
                    section_id=section_id_int,
                    user_id=user_id
                )
            logger.info(f"TOOLS_API_CALL: get_section_state returned: {result is not None}")
            
            if result:
                # Extract data from DentApp API response
                raw_content = result.get('content', '')
                raw_status = result.get('is_completed', False)
                
                # Convert status
                status = "done" if raw_status else "pending"
                
                logger.debug(f"DATABASE_DEBUG: DentApp API found data - Status: {status}")
                logger.debug(f"DATABASE_DEBUG: Content length: {len(raw_content) if raw_content else 0}")
                
                if raw_content and raw_content.strip():
                    # Convert plain text to Tiptap format
                    tiptap_content = plain_text_to_tiptap(raw_content)
                    draft = {
                        "content": tiptap_content,
                        "plain_text": raw_content
                    }
                    logger.info("DATABASE_DEBUG: ✅ Successfully loaded existing draft from DentApp API")
                else:
                    logger.debug("DATABASE_DEBUG: DentApp API content is empty, no draft loaded")
                    
                logger.info(f"DATABASE_DEBUG: DentApp API fetch result - status={status}, has_draft={draft is not None}")
                
        except Exception as dentapp_error:
            logger.warning(f"DATABASE_DEBUG: ⚠️ DentApp API failed: {dentapp_error}")
            logger.debug("DATABASE_DEBUG: Using default values")
    else:
        logger.warning("DATABASE_DEBUG: ⚠️ DentApp API disabled, using default values")
    
    logger.debug(f"DATABASE_DEBUG: Final context values - status: {status}, draft: {bool(draft)}")
    
    return {
        "section_id": section_id,
        "status": status,
        "system_prompt": system_prompt,
        "draft": draft,
        "validation_rules": {str(i): rule.model_dump() for i, rule in enumerate(template.validation_rules)},
        "required_fields": template.required_fields,
    }


@tool
async def save_section(
    user_id: int,
    thread_id: str,
    section_id: str,
    content: dict[str, Any],
    score: int | None = None,
    status: str = "done",
) -> dict[str, Any]:
    """
    Save or update a Social Pitch section in the database.
    
    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier
        section_id: Section identifier
        content: Section content (Tiptap JSON)
        score: Optional satisfaction score (0-5)
        status: Section status
    
    Returns:
        Updated section state
    """
    logger.info("=== DATABASE_DEBUG: save_section() ENTRY (Social Pitch) ===")
    logger.info(f"DATABASE_DEBUG: Saving Social Pitch section {section_id} for user {user_id}, doc {thread_id}")
    logger.debug(f"DATABASE_DEBUG: User ID type: {type(user_id)}, Thread ID type: {type(thread_id)}")
    logger.debug(f"DATABASE_DEBUG: Content type: {type(content)}, Score: {score}, Status: {status}")
    
    # [DIAGNOSTIC] Log all parameters passed to save_section
    logger.info(
        f"DATABASE_DEBUG: Full parameters - "
        f"user_id={user_id}, thread_id={thread_id}, section_id='{section_id}', "
        f"score={score}, status='{status}'"
    )
    logger.debug(f"DATABASE_DEBUG: Content structure: {content}")

    current_time = datetime.utcnow().isoformat() + "Z"
    logger.debug(f"DATABASE_DEBUG: Generated timestamp: {current_time}")
    
    # Try DentApp API first (if enabled)
    if settings.USE_DENTAPP_API:
        logger.info("=== TOOLS_API_CALL: save_section() using DentApp API (Social Pitch) ===")
        logger.info(f"TOOLS_API_CALL: section_id='{section_id}', user_id='{user_id}', thread_id='{thread_id}', score={score}, status='{status}'")
        try:
            # Convert section_id for DentApp API
            section_id_int = get_social_pitch_section_id_int(section_id)
            
            if section_id_int is None:
                logger.error(f"TOOLS_API_CALL: ❌ Invalid Social Pitch section_id: {section_id}")
                raise ValueError(f"Unknown Social Pitch section ID: {section_id}")
            
            # Convert Tiptap content to plain text
            plain_text = tiptap_to_plain_text(content) if content else ""
            logger.info(f"TOOLS_API_CALL: Mapped section_id '{section_id}' -> {section_id_int}")
            logger.info(f"TOOLS_API_CALL: Converted content length: {len(plain_text)} chars")
            
            log_api_operation("save_section", user_id=user_id, section_id=section_id, 
                            user_id_int=user_id, section_id_int=section_id_int,
                            content_length=len(plain_text), score=score, status=status)
            
            # Call DentApp API
            logger.info(f"TOOLS_API_CALL: Calling save_section_state(agent_id={SOCIAL_PITCH_AGENT_ID}, section_id={section_id_int}, user_id={user_id})")
            dentapp_client = get_dentapp_client()
            async with dentapp_client as client:
                result = await client.save_section_state(
                    agent_id=SOCIAL_PITCH_AGENT_ID,
                    section_id=section_id_int,
                    user_id=user_id,
                    content=plain_text,
                    metadata={}  # Empty metadata for MVP
                )
            logger.info(f"TOOLS_API_CALL: save_section_state returned: {result is not None}")
            
            if result:
                logger.info(f"DATABASE_DEBUG: ✅ Successfully saved Social Pitch section {section_id} via DentApp API")
                
                # Return response compatible with existing agent code
                return {
                    "id": str(result.get('id', uuid.uuid4())),
                    "user_id": user_id,
                    "thread_id": thread_id,
                    "section_id": section_id,
                    "content": content,  # Return original Tiptap format
                    "score": score,
                    "status": status,
                    "updated_at": result.get('updated_at', current_time),
                }
            else:
                # API call failed
                logger.warning("DATABASE_DEBUG: ⚠️ DentApp API save failed")
                raise Exception("DentApp API save returned None")
                
        except Exception as dentapp_error:
            logger.warning(f"DATABASE_DEBUG: ⚠️ DentApp API failed: {dentapp_error}")
            logger.debug("DATABASE_DEBUG: Using mock response")
            
            # Return mock response when DentApp API fails
            return {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "thread_id": thread_id,
                "section_id": section_id,
                "content": content,
                "score": score,
                "status": status,
                "updated_at": current_time,
            }
    else:
        # DentApp API disabled, use mock response
        logger.warning(f"DATABASE_DEBUG: ⚠️ DentApp API disabled, using mock response for Social Pitch section {section_id}")
        return {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "thread_id": thread_id,
            "section_id": section_id,
            "content": content,
            "score": score,
            "status": status,
            "updated_at": current_time,
        }


@tool
async def validate_field(
    field_name: str,
    value: Any,
    validation_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Validate a field value against defined rules.
    
    Args:
        field_name: Name of the field to validate
        value: Value to validate
        validation_rules: List of validation rules
    
    Returns:
        Validation result with is_valid flag and error messages
    """
    errors = []
    
    for rule in validation_rules:
        if rule.get("field_name") != field_name:
            continue
            
        rule_type = rule.get("rule_type")
        rule_value = rule.get("value")
        error_message = rule.get("error_message", "Validation failed")
        
        if rule_type == "required" and not value:
            errors.append(error_message)
        elif rule_type == "min_length" and len(str(value)) < rule_value:
            errors.append(error_message)
        elif rule_type == "max_length" and len(str(value)) > rule_value:
            errors.append(error_message)
        elif rule_type == "choices" and value not in rule_value:
            errors.append(error_message)
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "field_name": field_name,
        "value": value,
    }


@tool
async def get_all_sections_status(
    user_id: int,
    thread_id: str,
) -> list[dict[str, Any]]:
    """
    Get status of all Social Pitch sections for a document.
    
    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier
    
    Returns:
        List of section states with status
    """
    logger.info("=== DATABASE_DEBUG: get_all_sections_status() ENTRY (Social Pitch) ===")
    logger.info(f"DATABASE_DEBUG: Getting all Social Pitch section status for user {user_id}, doc {thread_id}")
    
    try:
        # Try DentApp API first (if enabled)
        if settings.USE_DENTAPP_API:
            logger.debug("DATABASE_DEBUG: ✅ DentApp API enabled, attempting to fetch all Social Pitch sections status")
            try:
                log_api_operation("get_all_sections_status", user_id=user_id, thread_id=thread_id, 
                                user_id_int=user_id)
                
                # Call DentApp API
                dentapp_client = get_dentapp_client()
                async with dentapp_client as client:
                    api_result = await client.get_all_sections_status(
                        agent_id=SOCIAL_PITCH_AGENT_ID,
                        user_id=user_id
                    )
                
                if api_result:
                    logger.info("DATABASE_DEBUG: ✅ Retrieved DentApp API response")
                    
                    # Extract sections data from DentApp API response
                    api_sections = api_result.get('sections', [])
                    logger.info(f"DATABASE_DEBUG: DentApp API returned {len(api_sections)} Social Pitch sections")
                    
                    # Convert DentApp API response to agent format
                    result = []
                    for api_section in api_sections:
                        # Map integer section_id back to string section_id
                        section_id_int = api_section.get('section_id')
                        section_id_str = None
                        
                        # Reverse lookup in Social Pitch section mapping
                        fallback_reverse_mapping = {
                            17: "name", 18: "same", 19: "fame", 
                            20: "pain", 21: "aim", 22: "game"
                        }
                        section_id_str = fallback_reverse_mapping.get(section_id_int)
                                
                        if section_id_str:
                            result.append({
                                'section_id': section_id_str,
                                'status': 'done' if api_section.get('is_completed', False) else 'pending',
                                'score': api_section.get('score'),
                                'has_content': bool(api_section.get('content', '').strip()),
                                'updated_at': api_section.get('updated_at'),
                            })
                    
                    logger.info(f"DATABASE_DEBUG: ✅ Successfully converted {len(result)} Social Pitch sections from DentApp API")
                else:
                    logger.warning("DATABASE_DEBUG: ⚠️ DentApp API returned None")
                    raise Exception("DentApp API returned None")
                    
            except Exception as dentapp_error:
                logger.warning(f"DATABASE_DEBUG: ⚠️ DentApp API failed: {dentapp_error}")
                logger.debug("DATABASE_DEBUG: Using empty result")
                result = []
        else:
            logger.warning("DATABASE_DEBUG: ⚠️ DentApp API disabled, using default empty result")
            result = []
        
        # Convert database results to expected format
        logger.debug("DATABASE_DEBUG: Processing database results to Social Pitch section status format")
        sections = []
        existing_sections = {row['section_id']: row for row in result} if result else {}
        logger.debug(f"DATABASE_DEBUG: Found existing Social Pitch sections in DB: {list(existing_sections.keys())}")
        
        # Ensure all required sections are represented
        logger.debug("DATABASE_DEBUG: Processing all required Social Pitch sections from SectionID enum")
        for section_id in SectionID:
            # Skip implementation section in status checks
            if section_id == SectionID.IMPLEMENTATION:
                continue
                
            if section_id.value in existing_sections:
                row = existing_sections[section_id.value]
                logger.debug(f"DATABASE_DEBUG: Processing existing Social Pitch section {section_id.value} - status: {row.get('status')}, score: {row.get('score')}")
                sections.append({
                    "section_id": section_id.value,
                    "status": row.get('status', SectionStatus.PENDING.value),
                    "score": row.get('score'),
                    "has_content": row.get('has_content', False),
                    "updated_at": row.get('updated_at'),
                })
            else:
                # Section doesn't exist in database yet
                logger.debug(f"DATABASE_DEBUG: Social Pitch section {section_id.value} not found in DB, creating default entry")
                sections.append({
                    "section_id": section_id.value,
                    "status": SectionStatus.PENDING.value,
                    "score": None,
                    "has_content": False,
                    "updated_at": None,
                })
        
        logger.info(f"DATABASE_DEBUG: ✅ Retrieved status for {len(sections)} Social Pitch sections total")
        logger.debug(f"DATABASE_DEBUG: Final Social Pitch sections summary: {[(s['section_id'], s['status']) for s in sections]}")
        return sections
        
    except Exception as e:
        logger.error(f"Error in get_all_sections_status for Social Pitch: {e}")
        # Return mock data on error
        sections = []
        for section_id in SectionID:
            if section_id == SectionID.IMPLEMENTATION:
                continue
            sections.append({
                "section_id": section_id.value,
                "status": SectionStatus.PENDING.value,
                "score": None,
                "has_content": False,
                "updated_at": None,
            })
        return sections


@tool
async def export_checklist(
    user_id: int,
    thread_id: str,
    pitch_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Export completed Social Pitch as a formatted deliverable.
    
    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier
        pitch_data: Complete Social Pitch data
    
    Returns:
        Export result with download URL
    """
    logger.info(f"Exporting Social Pitch checklist for doc {thread_id}")
    
    try:
        # First, verify that all required sections are complete
        sections_status = await get_all_sections_status.ainvoke({
            "user_id": user_id,
            "thread_id": thread_id
        })
        
        incomplete_sections = [
            s["section_id"] for s in sections_status 
            if s["status"] != SectionStatus.DONE.value and s["section_id"] != "implementation"
        ]
        
        if incomplete_sections:
            return {
                "success": False,
                "error": f"Cannot export: incomplete sections: {', '.join(incomplete_sections)}",
                "incomplete_sections": incomplete_sections,
            }
        
        current_time = datetime.utcnow().isoformat() + "Z"
        
        # Try DentApp API export first (if enabled)
        if settings.USE_DENTAPP_API:
            logger.debug("DATABASE_DEBUG: ✅ DentApp API enabled, attempting Social Pitch export via API")
            try:
                log_api_operation("export_checklist", user_id=user_id, thread_id=thread_id, 
                                user_id_int=user_id)
                
                # Call DentApp API export
                dentapp_client = get_dentapp_client()
                async with dentapp_client as client:
                    export_result = await client.export_agent_data(
                        user_id=user_id,
                        agent_id=SOCIAL_PITCH_AGENT_ID
                    )
                
                if export_result:
                    logger.info("DATABASE_DEBUG: ✅ Successfully exported Social Pitch via DentApp API")
                    
                    # Return export result using DentApp API response
                    return {
                        "success": True,
                        "format": "json",  # DentApp API provides structured data
                        "url": f"/api/dentapp/exports/{user_id}/{SOCIAL_PITCH_AGENT_ID}",  # Mock URL
                        "content": export_result.get('pitch_data', {}),
                        "generated_at": export_result.get('exported_at', current_time),
                        "total_sections": export_result.get('total_sections', 0),
                        "total_assets": export_result.get('total_assets', 0),
                        "summary": export_result.get('summary', {}),
                    }
                else:
                    logger.warning("DATABASE_DEBUG: ⚠️ DentApp API export failed, falling back to legacy")
                    raise Exception("DentApp API export returned None")
                    
            except Exception as dentapp_error:
                logger.warning(f"DATABASE_DEBUG: ⚠️ DentApp API export failed: {dentapp_error}")
                logger.debug("DATABASE_DEBUG: Using legacy Social Pitch export...")
                
                # Fallback to legacy export using pitch_data
                checklist_content = _generate_social_pitch_content(pitch_data)
                
                logger.info(f"Successfully exported Social Pitch checklist via legacy method for doc {thread_id}")
                
                return {
                    "success": True,
                    "format": "text",  # Legacy text format
                    "url": f"/api/exports/{thread_id}/social-pitch.txt",  # Mock URL
                    "content": checklist_content,
                    "generated_at": current_time,
                }
        else:
            logger.warning("DATABASE_DEBUG: ⚠️ DentApp API disabled, using legacy Social Pitch export")
            # Generate Social Pitch content from pitch data
            checklist_content = _generate_social_pitch_content(pitch_data)
            
            logger.info(f"Successfully exported Social Pitch checklist via legacy method for doc {thread_id}")
            
            return {
                "success": True,
                "format": "text",  # Legacy text format
                "url": f"/api/exports/{thread_id}/social-pitch.txt",  # Mock URL
                "content": checklist_content,
                "generated_at": current_time,
            }
        
    except Exception as e:
        logger.error(f"Error exporting Social Pitch checklist: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def _generate_social_pitch_content(pitch_data: dict[str, Any]) -> str:
    """
    Generate Social Pitch deliverable content from pitch data.
    
    Args:
        pitch_data: Complete Social Pitch data
    
    Returns:
        Formatted Social Pitch content
    """
    content = "# Your Complete Social Pitch\\n\\n"
    
    # NAME Component
    if pitch_data.get('user_name') and pitch_data.get('user_position') and pitch_data.get('company_name'):
        content += "## NAME (Clarity & Presence)\\n"
        content += f"**My name is {pitch_data['user_name']}, I'm the {pitch_data['user_position']} of a company called {pitch_data['company_name']}.**\\n\\n"
    
    # SAME Component
    if pitch_data.get('same_statement'):
        content += "## SAME (Instant Understanding)\\n"
        content += f"**{pitch_data['same_statement']}**\\n\\n"
    
    # FAME Component
    if pitch_data.get('fame_statement'):
        content += "## FAME (Differentiation)\\n"
        content += f"**{pitch_data['fame_statement']}**\\n\\n"
    
    # PAIN Component
    if pitch_data.get('pain_statement'):
        content += "## PAIN (Recognition)\\n"
        content += f"**{pitch_data['pain_statement']}**\\n\\n"
    
    # AIM Component
    if pitch_data.get('aim_statement'):
        content += "## AIM (Momentum)\\n"
        content += f"**{pitch_data['aim_statement']}**\\n\\n"
    
    # GAME Component
    if pitch_data.get('game_statement'):
        content += "## GAME (Purpose)\\n"
        content += f"**{pitch_data['game_statement']}**\\n\\n"
    
    # Complete Pitch
    content += "## Your Complete Social Pitch\\n\\n"
    if pitch_data.get('complete_pitch'):
        content += f"{pitch_data['complete_pitch']}\\n\\n"
    else:
        # Generate from components
        components = []
        if pitch_data.get('user_name'): components.append(f"My name is {pitch_data['user_name']}, I'm the {pitch_data['user_position']} of a company called {pitch_data['company_name']}.")
        if pitch_data.get('same_statement'): components.append(pitch_data['same_statement'])
        if pitch_data.get('fame_statement'): components.append(pitch_data['fame_statement'])
        if pitch_data.get('pain_statement'): components.append(pitch_data['pain_statement'])
        if pitch_data.get('aim_statement'): components.append(pitch_data['aim_statement'])
        if pitch_data.get('game_statement'): components.append(pitch_data['game_statement'])
        
        if components:
            content += " ".join(components) + "\\n\\n"
    
    # Usage Guidelines
    content += "## The Golf Bag Approach\\n\\n"
    content += "Think Golf Bag, Not Elevator Speech: Don't dump all six components on every conversation. Pick the right tool for each shot:\\n\\n"
    content += "- **Casual Networking:** NAME + SAME + FAME, then listen\\n"
    content += "- **Follow-up Interest:** Add PAIN + AIM to build momentum\\n"
    content += "- **Formal Introduction:** Deploy the complete framework\\n"
    content += "- **Podcast/Stage:** All six components in sequence\\n\\n"
    content += "**The Key:** Drill until instinctive, deploy naturally. You get what you pitch for, and you're always pitching.\\n\\n"
    
    # Implementation steps
    content += "## Next Steps\\n\\n"
    content += "1. Practice each component individually until natural\\n"
    content += "2. Test different combinations in real conversations\\n"
    content += "3. Pay attention to which components generate the most interest\\n"
    content += "4. Adjust based on audience and context\\n"
    content += "5. Remember: Market testing beats mind testing\\n"
    
    return content


@tool
async def create_tiptap_content(
    text: str,
    format_type: str = "paragraph",
) -> dict[str, Any]:
    """
    Create Tiptap JSON content from plain text.
    
    Args:
        text: Plain text content
        format_type: Type of formatting (paragraph, heading, list)
    
    Returns:
        Tiptap JSON document
    """
    content = []
    
    if format_type == "paragraph":
        content.append({
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        })
    elif format_type == "heading":
        content.append({
            "type": "heading",
            "attrs": {"level": 2},
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        })
    elif format_type == "list":
        items = text.split("\\n")
        list_items = []
        for item in items:
            if item.strip():
                list_items.append({
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": item.strip(),
                                }
                            ],
                        }
                    ],
                })
        content.append({
            "type": "bulletList",
            "content": list_items,
        })
    
    return {
        "type": "doc",
        "content": content,
    }


@tool
async def extract_plain_text(tiptap_json: dict[str, Any]) -> str:
    """
    Extract plain text from Tiptap JSON content.
    
    Args:
        tiptap_json: Tiptap JSON document
    
    Returns:
        Plain text string
    """
    def extract_text_from_node(node: dict[str, Any]) -> str:
        text_parts = []
        
        node_type = node.get("type")
        
        if node_type == "text":
            text_parts.append(node.get("text", ""))
        elif node_type == "hardBreak":
            text_parts.append("\\n")

        if "content" in node and isinstance(node["content"], list):
            for child in node["content"]:
                text_parts.append(extract_text_from_node(child))
        
        return "".join(text_parts)
    
    # Validate input with Pydantic model
    try:
        doc = TiptapDocument.model_validate(tiptap_json)
        return extract_text_from_node(doc.model_dump()).strip()
    except Exception as e:
        logger.error(f"Error validating or extracting text from Tiptap JSON: {e}")
        # Fallback for old format if validation fails
        return extract_text_from_node(tiptap_json).strip()


# Export all tools
__all__ = [
    "get_context",
    "save_section",
    "validate_field",
    "export_checklist",
    "get_all_sections_status",
    "create_tiptap_content",
    "extract_plain_text",
]