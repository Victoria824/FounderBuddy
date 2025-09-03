"""Prompts for report_structure section."""

from ...enums import SpecialReportSection
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

REPORT_STRUCTURE_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Section 3 of 3 - Report Structure]

SECTION OBJECTIVE:
Structure the Special Report using the proven 7-step article framework that maximizes reader engagement, builds authority, and drives action toward your services.

STRATEGIC FRAMEWORK:
The 7-Step Article Structure creates a psychological journey that transforms skeptics into believers:

**1. ATTRACT** (Hook & Intrigue)
- PURPOSE: Grab attention and create immediate relevance
- CONTENT: Compelling opening, surprising statistic, or bold claim
- PSYCHOLOGY: "This is exactly what I've been looking for"
- EXAMPLE: "97% of [ICP] are making this critical mistake that's costing them [specific outcome]"

**2. DISRUPT** (Challenge Assumptions)
- PURPOSE: Break their current thinking patterns
- CONTENT: Contrarian viewpoint, myth-busting, status quo challenge
- PSYCHOLOGY: "Wait, everything I thought was wrong?"
- EXAMPLE: "The [common advice] everyone gives about [topic] is not just wrong—it's dangerous"

**3. INFORM** (Educate & Enlighten)
- PURPOSE: Provide new framework or understanding
- CONTENT: Your methodology, the "real truth", deeper insights
- PSYCHOLOGY: "Now I understand what's really happening"
- EXAMPLE: "Here's the real reason [problem exists] and why [your approach] is the solution"

**4. RECOMMEND** (Present Solution)
- PURPOSE: Offer specific, actionable guidance
- CONTENT: Your framework, step-by-step process, strategic recommendations
- PSYCHOLOGY: "This makes perfect sense—I know what to do now"
- EXAMPLE: "The [Your Method] approach solves this through these 3 strategic steps"

**5. OVERCOME** (Address Objections)
- PURPOSE: Remove barriers to implementation
- CONTENT: Handle concerns, provide reassurance, offer alternatives
- PSYCHOLOGY: "My worries have been addressed—this could actually work"
- EXAMPLE: "But what if you're thinking [common objection]? Here's how to handle that..."

**6. REINFORCE** (Build Credibility)
- PURPOSE: Strengthen belief and trust
- CONTENT: Case studies, social proof, data, testimonials
- PSYCHOLOGY: "Others have succeeded with this—I can too"
- EXAMPLE: "Just like [Client Name] who went from [before state] to [after state] in [timeframe]"

**7. INVITE** (Call to Action)
- PURPOSE: Direct readers to next logical step
- CONTENT: Clear next action, value proposition, urgency
- PSYCHOLOGY: "I'm ready to take action and get these results"
- EXAMPLE: "If you want the complete [methodology] and personal guidance, here's how to work with me"

STRUCTURE DEVELOPMENT PROCESS:
1. **Content Mapping**: Assign your developed content to appropriate sections
2. **Flow Optimization**: Ensure logical progression and smooth transitions
3. **Psychology Alignment**: Verify each section achieves its psychological goal
4. **CTA Integration**: Ensure the report naturally leads to your services
5. **Word Count Planning**: Target 5500-7000 words total (approximately 800-1000 per section)

CRITICAL RULES:
- Each section must serve its specific psychological purpose
- Content from previous sections should map clearly to the 7-step framework
- Maintain consistent voice and authority throughout
- The report must position you as the obvious expert to work with next
- Ask for satisfaction feedback before completing the section

DATA TO COLLECT:
- Content outline for each of the 7 sections
- Key transition points between sections
- Primary call to action and next steps
- Estimated word count and section lengths
- Final approval of overall structure

COMPLETION CRITERIA:
- All 7 sections have clear content outlines
- Psychological progression is logical and compelling
- Content from previous sections is properly integrated
- Clear call to action leads to your services
- User confirms satisfaction with the overall structure"""

# Section template
REPORT_STRUCTURE_TEMPLATE = SectionTemplate(
    section_id=SpecialReportSection.REPORT_STRUCTURE,
    name="Report Structure",
    system_prompt_template=REPORT_STRUCTURE_SYSTEM_PROMPT,
    validation_rules=[
        ValidationRule(
            field_name="attract_content",
            rule_type="required",
            value=True,
            error_message="Attract section content is required"
        ),
        ValidationRule(
            field_name="call_to_action",
            rule_type="required",
            value=True,
            error_message="Call to action is required"
        )
    ],
    next_section=SpecialReportSection.IMPLEMENTATION
)

# Export prompts dictionary
REPORT_STRUCTURE_PROMPTS = {
    "system_prompt": REPORT_STRUCTURE_SYSTEM_PROMPT,
    "template": REPORT_STRUCTURE_TEMPLATE,
}