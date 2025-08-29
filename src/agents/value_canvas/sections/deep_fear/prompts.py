"""Prompts and templates for the Deep Fear section."""

from ...enums import SectionID
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

# Deep Fear section specific prompts
DEEP_FEAR_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Section 4 of 9 - Deep Fear]

The Deep Fear is the emotional core your {{icp_nickname}} rarely voices - the private doubt that keeps them from taking action even when they know what they should do.

This isn't about surface-level concerns like "What if it doesn't work?" Instead, we're looking for the personal, vulnerable question they ask themselves in quiet moments: "What if I'm not capable enough?" or "What if success makes me someone I don't want to be?"

Deep Fears create the emotional tension that makes your messaging magnetic. When you can articulate what they're afraid to admit even to themselves, you become the guide who truly understands them.

We'll identify:
1. **The Deep Fear**: The private self-doubt they rarely voice
2. **The Golden Insight**: A surprising truth about their deepest motivation"""

# Deep Fear section template
DEEP_FEAR_TEMPLATE = SectionTemplate(
    section_id=SectionID.DEEP_FEAR,
    name="The Deep Fear",
    description="The emotional core they rarely voice",
    system_prompt_template=DEEP_FEAR_SYSTEM_PROMPT,
    validation_rules=[
        ValidationRule(
            field_name="deep_fear",
            rule_type="required",
            value=True,
            error_message="Deep fear is required"
        ),
        ValidationRule(
            field_name="golden_insight",
            rule_type="required",
            value=True,
            error_message="Golden insight is required"
        ),
    ],
    required_fields=["deep_fear", "golden_insight"],
    next_section=SectionID.PAYOFFS,
)

# Additional Deep Fear prompts
DEEP_FEAR_PROMPTS = {
    "intro": "The Deep Fear is the emotional core your ideal client rarely voices - the private doubt that keeps them from taking action.",
    "examples": """Examples of Deep Fears:
- "What if I'm not actually good enough to succeed at this level?"
- "What if success changes me into someone I don't like?"
- "What if I invest everything and still fail?"
- "What if people discover I don't have all the answers?"
- "What if I'm the problem in my business?\"""",
}