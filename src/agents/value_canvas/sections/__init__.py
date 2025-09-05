"""Value Canvas sections module - aggregates all section templates and prompts."""

from typing import Any, Dict

# Import all section templates and prompts
from .base_prompt import BASE_PROMPTS, BASE_RULES
from .deep_fear import DEEP_FEAR_TEMPLATE
from .icp import ICP_TEMPLATE
from .icp_stress_test import ICP_STRESS_TEST_TEMPLATE
from .implementation import IMPLEMENTATION_TEMPLATE
from .interview import INTERVIEW_TEMPLATE
from .mistakes import MISTAKES_TEMPLATE
from .pain import PAIN_TEMPLATE
from .pain_payoff_symmetry import PAIN_PAYOFF_SYMMETRY_TEMPLATE
from .payoffs import PAYOFFS_TEMPLATE
from .prize import PRIZE_TEMPLATE
from .signature_method import SIGNATURE_METHOD_TEMPLATE

# Aggregate all section templates
SECTION_TEMPLATES: dict[str, Any] = {
    INTERVIEW_TEMPLATE.section_id.value: INTERVIEW_TEMPLATE,
    ICP_TEMPLATE.section_id.value: ICP_TEMPLATE,
    ICP_STRESS_TEST_TEMPLATE.section_id.value: ICP_STRESS_TEST_TEMPLATE,
    PAIN_TEMPLATE.section_id.value: PAIN_TEMPLATE,
    DEEP_FEAR_TEMPLATE.section_id.value: DEEP_FEAR_TEMPLATE,
    PAYOFFS_TEMPLATE.section_id.value: PAYOFFS_TEMPLATE,
    PAIN_PAYOFF_SYMMETRY_TEMPLATE.section_id.value: PAIN_PAYOFF_SYMMETRY_TEMPLATE,
    SIGNATURE_METHOD_TEMPLATE.section_id.value: SIGNATURE_METHOD_TEMPLATE,
    MISTAKES_TEMPLATE.section_id.value: MISTAKES_TEMPLATE,
    PRIZE_TEMPLATE.section_id.value: PRIZE_TEMPLATE,
    IMPLEMENTATION_TEMPLATE.section_id.value: IMPLEMENTATION_TEMPLATE,
}

# Export BASE_RULES directly (previously wrapped in SECTION_PROMPTS dict)
# The SECTION_PROMPTS dict was removed as it only contained one key
# and the name was misleading (it contained base rules, not section prompts)

__all__ = [
    "BASE_RULES",
    "BASE_PROMPTS",
    "SECTION_TEMPLATES",
    "INTERVIEW_TEMPLATE",
    "ICP_TEMPLATE",
    "PAIN_TEMPLATE",
    "DEEP_FEAR_TEMPLATE",
    "PAYOFFS_TEMPLATE",
    "SIGNATURE_METHOD_TEMPLATE",
    "MISTAKES_TEMPLATE",
    "PRIZE_TEMPLATE",
    "IMPLEMENTATION_TEMPLATE",
]