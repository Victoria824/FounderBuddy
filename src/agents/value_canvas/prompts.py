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
        SectionID.IMPLEMENTATION,
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
    """Get decision analysis prompt template for generate_decision_node - Simplified version without section_update"""
    return """You are analyzing a conversation to make routing decisions for a Value Canvas agent.

CURRENT CONTEXT:
- Section: {current_section}
- Last AI Reply: {last_ai_reply}

SECTION-SPECIFIC RULES AND CONTEXT:
The following is the complete prompt/rules for the current section. Study it carefully to understand when data should be saved:
---
{section_prompt}
---

CONVERSATION HISTORY:
{conversation_history}

DECISION MAKING RULES:

1. UNDERSTAND THE SECTION CONTEXT:
   - The section prompt above defines the exact flow and rules for this section
   - Understand where we are in the section's process by analyzing the conversation
   - Each section has specific completion criteria

2. DETERMINE IF CONTENT SHOULD BE SAVED (should_save_content):
   
   Set should_save_content = true when:
   - AI just presented a complete summary with all required data
   - AI is asking for satisfaction rating after showing summary
   - AI says "Here's what I gathered/collected" with actual data
   - AI shows refined/synthesized version of user input
   
   Set should_save_content = false when:
   - Still collecting information
   - Asking individual questions
   - Introduction or explanation phases
   - Partial data or intermediate confirmations

3. ROUTER DIRECTIVE DECISION:
   
   "stay": Continue current section when:
   - Section-specific completion criteria NOT met
   - Still collecting required information
   - User needs to provide corrections
   - ANY intermediate step is in progress
   
   "next": Move to next section ONLY when:
   - ALL section-specific completion criteria are met
   - ALL required data has been collected AND presented
   - User has confirmed satisfaction with COMPLETE section output
   
   "modify:X": Jump to section X when:
   - User explicitly requests different section
   - Examples: "Let's work on pain points", "I want to adjust my ICP"

4. SATISFACTION ANALYSIS:
   
   is_satisfied = true: User explicitly expressed satisfaction with summary
   is_satisfied = false: User wants changes or corrections
   is_satisfied = null: No clear satisfaction feedback yet

5. KEY PRINCIPLE:
   
   User satisfaction ≠ Section completion
   - Being satisfied with partial progress doesn't mean move to next
   - Check if ALL section requirements are met before using "next"

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
                "refined version", "let me present", "here's the summary"
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