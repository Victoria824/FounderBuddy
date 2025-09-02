"""Prompts and templates for Value Canvas sections - Compatibility layer after refactoring."""

from typing import Any

from .enums import SectionID, SectionStatus
from .sections.base_prompt import SectionTemplate, ValidationRule

# Import everything from the sections module
from .sections import (
    BASE_RULES,
    SECTION_TEMPLATES,
    SECTION_PROMPTS as SECTION_PROMPTS_DICT,
)

# Re-export SECTION_TEMPLATES for backward compatibility
# (It's already in the correct format from sections/__init__.py)

# Re-export SECTION_PROMPTS with base_rules for backward compatibility
SECTION_PROMPTS = SECTION_PROMPTS_DICT


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
    """Get decision analysis prompt template for generate_decision_node"""
    return """You are analyzing a conversation to extract structured decision data for a Value Canvas agent.

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

ENHANCED DECISION RULES - UNDERSTAND THE SECTION FLOW:

1. READ AND UNDERSTAND THE SECTION CONTEXT:
   - The section prompt above defines the exact flow and rules for this section
   - Understand where we are in the section's process by analyzing the conversation patterns
   - Different sections have different triggers for when to save data

2. 🔍 SECTION COMPLETENESS VERIFICATION:
   
   **CRITICAL: Before deciding to save data or move sections, verify ALL required fields are collected:**
   
   - Check the section's required_fields list in the prompt
   - For Pain section: Must have pain1_symptom, pain1_struggle, pain1_cost, pain1_consequence, 
     pain2_symptom, pain2_struggle, pain2_cost, pain2_consequence,
     pain3_symptom, pain3_struggle, pain3_cost, pain3_consequence (12 fields total)
   - For ICP section: Must have all ICP fields defined in the prompt
   - For Interview section: Must complete all 7 steps before saving
   
   **If ANY required field is missing:**
   - router_directive MUST be "stay"
   - section_update should be null
   - AI should continue collecting missing information

3. UNIVERSAL SECTION PATTERNS TO RECOGNIZE:

   ✅ SAVE DATA (generate section_update) when you see these patterns:
   
   **Interview Section Specific:**
   - "Ok, before I add that into memory, let me present a refined version:" + rating request → SAVE (Step 6) 
   - Key insight: Interview has 7 steps, saves at Step 6, NOT at Step 4 confirmation
   
   **Pain Section Specific:**
   - ALL 3 pain points fully collected (4 elements each)
   - AI presents synthesized summary of all pain points
   - AI asks for satisfaction rating AFTER showing complete summary
   
   **All Sections Universal Patterns:**
   - AI presents complete summary with bullet points or structured data
   - AI asks "Are you satisfied with this summary?" after showing summary
   - AI says "Here's what I gathered/collected" with actual data
   - AI shows refined/synthesized version of user input
   - AI asks "Is that directionally correct?" after presenting complete data
   
   ❌ DON'T SAVE DATA when:
   - Simple confirmation: "Is this correct?" without showing data summary
   - Still collecting information: asking individual questions
   - Introduction or explanation phases
   - Partial data display for verification only
   - ANY required fields are missing

4. INTELLIGENT DECISION MAKING:
   
   **For section_update decision:**
   - Analyze if AI's reply contains complete data summary or synthesis
   - Verify ALL required fields have been collected
   - Look for structured presentation (bullets, numbered lists, formatted data)
   - Check if AI is presenting refined/processed user input
   
   **For satisfaction feedback analysis:**
   - Identify when AI explicitly asks for satisfaction feedback
   - True when AI asks "Are you satisfied with this summary?" or similar satisfaction questions
   - False for content confirmation questions like "Is this correct?"
   
   **For router_directive decision:**
   - "stay": Continue current section (still collecting, user not satisfied, corrections needed, or MISSING REQUIRED FIELDS)
   - "next": Move to next section (user satisfied AND all required fields collected)
   - "modify:X": User explicitly requests different section

5. ⚠️ DEVIATION DETECTION:
   
   If the AI appears to be providing advice or solutions instead of collecting Value Canvas data:
   - router_directive: "stay"
   - section_update: null
   - The AI should be redirected back to the collection task

CRITICAL: You must output valid JSON with the ChatAgentDecision structure."""


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


def extract_section_data(conversation_history: str, section_id: str = "interview") -> dict:
    """Extract section-specific data from conversation history.
    
    This is a simplified version for the Interview section.
    Each section would need its own extraction logic.
    """
    # This is a placeholder - actual implementation would parse
    # the conversation to extract structured data
    return {
        "client_name": None,
        "company_name": None,
        "industry": None,
        "outcomes": None,
    }


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
    "extract_section_data",
]