"""Global prompts and section management for Special Report Agent."""

from typing import Any, List

from .enums import SpecialReportSection, SectionStatus
from .models import SectionTemplate

# Import all section prompts
from .sections.topic_selection.prompts import TOPIC_SELECTION_PROMPTS, TOPIC_SELECTION_TEMPLATE
from .sections.content_development.prompts import CONTENT_DEVELOPMENT_PROMPTS, CONTENT_DEVELOPMENT_TEMPLATE
from .sections.report_structure.prompts import REPORT_STRUCTURE_PROMPTS, REPORT_STRUCTURE_TEMPLATE
from .sections.implementation.prompts import IMPLEMENTATION_PROMPTS, IMPLEMENTATION_TEMPLATE

# Section templates registry
SECTION_TEMPLATES = {
    SpecialReportSection.TOPIC_SELECTION.value: TOPIC_SELECTION_TEMPLATE,
    SpecialReportSection.CONTENT_DEVELOPMENT.value: CONTENT_DEVELOPMENT_TEMPLATE,
    SpecialReportSection.REPORT_STRUCTURE.value: REPORT_STRUCTURE_TEMPLATE,
    SpecialReportSection.IMPLEMENTATION.value: IMPLEMENTATION_TEMPLATE,
}

# Section prompts registry
SECTION_PROMPTS = {
    SpecialReportSection.TOPIC_SELECTION.value: TOPIC_SELECTION_PROMPTS,
    SpecialReportSection.CONTENT_DEVELOPMENT.value: CONTENT_DEVELOPMENT_PROMPTS,
    SpecialReportSection.REPORT_STRUCTURE.value: REPORT_STRUCTURE_PROMPTS,
    SpecialReportSection.IMPLEMENTATION.value: IMPLEMENTATION_PROMPTS,
}


def get_section_order() -> List[SpecialReportSection]:
    """Get the ordered list of sections."""
    return [
        SpecialReportSection.TOPIC_SELECTION,
        SpecialReportSection.CONTENT_DEVELOPMENT,
        SpecialReportSection.REPORT_STRUCTURE,
        SpecialReportSection.IMPLEMENTATION,
    ]


def get_next_section(current: SpecialReportSection) -> SpecialReportSection | None:
    """Get the next section in the flow."""
    sections = get_section_order()
    try:
        current_index = sections.index(current)
        if current_index < len(sections) - 1:
            return sections[current_index + 1]
    except ValueError:
        pass
    return None


def get_next_unfinished_section(section_states: dict[str, Any]) -> SpecialReportSection | None:
    """Find the next section that hasn't been completed."""
    order = get_section_order()
    for section in order:
        state = section_states.get(section.value)
        if not state or state.status != SectionStatus.DONE:
            return section
    return None


def get_progress_info(section_states: dict[str, Any]) -> dict[str, Any]:
    """Get progress information for all sections."""
    sections = get_section_order()
    completed = sum(1 for section in sections if section_states.get(section.value, {}).get("status") == SectionStatus.DONE)
    
    return {
        "total_sections": len(sections),
        "completed_sections": completed,
        "current_section": get_next_unfinished_section(section_states),
        "progress_percentage": (completed / len(sections)) * 100,
    }