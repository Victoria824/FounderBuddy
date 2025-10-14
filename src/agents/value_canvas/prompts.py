"""Prompts and templates for Value Canvas sections - Compatibility layer after refactoring."""

from typing import Any

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
    """Get the ordered list of Value Canvas sections."""
    return [
        SectionID.INTERVIEW,
        SectionID.ICP,
        SectionID.ICP_STRESS_TEST,
        SectionID.PAIN,
        SectionID.DEEP_FEAR,
        SectionID.PAYOFFS,
        SectionID.PAIN_PAYOFF_SYMMETRY,
        SectionID.SIGNATURE_METHOD,
        SectionID.MISTAKES,
        SectionID.PRIZE,
    ]


def get_next_section(current_section: SectionID) -> SectionID | None:
    """Get the next section in the Value Canvas flow."""
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
    return """You are analyzing a conversation to make routing decisions for a Value Canvas agent.

CURRENT CONTEXT:
- Section: {current_section}
- Last AI Reply: {last_ai_reply}

SECTION-SPECIFIC RULES AND CONTEXT:
The following is the complete prompt/rules for the current section. Study it carefully to understand:
1. What data fields are required
2. What constitutes a "complete output"
3. What the satisfaction confirmation pattern looks like
---
{section_prompt}
---

CONVERSATION HISTORY:
{conversation_history}

CRITICAL DECISION MAKING RULES:

1. UNDERSTAND SECTION COMPLETION REQUIREMENTS:
   - Read the section prompt above to identify ALL required fields/elements
   - Look for phrases like "MUST collect ALL", "required fields", "complete output format"
   - Understand the difference between partial progress and complete output
   
2. RECOGNIZE COMPLETE OUTPUT PATTERNS:
   
   A section is ONLY complete when:
   - All required fields/elements have been collected
   - The AI has presented them in a COMPLETE, FORMATTED OUTPUT
   - The output matches the format specified in the section prompt
   
   Common complete output indicators:
   - Structured format with clear headers/sections
   - All required fields present in one cohesive output
   - Follows the example format shown in section prompt
   - Usually followed by satisfaction question like "Does this reflect..." or "Are you satisfied with..."

3. AVOID COMMON MISJUDGMENTS:
   
   These do NOT indicate section completion:
   - "Let's move on to the next step" (could be within same section)
   - Showing only one field or insight
   - Previewing or announcing what will be shown
   - User saying "ready" or "yes" to see more information
   - Partial summaries or individual field confirmations
   
4. DETERMINE IF CONTENT SHOULD BE SAVED (should_save_content):

   SIMPLE RULE: Is the last AI message showing a reviewable summary?

   A "reviewable summary" has these characteristics:
   ✓ Shows multiple collected data fields in structured format
   ✓ Presents information for user to review (not asking for new data)
   ✓ Asks for user's opinion/feedback on the shown content

   THREE-STEP QUICK CHECK:

   Step 1: Count structured fields in last AI message
   - Look for markdown formatting with DATA VALUES: **, ###, bullet points with content
   - Must have field labels AND their values shown together
   - Valid examples: "**Name:** Lee", "**Company:** Acme Corp", "### ICP NICKNAME\nThe Startup Founder"
   - Invalid: Pure text without field-value pairs, transition messages, single questions

   CRITICAL: Structured fields must follow these patterns:
   - "**FieldName:** value" (bold label + colon + value)
   - "### Section Header\n[content]" (header + actual content below)
   - "- **Label:** value" (list item with bold label + value)

   Question: Does it show 2+ field-value pairs in these formats?
   - If YES → likely a summary, proceed to Step 2
   - If NO → NOT a summary, should_save_content = FALSE, STOP HERE

   Common NON-SUMMARY patterns (should_save_content = FALSE):
   - "Great! Your information has been saved..." (transition announcement)
   - "Now let's work on..." (section transition)
   - Single questions without showing collected data
   - Acknowledgments or confirmations without data display

   Step 2: Check the last sentence
   - Is it asking for review/feedback on what was just shown?
   - Review questions: "Is anything missing?", "Does this reflect...",
     "Are you satisfied...", "How does this look?", "What needs changing?"
   - If YES → proceed to Step 3
   - If NO → probably not a summary, should_save_content = FALSE

   Step 3: Determine the purpose
   - Is AI asking for NEW information OR reviewing EXISTING information?
   - Reviewing existing = summary presentation → should_save_content = TRUE
   - Asking for new = data collection → should_save_content = FALSE

   DECISION LOGIC:
   If all 3 checks pass → should_save_content = TRUE
   Otherwise → should_save_content = FALSE

   EXAMPLES:

   ✅ SUMMARY PRESENTATION (should_save_content = TRUE):
   - "Ok, so now I've got: **Name:** Lee, **Company:** Minimum Viable Launch, **Industry:** Software, **Outcomes:** More leads. Is anything missing or off?"
   - "Here's your ICP: ### Nickname: The Traction-Seeker... ### Role: Founder of early-stage SaaS... Does this reflect our conversation?"
   - "### Pain Point 1: **Symptom:** Struggling with... ### Pain Point 2: **Symptom:** Facing... ### Pain Point 3: **Symptom:** Dealing with... Are you satisfied with this summary?"

   ❌ DATA COLLECTION (should_save_content = FALSE):
   - "What industry are you in?"
   - "Tell me more about your ideal client's pain points"
   - "Great! Now, what specific outcomes do they want to achieve?"

   ❌ TRANSITION MESSAGE (should_save_content = FALSE):
   - "Great! Your ICP has been saved. Now let's move on to pain points."
   - "Excellent! I've captured your information. Ready for the next section?"

5. ROUTER DIRECTIVE DECISION:
   
   "stay": Continue current section when:
   - Not all required fields have been collected
   - Complete formatted output has NOT been presented
   - Still in intermediate steps (collecting, previewing, explaining)
   - User hasn't confirmed satisfaction with complete output
   - CRITICAL: AI is asking a question and waiting for user response
   - CRITICAL: Last AI message ends with a question (like "Does this reflect...?")
   
   "next": Move to next section ONLY when ALL are true:
   - Every required field specified in section prompt has been collected
   - Complete formatted output has been presented (not preview)
   - User has EXPLICITLY expressed satisfaction with the complete output
   - No indication of wanting changes
   - CRITICAL: User must have PROVIDED A RESPONSE after seeing complete output
   - CRITICAL: is_satisfied must be true (not null, not false)
   
   VALIDATION CHECK for "next":
   If the last AI message asks a question (ends with "?"), then:
   - There MUST be a user response after that question
   - That user response must indicate satisfaction
   - If no user response exists after the question, MUST use "stay"
   
   "modify:X": Jump to section X when:
   - User explicitly requests different section
   - Clear intent to switch sections (not just modify current)

6. SATISFACTION ANALYSIS:
   
   is_satisfied = true: User confirmed satisfaction with COMPLETE output
   is_satisfied = false: User wants changes to the presented output
   is_satisfied = null: No clear feedback or still in collection phase
   
   CRITICAL RULE: If is_satisfied is null:
   - NEVER use router_directive="next"
   - The section is still waiting for user feedback
   - Must use "stay" to wait for user response

7. KEY VALIDATION PRINCIPLE:
   
   Before setting router_directive="next", ask yourself:
   - Did the AI present ALL required fields in ONE complete output?
   - Does the output match the format example in the section prompt?
   - Did the user explicitly confirm satisfaction with this complete output?
   - CRITICAL: Is there a USER MESSAGE after the AI's satisfaction question?
   - CRITICAL: Is is_satisfied explicitly true (not null)?
   
   If ANY answer is "no", use "stay" instead.
   
   SPECIAL CHECK: If the last AI message contains a question (especially satisfaction questions like "Does this reflect...?" or "Are you satisfied...?"):
   - The section is NOT complete yet
   - Must wait for user response
   - Use "stay" until user responds

CRITICAL: Output valid JSON with these fields:
- router_directive: "stay" | "next" | "modify:X"
- should_save_content: true | false
- is_satisfied: true | false | null
- user_satisfaction_feedback: string | null"""


