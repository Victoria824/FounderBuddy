"""Enumerations for Value Canvas Agent."""

from enum import Enum


class SectionStatus(str, Enum):
    """Status of a Value Canvas section."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class RouterDirective(str, Enum):
    """Router directive for navigation control."""
    STAY = "stay"
    NEXT = "next"
    MODIFY = "modify"  # Format: "modify:section_id"


class SectionID(str, Enum):
    """Value Canvas section identifiers."""
    # Initial Interview
    INTERVIEW = "interview"
    
    # Core Value Canvas Sections
    ICP = "icp"  # Ideal Customer Persona
    ICP_STRESS_TEST = "icp_stress_test"  # ICP Stress Test
    PAIN = "pain"  # The Pain (contains 3 pain points)
    DEEP_FEAR = "deep_fear"  # The Deep Fear
    PAYOFFS = "payoffs"  # The Payoffs (contains 3 payoff points)
    PAIN_PAYOFF_SYMMETRY = "pain_payoff_symmetry"  # Pain-Payoff Symmetry Analysis
    SIGNATURE_METHOD = "signature_method"  # Signature Method
    MISTAKES = "mistakes"  # The Mistakes
    PRIZE = "prize"  # The Prize
    
    # Implementation/Export
    IMPLEMENTATION = "implementation"