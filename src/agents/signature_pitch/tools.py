"""Tools for Signature Pitch Agent."""

import logging
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from core.settings import settings
from integrations.dentapp.dentapp_client import get_dentapp_client
from integrations.dentapp.dentapp_utils import (
    get_section_id_int,
    log_api_operation,
    tiptap_to_plain_text,
)

from .enums import SignaturePitchSectionID
from .prompts import BASE_RULES, SECTION_TEMPLATES

logger = logging.getLogger(__name__)

# Signature Pitch uses agent ID 5
SIGNATURE_PITCH_AGENT_ID = 5


@tool
async def get_context(
    user_id: int,
    thread_id: str,
    section_id: str,
    canvas_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get context packet for a specific Signature Pitch section.

    This tool fetches section data from the database and generates
    the appropriate system prompt based on the section template.

    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier
        section_id: Section identifier (e.g., 'active_change', 'specific_who')
        canvas_data: Current canvas data for template rendering

    Returns:
        Context packet with system prompt and draft content
    """
    logger.info("=== DATABASE_DEBUG: get_context() ENTRY ===")
    logger.info(f"DATABASE_DEBUG: Section: {section_id}, User: {user_id}, Thread: {thread_id}")
    logger.debug(
        f"DATABASE_DEBUG: User ID type: {type(user_id)}, Thread ID type: {type(thread_id)}"
    )
    logger.debug(f"DATABASE_DEBUG: Canvas data provided: {bool(canvas_data)}")

    # Get section template
    template = SECTION_TEMPLATES.get(section_id)
    if not template:
        raise ValueError(f"Unknown section ID: {section_id}")

    # Generate system prompt
    base_prompt = BASE_RULES
    section_prompt = template.system_prompt_template

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
    logger.debug("DATABASE_DEBUG: Starting database fetch for existing section state...")
    draft = None
    status = "pending"

    # Try DentApp API first (if enabled)
    if settings.USE_DENTAPP_API:
        logger.info("=== TOOLS_API_CALL: get_context() using DentApp API ===")
        logger.info(
            f"TOOLS_API_CALL: section_id='{section_id}', user_id='{user_id}', thread_id='{thread_id}'"
        )
        try:
            # Convert section_id for DentApp API
            section_id_int = get_section_id_int(section_id)

            if section_id_int is None:
                logger.error(f"TOOLS_API_CALL: ❌ Invalid section_id: {section_id}")
                raise ValueError(f"Unknown section ID: {section_id}")

            logger.info(f"TOOLS_API_CALL: Mapped section_id '{section_id}' -> {section_id_int}")

            # Get DentApp client and fetch data
            client = get_dentapp_client()
            response = await client.get_section_state(
                agent_id=SIGNATURE_PITCH_AGENT_ID,
                section_id=section_id_int,
                user_id=user_id,
            )

            log_api_operation(
                "get_context",
                "success",
                {
                    "section_id": section_id,
                    "section_id_int": section_id_int,
                    "user_id": user_id,
                    "thread_id": thread_id,
                    "response_data": bool(response),
                },
            )

            if response and response.get("content"):
                logger.info(f"TOOLS_API_CALL: ✅ Found existing data for section {section_id}")
                logger.debug(
                    f"TOOLS_API_CALL: Content preview: {str(response.get('content', ''))[:200]}..."
                )

                # Create draft content from database response
                draft = {
                    "content": response["content"],
                    "plain_text": tiptap_to_plain_text(response["content"])
                    if response.get("content")
                    else None,
                }

                # Determine status based on score
                score = response.get("score")
                if score is not None and score >= 3:
                    status = "done"
                elif response.get("content"):
                    status = "in_progress"
                else:
                    status = "pending"

                logger.info(f"TOOLS_API_CALL: Status determined: {status} (score: {score})")
            else:
                logger.info(f"TOOLS_API_CALL: ✅ No existing data for section {section_id}")

        except Exception as e:
            logger.error(f"TOOLS_API_CALL: ❌ DentApp API error in get_context: {e}")
            log_api_operation("get_context", section_id=section_id, status="error", error=str(e))
            # Continue without data (will use defaults)
            pass

    logger.info(f"DATABASE_DEBUG: Final status: {status}, draft: {bool(draft)}")
    logger.info("=== DATABASE_DEBUG: get_context() EXIT ===")

    return {
        "section_id": section_id,
        "status": status,
        "system_prompt": system_prompt,
        "draft": draft,
        "validation_rules": {
            str(i): rule.model_dump()
            for i, rule in enumerate(getattr(template, "validation_rules", []))
        },
    }


@tool
async def save_section(
    user_id: int,
    thread_id: str,
    section_id: str,
    content: dict[str, Any],
    score: int | None = None,
    status: str = "in_progress",
) -> dict[str, Any]:
    """
    Save section content to database.

    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier
        section_id: Section identifier
        content: Tiptap JSON content
        score: User satisfaction score (0-5)
        status: Section status

    Returns:
        Save operation result
    """
    logger.info("=== TOOLS_API_CALL: save_section() ENTRY ===")
    logger.info(
        f"TOOLS_API_CALL: section_id='{section_id}', user_id={user_id}, thread_id='{thread_id}'"
    )
    logger.info(f"TOOLS_API_CALL: score={score}, status='{status}'")
    logger.debug(f"TOOLS_API_CALL: content type: {type(content)}")

    if settings.USE_DENTAPP_API:
        try:
            # Convert section_id for DentApp API
            section_id_int = get_section_id_int(section_id)

            if section_id_int is None:
                logger.error(f"TOOLS_API_CALL: ❌ Invalid section_id: {section_id}")
                raise ValueError(f"Unknown section ID: {section_id}")

            logger.info(f"TOOLS_API_CALL: Mapped section_id '{section_id}' -> {section_id_int}")

            # Get DentApp client and save data (matching value canvas pattern)
            from integrations.dentapp.dentapp_utils import tiptap_to_plain_text

            # Convert tiptap content to plain text for database
            plain_text = tiptap_to_plain_text(content) if content else ""

            dentapp_client = get_dentapp_client()
            async with dentapp_client as client:
                response = await client.save_section_state(
                    agent_id=SIGNATURE_PITCH_AGENT_ID,
                    section_id=section_id_int,
                    user_id=user_id,  # Use the actual user_id parameter
                    content=plain_text,
                    metadata={},  # Empty metadata for MVP
                )

            logger.info(f"TOOLS_API_CALL: save_section_state returned: {response is not None}")

            if response:
                logger.info(f"TOOLS_API_CALL: ✅ Successfully saved section {section_id}")

                log_api_operation(
                    "save_section",
                    "success",
                    {
                        "section_id": section_id,
                        "section_id_int": section_id_int,
                        "user_id": user_id,
                        "thread_id": thread_id,
                        "score": score,
                        "status": status,
                    },
                )

                return {
                    "success": True,
                    "section_id": section_id,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                logger.error(f"TOOLS_API_CALL: ❌ Failed to save section {section_id}")
                raise Exception("Failed to save section to database")

        except Exception as e:
            logger.error(f"TOOLS_API_CALL: ❌ DentApp API error in save_section: {e}")
            log_api_operation("save_section", section_id=section_id, status="error", error=str(e))
            raise e

    # Fallback: return success (for development without API)
    return {
        "success": True,
        "section_id": section_id,
        "timestamp": datetime.now().isoformat(),
    }


@tool
async def get_all_sections_status(
    user_id: int,
    thread_id: str,
) -> dict[str, Any]:
    """
    Get status of all Signature Pitch sections.

    Args:
        user_id: Integer user ID from frontend
        thread_id: Thread identifier

    Returns:
        Status information for all sections
    """
    logger.info("=== TOOLS_API_CALL: get_all_sections_status() ENTRY ===")
    logger.info(f"TOOLS_API_CALL: user_id={user_id}, thread_id='{thread_id}'")

    sections_status = {}

    # Check all CAPSTONE framework sections
    all_sections = [
        SignaturePitchSectionID.CLARITY,
        SignaturePitchSectionID.AUTHORITY,
        SignaturePitchSectionID.PROBLEM,
        SignaturePitchSectionID.SOLUTION,
        SignaturePitchSectionID.THE_WHY,
        SignaturePitchSectionID.OPPORTUNITY,
        SignaturePitchSectionID.NEXT_STEPS,
        SignaturePitchSectionID.ESSENCE,
        SignaturePitchSectionID.IMPLEMENTATION,
    ]

    if settings.USE_DENTAPP_API:
        try:
            client = get_dentapp_client()

            for section in all_sections:
                section_id_int = get_section_id_int(section.value)
                if section_id_int:
                    response = await client.get_section_state(
                        agent_id=SIGNATURE_PITCH_AGENT_ID,
                        section_id=section_id_int,
                        user_id=user_id,  # Use the actual user_id parameter
                    )

                    if response and response.get("content"):
                        score = response.get("score", 0)
                        sections_status[section.value] = {
                            "status": "done" if score >= 3 else "in_progress",
                            "score": score,
                            "has_content": True,
                        }
                    else:
                        sections_status[section.value] = {
                            "status": "pending",
                            "score": None,
                            "has_content": False,
                        }
                else:
                    sections_status[section.value] = {
                        "status": "pending",
                        "score": None,
                        "has_content": False,
                    }

        except Exception as e:
            logger.error(f"TOOLS_API_CALL: ❌ Error getting sections status: {e}")
            # Return pending status for all sections on error
            for section in all_sections:
                sections_status[section.value] = {
                    "status": "pending",
                    "score": None,
                    "has_content": False,
                }

    logger.info(f"TOOLS_API_CALL: ✅ Retrieved status for {len(sections_status)} sections")
    return sections_status


@tool
async def export_signature_pitch_framework(
    user_id: int,
    thread_id: str,
    canvas_data: dict[str, Any],
) -> str:
    """
    Export complete signature pitch framework as formatted text.

    Args:
        user_id: Integer user ID
        thread_id: Thread identifier
        canvas_data: Complete signature pitch data

    Returns:
        Formatted signature pitch framework text
    """
    logger.info("=== TOOLS: export_signature_pitch_framework() ===")

    content = "# Signature Pitch Framework\\n\\n"

    # CAPSTONE Framework Sections
    
    # Step 1: CLARITY
    if canvas_data.get("name") or canvas_data.get("same") or canvas_data.get("fame"):
        content += "## Step 1: CLARITY\\n"
        if canvas_data.get("name"):
            content += f"**Name:** {canvas_data['name']}\\n"
        if canvas_data.get("same"):
            content += f"**Same:** {canvas_data['same']}\\n"
        if canvas_data.get("fame"):
            content += f"**Fame:** {canvas_data['fame']}\\n"
        content += "\\n"

    # Step 2: AUTHORITY
    if canvas_data.get("authority_pillars"):
        content += f"## Step 2: AUTHORITY\\n{canvas_data['authority_pillars']}\\n\\n"

    # Step 3: PROBLEM
    if canvas_data.get("context") or canvas_data.get("dominant_problems"):
        content += "## Step 3: PROBLEM\\n"
        if canvas_data.get("context"):
            content += f"**Context:** {canvas_data['context']}\\n"
        if canvas_data.get("dominant_problems"):
            content += f"**Problems:** {canvas_data['dominant_problems']}\\n"
        content += "\\n"

    # Step 4: SOLUTION
    if canvas_data.get("focus") or canvas_data.get("payoffs") or canvas_data.get("what_how") or canvas_data.get("prize"):
        content += "## Step 4: SOLUTION\\n"
        if canvas_data.get("focus"):
            content += f"**Focus:** {canvas_data['focus']}\\n"
        if canvas_data.get("payoffs"):
            content += f"**Payoffs:** {canvas_data['payoffs']}\\n"
        if canvas_data.get("what_how"):
            content += f"**Method:** {canvas_data['what_how']}\\n"
        if canvas_data.get("prize"):
            content += f"**Prize:** {canvas_data['prize']}\\n"
        content += "\\n"

    # Step 5: THE WHY
    if canvas_data.get("origin") or canvas_data.get("mission") or canvas_data.get("vision"):
        content += "## Step 5: THE WHY\\n"
        if canvas_data.get("origin"):
            content += f"**Origin:** {canvas_data['origin']}\\n"
        if canvas_data.get("mission"):
            content += f"**Mission:** {canvas_data['mission']}\\n"
        if canvas_data.get("vision"):
            content += f"**Vision:** {canvas_data['vision']}\\n"
        content += "\\n"

    # Step 6: OPPORTUNITY
    if canvas_data.get("proposal") or canvas_data.get("wedding") or canvas_data.get("honeymoon"):
        content += "## Step 6: OPPORTUNITY\\n"
        if canvas_data.get("proposal"):
            content += f"**Proposal:** {canvas_data['proposal']}\\n"
        if canvas_data.get("wedding"):
            content += f"**Wedding:** {canvas_data['wedding']}\\n"
        if canvas_data.get("honeymoon"):
            content += f"**Honeymoon:** {canvas_data['honeymoon']}\\n"
        content += "\\n"

    # Step 7: NEXT STEPS
    if canvas_data.get("call_to_action"):
        content += f"## Step 7: NEXT STEPS\\n{canvas_data['call_to_action']}\\n\\n"

    # Step 8: ESSENCE
    if canvas_data.get("reputation") or canvas_data.get("feeling"):
        content += "## Step 8: ESSENCE\\n"
        if canvas_data.get("reputation"):
            content += f"**Reputation:** {canvas_data['reputation']}\\n"
        if canvas_data.get("feeling"):
            content += f"**Feeling:** {canvas_data['feeling']}\\n"
        content += "\\n"

    # 90-Second Pitch Flow
    content += "## 90-Second Pitch Flow\\n"
    content += "1. **Hook with your Signature Line** (10 seconds)\\n"
    content += "2. **Share your Story Spark** (20 seconds)\\n"
    content += "3. **Explain your Active Change** (25 seconds)\\n"
    content += "4. **Highlight Core Credibility** (15 seconds)\\n"
    content += "5. **Paint the Outcome/Prize** (15 seconds)\\n"
    content += "6. **Close with invitation to connect** (5 seconds)\\n\\n"

    # Implementation steps
    content += "## Implementation Steps\\n"
    content += "1. Practice the 90-second flow until it feels natural\\n"
    content += "2. Test with colleagues and gather feedback\\n"
    content += "3. Use in networking conversations and observe reactions\\n"
    content += "4. Create variants (30-second, 2-minute, 5-minute versions)\\n"
    content += "5. Build assets (LinkedIn profile, website bio, speaker materials)\\n"
    content += "6. Refine based on real-world feedback\\n"

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
        content.append(
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": text,
                    }
                ],
            }
        )
    elif format_type == "heading":
        content.append(
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [
                    {
                        "type": "text",
                        "text": text,
                    }
                ],
            }
        )
    elif format_type == "list":
        items = text.split("\\n")
        list_items = []
        for item in items:
            if item.strip():
                list_items.append(
                    {
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
                    }
                )
        content.append(
            {
                "type": "bulletList",
                "content": list_items,
            }
        )

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

        if node.get("type") == "text":
            text_parts.append(node.get("text", ""))
        elif node.get("content"):
            for child_node in node["content"]:
                text_parts.append(extract_text_from_node(child_node))

        return "".join(text_parts)

    if not isinstance(tiptap_json, dict):
        return str(tiptap_json)

    return extract_text_from_node(tiptap_json)


@tool
async def validate_field(
    field_name: str,
    field_value: str,
    validation_rules: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate a field value against defined rules.

    Args:
        field_name: Name of the field to validate
        field_value: Value to validate
        validation_rules: Validation rules to apply

    Returns:
        Validation result with is_valid flag and error messages
    """
    errors = []

    # Add validation logic based on rules
    if validation_rules:
        # Example validation logic - customize as needed
        min_length = validation_rules.get("min_length")
        if min_length and len(field_value) < min_length:
            errors.append(f"{field_name} must be at least {min_length} characters")

        max_length = validation_rules.get("max_length")
        if max_length and len(field_value) > max_length:
            errors.append(f"{field_name} must be no more than {max_length} characters")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "field_name": field_name,
    }


# Define tools for each node
router_tools = [get_context]

memory_updater_tools = [
    save_section,
    get_all_sections_status,
    create_tiptap_content,
    extract_plain_text,
    validate_field,
]

implementation_tools = [export_signature_pitch_framework]
