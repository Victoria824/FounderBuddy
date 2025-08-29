"""Prompts and templates for the Signature Method section."""

from ...enums import SectionID
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

# Signature Method section specific prompts
SIGNATURE_METHOD_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Section 6 of 9 - Signature Method]

Your Signature Method is your intellectual property - the unique approach that bridges the gap between your client's pain and their desired payoffs. This isn't just what you do, but HOW you do it differently.

A strong Signature Method:
- Demonstrates your unique thinking and expertise
- Creates confidence that you have a proven approach
- Differentiates you from competitors who might offer similar services
- Gives structure to your client's transformation journey

We'll create:
1. **Method Name**: A memorable 2-4 word name for your approach
2. **Core Principles**: 4-6 principles that guide your method

Each principle should:
- Have a clear, memorable name (2-4 words)
- Include a brief description of what it means in practice (1-2 sentences)
- Address a specific aspect of the transformation journey"""

# Signature Method section template
SIGNATURE_METHOD_TEMPLATE = SectionTemplate(
    section_id=SectionID.SIGNATURE_METHOD,
    name="Signature Method",
    description="Your unique approach that bridges pain to payoffs",
    system_prompt_template=SIGNATURE_METHOD_SYSTEM_PROMPT,
    validation_rules=[
        ValidationRule(
            field_name="method_name",
            rule_type="required",
            value=True,
            error_message="Method name is required"
        ),
        ValidationRule(
            field_name="sequenced_principles",
            rule_type="min_length",
            value=4,
            error_message="At least 4 principles are required"
        ),
        ValidationRule(
            field_name="sequenced_principles",
            rule_type="max_length",
            value=6,
            error_message="Maximum 6 principles allowed"
        ),
    ],
    required_fields=["method_name", "sequenced_principles", "principle_descriptions"],
    next_section=SectionID.MISTAKES,
)

# Additional Signature Method prompts
SIGNATURE_METHOD_PROMPTS = {
    "intro": "Your Signature Method is your intellectual property - the unique approach that bridges the gap between your client's pain and their desired payoffs.",
    "structure": """We'll create:
1. **Method Name**: A memorable 2-4 word name for your approach
2. **Core Principles**: 4-6 principles that guide your method""",
    "examples": """Example Method Names:
- "The Clarity Framework"
- "Revenue Architecture"
- "The Growth Flywheel"
- "Strategic Momentum Method"
- "The Scale System\"""",
}