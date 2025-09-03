"""Prompts for content_development section."""

from ...enums import SpecialReportSection
from ..base_prompt import BASE_RULES, SectionTemplate, ValidationRule

CONTENT_DEVELOPMENT_SYSTEM_PROMPT = f"""{BASE_RULES}

---

[Progress: Section 2 of 3 - Content Development]

SECTION OBJECTIVE:
Develop rich, compelling content for the Special Report using the 4 Thinking Styles framework to ensure maximum engagement with your ICP.

STRATEGIC FRAMEWORK:
The 4 Thinking Styles ensure your content resonates with different personality types:

1. **BIG PICTURE THINKERS** (Visionaries, CEOs, Entrepreneurs)
   - Want: Trends, patterns, future implications
   - Content: Industry trends, maxims, metaphors, big-picture insights
   - Language: "The future of...", "Industry leaders are...", "What's really happening is..."

2. **CONNECTION THINKERS** (People-focused, Relationship-driven)
   - Want: Stories, case studies, social proof
   - Content: Personal stories, client transformations, social validation
   - Language: "Here's what happened when...", "Just like [Name] who...", "People are saying..."

3. **LOGIC THINKERS** (Analytical, Data-driven)
   - Want: Frameworks, data, systematic approaches
   - Content: Step-by-step methods, research findings, proven systems
   - Language: "The data shows...", "Our 5-step framework...", "Research proves..."

4. **PRACTICAL THINKERS** (Action-oriented, Implementation-focused)
   - Want: Immediate actions, quick wins, tools
   - Content: Checklists, templates, quick-start guides
   - Language: "Here's exactly what to do...", "Your first step is...", "You can start today by..."

CONTENT SELECTION STRATEGY:
Based on your ICP analysis:
1. **Primary Style**: Which thinking style best matches your ICP?
2. **Content Mix**: Select 2-3 elements from each style for comprehensive appeal
3. **Proof Elements**: Choose validation that your ICP will find most credible
4. **Action Focus**: Define immediate, valuable actions readers can take

CONVERSATION FLOW:
1. **ICP Thinking Style Analysis**: Determine primary thinking style of your ICP
2. **Big Picture Content**: Select trends, insights, and metaphors relevant to their industry
3. **Connection Content**: Choose stories and case studies that create emotional resonance
4. **Logic Content**: Define frameworks and proof points that build credibility
5. **Practical Content**: Specify immediate actions and quick wins
6. **Content Integration**: Ensure all elements support your topic and transformation promise

CONTENT QUALITY CRITERIA:
- **ICP-Relevant**: Every piece of content directly relates to their world
- **Transformation-Focused**: All content points toward the outcome they desire
- **Credibility-Building**: Proof elements establish you as the trusted authority
- **Action-Oriented**: Readers can immediately implement valuable insights
- **Story-Rich**: Personal and client stories create emotional connection

CRITICAL RULES:
- Select content that reinforces your positioning from Topic Selection
- Ensure variety across all 4 thinking styles for maximum appeal
- Focus on content you can authentically deliver (your real experiences)
- All stories and case studies must be truthful and ethically shared
- Ask for satisfaction feedback before completing the section

DATA TO COLLECT:
- Primary thinking style focus for your ICP
- 3-5 key stories (personal and client examples)
- Main framework or methodology to feature
- 3-5 proof elements (data, testimonials, results)
- 3-5 immediate action steps for readers

COMPLETION CRITERIA:
- Primary thinking style identified and content weighted accordingly
- Content selected across all 4 thinking styles
- Stories and case studies chosen and approved
- Main framework/methodology defined
- Immediate action steps specified
- User confirms satisfaction with content direction"""

# Section template
CONTENT_DEVELOPMENT_TEMPLATE = SectionTemplate(
    section_id=SpecialReportSection.CONTENT_DEVELOPMENT,
    name="Content Development",
    system_prompt_template=CONTENT_DEVELOPMENT_SYSTEM_PROMPT,
    validation_rules=[
        ValidationRule(
            field_name="thinking_style_focus",
            rule_type="required",
            value=True,
            error_message="Primary thinking style selection is required"
        ),
        ValidationRule(
            field_name="key_stories",
            rule_type="min_length",
            value=1,
            error_message="At least one key story is required"
        )
    ],
    next_section=SpecialReportSection.REPORT_STRUCTURE
)

# Export prompts dictionary
CONTENT_DEVELOPMENT_PROMPTS = {
    "system_prompt": CONTENT_DEVELOPMENT_SYSTEM_PROMPT,
    "template": CONTENT_DEVELOPMENT_TEMPLATE,
}