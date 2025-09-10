"""Utility functions for DentApp AI Builder API integration."""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# No longer needed - frontend now passes integer user_id directly


def _get_config_based_on_url() -> tuple[dict[str, int], int]:
    """
    Get SECTION_ID_MAPPING and AGENT_ID based on DENTAPP_API_URL.
    
    Returns:
        tuple: (section_id_mapping, agent_id)
    """
    dentapp_api_url = os.getenv("DENTAPP_API_URL", "")
    
    if "gsd.keypersonofinfluence.com" in dentapp_api_url:
        # GSD configuration: 
        # Value Canvas: section IDs 9-16, agent ID 2
        # Social Pitch: section IDs 17-22, agent ID 3
        # Mission Pitch: section IDs 23-31, agent ID 4
        # Signature Pitch: section IDs 32-39, agent ID 5
        # Special Report: section IDs 40-43, agent ID 6
        section_mapping = {
            # Value Canvas sections
            "interview": 9,
            "icp": 10,
            "pain": 11,
            "deep_fear": 12,
            "payoffs": 13,
            "signature_method": 14,
            "mistakes": 15,
            "prize": 16,
            # Social Pitch sections
            "name": 17,
            "same": 18,
            "fame": 19,
            "sp_pain": 20,  # Social Pitch pain (different from Value Canvas pain)
            "aim": 21,
            "game": 22,
            # Mission Pitch sections
            "hidden_theme": 23,
            "personal_origin": 24,
            "business_origin": 25,
            "mission": 26,
            "three_year_vision": 27,
            "big_vision": 28,
            "implementation": 29,
            # Signature Pitch sections
            "active_change": 32,
            "specific_who": 33,
            "outcome_prize": 34,
            "core_credibility": 35,
            "story_spark": 36,
            "signature_line": 37,
            # Special Report sections (old sections for backward compatibility)
            "topic_selection": 40,
            "content_development": 41,
            "report_structure": 42,
            "sr_implementation": 43,  # Special Report implementation
            # Special Report sections (new 7-step framework)
            "attract": 44,      # Step 1: Compelling topic
            "disrupt": 45,      # Step 2: Challenge assumptions
            "inform": 46,       # Step 3: Teach concept
            "recommend": 47,    # Step 4: Recommend actions
            "overcome": 48,     # Step 5: Handle objections
            "reinforce": 49,    # Step 6: Reinforce value
            "invite": 50,       # Step 7: Call to action
            "implementation": 51,  # Implementation/Export
        }
        agent_id = 2  # Default to Value Canvas agent ID (will be overridden by agent-specific calls)
        logger.info("Using GSD configuration: Value Canvas (IDs 9-16, agent 2), Social Pitch (IDs 17-22, agent 3), Mission Pitch (IDs 23-31, agent 4), Signature Pitch (IDs 32-39, agent 5)")
    elif "dentappaibuilder.enspirittech.co.uk" in dentapp_api_url:
        # DentApp AI Builder configuration:
        # Value Canvas: section IDs 1-8, agent ID 1  
        # Social Pitch: section IDs 9-14, agent ID 3
        # Mission Pitch: section IDs 15-23, agent ID 4
        # Signature Pitch: section IDs 24-31, agent ID 5
        # Special Report: section IDs 32-35, agent ID 6
        section_mapping = {
            # Value Canvas sections
            "interview": 1,
            "icp": 2,
            "pain": 3,
            "deep_fear": 4,
            "payoffs": 5,
            "signature_method": 6,
            "mistakes": 7,
            "prize": 8,
            # Social Pitch sections
            "name": 9,
            "same": 10,
            "fame": 11,
            "pain": 12,  # Social Pitch pain (uses "pain" in enum, not "sp_pain")
            "aim": 13,
            "game": 14,
            "implementation": 15,  # Social Pitch implementation section
            # Mission Pitch sections
            "hidden_theme": 16,
            "personal_origin": 17,
            "business_origin": 18,
            "mission": 19,
            "three_year_vision": 20,
            "big_vision": 21,
            "implementation": 22,  # Mission Pitch implementation
            # Signature Pitch sections
            "active_change": 24,
            "specific_who": 25,
            "outcome_prize": 26,
            "core_credibility": 27,
            "story_spark": 28,
            "signature_line": 29,
            "implementation": 30,  # Signature Pitch implementation
            # Special Report sections (old sections for backward compatibility)
            "topic_selection": 32,
            "content_development": 33,
            "report_structure": 34,
            "sr_implementation": 35,  # Special Report implementation
            # Special Report sections (new 7-step framework)
            "attract": 36,      # Step 1: Compelling topic
            "disrupt": 37,      # Step 2: Challenge assumptions
            "inform": 38,       # Step 3: Teach concept
            "recommend": 39,    # Step 4: Recommend actions
            "overcome": 40,     # Step 5: Handle objections
            "reinforce": 41,    # Step 6: Reinforce value
            "invite": 42,       # Step 7: Call to action
            "implementation": 43,  # Implementation/Export
        }
        agent_id = 1  # Default to Value Canvas agent ID (will be overridden by agent-specific calls)
        logger.info("Using DentApp AI Builder configuration: Value Canvas (IDs 1-8, agent 1), Social Pitch (IDs 9-14, agent 3), Mission Pitch (IDs 15-23, agent 4), Signature Pitch (IDs 24-31, agent 5), Special Report (IDs 32-35, agent 6)")
    else:
        # Default fallback to GSD configuration
        section_mapping = {
            # Value Canvas sections
            "interview": 9,
            "icp": 10,
            "pain": 11,
            "deep_fear": 12,
            "payoffs": 13,
            "signature_method": 14,
            "mistakes": 15,
            "prize": 16,
            # Social Pitch sections
            "name": 17,
            "same": 18,
            "fame": 19,
            "pain": 20,  # Social Pitch pain (uses "pain" in enum, not "sp_pain")
            "aim": 21,
            "game": 22,
            "implementation": 23,  # Social Pitch implementation
            # Mission Pitch sections
            "hidden_theme": 24,
            "personal_origin": 25,
            "business_origin": 26,
            "mission": 27,
            "three_year_vision": 28,
            "big_vision": 29,
            "implementation": 30,  # Mission Pitch implementation
            # Signature Pitch sections
            "active_change": 32,
            "specific_who": 33,
            "outcome_prize": 34,
            "core_credibility": 35,
            "story_spark": 36,
            "signature_line": 37,
            "implementation": 38,  # Signature Pitch implementation
            # Special Report sections (old sections for backward compatibility)
            "topic_selection": 40,
            "content_development": 41,
            "report_structure": 42,
            "sr_implementation": 43,  # Special Report implementation
            # Special Report sections (new 7-step framework)
            "attract": 44,      # Step 1: Compelling topic
            "disrupt": 45,      # Step 2: Challenge assumptions
            "inform": 46,       # Step 3: Teach concept
            "recommend": 47,    # Step 4: Recommend actions
            "overcome": 48,     # Step 5: Handle objections
            "reinforce": 49,    # Step 6: Reinforce value
            "invite": 50,       # Step 7: Call to action
            "implementation": 51,  # Implementation/Export
        }
        agent_id = 2  # Default to Value Canvas agent ID
        logger.warning(f"Unknown DENTAPP_API_URL: {dentapp_api_url}, using default GSD configuration")
    
    return section_mapping, agent_id


