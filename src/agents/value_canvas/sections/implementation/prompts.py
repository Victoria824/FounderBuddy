"""Prompts and templates for the Implementation section."""

from ...enums import SectionID
from ..base_prompt import BASE_RULES, SectionTemplate

# Implementation section specific prompts
IMPLEMENTATION_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Section 9 of 9 - Implementation]

Congratulations! You've completed your Value Canvas.

Here's your complete Value Canvas summary:

PRIZE: {{refined_prize}}

PAINS → PAYOFFS:
- {{pain1_symptom}} → {{payoff1_objective}}
- {{pain2_symptom}} → {{payoff2_objective}}
- {{pain3_symptom}} → {{payoff3_objective}}

SIGNATURE METHOD: {{method_name}}

Your Prize statement is the destination that all other elements drive toward.

Implementation Guidance:
1. Brief writers, designers, and team members using this framework
2. Test messaging components in real conversations with prospects
3. Audit existing marketing assets against this new messaging backbone
4. Integrate these elements into sales conversations and presentations
5. Schedule quarterly reviews to refine based on market feedback

Would you like me to generate your implementation checklist and export your Value Canvas?"""

# Implementation section template
IMPLEMENTATION_TEMPLATE = SectionTemplate(
    section_id=SectionID.IMPLEMENTATION,
    name="Implementation",
    description="Export completed Value Canvas as checklist/PDF",
    system_prompt_template=IMPLEMENTATION_SYSTEM_PROMPT,
    validation_rules=[],
    required_fields=[],
    next_section=None,
)

