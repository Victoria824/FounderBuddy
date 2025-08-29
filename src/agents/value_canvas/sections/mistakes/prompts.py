"""Prompts and templates for the Mistakes section."""

from ...enums import SectionID
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

# Mistakes section specific prompts
MISTAKES_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Section 7 of 9 - The Mistakes]

The Mistakes section reveals why your {{icp_nickname}} stays stuck despite their best efforts. These aren't character flaws - they're logical actions based on incomplete understanding that actually make their problems worse.

Great mistakes create "aha" moments. They explain why common advice hasn't worked and position your Signature Method as the missing piece they've been searching for.

For each Signature Method principle, we'll identify:
1. **Error in Thinking**: The flawed belief that keeps them stuck
2. **Error in Action**: The counterproductive action that feels right but backfires

These mistakes should:
- Feel counterintuitive (what seems right is actually wrong)
- Explain why they haven't solved this problem already
- Create urgency for a new approach (your method)"""

# Mistakes section template
MISTAKES_TEMPLATE = SectionTemplate(
    section_id=SectionID.MISTAKES,
    name="The Mistakes",
    description="Hidden errors that keep clients stuck",
    system_prompt_template=MISTAKES_SYSTEM_PROMPT,
    validation_rules=[
        ValidationRule(
            field_name="mistakes",
            rule_type="required",
            value=True,
            error_message="Mistakes list is required"
        ),
    ],
    required_fields=["mistakes"],
    next_section=SectionID.PRIZE,
)

# Additional Mistakes prompts
MISTAKES_PROMPTS = {
    "intro": "The Mistakes section reveals why your ideal client stays stuck despite their best efforts.",
    "structure": """For each Signature Method principle, we'll identify:
1. **Error in Thinking**: The flawed belief that keeps them stuck
2. **Error in Action**: The counterproductive action that feels right but backfires""",
    "examples": """Example Mistakes:
- Error in Thinking: "More features will attract more customers"
  Error in Action: Adding complexity instead of focusing on core value
  
- Error in Thinking: "I need to be available 24/7 to be valuable"
  Error in Action: Saying yes to everything, leading to burnout
  
- Error in Thinking: "If I just work harder, results will come"
  Error in Action: Increasing effort without changing strategy""",
}