# Dynamic configuration based on environment
SECTION_ID_MAPPING, AGENT_ID = _get_config_based_on_url()

# Agent ID constants
VALUE_CANVAS_AGENT_ID = 2  # GSD environment
SOCIAL_PITCH_AGENT_ID = 3
MISSION_PITCH_AGENT_ID = 4
SIGNATURE_PITCH_AGENT_ID = 5
SPECIAL_REPORT_AGENT_ID = 6

# Adjust agent IDs based on environment
dentapp_api_url = os.getenv("DENTAPP_API_URL", "")
if "dentappaibuilder.enspirittech.co.uk" in dentapp_api_url:
    # DentApp environment uses different IDs
    VALUE_CANVAS_AGENT_ID = 1
    SOCIAL_PITCH_AGENT_ID = 3
    MISSION_PITCH_AGENT_ID = 4
    SIGNATURE_PITCH_AGENT_ID = 5
    SPECIAL_REPORT_AGENT_ID = 6


def get_agent_id_for_section(section_id_str: str, agent_context: str = None) -> int:
    """
    Get the appropriate agent ID based on the section type.
    
    Args:
        section_id_str: Section ID string  
        agent_context: Optional context to distinguish agents (e.g., "social_pitch", "value_canvas", "mission_pitch")
        
    Returns:
        Agent ID (2/3/4/5 for GSD, 1/3/4/5 for DentApp)
    """
    # If we have explicit agent context, use it
    if agent_context == "social_pitch":
        return SOCIAL_PITCH_AGENT_ID
    elif agent_context == "value_canvas":
        return VALUE_CANVAS_AGENT_ID
    elif agent_context == "mission_pitch":
        return MISSION_PITCH_AGENT_ID
    elif agent_context == "signature_pitch":
        return SIGNATURE_PITCH_AGENT_ID
    elif agent_context == "special_report":
        return SPECIAL_REPORT_AGENT_ID
    
    # Value Canvas exclusive sections
    value_canvas_sections = {
        "interview", "icp", "deep_fear", 
        "payoffs", "signature_method", "mistakes", "prize"
    }
    
    # Social Pitch exclusive sections  
    social_pitch_sections = {
        "name", "same", "fame", "aim", "game"
    }
    
    # Mission Pitch exclusive sections
    mission_pitch_sections = {
        "hidden_theme", "personal_origin", "business_origin", "mission",
        "three_year_vision", "big_vision", "implementation"
    }
    
    # Signature Pitch exclusive sections
    signature_pitch_sections = {
        "active_change", "specific_who", "outcome_prize", 
        "core_credibility", "story_spark", "signature_line"
    }
    
    # Special Report exclusive sections
    special_report_sections = {
        "topic_selection", "content_development", "report_structure", "sr_implementation",
        "attract", "disrupt", "inform", "recommend", "overcome", "reinforce", "invite", "implementation"
    }
    
    # Handle special cases
    if section_id_str == "sp_pain":
        return SOCIAL_PITCH_AGENT_ID
    elif section_id_str == "pain":
        # Default to Value Canvas for ambiguous pain section
        return VALUE_CANVAS_AGENT_ID
    elif section_id_str in value_canvas_sections:
        return VALUE_CANVAS_AGENT_ID
    elif section_id_str in social_pitch_sections:
        return SOCIAL_PITCH_AGENT_ID
    elif section_id_str in mission_pitch_sections:
        return MISSION_PITCH_AGENT_ID
    elif section_id_str in signature_pitch_sections:
        return SIGNATURE_PITCH_AGENT_ID
    elif section_id_str in special_report_sections:
        return SPECIAL_REPORT_AGENT_ID
    else:
        logger.warning(f"Unknown section type: {section_id_str}, defaulting to Value Canvas agent")
        return VALUE_CANVAS_AGENT_ID


