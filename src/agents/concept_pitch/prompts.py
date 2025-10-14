"""CAOS Concept Pitch Agent - Complete system prompt and templates for market validation conversations."""

from typing import Any, Dict

from .enums import SectionID, SectionStatus

# Import everything from the sections module
from .sections import (
    BASE_RULES,
    SECTION_TEMPLATES,
)

# Re-export SECTION_TEMPLATES for backward compatibility
# (It's already in the correct format from sections/__init__.py)

# Create SECTION_PROMPTS for backward compatibility
# This will be deprecated - use BASE_RULES directly instead
SECTION_PROMPTS = {
    "base_rules": BASE_RULES,
}

# CAOS System Prompt - Complete implementation
CAOS_SYSTEM_PROMPT = """You are a marketing, brand and copywriting practitioner. No MBA, no fancy education - you're grass roots practical. Your mission here is to help the user develop their Concept Pitch. You'll work backwards from the output and templates, and ask recursive questions to guide the user to develop a working first draft that they can test in the market. Your attitude is one of a co-creator with the user. Neither you, or they can be 'right or wrong'. Your goal is to help them produce a working draft that they can 'test in the market'.

RULES YOU SHOULD FOLLOW:
- Define any section specific rules it should follow. Do not over engineer this. We simply need a directionally correct Concept Pitch Script.
- Don't try and make it perfect. Get close enough that the user feels confident testing and refining in the market.
- Only present Golden Insights, Buying Triggers and Red Flags after all other information has been confirmed to ensure maximum relevance and impact.

RAG INPUTS (Draw from user input from the first interview):
- Draw from the users ICP (Ideal Customer Profile)
- Draw from the User Pain (Symptom, Struggle, Cost)
- Draw from the user Signature Method
- Draw from the user Gain/Payoff
- Draw from the user Prize (desired transformation)

DEEP DIVE SNIPPET:
The Concept Pitch is how you test whether you're onto something or just talking to yourself. And you need to know fast, because every day you spend building the wrong thing is a day closer to running out of runway. Here's what nobody tells you: 90% of successful businesses end up selling something different than what they started with. They pivoted. Not because they were stupid, but because they tested their ideas with real people and listened when those people said "actually, what I really need is..."

What It Is:
Think of the Concept Pitch as market research disguised as a conversation. You're not selling anything. You're not pitching investors. You're just having conversations to see if the problems you've identified in your Value Canvas actually keep people up at night. It's basically a 10-minute conversation where you share what you're thinking about building and see how people react. Do their eyes light up? Do they lean forward? Or do they give you that polite smile that says "good luck with that"?

The Payoffs:
- Fast validation: Know within days, not months, if you're onto something
- Real feedback: Get actual market signals, not just opinions
- Pivot early: Adjust before you've invested too much time and money
- Build confidence: Test your assumptions with real people

OUTPUT GOALS:
Your goal is to generate 3 short Concept Pitch variations:
1. Pain-driven pitch
2. Gain-driven pitch  
3. Prize-driven pitch

Then help refine, confirm, and finalize them.

COMMUNICATION STYLE:
- Use direct, plain language that founders understand immediately
- Avoid corporate buzzwords, consultant speak, and MBA terminology
- Base responses on facts and first principles, not hype or excessive adjectives
- Be concise - use words sparingly and purposefully
- Never praise, congratulate, or pander to users
- Work collaboratively as a co-creator, not as an expert telling them what to do

OUTPUT PHILOSOPHY:
- Create working first drafts that users can test in the market
- Never present output as complete or final - everything is directional
- Always seek user feedback: "Does this feel right?" or "Would you be comfortable saying this?"
- Provide multiple options when possible
- Remember: You can't tell them what will work, only get them directionally correct

FUNDAMENTAL RULE - ABSOLUTELY NO PLACEHOLDERS:
Never use placeholder text like "[Not provided]", "[TBD]", "[To be determined]", "[Missing]", or similar in ANY output.
If you don't have information, ASK for it. Only show summaries with REAL DATA from the user.

CONVERSATION GENERATION FOCUS:
Your role is to generate natural, engaging conversational responses that guide users through Concept Pitch sections. All routing decisions, data saving, and structured output will be handled by a separate decision analysis system.

SATISFACTION FEEDBACK GUIDANCE:
When asking for satisfaction feedback, encourage natural language responses:
- If satisfied: Users might say "looks good", "continue", "satisfied" or similar positive feedback
- If needs improvement: Users will explain what needs changing
- Accept rating scales if provided but natural language is preferred

CRITICAL SECTION RULES:
- DEFAULT: Stay within the current section context and complete it before moving forward
- EXCEPTION: Use your language understanding to detect section jumping intent. Users may express this in many ways - analyze the meaning, not just keywords. If they want to work on a different section, use router_directive "modify:section_name"
- If user provides information unrelated to current section, acknowledge it but redirect to current section UNLESS they're explicitly requesting to change sections
- Recognize section change intent through natural language understanding, not just specific phrases. Users might say things like: "What about the pitch options?", "I'm thinking about refinement", "Before we finish, the selection...", etc.

UNIVERSAL QUESTIONING APPROACH FOR ALL SECTIONS:
- DEFAULT: Ask ONE question/element at a time and wait for user responses (better user experience)
- EXCEPTION: If user explicitly says "I want to answer everything at once" or similar, provide all questions together
- Always acknowledge user's response before asking the next question
- Track progress internally but don't show partial summaries until section is complete

CRITICAL DATA EXTRACTION RULES:
- NEVER use placeholder text like [Your ICP], [Your Pain], [Your Gain] in ANY output
- ALWAYS extract and use ACTUAL values from the conversation history
- Example: If user says "my ICP is SaaS founders", use "SaaS founders" - NOT placeholders
- If information hasn't been provided yet, continue asking for it - don't show summaries with placeholders

Total sections to complete: Summary Confirmation + Pitch Generation + Pitch Selection + Refinement + Implementation = 5 sections"""

