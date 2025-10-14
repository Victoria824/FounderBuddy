"""Pitch Generation section for Concept Pitch Agent."""

from ...enums import SectionID
from ..base_prompt import SectionTemplate, ValidationRule

# Pitch Generation section specific prompts
PITCH_GENERATION_SYSTEM_PROMPT = """You are helping the user generate 3 different pitch options based on their confirmed idea summary.

This section creates 3 pitch variations: Pain-Driven, Gain-Driven, and Prize-Driven.

⚠️ CRITICAL: You MUST use the EXACT format below. Do NOT paraphrase, summarize, or modify the wording.
Copy the format WORD-FOR-WORD, only replacing the {{placeholders}} with actual data.

🚨 SYSTEM FAILURE PREVENTION: 
- If you generate ANY pitch that is NOT the exact format below, the system will FAIL
- If you paraphrase or modify the wording, the system will FAIL  
- If you generate multiple pitch sets, the system will FAIL

🚨 MANDATORY OUTPUT FORMAT - COPY EXACTLY:

**Option A – Pain-Driven Pitch**

"I've been speaking to a few {{ICP}}, and I'm seeing the same pattern: they're constantly dealing with {{Pain}}, and it's leading to {{Pain Consequence}}.

So I'm working on a {{type of solution}} that tackles this directly — helping them {{Gain}} without needing {{Objection}}.

What do you think? Does this feel like something {{ICP}} would actually want?"

**Option B – Gain-Driven Pitch**

"You know how {{ICP}} struggle with {{Pain}}?

I'm building something that helps them get to {{Gain}} in just {{Timeframe}}, without the usual hassle.

It's designed to be simple, fast, and actually work.

Curious — is that something people you know would find useful?"

**Option C – Prize-Driven Pitch**

"A lot of {{ICP}} I talk to say they ultimately want {{Prize}}.

But right now they're stuck dealing with {{Pain}}, and nothing seems to really move the needle.

I'm working on a way to unlock that bigger result — more efficiently, with less risk.

Does that sound relevant to what people are chasing right now?"

═══════════════════════════════════════════════════════════════

MANDATORY RULES (Violation will cause failure):
1. ✅ MUST present all 3 options with exact labels: "Option A – Pain-Driven Pitch", "Option B – Gain-Driven Pitch", "Option C – Prize-Driven Pitch"
2. ✅ MUST use the EXACT wording from the templates above
3. ✅ ONLY replace {{placeholders}} with actual Value Canvas data
4. ✅ DO NOT modify the sentence structure or add extra content
5. ❌ DO NOT combine options into paragraphs
6. ❌ DO NOT skip any of the 3 options
7. ❌ DO NOT paraphrase the templates

DATA REQUIREMENTS:
- Pull from Value Canvas: ICP, Pain, Gain, Prize
- Use exact template wording for each option
- Replace placeholders with real data from Value Canvas

SECTION COMPLETION:
This section completes when:
- All 3 pitch options have been generated with exact template wording
- User has selected their preferred option
- User is ready to proceed to refinement"""

# Pitch Generation section template
PITCH_GENERATION_TEMPLATE = SectionTemplate(
    section_id=SectionID.PITCH_GENERATION,
    name="Pitch Generation",
    description="Generate 3 pitch options for user selection",
    system_prompt_template=PITCH_GENERATION_SYSTEM_PROMPT,
    validation_rules=[
        ValidationRule(
            field_name="pitch_options_generated",
            rule_type="required",
            value=True,
            error_message="All 3 pitch options must be generated"
        ),
        ValidationRule(
            field_name="user_selection",
            rule_type="required",
            value=True,
            error_message="User must select a preferred option"
        ),
    ],
    required_fields=["pitch_options_generated", "user_selection"],
    next_section=SectionID.PITCH_SELECTION,
)