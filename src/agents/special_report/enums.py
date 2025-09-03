"""Enums for Special Report Agent."""

from enum import Enum


class RouterDirective(str, Enum):
    """Router directive for state transitions."""
    STAY = "stay"
    NEXT = "next"
    MODIFY = "modify"  # Format: "modify:section_id"


class SpecialReportSection(str, Enum):
    """Special Report section identifiers."""
    TOPIC_SELECTION = "topic_selection"
    CONTENT_DEVELOPMENT = "content_development"
    REPORT_STRUCTURE = "report_structure"
    IMPLEMENTATION = "implementation"


class SectionStatus(str, Enum):
    """Section completion status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"