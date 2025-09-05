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
   
   **CRITICAL: User satisfaction ≠ Section completion**
   
   Before EVER using router_directive="next", verify:
   - Has the section reached its FINAL step/output as defined in the section prompt?
   - For multi-step sections: Are ALL steps completed?
   - For data collection sections: Are ALL required fields collected AND presented in final summary?
   - Has the user confirmed satisfaction with the COMPLETE section output (not just intermediate confirmations)?
   
   Common mistakes to avoid:
   - Confusing intermediate confirmations (e.g., "Yes, that makes sense" to explanations) with section completion
   - Moving to next section when user is satisfied with partial progress
   - Ignoring section-specific flow requirements
   
   **Section-specific requirements:**
   - Pain section: Must have pain1_symptom, pain1_struggle, pain1_cost, pain1_consequence, 
     pain2_symptom, pain2_struggle, pain2_cost, pain2_consequence,
     pain3_symptom, pain3_struggle, pain3_cost, pain3_consequence (12 fields total)
   - ICP section: Must have all 8 ICP fields defined in the prompt
   - Interview section: Must complete all 7 steps before moving to next section
   
   **If ANY required step/field is missing:**
   - router_directive MUST be "stay"
   - section_update should be null
   - AI should continue with the next step/question

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
   
   🚨 CRITICAL: Your router_directive is the FINAL decision and will NOT be overridden.
   
   - "stay": Continue current section when:
     - Section-specific completion criteria NOT met (check section prompt for exact requirements)
     - Still collecting required information
     - User needs to provide corrections
     - ANY intermediate step is in progress
     - User confirms understanding but section work continues
     
   - "next": Move to next section ONLY when:
     - ALL section-specific completion criteria are met
     - ALL required data has been collected AND presented
     - Section-specific final step is reached (e.g., Interview Step 7)
     - User has confirmed satisfaction with COMPLETE section output
     - The section prompt explicitly indicates readiness to move
     
   - "modify:X": User explicitly requests different section OR requests to modify core framework data
     - Common section jumping patterns: "Let's work on...", "I want to do the...", "What about the..."
     - ICP modification patterns: "adjust my icp", "change the role to", "focus on [different segment]", "target [different decision maker]", "modify the icp"
     - Pain modification patterns: "change the pain points", "adjust the problems", "modify the pain"
     - Payoffs modification patterns: "change the benefits", "adjust the outcomes", "modify the payoffs"
     - When in ICP Stress Test and user wants to implement suggested ICP changes: → "modify:icp"

   ⚠️ IMPORTANT: is_satisfied does NOT automatically mean "next"!
   - is_satisfied=true with incomplete section → router_directive="stay"
   - is_satisfied=true with complete section → router_directive="next"
   - Let the section completion status, not just satisfaction, guide your decision
   
   CRITICAL: "User satisfaction" alone is NOT sufficient for "next". 
   Each section defines its own completion criteria in its prompt. 
   You MUST verify these criteria are fully met before using "next".

   **Examples of CORRECT decision making:**
   - Interview Step 3: User says "Yes, that sounds good" → router_directive="stay" (Steps 4-7 still needed)
   - Interview Step 7: User confirms "Ready to proceed" → router_directive="next" (All steps completed)
   - ICP: User satisfied with first question answer → router_directive="stay" (7 more fields needed)
   - ICP: User satisfied with complete 8-field summary → router_directive="next" (Section complete)
   - Pain: User satisfied with first pain point → router_directive="stay" (2 more pain points needed)
   - Pain: User satisfied with all 3 pain points summary → router_directive="next" (Section complete)

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