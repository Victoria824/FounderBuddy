"""Global prompts and section management for Special Report Agent."""

from typing import Any

from .enums import SectionStatus, SpecialReportSection
from .framework_prompts import (
    SECTION_TEMPLATES,
    get_progress_info as get_framework_progress_info,
    get_section_order as get_framework_section_order,
    get_next_section as get_framework_next_section,
    get_next_unfinished_section as get_framework_next_unfinished_section,
)

# Base rules for Special Report agent
BASE_RULES = """This agent uses the 7-Step Special Report Framework. Please see framework_templates.py for the complete 7-step framework."""

# Use framework templates and functions
# Create SECTION_PROMPTS for backward compatibility (deprecated)
SECTION_PROMPTS = {
    "base_rules": BASE_RULES
}


def get_section_order() -> list[SpecialReportSection]:
    """Get the ordered list of sections."""
    return get_framework_section_order()


def get_next_section(current: SpecialReportSection) -> SpecialReportSection | None:
    """Get the next section in the flow."""
    return get_framework_next_section(current)


def get_next_unfinished_section(section_states: dict[str, Any]) -> SpecialReportSection | None:
    """Find the next section that hasn't been completed."""
    return get_framework_next_unfinished_section(section_states)


def get_progress_info(section_states: dict[str, Any]) -> dict[str, Any]:
    """Get progress information for all sections."""
    return get_framework_progress_info(section_states)
