"""Prompts and templates for the Payoffs section."""

from ...enums import SectionID
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

# Payoffs section specific prompts
PAYOFFS_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Section 5 of 9 - The Payoffs]

Now let's flip the script. Instead of focusing on pain, we'll articulate the specific outcomes your {{icp_nickname}} desires - the payoffs that make transformation worth pursuing.

Great payoffs don't just promise generic benefits. They paint a vivid picture of life after the problem is solved, addressing both practical outcomes and emotional rewards. This creates pull toward your solution rather than just push away from pain.

We'll create three Payoff points that directly mirror your Pain points. Each will follow this structure:
1. **Objective** (1-3 words): What they want to achieve
2. **Desire** (1-2 sentences): What they specifically want
3. **Without** (Pre-handle objections): Address common concerns
4. **Resolution**: How this resolves the corresponding pain

CRITICAL: Each Payoff should directly address and resolve one of the Pain points identified earlier. The resolution should create a clear before/after contrast."""

# Payoffs section template
PAYOFFS_TEMPLATE = SectionTemplate(
    section_id=SectionID.PAYOFFS,
    name="The Payoffs",
    description="Three specific outcomes that mirror the pain points",
    system_prompt_template=PAYOFFS_SYSTEM_PROMPT,
    validation_rules=[
        # Payoff Point 1
        ValidationRule(
            field_name="payoff1_objective",
            rule_type="required",
            value=True,
            error_message="Payoff point 1 objective is required"
        ),
        ValidationRule(
            field_name="payoff1_desire",
            rule_type="required",
            value=True,
            error_message="Payoff point 1 desire is required"
        ),
        ValidationRule(
            field_name="payoff1_without",
            rule_type="required",
            value=True,
            error_message="Payoff point 1 without is required"
        ),
        ValidationRule(
            field_name="payoff1_resolution",
            rule_type="required",
            value=True,
            error_message="Payoff point 1 resolution is required"
        ),
        # Payoff Point 2
        ValidationRule(
            field_name="payoff2_objective",
            rule_type="required",
            value=True,
            error_message="Payoff point 2 objective is required"
        ),
        ValidationRule(
            field_name="payoff2_desire",
            rule_type="required",
            value=True,
            error_message="Payoff point 2 desire is required"
        ),
        ValidationRule(
            field_name="payoff2_without",
            rule_type="required",
            value=True,
            error_message="Payoff point 2 without is required"
        ),
        ValidationRule(
            field_name="payoff2_resolution",
            rule_type="required",
            value=True,
            error_message="Payoff point 2 resolution is required"
        ),
        # Payoff Point 3
        ValidationRule(
            field_name="payoff3_objective",
            rule_type="required",
            value=True,
            error_message="Payoff point 3 objective is required"
        ),
        ValidationRule(
            field_name="payoff3_desire",
            rule_type="required",
            value=True,
            error_message="Payoff point 3 desire is required"
        ),
        ValidationRule(
            field_name="payoff3_without",
            rule_type="required",
            value=True,
            error_message="Payoff point 3 without is required"
        ),
        ValidationRule(
            field_name="payoff3_resolution",
            rule_type="required",
            value=True,
            error_message="Payoff point 3 resolution is required"
        ),
    ],
    required_fields=[
        "payoff1_objective", "payoff1_desire", "payoff1_without", "payoff1_resolution",
        "payoff2_objective", "payoff2_desire", "payoff2_without", "payoff2_resolution",
        "payoff3_objective", "payoff3_desire", "payoff3_without", "payoff3_resolution"
    ],
    next_section=SectionID.SIGNATURE_METHOD,
)

# Additional Payoffs prompts
PAYOFFS_PROMPTS = {
    "intro": "Now let's flip the script. Instead of focusing on pain, we'll articulate the specific outcomes your ideal client desires.",
    "structure": """For each Payoff Point, we'll capture:
1. **Objective** (1-3 words): What they want to achieve
2. **Desire** (1-2 sentences): What they specifically want
3. **Without** (Pre-handle objections): Address common concerns
4. **Resolution**: How this resolves the corresponding pain""",
}