"""Tools for Value Canvas Agent with Supabase integration."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from supabase import create_client, Client

from agents.value_canvas_models import (
    ContextPacket,
    SectionContent,
    SectionID,
    SectionState,
    SectionStatus,
    TiptapDocument,
    ValidationRule,
)
from agents.value_canvas_prompts import SECTION_PROMPTS, SECTION_TEMPLATES
from core.settings import settings

logger = logging.getLogger(__name__)

# Initialize Supabase client
def get_supabase_client() -> Client:
    """Get configured Supabase client."""
    supabase_url = getattr(settings, 'SUPABASE_URL', None)
    supabase_key = getattr(settings, 'SUPABASE_ANON_KEY', None)
    
    # Convert SecretStr to string if needed
    if supabase_url and hasattr(supabase_url, 'get_secret_value'):
        supabase_url = supabase_url.get_secret_value()
    if supabase_key and hasattr(supabase_key, 'get_secret_value'):
        supabase_key = supabase_key.get_secret_value()
    
    if not supabase_url or not supabase_key:
        logger.warning("Supabase credentials not configured, using mock mode")
        return None
    
    return create_client(supabase_url, supabase_key)


@tool
async def get_context(
    user_id: str,
    doc_id: str,
    section_id: str,
    canvas_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Get context packet for a specific Value Canvas section.
    
    This tool fetches section data from the database and generates
    the appropriate system prompt based on the section template.
    
    Args:
        user_id: User identifier
        doc_id: Document identifier
        section_id: Section identifier (e.g., 'icp', 'pain_1')
        canvas_data: Current canvas data for template rendering
    
    Returns:
        Context packet with system prompt and draft content
    """
    logger.info(f"Getting context for section {section_id} - user: {user_id}, doc: {doc_id}")
    
    # Get section template
    template = SECTION_TEMPLATES.get(section_id)
    if not template:
        raise ValueError(f"Unknown section ID: {section_id}")
    
    # Generate system prompt
    base_prompt = SECTION_PROMPTS.get("base_rules", "")
    section_prompt = template.system_prompt_template
    
    # Render template with canvas data if provided
    if canvas_data:
        try:
            section_prompt = section_prompt.format(**canvas_data)
        except KeyError as e:
            logger.warning(f"Missing keys in canvas_data for template rendering: {e}")
            # If some keys are missing, use what we have
            pass
    
    system_prompt = f"{base_prompt}\\n\\n---\\n\\n{section_prompt}"
    
    # Fetch draft from database using Supabase MCP
    draft = None
    status = "pending"
    
    try:
        # Use the Supabase MCP tool to query the database
        query = f"""
        SELECT content, status, score, updated_at
        FROM section_states 
        WHERE user_id = '{user_id}' 
          AND doc_id = '{doc_id}' 
          AND section_id = '{section_id}'
        LIMIT 1;
        """
        
        # Execute query using Supabase SDK
        supabase = get_supabase_client()
        if supabase:
            try:
                result = supabase.rpc('get_section_state', {
                    'p_user_id': user_id,
                    'p_doc_id': doc_id, 
                    'p_section_id': section_id
                }).execute()
                result = result.data if result.data else []
            except Exception as e:
                logger.error(f"Supabase query failed: {e}")
                result = []
        else:
            logger.info("Using mock data for development (no Supabase configured)")
            result = []
        
        if result and len(result) > 0:
            row = result[0]
            status = row.get('status', 'pending')
            content_data = row.get('content')
            
            if content_data and content_data != {'type': 'doc', 'content': []}:
                # Convert to SectionContent format
                draft = {
                    "content": content_data,
                    "plain_text": await extract_plain_text.ainvoke(content_data)
                }
                
        logger.info(f"Retrieved section state: status={status}, has_draft={draft is not None}")
        
    except Exception as e:
        logger.error(f"Error fetching section state: {e}")
        # Use defaults on error
    
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
    user_id: str,
    doc_id: str,
    section_id: str,
    content: Dict[str, Any],
    score: Optional[int] = None,
    status: str = "done",
) -> Dict[str, Any]:
    """
    Save or update a Value Canvas section in the database.
    
    Args:
        user_id: User identifier
        doc_id: Document identifier
        section_id: Section identifier
        content: Section content (Tiptap JSON)
        score: Optional satisfaction score (0-5)
        status: Section status
    
    Returns:
        Updated section state
    """
    logger.info(f"Saving section {section_id} for user {user_id}, doc {doc_id}")
    
    current_time = datetime.utcnow().isoformat() + "Z"
    
    # Execute query using Supabase SDK
    supabase = get_supabase_client()
    if supabase:
        try:
            # Use upsert for save_section
            result = supabase.table('section_states').upsert({
                'user_id': user_id,
                'doc_id': doc_id,
                'section_id': section_id,
                'content': content,
                'score': score,
                'status': status,
                'updated_at': current_time
            }).execute()
            
            if result.data and len(result.data) > 0:
                row = result.data[0]
                logger.info(f"Successfully saved section {section_id}")
                return {
                    "id": row.get('id'),
                    "user_id": row.get('user_id'),
                    "doc_id": row.get('doc_id'),
                    "section_id": row.get('section_id'),
                    "content": row.get('content'),
                    "score": row.get('score'),
                    "status": row.get('status'),
                    "updated_at": row.get('updated_at'),
                }
            else:
                logger.warning(f"No data returned from Supabase for section {section_id}")
                # Fall through to mock response
        except Exception as e:
            logger.error(f"Supabase operation failed: {e}")
            # Fall through to mock response
        
        # Mock response for development (both no Supabase config and Supabase errors)
        logger.info(f"Using mock response for section {section_id}")
        return {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "doc_id": doc_id,
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
    validation_rules: List[Dict[str, Any]],
) -> Dict[str, Any]:
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
    user_id: str,
    doc_id: str,
) -> List[Dict[str, Any]]:
    """
    Get status of all Value Canvas sections for a document.
    
    Args:
        user_id: User identifier
        doc_id: Document identifier
    
    Returns:
        List of section states with status
    """
    logger.info(f"Getting all section status for user {user_id}, doc {doc_id}")
    
    try:
        # Use the helper function from migration to get document sections
        query = f"""
        SELECT * FROM get_document_sections('{user_id}', '{doc_id}');
        """
        
        # Execute query using Supabase SDK
        supabase = get_supabase_client()
        if supabase:
            try:
                result = supabase.rpc('get_document_sections', {
                    'p_user_id': user_id,
                    'p_doc_id': doc_id
                }).execute()
                result = result.data if result.data else []
            except Exception as e:
                logger.error(f"Supabase query failed: {e}")
                result = []
        else:
            logger.info("Mock mode: returning empty sections list")
            result = []
        
        # Convert database results to expected format
        sections = []
        existing_sections = {row['section_id']: row for row in result} if result else {}
        
        # Ensure all required sections are represented
        for section_id in SectionID:
            if section_id.value in existing_sections:
                row = existing_sections[section_id.value]
                sections.append({
                    "section_id": section_id.value,
                    "status": row.get('status', SectionStatus.PENDING.value),
                    "score": row.get('score'),
                    "has_content": row.get('has_content', False),
                    "updated_at": row.get('updated_at'),
                })
            else:
                # Section doesn't exist in database yet
                sections.append({
                    "section_id": section_id.value,
                    "status": SectionStatus.PENDING.value,
                    "score": None,
                    "has_content": False,
                    "updated_at": None,
                })
        
        logger.info(f"Retrieved status for {len(sections)} sections")
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
    user_id: str,
    doc_id: str,
    canvas_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Export completed Value Canvas as a checklist/PDF.
    
    Args:
        user_id: User identifier
        doc_id: Document identifier
        canvas_data: Complete canvas data
    
    Returns:
        Export result with download URL
    """
    logger.info(f"Exporting checklist for doc {doc_id}")
    
    try:
        # First, verify that all required sections are complete
        sections_status = await get_all_sections_status.ainvoke({
            "user_id": user_id,
            "doc_id": doc_id
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
        
        # Generate checklist content from canvas data
        checklist_content = _generate_checklist_content(canvas_data)
        
        # For now, we'll store the checklist as a simple text file
        # In a full implementation, you'd generate a PDF using a library like weasyprint
        current_time = datetime.utcnow().isoformat() + "Z"
        
        # Update the document as completed
        update_query = f"""
        UPDATE value_canvas_documents 
        SET completed = true, completed_at = NOW(), export_url = 'generated'
        WHERE id = '{doc_id}' AND user_id = '{user_id}';
        """
        
        # Execute query using Supabase SDK
        supabase = get_supabase_client()
        if supabase:
            try:
                supabase.table('value_canvas_documents').update({
                    'completed': True,
                    'completed_at': datetime.now().isoformat(),
                    'export_url': 'generated'
                }).eq('id', doc_id).eq('user_id', user_id).execute()
            except Exception as e:
                logger.error(f"Supabase update failed: {e}")
        else:
            logger.info("Mock mode: document marked as completed")
        
        logger.info(f"Successfully exported checklist for doc {doc_id}")
        
        return {
            "success": True,
            "format": "text",  # Would be "pdf" in full implementation
            "url": f"/api/exports/{doc_id}/checklist.txt",  # Mock URL
            "content": checklist_content,
            "generated_at": current_time,
        }
        
    except Exception as e:
        logger.error(f"Error exporting checklist: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def _generate_checklist_content(canvas_data: Dict[str, Any]) -> str:
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
) -> Dict[str, Any]:
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
async def extract_plain_text(tiptap_json: Dict[str, Any]) -> str:
    """
    Extract plain text from Tiptap JSON content.
    
    Args:
        tiptap_json: Tiptap JSON document
    
    Returns:
        Plain text string
    """
    def extract_text_from_node(node: Dict[str, Any]) -> str:
        text_parts = []
        
        if node.get("type") == "text":
            text_parts.append(node.get("text", ""))
        
        if "content" in node and isinstance(node["content"], list):
            for child in node["content"]:
                text_parts.append(extract_text_from_node(child))
        
        return " ".join(text_parts)
    
    return extract_text_from_node(tiptap_json).strip()


# Helper function to execute SQL queries
async def _execute_sql_query(query: str) -> List[Dict[str, Any]]:
    """
    Execute SQL query using Supabase MCP tool.
    
    Args:
        query: SQL query to execute
    
    Returns:
        Query results as list of dictionaries
    """
    try:
        logger.info(f"Executing SQL query: {query[:100]}...")
        supabase = get_supabase_client()
        if supabase:
            # This is a generic SQL execution function - would need specific implementation
            # For now, return empty result in development mode
            logger.warning("Generic SQL execution not implemented with Supabase SDK")
            return []
        else:
            logger.info("Mock mode: returning empty SQL result")
            return []
        
    except Exception as e:
        logger.error(f"Error executing SQL query: {e}")
        return []


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