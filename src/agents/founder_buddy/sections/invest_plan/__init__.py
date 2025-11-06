"""Investment Plan section for Founder Buddy."""

from ...enums import SectionID
from ..base_prompt import SectionTemplate, ValidationRule

INVEST_PLAN_TEMPLATE = SectionTemplate(
    section_id=SectionID.INVEST_PLAN,
    name="Investment Plan",
    description="Define your investment needs and plan",
    system_prompt_template="""
You are helping the founder clarify their investment plan.

In this section, you need to gather:
1. Funding amount - How much funding are you seeking?
2. Funding use - What will you use the funding for?
3. Valuation - What is your current/expected valuation?
4. Exit strategy - What is your long-term exit plan?

Guidelines:
- Ask one question at a time
- Be realistic about funding needs
- Help them think through how funding will accelerate growth
- Discuss timeline and milestones
- Once you have all elements, present a summary and ask if they're satisfied
""",
    validation_rules=[
        ValidationRule(
            field_name="funding_amount",
            rule_type="required",
            value=True,
            error_message="Funding amount is required"
        ),
        ValidationRule(
            field_name="funding_use",
            rule_type="required",
            value=True,
            error_message="Funding use is required"
        ),
    ],
    required_fields=["funding_amount", "funding_use"],
    next_section=None,  # This is the last section
)

