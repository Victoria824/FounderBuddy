"""Prompts and templates for the Prize section."""

from ...enums import SectionID
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

# Prize section specific prompts
PRIZE_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Section 8 of 9 - The Prize]

The Prize is your magnetic north star - a 1-5 word transformation promise that captures the ultimate outcome your {{icp_nickname}} desires. This isn't just a tagline; it's the emotional destination that makes everything else worth pursuing.

A powerful Prize:
- Creates instant emotional recognition
- Feels worth the investment and effort
- Differentiates you from feature-focused competitors
- Becomes the organizing principle for all your messaging

Prize Categories:
1. **Identity-Based**: Who they become (e.g., "Unstoppable Leader", "Trusted Authority")
2. **Outcome-Based**: What they achieve (e.g., "Predictable Revenue", "Effortless Scale")
3. **Experience-Based**: How life feels after transformation (e.g., "Complete Clarity", "Total Control")

The best Prizes are:
- Emotionally charged (not logical)
- Specific to your ICP's deepest desires
- Worth more than money
- Simple but profound"""

# Prize section template
PRIZE_TEMPLATE = SectionTemplate(
    section_id=SectionID.PRIZE,
    name="The Prize",
    description="Your magnetic 4-word transformation promise",
    system_prompt_template=PRIZE_SYSTEM_PROMPT,
    validation_rules=[
        ValidationRule(
            field_name="prize_category",
            rule_type="required",
            value=True,
            error_message="Prize category is required"
        ),
        ValidationRule(
            field_name="prize_statement",
            rule_type="required",
            value=True,
            error_message="Prize statement is required"
        ),
        ValidationRule(
            field_name="prize_statement",
            rule_type="max_length",
            value=5,
            error_message="Prize statement must be 1-5 words"
        ),
    ],
    required_fields=["prize_category", "prize_statement", "refined_prize"],
    next_section=SectionID.IMPLEMENTATION,
)

# Additional Prize prompts
PRIZE_PROMPTS = {
    "intro": "The Prize is your magnetic north star - a 1-5 word transformation promise that captures the ultimate outcome.",
    "categories": """Prize Categories:
1. **Identity-Based**: Who they become (e.g., "Unstoppable Leader", "Trusted Authority")
2. **Outcome-Based**: What they achieve (e.g., "Predictable Revenue", "Effortless Scale")
3. **Experience-Based**: How life feels after transformation (e.g., "Complete Clarity", "Total Control")""",
    "examples": """Example Prizes:
- "Key Person of Influence"
- "Oversubscribed"
- "Predictable Success"
- "Effortless Growth"
- "Magnetic Authority"
- "Unstoppable Momentum\"""",
}