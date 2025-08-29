"""Prompts and templates for the ICP section."""

from ...enums import SectionID
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

# ICP section specific prompts (simplified for demonstration)
ICP_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Section 2 of 9 - Ideal Client Persona]

CRITICAL INSTRUCTION FOR YOUR FIRST MESSAGE:
When you start this section, your very first message to the user should include the following text in the "reply" field of your JSON response. Use this exact text:

Let me start with some context around your ICP.

Your Ideal Client Persona (ICP)—the ultimate decision maker who will be the focus of your Value Canvas. Rather than trying to appeal to everyone, we'll create messaging that resonates deeply with this specific person.

Your ICP isn't just a 'nice to have' — it's your business foundation. The most expensive mistake in business is talking to the wrong people about the right things. This section helps ensure every other part of your Value Canvas speaks directly to someone who can actually invest in your product / service.

For our first pass, we're going to work on a basic summary of your ICP that's enough to get us through a first draft of your Value Canvas.

Then your job is to test in the market. You can start with testing it on others on the KPI program, family, friends, team, trusted clients and ultimately, prospects.

The Sprint Playbook, and the Beyond the Sprint Playbook will guide you on how to refine it in the real world. Then you can come back and refine it with me later, ensuring I've got the latest and most relevant version in my memory.

Remember, we test in the market, not in our minds.

The first thing I'd like you to do is to give me a brain dump of your current best thinking of who your ICP is.

You may already know and have done some deep work on this in which case, this won't take long, or, you may be unsure, in which case, this process should be quite useful.

Just go on a bit of a rant and I'll do my best to refine it with you if needed.

[Additional ICP-specific rules and instructions would continue here...]"""

# ICP section template
ICP_TEMPLATE = SectionTemplate(
    section_id=SectionID.ICP,
    name="Ideal Client Persona",
    description="Define the ultimate decision-maker who will be the focus of the Value Canvas",
    system_prompt_template=ICP_SYSTEM_PROMPT,
    validation_rules=[
        ValidationRule(
            field_name="icp_nickname",
            rule_type="required",
            value=True,
            error_message="ICP nickname is required"
        ),
        ValidationRule(
            field_name="icp_role_identity",
            rule_type="required",
            value=True,
            error_message="ICP role/identity is required"
        ),
    ],
    required_fields=[
        "icp_nickname",
        "icp_role_identity",
        "icp_context_scale",
        "icp_industry_sector_context",
        "icp_demographics",
        "icp_interests",
        "icp_values",
        "icp_golden_insight"
    ],
    next_section=SectionID.PAIN,
)

# Additional ICP prompts
ICP_PROMPTS = {
    "intro": """Let me start with some context around your ICP.

Your Ideal Client Persona (ICP)—the ultimate decision maker who will be the focus of your Value Canvas. Rather than trying to appeal to everyone, we'll create messaging that resonates deeply with this specific person.""",
    "brain_dump": """The first thing I'd like you to do is to give me a brain dump of your current best thinking of who your ICP is.

You may already know and have done some deep work on this in which case, this won't take long, or, you may be unsure, in which case, this process should be quite useful.

Just go on a bit of a rant and I'll do my best to refine it with you if needed.""",
}