"""Prompts and templates for Signature Pitch CAPSTONE Framework.

This module now uses the CAPSTONE framework templates instead of the legacy approach.
The complete CAPSTONE framework with all 8 steps is imported from capstone_templates.py.
"""

from typing import Any

from .capstone_templates import (
    CAPSTONE_TEMPLATES,
    get_capstone_progress_info,
    get_capstone_section_order,
)
from .enums import SectionStatus, SignaturePitchSectionID

# Import the CAPSTONE framework templates
SECTION_TEMPLATES = CAPSTONE_TEMPLATES


def get_progress_info(section_states: dict[str, Any]) -> dict[str, Any]:
    """Get progress information for CAPSTONE framework completion."""
    return get_capstone_progress_info(section_states)


def get_section_order() -> list[SignaturePitchSectionID]:
    """Get the ordered list of CAPSTONE framework sections."""
    return get_capstone_section_order()


def get_next_section(current_section: SignaturePitchSectionID) -> SignaturePitchSectionID | None:
    """Get the next section in the CAPSTONE framework flow."""
    order = get_section_order()
    try:
        current_index = order.index(current_section)
        if current_index < len(order) - 1:
            return order[current_index + 1]
    except ValueError:
        pass
    return None


def get_next_unfinished_section(section_states: dict[str, Any]) -> SignaturePitchSectionID | None:
    """Find the next section that should be worked on based on CAPSTONE sequential progression."""
    order = get_section_order()

    # Find the last completed section
    last_completed_index = -1
    for i, section in enumerate(order):
        state = section_states.get(section.value)
        if state and state.status == SectionStatus.DONE:
            last_completed_index = i
        else:
            # Stop at first non-completed section - don't skip ahead
            break

    # Return the next section after the last completed one
    next_index = last_completed_index + 1
    if next_index < len(order):
        return order[next_index]

    return None


# Base rules for Signature Pitch agent
BASE_RULES = """This agent now uses the CAPSTONE Framework. Please see capstone_templates.py for the complete 8-step framework."""

# Legacy compatibility exports for backward compatibility during transition
SECTION_PROMPTS = {
    "base_rules": BASE_RULES
}

# Export the main template access for the agent
__all__ = [
    "SECTION_TEMPLATES",
    "get_progress_info",
    "get_section_order",
    "get_next_section",
    "get_next_unfinished_section",
    "BASE_RULES",
    "SECTION_PROMPTS",  # Legacy compatibility
]