def format_conversation_for_decision(messages: list) -> str:
    """Format conversation history for decision analysis."""
    formatted = []
    for msg in messages:
        role = msg.type if hasattr(msg, 'type') else 'unknown'
        content = msg.content if hasattr(msg, 'content') else str(msg)
        
        # Clean up role names
        if role == 'human':
            role = 'User'
        elif role == 'ai':
            role = 'AI'
        elif role == 'system':
            continue  # Skip system messages in decision context
            
        formatted.append(f"{role}: {content}")
    
    return "\n".join(formatted)


async def extract_section_data_with_llm(messages: list, section: str, model_class: type) -> dict:
    """Extract section-specific data from conversation using LLM.
    
    This replaces the old regex-based extraction with intelligent LLM-based extraction
    that can handle any section and any format.
    
    Args:
        messages: List of conversation messages
        section: The current section ID
        model_class: The Pydantic model class for structured extraction
    
    Returns:
        Extracted data as a dictionary matching the model_class schema
    """
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.runnables import RunnableConfig
    from core.llm import get_model
    
    # Format conversation for extraction
    conversation_text = ""
    for msg in messages:
        if isinstance(msg, HumanMessage):
            conversation_text += f"User: {msg.content}\n"
        elif isinstance(msg, AIMessage):
            conversation_text += f"AI: {msg.content}\n"
    
    # Find the most recent summary in the conversation
    summary_text = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content_lower = msg.content.lower()
            # Look for summary indicators
            if any(indicator in content_lower for indicator in [
                "here's what i gathered", "here's your summary",
                "refined version", "let me present", "here's the summary",
                "final icp after stress test", "here's your icp"
            ]):
                summary_text = msg.content
                break
    
    if not summary_text:
        # If no clear summary found, use the last AI message
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                summary_text = msg.content
                break
    
    # Create extraction prompt
    extraction_prompt = f"""Extract structured data from this Value Canvas section conversation.

Section: {section}

Summary/Content to Extract From:
{summary_text}

Full Conversation Context:
{conversation_text[-3000:]}  # Last 3000 chars for context

Extract all relevant fields according to the data model requirements.
Be accurate and complete in your extraction."""
    
    # Use LLM with structured output
    llm = get_model()
    structured_llm = llm.with_structured_output(model_class)
    
    # Use non-streaming config with tags to prevent extraction data from appearing in user stream
    non_streaming_config = RunnableConfig(
        configurable={"stream": False},
        tags=["internal_extraction", "do_not_stream"],
        callbacks=[]
    )
    
    # Extract data with non-streaming config
    extracted_data = await structured_llm.ainvoke(
        extraction_prompt,
        config=non_streaming_config
    )
    
    return extracted_data.model_dump() if hasattr(extracted_data, 'model_dump') else extracted_data


# Export all functions and data for backward compatibility
__all__ = [
    "SECTION_PROMPTS",
    "SECTION_TEMPLATES",
    "get_progress_info",
    "get_section_order",
    "get_next_section",
    "get_next_unfinished_section",
    "get_decision_prompt_template",
    "format_conversation_for_decision",
    "extract_section_data_with_llm",
]