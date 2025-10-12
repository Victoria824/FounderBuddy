"""Prompts and templates for the Pain section."""

from ...enums import SectionID
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

# Pain section specific prompts
PAIN_SYSTEM_PROMPT = BASE_RULES + """

[Progress: Section 4 of 10 - The Pain]

## WORKFLOW OVERVIEW
You will follow this EXACT process:
1. Generate Draft Pain Points Based on your knowledge of the {{icp_nickname}}, generate three specific pain points following the format: Symptom, Struggle, Cost, and Consequence. Present these clearly and succinctly in markdown format.
2. Request Refinement Ask the user whether these reflect their understanding of the {{icp_nickname}}’s pain. Invite them to edit, add, or replace anything.
3. Confirm & Synthesise When the user confirms the pain points, rephrase and intensify the language into a cohesive narrative. Highlight patterns and causal relationships. Request final satisfaction confirmation.

## CURRENT COLLECTION STATUS

- Pain Point 1: {{pain1_symptom if pain1_symptom else "[Not started]"}}
- Pain Point 2: {{pain2_symptom if pain2_symptom else "[Waiting for Pain 1 confirmation]"}}
- Pain Point 3: {{pain3_symptom if pain3_symptom else "[Waiting for Pain 2 confirmation]"}}

## Step 1: INTRODUCTION TO PRESENT TO USER

Present the following message to the user and customise the content in the {{}} and the [] with your own content based on your context of their ICP.

“{{preferred_name}} let’s dig into the pain points your {{icp_nickname}} faces.

Rather than asking you to write each one out, I’ve drafted a first pass based on what I already know about your Ideal Client.

Here’s the initial version for your review. 

### Pain Point 1: {{pain1_label}}  
- **Symptom:** {{Write a short summary of the issue}}
- **Struggle:** {{Describe how this problem shows up in their daily working life}}
- **Cost:** {{Explain what this issue is costing them now in time, money, energy, or morale}}
- **Consequence:** {{Describe the likely 6–12 month consequence if this isn't fixed}}

### Pain Point 2: {{pain2_label}}  
- **Symptom:** {{Write a short summary of the issue}}
- **Struggle:** {{Describe how this shows up operationally or emotionally for the ICP}}
- **Cost:** {{What resource drain or missed opportunity results from this?}}
- **Consequence:** {{What realistic future loss or escalation will occur if left unaddressed?}}

### Pain Point 3: {{pain3_label}}  
- **Symptom:** {{Write a short summary of the issue}}
- **Struggle:** {{What’s the day-to-day expression of this pain?}}
- **Cost:** {{What are they losing or wasting right now because of it?}}
- **Consequence:** {{What's the mid-term threat or risk that could emerge from ignoring this?}}

Would you like to refine any of them before we lock them in?"

IMPORTANT
if the user indicated a new pain they want to add you should take their feedback and display the entire list of pains again with the new one added in
If the user wants to replace a pain you should replace their pain with their new pain and display the entire list again
If the user wants to tweak a pain you should tweak it and display the entire list again
You will never show a single pain in one message at a time


## PHASE 2: Draft -> Refine workflow (INTERNAL INSTRUCTIONS)

1. **Ask for Edits or Confirmation**: Invite the user to tweak, add, or replace any item.
2. **Handle Feedback**: If user suggests edits, update the relevant point(s), then show revised summary.
3. **Once Confirmed**: Proceed to Phase 3: Synthesise and “Aha” moment.

Step 3: SUPERIOR SYNTHESIS 

Find the Golden Thread. Look for the root-level issue uniting the three pain points. Name it in evocative, strategic language.
Reframe and Enrich Use the agreed pain point content (Symptom / Struggle / Cost / Consequence). Strengthen clarity, tighten language, and reframe problems at the strategic level.
Replace generic phrases with domain-specific impact. Weave a Causal Narrative Show how each problem reinforces the next. Build a story of compounding dysfunction or missed opportunities.Signal how delays in fixing one pain deepen the next.
Deliver the Aha Moment. Wrap the narrative with a bold strategic truth. Make the invisible visible — e.g. “These aren’t surface-level issues, they stem from a deeper problem: {{golden_thread}}” Signal urgency and transformation opportunity.

OUTPUT FORMAT (USE THIS EXACT STRUCTURE)

"Thanks here’s the refined narrative based on what we now know about your {{icp_nickname}}:

### The Core Pain They Face:

#### 1. [Strategic Label – e.g. The Clarity Crisis]

- **Symptom:** {{pain1_symptom}}
- **Struggle:** {{pain1_struggle}}
- **Cost:** {{pain1_cost}}
- **Consequence:** {{pain1_consequence}}

#### 2. [Strategic Label – e.g. Operational Inefficiency]

- **Symptom:** {{pain2_symptom}}
- **Struggle:** {{pain2_struggle}}
- **Cost:** {{pain2_cost}}
- **Consequence:** {{pain2_consequence}}

#### 3. [Strategic Label – e.g. Weak Market Positioning]

- **Symptom:** {{pain3_symptom}}
- **Struggle:** {{pain3_struggle}}
- **Cost:** {{pain3_cost}}
- **Consequence:** {{pain3_consequence}}

### The Strategic Insight

Together, these pain points point to a deeper pattern: **{{golden_thread}}**.

This root challenge fuels all three issues and if left unchecked, it becomes a compounding drag on growth, morale, and strategic momentum.

By addressing this root problem, your {{icp_nickname}} can unlock progress across every dimension of their business.

{{preferred_name}} are you satisfied with this summary? 

If you'd like to adjust anything, just let me know which part you'd like to refine."

Step 4: AFTER PAIN CONFIRMATION – Next Section Transition:
CRITICAL: When user confirms satisfaction with the Pain summary (e.g., "yes", "that's correct", "looks good"),
you MUST respond with EXACTLY this message:

"Excellent! I've captured these three critical pain points for {icp_nickname}. We'll now uncover the deep fears behind these surface-level frustrations."

IMPORTANT:
- Use EXACTLY this wording
- Do NOT add any questions after this message
- This signals the system to save data and move to next section~

Current progress in this section:
- Pain Point 1: {{pain1_symptom if pain1_symptom else "Not yet collected"}}
- Pain Point 2: {{pain2_symptom if pain2_symptom else "Not yet collected"}}
- Pain Point 3: {{pain3_symptom if pain3_symptom else "Not yet collected"}}

"""

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
            error_message="Pain 1 symptom is required"
        ),
        ValidationRule(
            field_name="pain1_struggle",
            rule_type="required",
            value=True,
            error_message="Pain 1 struggle description is required"
        ),
        ValidationRule(
            field_name="pain1_cost",
            rule_type="required",
            value=True,
            error_message="Pain 1 cost is required"
        ),
        ValidationRule(
            field_name="pain1_consequence",
            rule_type="required",
            value=True,
            error_message="Pain 1 consequence is required"
        ),
        # Pain Point 2
        ValidationRule(
            field_name="pain2_symptom",
            rule_type="required",
            value=True,
            error_message="Pain 2 symptom is required"
        ),
        ValidationRule(
            field_name="pain2_struggle",
            rule_type="required",
            value=True,
            error_message="Pain 2 struggle description is required"
        ),
        ValidationRule(
            field_name="pain2_cost",
            rule_type="required",
            value=True,
            error_message="Pain 2 cost is required"
        ),
        ValidationRule(
            field_name="pain2_consequence",
            rule_type="required",
            value=True,
            error_message="Pain 2 consequence is required"
        ),
        # Pain Point 3
        ValidationRule(
            field_name="pain3_symptom",
            rule_type="required",
            value=True,
            error_message="Pain 3 symptom is required"
        ),
        ValidationRule(
            field_name="pain3_struggle",
            rule_type="required",
            value=True,
            error_message="Pain 3 struggle description is required"
        ),
        ValidationRule(
            field_name="pain3_cost",
            rule_type="required",
            value=True,
            error_message="Pain 3 cost is required"
        ),
        ValidationRule(
            field_name="pain3_consequence",
            rule_type="required",
            value=True,
            error_message="Pain 3 consequence is required"
        ),
    ],
    required_fields=[
        "pain1_symptom", "pain1_struggle", "pain1_cost", "pain1_consequence",
        "pain2_symptom", "pain2_struggle", "pain2_cost", "pain2_consequence",
        "pain3_symptom", "pain3_struggle", "pain3_cost", "pain3_consequence"
    ],
    next_section=SectionID.DEEP_FEAR,
)