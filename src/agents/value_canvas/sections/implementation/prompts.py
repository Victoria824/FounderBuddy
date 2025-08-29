"""Prompts and templates for the Implementation section."""

from ...enums import SectionID
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

# Implementation section specific prompts
IMPLEMENTATION_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Section 9 of 9 - Implementation]

Congratulations! You've completed your Value Canvas framework. Now let's create your implementation roadmap to turn this framework into real-world results.

This section provides:
1. **Immediate Next Steps**: What to do in the next 7 days
2. **Testing Strategy**: How to validate your messaging in the market
3. **Refinement Process**: How to iterate based on feedback
4. **Integration Points**: Where to use your Value Canvas across your business

Remember: The Value Canvas is a living document. Your first version is a hypothesis to test, not a final answer. The magic happens when you take it to market and refine based on real feedback.

Key Implementation Areas:
- Website and landing pages
- Sales conversations
- Marketing materials
- Social media messaging
- Email sequences
- Content strategy"""

# Implementation section template
IMPLEMENTATION_TEMPLATE = SectionTemplate(
    section_id=SectionID.IMPLEMENTATION,
    name="Implementation",
    description="Your roadmap for putting the Value Canvas into action",
    system_prompt_template=IMPLEMENTATION_SYSTEM_PROMPT,
    validation_rules=[],
    required_fields=[],
    next_section=None,  # This is the final section
)

# Additional Implementation prompts
IMPLEMENTATION_PROMPTS = {
    "intro": "Congratulations! You've completed your Value Canvas framework. Now let's create your implementation roadmap.",
    "next_steps": """Immediate Next Steps (Next 7 Days):
1. Share your Value Canvas with 3 trusted clients for feedback
2. Update your LinkedIn headline using your Prize statement
3. Rewrite one key page on your website using the Pain-Payoff framework
4. Test your ICP definition in 5 sales conversations
5. Create one piece of content addressing your top Pain point""",
    "testing": """Testing Strategy:
- Start with low-risk environments (team, partners, existing clients)
- Document which elements get the strongest reactions
- A/B test different versions of your Prize statement
- Track conversation quality when using the framework
- Note where prospects say "that's exactly right!\"""",
    "refinement": """Refinement Process:
- Week 1-2: Internal testing and initial adjustments
- Week 3-4: Test with friendly market (existing network)
- Week 5-8: Test with cold market (new prospects)
- Week 9-12: Major refinement based on patterns
- Ongoing: Quarterly reviews and updates""",
}