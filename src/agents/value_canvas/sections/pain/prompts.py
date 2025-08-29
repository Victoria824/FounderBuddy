"""Prompts and templates for the Pain section."""

from ...enums import SectionID
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

# Pain section specific prompts
PAIN_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Section 3 of 9 - The Pain]

Now let's identify what keeps your {{icp_nickname}} up at night. The Pain section is the hook that creates instant recognition and resonance. When you can describe their challenges better than they can themselves, you build immediate trust and credibility.

While generic problems live in the analytical mind, real Pain lives in both the mind and heart—exactly where buying decisions are made. By identifying specific pain points that hit them emotionally, you'll create messaging that stops your ideal client in their tracks and makes them think 'that's exactly what I'm experiencing!'

We'll focus on creating three distinct Pain points that speak directly to your {{icp_nickname}}. Each will follow a specific structure that builds tension between where they are now and where they want to be. This tension becomes the driver for all your messaging.

For each Pain Point, we'll capture four essential elements:
1. **Symptom** (1-3 words): The observable problem
2. **Struggle** (1-2 sentences): How this shows up in their daily work life
3. **Cost** (Immediate impact): What it's costing them right now
4. **Consequence** (Future impact): What happens if they don't solve this

CRITICAL SUMMARY RULE:
- **MENTAL WORKFLOW FOR SUPERIOR SYNTHESIS:** Before writing the summary, follow these steps internally:
  1. **Identify the Golden Thread:** Read through all three pain points. What is the single underlying theme or root cause connecting them? Is it a lack of strategy? Operational chaos? A failure to connect with the market? Start your summary with this core insight.
  2. **Reframe, Don't Repeat:** For each pain point, elevate the user's language. Transform their descriptions into strategic-level insights. Use metaphors and stronger vocabulary.
  3. **Weave a Narrative:** Don't just list the points. Show how they are causally linked. Explain how the Struggle of one point creates the Symptom of another. Build a story of escalating consequences.
  4. **Deliver the "Aha" Moment:** Conclude by summarizing the interconnected nature of these problems and frame them as a single, critical challenge that must be addressed.

CRITICAL: Only provide section_update with ALL THREE pain points when they are complete. The rating should be requested only after all three pain points have been collected."""

# Pain section template
PAIN_TEMPLATE = SectionTemplate(
    section_id=SectionID.PAIN,
    name="The Pain",
    description="Three specific frustrations that create instant recognition",
    system_prompt_template=PAIN_SYSTEM_PROMPT,
    validation_rules=[
        # Pain Point 1
        ValidationRule(
            field_name="pain1_symptom",
            rule_type="required",
            value=True,
            error_message="Pain point 1 symptom is required"
        ),
        ValidationRule(
            field_name="pain1_struggle",
            rule_type="required",
            value=True,
            error_message="Pain point 1 struggle is required"
        ),
        ValidationRule(
            field_name="pain1_cost",
            rule_type="required",
            value=True,
            error_message="Pain point 1 cost is required"
        ),
        ValidationRule(
            field_name="pain1_consequence",
            rule_type="required",
            value=True,
            error_message="Pain point 1 consequence is required"
        ),
        # Pain Point 2
        ValidationRule(
            field_name="pain2_symptom",
            rule_type="required",
            value=True,
            error_message="Pain point 2 symptom is required"
        ),
        ValidationRule(
            field_name="pain2_struggle",
            rule_type="required",
            value=True,
            error_message="Pain point 2 struggle is required"
        ),
        ValidationRule(
            field_name="pain2_cost",
            rule_type="required",
            value=True,
            error_message="Pain point 2 cost is required"
        ),
        ValidationRule(
            field_name="pain2_consequence",
            rule_type="required",
            value=True,
            error_message="Pain point 2 consequence is required"
        ),
        # Pain Point 3
        ValidationRule(
            field_name="pain3_symptom",
            rule_type="required",
            value=True,
            error_message="Pain point 3 symptom is required"
        ),
        ValidationRule(
            field_name="pain3_struggle",
            rule_type="required",
            value=True,
            error_message="Pain point 3 struggle is required"
        ),
        ValidationRule(
            field_name="pain3_cost",
            rule_type="required",
            value=True,
            error_message="Pain point 3 cost is required"
        ),
        ValidationRule(
            field_name="pain3_consequence",
            rule_type="required",
            value=True,
            error_message="Pain point 3 consequence is required"
        ),
    ],
    required_fields=[
        "pain1_symptom", "pain1_struggle", "pain1_cost", "pain1_consequence",
        "pain2_symptom", "pain2_struggle", "pain2_cost", "pain2_consequence",
        "pain3_symptom", "pain3_struggle", "pain3_cost", "pain3_consequence"
    ],
    next_section=SectionID.DEEP_FEAR,
)

# Additional Pain prompts
PAIN_PROMPTS = {
    "intro": "Now let's identify what keeps your ideal client up at night.",
    "structure": """For each Pain Point, we'll capture four essential elements:
1. **Symptom** (1-3 words): The observable problem
2. **Struggle** (1-2 sentences): How this shows up in their daily work life
3. **Cost** (Immediate impact): What it's costing them right now
4. **Consequence** (Future impact): What happens if they don't solve this""",
}