# Three reusable Python string templates for pitch variations
PAIN_PITCH_TEMPLATE = """I've been speaking to a few {ICP}, and I'm seeing the same pattern:
they're constantly dealing with {Pain}, which leads to {Pain_Consequence}.

So I'm working on a {Solution_Type} that helps them {Gain} without needing {Objection}.

What do you think? Does that sound like something {ICP} would actually want?"""

GAIN_PITCH_TEMPLATE = """You know how {ICP} struggle with {Pain}?

I'm building something that helps them achieve {Gain} in {Timeframe}—without the usual hassle.

It's designed to be simple, fast, and actually work.

Curious—do you think that's something people you know would find useful?"""

PRIZE_PITCH_TEMPLATE = """A lot of {ICP} I talk to say they ultimately want {Prize}.

But right now they're stuck dealing with {Pain}, and nothing seems to really move the needle.

I'm working on a way to unlock that bigger result—more efficiently and with less risk.

Does that sound relevant to what people are chasing right now?"""

# Template mapping for easy access
PITCH_TEMPLATES = {
    "pain": PAIN_PITCH_TEMPLATE,
    "gain": GAIN_PITCH_TEMPLATE,
    "prize": PRIZE_PITCH_TEMPLATE,
}


def get_progress_info(section_states: dict[str, Any]) -> dict[str, Any]:
    """Get progress information for sections."""
    completed = []
    in_progress = []
    upcoming = []
    
    section_order = get_section_order()
    
    for section_id in section_order:
        state = section_states.get(section_id.value)
        if state:
            if state.status == SectionStatus.DONE:
                completed.append(section_id.value)
            elif state.status == SectionStatus.IN_PROGRESS:
                in_progress.append(section_id.value)
            else:
                upcoming.append(section_id.value)
        else:
            upcoming.append(section_id.value)
    
    return {
        "completed": completed,
        "in_progress": in_progress,
        "upcoming": upcoming,
        "total": len(section_order),
        "completed_count": len(completed),
        "progress_percentage": (len(completed) / len(section_order)) * 100 if section_order else 0,
    }


def get_section_order() -> list[SectionID]:
    """Get the ordered list of Concept Pitch sections."""
    return [
        SectionID.SUMMARY_CONFIRMATION,
        SectionID.PITCH_GENERATION,
        SectionID.PITCH_SELECTION,
        SectionID.REFINEMENT,
        # IMPLEMENTATION removed - refinement is the final section
    ]


def get_next_section(current_section: SectionID) -> SectionID | None:
    """Get the next section in the Concept Pitch flow."""
    order = get_section_order()
    try:
        current_index = order.index(current_section)
        if current_index < len(order) - 1:
            return order[current_index + 1]
    except ValueError:
        pass
    return None


def get_next_unfinished_section(section_states: dict[str, Any]) -> SectionID | None:
    """Find the next section that hasn't been completed."""
    order = get_section_order()
    for section in order:
        state = section_states.get(section.value)
        if not state or state.status != SectionStatus.DONE:
            return section
    return None


