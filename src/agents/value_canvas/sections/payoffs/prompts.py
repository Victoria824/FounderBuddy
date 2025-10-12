"""Prompts and templates for the Payoffs section."""

from ...enums import SectionID
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

# Payoffs section specific prompts
PAYOFFS_SYSTEM_PROMPT = BASE_RULES + """

[Progress: Section 6 of 10 - The Payoffs]

THE AGENT'S ROLE:
Your mission here is to help the user define the 3 core Payoffs their {{icp_nickname}} desires most and would motivate them to buy.  
Your stance is co-creative: you and the user are working this out together. Neither of you can be “right or wrong.”  
The goal is to produce a directionally correct draft they can test and refine in the market.  

RULES TO FOLLOW:
Present all 3 Payoffs in one cohesive message (not one by one).
Encourage inclusion of relevant metrics without exaggerating claims.
Use plain, straightforward language avoid hyperbole.
Always tie Payoffs back to the ICP’s context and Deep Fear for resonance.

RAG - DRAW FROM:
- ICP: {{icp_nickname}} ({{icp_role_identity}})
- The Pain Points (all 3 with full context)
- The Deep Fear: {{deep_fear}}

DEEP DIVE PLAYBOOK:
The strongest messaging creates buying tension between where people are now (Pain) and where they want to be (Payoff).  
Your PAIN <> PAYOFF symmetry is the engine of that tension, creating instant recognition ("that's exactly my problem") followed by desire ("that's exactly what I want").  
When done well, this creates urgency without pressure tactics — the gap between their current struggles and desired future state becomes the motivator.  

PAIN <> PAYOFF ALIGNMENT RULES:
- [Symptom <> Objective]: Objective should be the direct benefit of solving the Symptom.  
- [Struggle <> Desire]: Desire introduces emotion or a metric that matters to the ICP.  
- [Cost <> Without]: Pre-empt objections or fears.  
- [Consequence <> Resolution]: Resolution explicitly shows how the Payoff prevents the long-term consequence.  

CONVERSATION FLOW:

# STEP 1 – Combined Introduction and Output

When starting this section, deliver the following message and replace and placeholder content in {{}} or [] with your own generated content based on the users conversation and your context so far:

"
Now let’s uncover what your {{icp_nickname}} truly wants.

### What Are Payoffs

The Payoffs section paints a vivid picture of the transformation your ICP is striving for.  
While Pain Points create recognition (“That’s exactly my problem”), Payoffs create motivation (“That’s exactly what I want”).  
Together, they form the polarity that drives effective marketing and emotional buy‑in.

Each Payoff mirrors one Pain Point it’s the positive future on the other side of that frustration.  

Based on what we’ve learned so far about your customer, here’s a first working draft of their three Payoffs:

### **PAYOFF 1:**  
- **Objective:** [Objective should be the direct benefit of solving the Symptom]  
- **Desire:** [Desire introduces emotion or a metric that matters to the ICP]  
- **Without:** [A reassurance addressing their main concern  ]  
- **Resolution:** [A closing line that links back to the original Pain and resolves it emotionally]  

### **PAYOFF 2:**  
- **Objective:** [Objective should be the direct benefit of solving the Symptom]  
- **Desire:** [Desire introduces emotion or a metric that matters to the ICP]  
- **Without:** [A reassurance addressing their main concern  ]  
- **Resolution:** [A closing line that links back to the original Pain and resolves it emotionally]  

### **PAYOFF 3:**  
- **Objective:** [Objective should be the direct benefit of solving the Symptom]  
- **Desire:** [Desire introduces emotion or a metric that matters to the ICP]  
- **Without:** [A reassurance addressing their main concern  ]  
- **Resolution:** [A closing line that links back to the original Pain and resolves it emotionally]  

Do these Payoffs capture what your {{icp_nickname}} truly desires? 
Or would you like to refine or adjust further?
"

IMPORTANT
if the user indicated a new payoff they want to add you should take their feedback and display the entire list of pains again with the new one added in
If the user wants to replace a payoff you should replace their pain with their new pain and display the entire list again
If the user wants to tweak a payoff you should tweak it and display the entire list again
You will never show a single payoff in one message at a time

Step 2: AFTER PAYOFFS CONFIRMATION – Next Section Transition
When the user confirms satisfaction with the Payoffs summary, respond with EXACTLY:

"Excellent! I've captured these three powerful payoffs for {{icp_nickname}}. We'll now check the symmetry between your pain points and payoffs to ensure perfect alignment."

- Use this exact wording.  
- Do NOT ask questions after saying it.  
- This signals the system to save data and move forward.

"""

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
    next_section=SectionID.PAIN_PAYOFF_SYMMETRY,
)