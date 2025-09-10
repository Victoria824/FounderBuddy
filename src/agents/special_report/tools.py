"""Tools for Special Report Agent."""

import logging
from typing import Any

from langchain_core.tools import tool

from core.settings import settings
from integrations.dentapp.dentapp_client import get_dentapp_client
from integrations.dentapp.dentapp_utils import (
    get_section_id_int,
    tiptap_to_plain_text,
)

from .models import SectionStatus

logger = logging.getLogger(__name__)

# Special Report uses agent ID 6
SPECIAL_REPORT_AGENT_ID = 6


@tool
async def get_context(
    user_id: int,
    section_id: str,
    thread_id: str,
    canvas_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get context packet for a specific Special Report section."""
    logger.info(f"Getting context for section {section_id}, user {user_id}, thread {thread_id}")

    # Get section template from framework
    from .framework_templates import FRAMEWORK_TEMPLATES

    template = FRAMEWORK_TEMPLATES.get(section_id)
    if not template:
        raise ValueError(f"Unknown section ID: {section_id}")

    # Generate system prompt with placeholder handling
    from .prompts import BASE_RULES

    base_prompt = BASE_RULES
    # Extract the system_prompt_template from the SectionTemplate object
    section_prompt = template.system_prompt_template if hasattr(template, 'system_prompt_template') else str(template)

    # Render template with canvas data if provided
    if canvas_data is None:
        canvas_data = {}

    # Allow partial rendering: missing keys will be replaced with empty string
    import re

    def _replace_placeholder(match):
        key = match.group(1)
        return str(canvas_data.get(key, "")) if isinstance(canvas_data, dict) else ""

    # Only replace simple placeholders like {identifier}, keep other braces unchanged
    section_prompt = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", _replace_placeholder, section_prompt)

    system_prompt = f"{base_prompt}\\n\\n---\\n\\n{section_prompt}"

    # Fetch draft from database
    draft = None
    status = SectionStatus.PENDING.value

    if settings.USE_DENTAPP_API:
        try:
            section_id_int = get_section_id_int(section_id)
            if section_id_int is None:
                raise ValueError(f"Unknown section ID: {section_id}")

            client = get_dentapp_client()
            response = await client.get_section_state(
                agent_id=SPECIAL_REPORT_AGENT_ID,
                section_id=section_id_int,
                user_id=user_id,
            )

            if response and response.get("content"):
                draft = {
                    "content": response["content"],
                    "plain_text": tiptap_to_plain_text(response["content"])
                    if response.get("content")
                    else None,
                }

                score = response.get("score")
                if score is not None and score >= 3:
                    status = SectionStatus.DONE.value
                elif response.get("content"):
                    status = SectionStatus.IN_PROGRESS.value
                else:
                    status = SectionStatus.PENDING.value

        except Exception as e:
            logger.error(f"DentApp API error in get_context: {e}")

    return {
        "section_id": section_id,
        "status": status,
        "system_prompt": system_prompt,
        "draft": draft,
        "validation_rules": {},
    }


@tool
async def get_all_section_status(user_id: int, thread_id: str) -> dict[str, str]:
    """Get status of all sections."""
    from .framework_templates import FRAMEWORK_TEMPLATES

    status_map = {}

    # Check all sections
    for section_id in FRAMEWORK_TEMPLATES.keys():
        try:
            # Use the same pattern as get_context
            if settings.USE_DENTAPP_API:
                section_id_int = get_section_id_int(section_id)
                if section_id_int is None:
                    status_map[section_id] = SectionStatus.PENDING.value
                    continue

                client = get_dentapp_client()
                response = await client.get_section_state(
                    agent_id=SPECIAL_REPORT_AGENT_ID,
                    section_id=section_id_int,
                    user_id=user_id,
                )

                if response and response.get("content"):
                    score = response.get("score")
                    if score is not None and score >= 3:
                        status_map[section_id] = SectionStatus.DONE.value
                    else:
                        status_map[section_id] = SectionStatus.IN_PROGRESS.value
                else:
                    status_map[section_id] = SectionStatus.PENDING.value
            else:
                status_map[section_id] = SectionStatus.PENDING.value
        except Exception as e:
            logger.error(f"Error getting status for section {section_id}: {e}")
            status_map[section_id] = SectionStatus.PENDING.value

    return status_map


@tool
async def save_section(
    user_id: int,
    thread_id: str,
    section_id: str,
    content: dict[str, Any],
    score: int | None = None,
    status: str = SectionStatus.IN_PROGRESS.value,
) -> dict[str, Any]:
    """Save section content to database."""
    logger.info(f"TOOLS_API_CALL: save_section() - section_id='{section_id}', user_id={user_id}")
    logger.info(f"TOOLS_API_CALL: score={score}, status='{status}'")

    if settings.USE_DENTAPP_API:
        try:
            # Convert section_id for DentApp API
            section_id_int = get_section_id_int(section_id)
            if section_id_int is None:
                raise ValueError(f"Unknown section ID: {section_id}")

            # CRITICAL: Use correct database methods (copy from value canvas)
            from integrations.dentapp.dentapp_utils import tiptap_to_plain_text

            plain_text = tiptap_to_plain_text(content) if content else ""

            dentapp_client = get_dentapp_client()
            async with dentapp_client as client:
                response = await client.save_section_state(  # ✅ Correct method name
                    agent_id=SPECIAL_REPORT_AGENT_ID,
                    section_id=section_id_int,
                    user_id=user_id,
                    content=plain_text,  # ✅ Convert to plain text
                    metadata={},
                )

            if response:
                logger.info(f"TOOLS_API_CALL: ✅ Successfully saved section {section_id}")
                return {"success": True, "section_id": section_id}
            else:
                raise Exception("Failed to save section to database")

        except Exception as e:
            logger.error(f"TOOLS_API_CALL: ❌ Database error: {e}")
            raise e

    # Fallback for development
    return {"success": True, "section_id": section_id}


@tool
async def create_tiptap_content(text: str) -> dict[str, Any]:
    """Create Tiptap JSON content from plain text."""
    paragraphs = text.split("\n\n")
    content = []

    for paragraph in paragraphs:
        if paragraph.strip():
            # Split by line breaks within paragraphs
            lines = paragraph.split("\n")
            paragraph_content = []

            for i, line in enumerate(lines):
                if line.strip():
                    paragraph_content.append({"type": "text", "text": line.strip()})
                    # Add hard break if not the last line
                    if i < len(lines) - 1:
                        paragraph_content.append({"type": "hardBreak"})

            if paragraph_content:
                content.append({"type": "paragraph", "content": paragraph_content})

    return {"type": "doc", "content": content}


@tool
async def extract_plain_text(tiptap_json: dict[str, Any]) -> str:
    """Extract plain text from Tiptap JSON."""
    try:
        return tiptap_to_plain_text(tiptap_json)
    except Exception as e:
        logger.error(f"Error extracting plain text: {e}")
        return str(tiptap_json)


@tool
async def validate_field(field_name: str, value: str, rules: list[dict]) -> dict[str, Any]:
    """Validate field value against rules."""
    errors = []

    for rule in rules:
        rule_type = rule.get("rule_type")
        rule_value = rule.get("value")
        error_message = rule.get("error_message", f"Validation failed for {field_name}")

        if rule_type == "required" and rule_value and not value:
            errors.append(error_message)
        elif rule_type == "min_length" and len(value) < rule_value:
            errors.append(error_message)
        elif rule_type == "max_length" and len(value) > rule_value:
            errors.append(error_message)
        elif rule_type == "choices" and value not in rule_value:
            errors.append(error_message)

    return {"valid": len(errors) == 0, "errors": errors}


@tool
async def export_report(
    user_id: int,
    thread_id: str,
    report_data: dict[str, Any],
) -> dict[str, Any]:
    """Export completed special report as PDF/document."""
    logger.info(f"Exporting special report for user {user_id}")

    try:
        # This would integrate with report generation service
        # For now, return a placeholder response
        return {
            "success": True,
            "url": f"https://example.com/reports/{user_id}/{thread_id}/special-report.pdf",
            "format": "pdf",
            "generated_at": "2024-01-01T00:00:00Z",
        }
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        return {"success": False, "error": str(e)}