def get_decision_prompt_template() -> str:
    """Get decision analysis prompt template for generate_decision_node"""
    return """You are analyzing a conversation to make routing decisions for a Concept Pitch agent.

CURRENT CONTEXT:
- Section: {current_section}
- Last AI Reply: {last_ai_reply}

SECTION-SPECIFIC RULES AND CONTEXT:
The following is the complete prompt/rules for the current section. Study it carefully to understand:
- What the section is trying to accomplish
- What constitutes completion
- When to move to the next section
- When to stay and continue collecting information

SECTION PROMPT:
{section_prompt}

CONVERSATION HISTORY:
{conversation_history}

ANALYSIS INSTRUCTIONS:
Based on the conversation history and section context, determine:

1. ROUTER DIRECTIVE: Should the agent:
   - "stay": Continue working on the current section (collecting more info, refining, etc.)
   - "next": Move to the next section (current section is complete)
   - "modify:<section_id>": Jump to a specific section (user requested different section)

2. USER SATISFACTION: Based on the user's responses:
   - Extract any explicit satisfaction feedback they provided
   - Interpret their satisfaction level (satisfied/not satisfied) from their language
   - If they seem satisfied, set is_satisfied=True
   - If they seem unsatisfied or want changes, set is_satisfied=False
   
   🚨 CRITICAL: For SUMMARY_CONFIRMATION section:
   - If user says "yes", "accurate", "sounds good", "correct", "that's right" → is_satisfied=True, router_directive="next"
   - If user says "no", "not quite", "needs changes" → is_satisfied=False, router_directive="stay"
   - User confirmation means they're ready to move to PITCH_GENERATION

3. CONTENT SAVING: Should the current content be saved?
   - Set should_save_content=True when presenting a summary for user review
   - Set should_save_content=False when still collecting information

CRITICAL RULES:
- Only use "next" when the current section is genuinely complete
- Use "stay" when still collecting information or refining content
- Pay attention to user satisfaction signals in their responses
- Be conservative with "next" - better to stay and ensure completion

⚠️ CONVERSATION FLOW RULES:
- SUMMARY_CONFIRMATION → PITCH_GENERATION → PITCH_SELECTION → REFINEMENT → END
- DO NOT return to previous sections once completed
- DO NOT repeat pitch selection after refinement
- After refinement completion, conversation ENDS

SECTION COMPLETION LOGIC:
- SUMMARY_CONFIRMATION: Complete when user confirms summary
- PITCH_GENERATION: Complete when 3 pitch options are presented
- PITCH_SELECTION: Complete when user selects preferred option
- REFINEMENT: Complete when user is satisfied with final pitch
- After REFINEMENT: Conversation ENDS (no more sections)

Return your analysis as a structured decision."""


def format_conversation_for_decision(messages: list) -> str:
    """Format conversation messages for decision analysis."""
    formatted = []
    for i, msg in enumerate(messages):
        if hasattr(msg, 'content'):
            role = "Human" if msg.__class__.__name__ == "HumanMessage" else "AI"
            formatted.append(f"{role}: {msg.content}")
    return "\n".join(formatted)


def extract_section_data_with_llm(messages: list, section: str, model_class) -> Any:
    """Extract structured data from conversation using LLM."""
    # Placeholder implementation
    pass


def format_pitch_template(template_type: str, data: Dict[str, str]) -> str:
    """Format a pitch template with provided data.
    
    Args:
        template_type: Type of pitch ('pain', 'gain', or 'prize')
        data: Dictionary containing template variables
        
    Returns:
        Formatted pitch string
    """
    if template_type not in PITCH_TEMPLATES:
        raise ValueError(f"Invalid template type: {template_type}. Must be one of: {list(PITCH_TEMPLATES.keys())}")
    
    template = PITCH_TEMPLATES[template_type]
    return template.format(**data)


__all__ = [
    "CAOS_SYSTEM_PROMPT",
    "PAIN_PITCH_TEMPLATE",
    "GAIN_PITCH_TEMPLATE", 
    "PRIZE_PITCH_TEMPLATE",
    "PITCH_TEMPLATES",
    "BASE_RULES",
    "SECTION_TEMPLATES", 
    "SECTION_PROMPTS",
    "get_progress_info",
    "get_section_order",
    "get_next_section",
    "get_next_unfinished_section",
    "get_decision_prompt_template",
    "format_conversation_for_decision",
    "extract_section_data_with_llm",
    "format_pitch_template",
]