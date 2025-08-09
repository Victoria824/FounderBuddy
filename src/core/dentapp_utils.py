"""Utility functions for DentApp AI Builder API integration."""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Global UUID to integer mapping cache (in-memory for MVP)
_uuid_to_int_cache: Dict[str, int] = {}
_next_user_id = 1  # Start from 1 to match existing DentApp test user

# Section ID mapping: agent section -> DentApp API section_id
SECTION_ID_MAPPING = {
    "interview": 1,
    "icp": 2,
    "pain": 3,
    "deep_fear": 4,
    "payoffs": 5,
    "signature_method": 6,
    "mistakes": 7,
    "prize": 8,
}

# Fixed agent ID for MVP
AGENT_ID = 1


def get_user_id_int(uuid_str: str) -> int:
    """
    Convert UUID string to integer ID using in-memory mapping.
    For MVP: all users map to user_id=1 (test user in DentApp)
    
    Args:
        uuid_str: UUID string from the agent
        
    Returns:
        Integer ID for DentApp API (always 1 for MVP)
    """
    # MVP: Use fixed user_id=1 for all users to work with DentApp test data
    if uuid_str not in _uuid_to_int_cache:
        _uuid_to_int_cache[uuid_str] = 1  # Always map to test user
        logger.info(f"Mapped UUID {uuid_str} to test user_id=1 (MVP mode)")
    
    return _uuid_to_int_cache[uuid_str]


def get_section_id_int(section_id_str: str) -> Optional[int]:
    """
    Convert agent section ID string to DentApp API section_id integer.
    
    Args:
        section_id_str: Section ID from the agent (e.g., "interview", "icp")
        
    Returns:
        Integer section_id for DentApp API, or None if not found
    """
    section_id_int = SECTION_ID_MAPPING.get(section_id_str)
    if section_id_int is None:
        logger.error(f"Unknown section ID: {section_id_str}")
    return section_id_int


def tiptap_to_plain_text(tiptap_json: Dict[str, Any]) -> str:
    """
    Convert Tiptap JSON content to plain text for DentApp API.
    
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
    
    if not tiptap_json or not isinstance(tiptap_json, dict):
        return ""
        
    plain_text = extract_text_from_node(tiptap_json).strip()
    logger.debug(f"Converted Tiptap to plain text: {len(plain_text)} characters")
    return plain_text


def plain_text_to_tiptap(plain_text: str) -> Dict[str, Any]:
    """
    Convert plain text to basic Tiptap JSON format.
    
    Args:
        plain_text: Plain text string from DentApp API
        
    Returns:
        Tiptap JSON document
    """
    if not plain_text:
        return {"type": "doc", "content": []}
    
    # Simple paragraph-based conversion
    paragraphs = plain_text.split('\n\n')
    content = []
    
    for paragraph in paragraphs:
        if paragraph.strip():
            content.append({
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": paragraph.strip(),
                    }
                ],
            })
    
    tiptap_json = {
        "type": "doc",
        "content": content,
    }
    
    logger.debug(f"Converted plain text to Tiptap: {len(content)} paragraphs")
    return tiptap_json


def convert_dentapp_status_to_agent(dentapp_status: str) -> str:
    """
    Convert DentApp API status to agent status format.
    
    Args:
        dentapp_status: Status from DentApp API
        
    Returns:
        Status string compatible with agent
    """
    # Map DentApp status to agent status
    status_mapping = {
        "completed": "done",
        "in_progress": "in_progress", 
        "pending": "pending",
        "not_started": "pending",
    }
    
    agent_status = status_mapping.get(dentapp_status, "pending")
    logger.debug(f"Converted DentApp status '{dentapp_status}' to agent status '{agent_status}'")
    return agent_status


def convert_agent_score_to_dentapp(score: Optional[int]) -> Optional[int]:
    """
    Convert agent score to DentApp API format.
    
    Args:
        score: Score from agent (0-5 or None)
        
    Returns:
        Score for DentApp API (same format)
    """
    # Scores are the same format (0-5), just validate
    if score is not None and (score < 0 or score > 5):
        logger.warning(f"Invalid score {score}, setting to None")
        return None
    
    return score


def log_api_operation(operation: str, **kwargs):
    """
    Log DentApp API operations for debugging.
    
    Args:
        operation: Operation name (e.g., "get_context", "save_section")
        **kwargs: Additional context to log
    """
    logger.info(f"DentApp API Operation: {operation}")
    for key, value in kwargs.items():
        logger.debug(f"  {key}: {value}")


def get_mapping_stats() -> Dict[str, Any]:
    """
    Get current UUID mapping statistics for debugging.
    
    Returns:
        Dictionary with mapping statistics
    """
    return {
        "total_mapped_uuids": len(_uuid_to_int_cache),
        "next_user_id": _next_user_id,
        "mapped_uuids": list(_uuid_to_int_cache.keys()),
        "section_mappings": SECTION_ID_MAPPING,
        "agent_id": AGENT_ID,
    }