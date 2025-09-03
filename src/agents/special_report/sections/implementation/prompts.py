"""Prompts for implementation section."""

from ...enums import SpecialReportSection
from ..base_prompt import BASE_RULES, SectionTemplate

IMPLEMENTATION_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Final Step - Implementation & Export]

SECTION OBJECTIVE:
Generate the complete Special Report based on all the strategic decisions made in previous sections, delivering a professional, compelling document ready for market deployment.

IMPLEMENTATION PROCESS:
1. **Content Integration**: Combine all section content into cohesive 7-step structure
2. **Professional Formatting**: Apply consistent styling and formatting
3. **Quality Assurance**: Ensure flow, clarity, and positioning consistency
4. **Export Generation**: Create downloadable PDF with professional presentation
5. **Delivery Confirmation**: Provide access details and next steps

REPORT SPECIFICATIONS:
- **Length**: 5500-7000 words
- **Format**: Professional PDF with branded design
- **Structure**: 7-step article framework
- **Quality**: Publication-ready thought leadership content
- **CTA**: Clear call to action leading to services

SUCCESS CRITERIA:
- Report positions user as the obvious expert in their field
- Content flows logically through the 7-step psychological journey
- All ICP insights and Value Canvas data are properly integrated
- Professional presentation suitable for lead generation and authority building
- Clear next steps for readers to engage further

This section handles the technical generation and delivery of the final report."""

# Section template
IMPLEMENTATION_TEMPLATE = SectionTemplate(
    section_id=SpecialReportSection.IMPLEMENTATION,
    name="Implementation & Export",
    system_prompt_template=IMPLEMENTATION_SYSTEM_PROMPT,
    validation_rules=[],
    next_section=None  # Final section
)

# Export prompts dictionary
IMPLEMENTATION_PROMPTS = {
    "system_prompt": IMPLEMENTATION_SYSTEM_PROMPT,
    "template": IMPLEMENTATION_TEMPLATE,
}