"""Tools for Value Canvas Agent."""

import logging
import uuid
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from core.settings import settings
from integrations.dentapp.dentapp_client import get_dentapp_client
from integrations.dentapp.dentapp_utils import (
    AGENT_ID,
    SECTION_ID_MAPPING,
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
from .sections import BASE_RULES, SECTION_TEMPLATES

logger = logging.getLogger(__name__)



@tool
async def get_context(
    user_id: int,
    thread_id: str,
    section_id: str,
    canvas_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get context packet for a specific Value Canvas section.
    
    This tool fetches section data from the database and generates
    the appropriate system prompt based on the section template.
    
    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier
        section_id: Section identifier (e.g., 'icp', 'pain_1')
        canvas_data: Current canvas data for template rendering
    
    Returns:
        Context packet with system prompt and draft content
    """
    logger.info("=== DATABASE_DEBUG: get_context() ENTRY ===")
    logger.info(f"DATABASE_DEBUG: Section: {section_id}, User: {user_id}, Thread: {thread_id}")
    logger.debug(f"DATABASE_DEBUG: User ID type: {type(user_id)}, Thread ID type: {type(thread_id)}")
    logger.debug(f"DATABASE_DEBUG: Canvas data provided: {bool(canvas_data)}")
    
    # Get section template
    template = SECTION_TEMPLATES.get(section_id)
    if not template:
        raise ValueError(f"Unknown section ID: {section_id}")
    
    # Generate system prompt
    base_prompt = BASE_RULES
    section_prompt = template.system_prompt_template
    
    # Render template with canvas data if provided
    # --- SAFE PARTIAL TEMPLATE RENDERING ---------------------------------
    if canvas_data is None:
        canvas_data = {}

    # Allow partial rendering: missing keys will be replaced with empty string
    import re
    def _replace_placeholder(match):
        key = match.group(1)
        value = canvas_data.get(key, "") if isinstance(canvas_data, dict) else ""
        
        # Special handling for Pain section progress indicators
        if section_id == "pain" and key.startswith("pain") and key.endswith("_symptom"):
            # Check if we have conditional logic in the template
            if " if " in match.group(0):
                # This is a conditional placeholder, let it handle itself
                return match.group(0)
        
        if not value:
            logger.debug(f"Template placeholder '{{{{{key}}}}}' not found in canvas_data, replacing with empty string")
        return str(value)

    # First pass: Replace simple placeholders like {{identifier}}
    section_prompt = re.sub(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}", _replace_placeholder, section_prompt)
    
    # Second pass: Handle conditional placeholders for Pain section
    # These are in format: {{pain1_symptom if pain1_symptom else "Not yet collected"}}
    if section_id == "pain":
        def _replace_conditional(match):
            full_expr = match.group(1)
            # Parse the conditional expression
            if " if " in full_expr and " else " in full_expr:
                parts = full_expr.split(" if ")
                if len(parts) == 2:
                    var_part = parts[0].strip()
                    condition_else = parts[1].split(" else ")
                    if len(condition_else) == 2:
                        var_name = condition_else[0].strip()
                        else_value = condition_else[1].strip().strip('"').strip("'")
                        # Get the value from canvas_data
                        value = canvas_data.get(var_name, "")
                        return str(value) if value else else_value
            return match.group(0)
        
        # Replace conditional placeholders
        section_prompt = re.sub(r"\{\{([^}]+)\}\}", _replace_conditional, section_prompt)
    
    system_prompt = f"{base_prompt}\\n\\n---\\n\\n{section_prompt}"
    
    # Fetch draft from database
    logger.debug("DATABASE_DEBUG: Starting database fetch for existing section state...")
    draft = None
    status = "pending"
    
    # Try DentApp API first (if enabled)
    if settings.USE_DENTAPP_API:
        logger.info("=== TOOLS_API_CALL: get_context() using DentApp API ===")
        logger.info(f"TOOLS_API_CALL: section_id='{section_id}', user_id='{user_id}', thread_id='{thread_id}'")
        try:
            # Convert section_id for DentApp API (MVP: always use user_id=1)
            section_id_int = get_section_id_int(section_id)
            
            if section_id_int is None:
                logger.error(f"TOOLS_API_CALL: ❌ Invalid section_id: {section_id}")
                raise ValueError(f"Unknown section ID: {section_id}")
            
            logger.info(f"TOOLS_API_CALL: Mapped section_id '{section_id}' -> {section_id_int}")
            log_api_operation("get_context", user_id=user_id, section_id=section_id, 
                            user_id_int=user_id, section_id_int=section_id_int)
            
            # Call DentApp API
            logger.info(f"TOOLS_API_CALL: Calling get_section_state(agent_id={AGENT_ID}, section_id={section_id_int}, user_id={user_id})")
            dentapp_client = get_dentapp_client()
            async with dentapp_client as client:
                result = await client.get_section_state(
                    agent_id=AGENT_ID,
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
    satisfaction_feedback: str | None = None,
    status: str = "done",
) -> dict[str, Any]:
    """
    Save or update a Value Canvas section in the database.
    
    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier
        section_id: Section identifier
        content: Section content (Tiptap JSON)
        satisfaction_feedback: Optional user satisfaction feedback text
        status: Section status
    
    Returns:
        Updated section state
    """
    logger.info("=== DATABASE_DEBUG: save_section() ENTRY ===")
    logger.info(f"DATABASE_DEBUG: Saving section {section_id} for user {user_id}, doc {thread_id}")
    logger.debug(f"DATABASE_DEBUG: User ID type: {type(user_id)}, Thread ID type: {type(thread_id)}")
    logger.debug(f"DATABASE_DEBUG: Content type: {type(content)}, Satisfaction feedback: {satisfaction_feedback}, Status: {status}")
    
    # [DIAGNOSTIC] Log all parameters passed to save_section
    logger.info(
        f"DATABASE_DEBUG: Full parameters - "
        f"user_id={user_id}, thread_id={thread_id}, section_id='{section_id}', "
        f"satisfaction_feedback={satisfaction_feedback}, status='{status}'"
    )
    logger.debug(f"DATABASE_DEBUG: Content structure: {content}")

    current_time = datetime.utcnow().isoformat() + "Z"
    logger.debug(f"DATABASE_DEBUG: Generated timestamp: {current_time}")
    
    # Try DentApp API first (if enabled)
    if settings.USE_DENTAPP_API:
        logger.info("=== TOOLS_API_CALL: save_section() using DentApp API ===")
        logger.info(f"TOOLS_API_CALL: section_id='{section_id}', user_id='{user_id}', thread_id='{thread_id}', satisfaction_feedback={satisfaction_feedback}, status='{status}'")
        try:
            # Convert section_id for DentApp API (MVP: always use user_id=1)
            section_id_int = get_section_id_int(section_id)
            
            if section_id_int is None:
                logger.error(f"TOOLS_API_CALL: ❌ Invalid section_id: {section_id}")
                raise ValueError(f"Unknown section ID: {section_id}")
            
            # Convert Tiptap content to plain text
            plain_text = tiptap_to_plain_text(content) if content else ""
            logger.info(f"TOOLS_API_CALL: Mapped section_id '{section_id}' -> {section_id_int}")
            logger.info(f"TOOLS_API_CALL: Converted content length: {len(plain_text)} chars")
            
            log_api_operation("save_section", user_id=user_id, section_id=section_id, 
                            user_id_int=user_id, section_id_int=section_id_int,
                            content_length=len(plain_text), satisfaction_feedback=satisfaction_feedback, status=status)
            
            # Call DentApp API
            logger.info(f"TOOLS_API_CALL: Calling save_section_state(agent_id={AGENT_ID}, section_id={section_id_int}, user_id={user_id})")
            dentapp_client = get_dentapp_client()
            async with dentapp_client as client:
                result = await client.save_section_state(
                    agent_id=AGENT_ID,
                    section_id=section_id_int,
                    user_id=user_id,
                    content=plain_text,
                    metadata={}  # Empty metadata for MVP
                )
            logger.info(f"TOOLS_API_CALL: save_section_state returned: {result is not None}")
            
            if result:
                logger.info(f"DATABASE_DEBUG: ✅ Successfully saved section {section_id} via DentApp API")
                
                # Return response compatible with existing agent code
                return {
                    "id": str(result.get('id', uuid.uuid4())),
                    "user_id": user_id,
                    "thread_id": thread_id,
                    "section_id": section_id,
                    "content": content,  # Return original Tiptap format
                    "satisfaction_feedback": satisfaction_feedback,
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
                "satisfaction_feedback": satisfaction_feedback,
                "status": status,
                "updated_at": current_time,
            }
    else:
        # DentApp API disabled, use mock response
        logger.warning(f"DATABASE_DEBUG: ⚠️ DentApp API disabled, using mock response for section {section_id}")
        return {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "thread_id": thread_id,
            "section_id": section_id,
            "content": content,
            "satisfaction_feedback": satisfaction_feedback,
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
    Get status of all Value Canvas sections for a document.
    
    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier
    
    Returns:
        List of section states with status
    """
    logger.info("=== DATABASE_DEBUG: get_all_sections_status() ENTRY ===")
    logger.info(f"DATABASE_DEBUG: Getting all section status for user {user_id}, doc {thread_id}")
    
    try:
        # Try DentApp API first (if enabled)
        if settings.USE_DENTAPP_API:
            logger.debug("DATABASE_DEBUG: ✅ DentApp API enabled, attempting to fetch all sections status")
            try:
                log_api_operation("get_all_sections_status", user_id=user_id, thread_id=thread_id, 
                                user_id_int=user_id)
                
                # Call DentApp API
                dentapp_client = get_dentapp_client()
                async with dentapp_client as client:
                    api_result = await client.get_all_sections_status(
                        agent_id=AGENT_ID,
                        user_id=user_id
                    )
                
                if api_result:
                    logger.info("DATABASE_DEBUG: ✅ Retrieved DentApp API response")
                    
                    # Extract sections data from DentApp API response
                    # The API returns a structured response with sections information
                    api_sections = api_result.get('sections', [])
                    logger.info(f"DATABASE_DEBUG: DentApp API returned {len(api_sections)} sections")
                    
                    # Convert DentApp API response to agent format
                    result = []
                    for api_section in api_sections:
                        # Map integer section_id back to string section_id
                        section_id_int = api_section.get('section_id')
                        section_id_str = None
                        
                        # Reverse lookup in section mapping
                        for str_id, int_id in SECTION_ID_MAPPING.items():
                            if int_id == section_id_int:
                                section_id_str = str_id
                                break
                                
                        if section_id_str:
                            result.append({
                                'section_id': section_id_str,
                                'status': 'done' if api_section.get('is_completed', False) else 'pending',
                                'score': api_section.get('score'),
                                'has_content': bool(api_section.get('content', '').strip()),
                                'updated_at': api_section.get('updated_at'),
                            })
                    
                    logger.info(f"DATABASE_DEBUG: ✅ Successfully converted {len(result)} sections from DentApp API")
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
        logger.debug("DATABASE_DEBUG: Processing database results to section status format")
        sections = []
        existing_sections = {row['section_id']: row for row in result} if result else {}
        logger.debug(f"DATABASE_DEBUG: Found existing sections in DB: {list(existing_sections.keys())}")
        
        # Ensure all required sections are represented
        logger.debug("DATABASE_DEBUG: Processing all required sections from SectionID enum")
        for section_id in SectionID:
            if section_id.value in existing_sections:
                row = existing_sections[section_id.value]
                logger.debug(f"DATABASE_DEBUG: Processing existing section {section_id.value} - status: {row.get('status')}, score: {row.get('score')}")
                sections.append({
                    "section_id": section_id.value,
                    "status": row.get('status', SectionStatus.PENDING.value),
                    "satisfaction_feedback": row.get('satisfaction_feedback'),
                    "has_content": row.get('has_content', False),
                    "updated_at": row.get('updated_at'),
                })
            else:
                # Section doesn't exist in database yet
                logger.debug(f"DATABASE_DEBUG: Section {section_id.value} not found in DB, creating default entry")
                sections.append({
                    "section_id": section_id.value,
                    "status": SectionStatus.PENDING.value,
                    "satisfaction_feedback": None,
                    "has_content": False,
                    "updated_at": None,
                })
        
        logger.info(f"DATABASE_DEBUG: ✅ Retrieved status for {len(sections)} sections total")
        logger.debug(f"DATABASE_DEBUG: Final sections summary: {[(s['section_id'], s['status']) for s in sections]}")
        return sections
        
    except Exception as e:
        logger.error(f"Error in get_all_sections_status: {e}")
        # Return mock data on error
        sections = []
        for section_id in SectionID:
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
    canvas_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Export completed Value Canvas as a checklist/PDF.
    
    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier
        canvas_data: Complete canvas data
    
    Returns:
        Export result with download URL
    """
    logger.info(f"Exporting checklist for doc {thread_id}")
    
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
            logger.debug("DATABASE_DEBUG: ✅ DentApp API enabled, attempting export via API")
            try:
                log_api_operation("export_checklist", user_id=user_id, thread_id=thread_id, 
                                user_id_int=user_id)
                
                # Call DentApp API export
                dentapp_client = get_dentapp_client()
                async with dentapp_client as client:
                    export_result = await client.export_agent_data(
                        user_id=user_id,
                        agent_id=AGENT_ID
                    )
                
                if export_result:
                    logger.info("DATABASE_DEBUG: ✅ Successfully exported via DentApp API")
                    
                    # Return export result using DentApp API response
                    return {
                        "success": True,
                        "format": "json",  # DentApp API provides structured data
                        "url": f"/api/dentapp/exports/{user_id}/{AGENT_ID}",  # Mock URL
                        "content": export_result.get('canvas_data', {}),
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
                logger.debug("DATABASE_DEBUG: Using legacy export...")
                
                # Fallback to legacy export using canvas_data
                checklist_content = _generate_checklist_content(canvas_data)
                
                logger.info(f"Successfully exported checklist via legacy method for doc {thread_id}")
                
                return {
                    "success": True,
                    "format": "text",  # Legacy text format
                    "url": f"/api/exports/{thread_id}/checklist.txt",  # Mock URL
                    "content": checklist_content,
                    "generated_at": current_time,
                }
        else:
            logger.warning("DATABASE_DEBUG: ⚠️ DentApp API disabled, using legacy export")
            # Generate checklist content from canvas data
            checklist_content = _generate_checklist_content(canvas_data)
            
            logger.info(f"Successfully exported checklist via legacy method for doc {thread_id}")
            
            return {
                "success": True,
                "format": "text",  # Legacy text format
                "url": f"/api/exports/{thread_id}/checklist.txt",  # Mock URL
                "content": checklist_content,
                "generated_at": current_time,
            }
        
    except Exception as e:
        logger.error(f"Error exporting checklist: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def _generate_checklist_content(canvas_data: dict[str, Any]) -> str:
    """
    Generate implementation checklist content from canvas data.
    
    Args:
        canvas_data: Complete Value Canvas data
    
    Returns:
        Formatted checklist content
    """
    content = "# Value Canvas Implementation Checklist\\n\\n"
    
    # ICP Section
    if canvas_data.get('icp_nickname'):
        content += f"## Target Customer: {canvas_data['icp_nickname']}\\n"
        content += f"- Demographics: {canvas_data.get('icp_demographics', 'Not specified')}\\n"
        content += f"- Geography: {canvas_data.get('icp_geography', 'Not specified')}\\n\\n"
    
    # Pain Points
    content += "## Pain Points to Address:\\n"
    for i in range(1, 4):
        pain_symptom = canvas_data.get(f'pain{i}_symptom')
        if pain_symptom:
            content += f"{i}. {pain_symptom}\\n"
    content += "\\n"
    
    # Payoffs
    content += "## Expected Outcomes:\\n"
    for i in range(1, 4):
        payoff_objective = canvas_data.get(f'payoff{i}_objective')
        if payoff_objective:
            content += f"{i}. {payoff_objective}\\n"
    content += "\\n"
    
    # Signature Method
    if canvas_data.get('method_name'):
        content += f"## Signature Method: {canvas_data['method_name']}\\n"
        principles = canvas_data.get('sequenced_principles', [])
        for i, principle in enumerate(principles, 1):
            content += f"{i}. {principle}\\n"
        content += "\\n"
    
    # Prize
    if canvas_data.get('refined_prize'):
        content += f"## Transformation Promise:\\n{canvas_data['refined_prize']}\\n\\n"
    
    # Implementation steps
    content += "## Next Steps:\\n"
    content += "1. Review and validate this Value Canvas with your team\\n"
    content += "2. Create marketing materials based on these insights\\n"
    content += "3. Test messaging with target customers\\n"
    content += "4. Iterate based on feedback\\n"
    content += "5. Scale successful messaging across all channels\\n"
    
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