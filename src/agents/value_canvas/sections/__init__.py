"""Value Canvas sections module - aggregates all section templates and prompts."""

from typing import Dict, Any

# Import all section templates and prompts
from .base_prompt import BASE_RULES, BASE_PROMPTS
from .interview import INTERVIEW_TEMPLATE, INTERVIEW_PROMPTS
from .icp import ICP_TEMPLATE, ICP_PROMPTS
from .icp_stress_test import ICP_STRESS_TEST_TEMPLATE, ICP_STRESS_TEST_PROMPTS
from .pain import PAIN_TEMPLATE, PAIN_PROMPTS
from .deep_fear import DEEP_FEAR_TEMPLATE, DEEP_FEAR_PROMPTS
from .payoffs import PAYOFFS_TEMPLATE, PAYOFFS_PROMPTS
from .pain_payoff_symmetry import PAIN_PAYOFF_SYMMETRY_TEMPLATE, PAIN_PAYOFF_SYMMETRY_PROMPTS
from .signature_method import SIGNATURE_METHOD_TEMPLATE, SIGNATURE_METHOD_PROMPTS
from .mistakes import MISTAKES_TEMPLATE, MISTAKES_PROMPTS
from .prize import PRIZE_TEMPLATE, PRIZE_PROMPTS
from .implementation import IMPLEMENTATION_TEMPLATE, IMPLEMENTATION_PROMPTS

# Aggregate all section templates
SECTION_TEMPLATES: Dict[str, Any] = {
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

# Aggregate all section prompts
SECTION_PROMPTS: Dict[str, Any] = {
    "base_rules": BASE_RULES,
    "interview": INTERVIEW_PROMPTS,
    "icp": ICP_PROMPTS,
    "icp_stress_test": ICP_STRESS_TEST_PROMPTS,
    "pain": PAIN_PROMPTS,
    "deep_fear": DEEP_FEAR_PROMPTS,
    "payoffs": PAYOFFS_PROMPTS,
    "pain_payoff_symmetry": PAIN_PAYOFF_SYMMETRY_PROMPTS,
    "signature_method": SIGNATURE_METHOD_PROMPTS,
    "mistakes": MISTAKES_PROMPTS,
    "prize": PRIZE_PROMPTS,
    "implementation": IMPLEMENTATION_PROMPTS,
}

__all__ = [
    "BASE_RULES",
    "BASE_PROMPTS",
    "SECTION_TEMPLATES",
    "SECTION_PROMPTS",
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