def get_user_id_int(user_id: int) -> int:
    """
    Pass through the integer user_id directly from frontend.
    
    Args:
        user_id: Integer user ID from the frontend
        
    Returns:
        Same integer ID for DentApp API
    """
    logger.debug(f"Using user_id={user_id} from frontend")
    return user_id


def get_section_id_int(section_id_str: str) -> int | None:
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


def tiptap_to_plain_text(tiptap_json: dict[str, Any]) -> str:
    """
    Convert Tiptap JSON content to plain text for DentApp API.
    
    Args:
        tiptap_json: Tiptap JSON document
        
    Returns:
        Plain text string
    """
    def extract_text_from_node(node: dict[str, Any]) -> str:
        text_parts = []
        
        # 1. Add text from the node itself, if it exists.
        if node.get("text"):
            text_parts.append(node["text"])

        # 2. Add newline for hard breaks.
        if node.get("type") == "hardBreak":
            text_parts.append("\n")

        # 3. Recurse into children.
        if "content" in node and isinstance(node["content"], list):
            for child in node["content"]:
                text_parts.append(extract_text_from_node(child))
                
        return "".join(text_parts)
    
    if not tiptap_json or not isinstance(tiptap_json, dict):
        return ""
        
    plain_text = extract_text_from_node(tiptap_json).strip()
    logger.debug(f"Converted Tiptap to plain text: {len(plain_text)} characters")
    return plain_text


def plain_text_to_tiptap(plain_text: str) -> dict[str, Any]:
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


def convert_agent_score_to_dentapp(score: int | None) -> int | None:
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


def get_mapping_stats() -> dict[str, Any]:
    """
    Get current mapping statistics for debugging.
    
    Returns:
        Dictionary with mapping statistics
    """
    return {
        "section_mappings": SECTION_ID_MAPPING,
        "agent_id": AGENT_ID,
        "dentapp_api_url": os.getenv("DENTAPP_API_URL", ""),
    }