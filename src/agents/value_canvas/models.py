'''Pydantic models for Value Canvas Agent - Compatibility layer after refactoring.'''

from typing import Any, Literal
from uuid import UUID
import uuid

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field, field_validator

# Import enums and base models
from .enums import SectionStatus, RouterDirective, SectionID
from .sections.base_prompt import ValidationRule, SectionTemplate

# Import section-specific models
from .sections.interview import InterviewData
from .sections.icp import ICPData
from .sections.icp_stress_test import ICPStressTestData
from .sections.pain import PainData, PainPoint
from .sections.deep_fear import DeepFearData
from .sections.payoffs import PayoffsData, PayoffPoint
from .sections.pain_payoff_symmetry import PainPayoffSymmetryData
from .sections.signature_method import SignatureMethodData, Principle
from .sections.mistakes import MistakesData, Mistake
from .sections.prize import PrizeData
from .sections.implementation import ImplementationData








class TiptapTextNode(BaseModel):
    """Tiptap text node."""
    type: Literal["text"] = "text"
    text: str
    marks: list[dict[str, Any]] | None = Field(None, max_length=5)


class TiptapHardBreakNode(BaseModel):
    """Tiptap hard break node."""
    type: Literal["hardBreak"] = "hardBreak"


# Union type for inline content nodes
TiptapInlineNode = TiptapTextNode | TiptapHardBreakNode


class TiptapParagraphNode(BaseModel):
    """Tiptap paragraph node."""
    type: Literal["paragraph"] = "paragraph"
    content: list[TiptapInlineNode] = Field(default_factory=list, max_length=50)  # Relaxed for interview section
    attrs: dict[str, Any] | None = None


class TiptapNode(BaseModel):
    """Base Tiptap node structure."""
    type: str
    content: list[TiptapInlineNode] | None = Field(None, max_length=5)  # Further reduced
    text: str | None = None
    attrs: dict[str, Any] | None = None
    marks: list[dict[str, Any]] | None = Field(None, max_length=2)  # Further reduced


class TiptapDocument(BaseModel):
    """Tiptap document structure."""
    type: Literal["doc"] = "doc"
    content: list[TiptapParagraphNode] = Field(default_factory=list, max_length=30)  # Relaxed for complex sections


class SectionContent(BaseModel):
    """Content for a Value Canvas section."""
    content: TiptapDocument  # Rich text content in Tiptap JSON format
    plain_text: str | None = None  # Plain text version for LLM processing


class SectionState(BaseModel):
    """State of a single Value Canvas section."""
    section_id: SectionID
    content: SectionContent | None = None
    satisfaction_status: str | None = None  # satisfied, needs_improvement, or None
    status: SectionStatus = SectionStatus.PENDING


class ContextPacket(BaseModel):
    """Context packet for current section."""
    section_id: SectionID
    status: SectionStatus
    system_prompt: str
    draft: SectionContent | None = None
    validation_rules: dict[str, Any] | None = None


class ValueCanvasData(BaseModel):
    """Complete Value Canvas data structure."""
    # Basic information from initial interview
    client_name: str | None = None
    preferred_name: str | None = None  # Add nickname field
    company_name: str | None = None
    industry: str | None = None
    specialty: str | None = None
    career_highlight: str | None = None
    client_outcomes: str | None = None
    awards_media: str | None = None
    published_content: str | None = None
    specialized_skills: str | None = None
    notable_partners: str | None = None

    # ICP data - corresponds to the 8 sections in ICP Template
    icp_nickname: str | None = None  # ICP Nick Name
    icp_role_identity: str | None = None  # ROLE/IDENTITY section content
    icp_context_scale: str | None = None  # CONTEXT/SCALE section content
    icp_industry_sector_context: str | None = None  # INDUSTRY/SECTOR CONTEXT section content (includes both industry and insight)
    icp_demographics: str | None = None  # DEMOGRAPHICS section content
    icp_interests: str | None = None  # INTERESTS section content (all 3 interests)
    icp_values: str | None = None  # VALUES section content (both lifestyle indicators)
    icp_golden_insight: str | None = None  # GOLDEN INSIGHT section content

    # ICP Stress Test data
    icp_stress_test_can_influence: int | None = None
    icp_stress_test_like_working: int | None = None
    icp_stress_test_afford_premium: int | None = None
    icp_stress_test_decision_maker: int | None = None
    icp_stress_test_significant_transformation: int | None = None
    icp_stress_test_total_score: int | None = None
    icp_stress_test_passed: bool | None = None
    icp_stress_test_golden_insight: str | None = None
    icp_stress_test_refinements: str | None = None

    # Pain points (3)
    pain1_symptom: str | None = None
    pain1_struggle: str | None = None
    pain1_cost: str | None = None
    pain1_consequence: str | None = None

    pain2_symptom: str | None = None
    pain2_struggle: str | None = None
    pain2_cost: str | None = None
    pain2_consequence: str | None = None

    pain3_symptom: str | None = None
    pain3_struggle: str | None = None
    pain3_cost: str | None = None
    pain3_consequence: str | None = None

    # Deep Fear
    deep_fear: str | None = None
    golden_insight: str | None = None

    # Payoffs (3)
    payoff1_objective: str | None = None
    payoff1_desire: str | None = None
    payoff1_without: str | None = None
    payoff1_resolution: str | None = None

    payoff2_objective: str | None = None
    payoff2_desire: str | None = None
    payoff2_without: str | None = None
    payoff2_resolution: str | None = None

    payoff3_objective: str | None = None
    payoff3_desire: str | None = None
    payoff3_without: str | None = None
    payoff3_resolution: str | None = None

    # Pain-Payoff Symmetry insights
    pain_payoff_golden_insight_1: str | None = None
    pain_payoff_golden_insight_2: str | None = None
    pain_payoff_golden_insight_3: str | None = None
    pain_payoff_golden_insight_4: str | None = None
    pain_payoff_golden_insight_5: str | None = None
    pain_payoff_insights_presented: bool | None = None
    pain_payoff_user_ready: bool | None = None

    # Signature Method
    method_name: str | None = None
    sequenced_principles: list[str] | None = Field(None, max_length=10)
    principle_descriptions: dict[str, str] | None = None

    # Mistakes
    mistakes: list[dict[str, Any]] | None = Field(None, max_length=10)

    # Prize
    prize_category: str | None = None
    prize_statement: str | None = None
    refined_prize: str | None = None


class ChatAgentDecision(BaseModel):
    """Structured decision data from Decision Agent node."""
    
    router_directive: str = Field(
        ...,
        description="Navigation control: 'stay' to continue on the current section, 'next' to proceed to the next section, or 'modify:<section_id>' to jump to a specific section.",
    )
    user_satisfaction_feedback: str | None = Field(
        None, description="User's natural language feedback about satisfaction with the section content."
    )
    is_satisfied: bool | None = Field(
        None, description="AI's interpretation of user satisfaction based on their feedback. True if satisfied, False if needs improvement."
    )
    section_update: dict[str, Any] | None = Field(
        None,
        description="Content for the current section in Tiptap JSON format. REQUIRED when providing summary or asking for rating. Example: {'content': {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'content here'}]}]}}",
    )

    @field_validator("router_directive")
    def validate_router_directive(cls, v):
        """Validate the router_directive field."""
        if v not in ["stay", "next"] and not v.startswith("modify:"):
            raise ValueError(
                "router_directive must be 'stay', 'next', or start with 'modify:'"
            )
        if v.startswith("modify:"):
            section_id = v.split(":", 1)[1]
            if not section_id:
                raise ValueError("modify directive must include a section_id")
        return v

    @field_validator("section_update")
    def validate_section_update(cls, v):
        """Validate section_update with relaxed rules to allow LLM flexibility."""
        if v is None:
            return v
            
        # Basic structure check - just ensure it's a dict
        if not isinstance(v, dict):
            raise ValueError("Section update must be a dictionary")
            
        # Very minimal validation - just check that it has the expected Tiptap structure
        if 'content' in v:
            content = v['content']
            if isinstance(content, dict):
                # Just ensure it looks like Tiptap JSON structure
                if 'type' not in content:
                    raise ValueError("Section content must have 'type' field")
                # Skip the length check that was causing issues
        
        return v


class ChatAgentOutput(BaseModel):
    """Complete output from Chat Agent (reply + decision data)."""

    reply: str = Field(..., description="Conversational response to the user.")
    router_directive: str = Field(
        ...,
        description="Navigation control: 'stay' to continue on the current section, 'next' to proceed to the next section, or 'modify:<section_id>' to jump to a specific section.",
    )
    user_satisfaction_feedback: str | None = Field(
        None, description="User's natural language feedback about satisfaction with the section content."
    )
    is_satisfied: bool | None = Field(
        None, description="AI's interpretation of user satisfaction based on their feedback. True if satisfied, False if needs improvement."
    )
    section_update: dict[str, Any] | None = Field(
        None,
        description="Content for the current section in Tiptap JSON format. REQUIRED when providing summary or asking for rating. Example: {'content': {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'content here'}]}]}}",
    )

    @field_validator("router_directive")
    def validate_router_directive(cls, v):
        """Validate the router_directive field."""
        if v not in ["stay", "next"] and not v.startswith("modify:"):
            raise ValueError(
                "router_directive must be 'stay', 'next', or start with 'modify:'"
            )
        if v.startswith("modify:"):
            section_id = v.split(":", 1)[1]
            if not section_id:
                raise ValueError("modify directive must include a section_id")
        return v

    @field_validator("section_update")
    def validate_section_update(cls, v):
        """Validate section_update with relaxed rules to allow LLM flexibility."""
        if v is None:
            return v
            
        # Basic structure check - just ensure it's a dict
        if not isinstance(v, dict):
            raise ValueError("Section update must be a dictionary")
            
        # Very minimal validation - just check that it has the expected Tiptap structure
        if 'content' in v:
            content = v['content']
            if isinstance(content, dict):
                # Just ensure it looks like Tiptap JSON structure
                if 'type' not in content:
                    raise ValueError("Section content must have 'type' field")
                # Skip the length check that was causing issues
        
        return v


class ValueCanvasState(MessagesState):
    """State for Value Canvas agent."""
    # User and document identification
    user_id: int = 1
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Navigation and progress
    current_section: SectionID = SectionID.INTERVIEW
    context_packet: ContextPacket | None = None
    section_states: dict[str, SectionState] = Field(default_factory=dict)
    # On initial entry, Router should call get_context directly, so default to NEXT
    router_directive: str = RouterDirective.NEXT
    finished: bool = False

    # Value Canvas data
    canvas_data: ValueCanvasData = Field(default_factory=ValueCanvasData)

    # Memory management
    short_memory: list[BaseMessage] = Field(default_factory=list)

    # Agent output
    agent_output: ChatAgentOutput | None = None
    # Flag indicating the agent has asked a question and is waiting for user's reply
    awaiting_user_input: bool = False
    awaiting_satisfaction_feedback: bool = False  # Track if we're waiting for user satisfaction feedback

    # Error tracking
    error_count: int = 0
    last_error: str | None = None




# --- Structured Output Models for Data Extraction ---
# These are now imported from their respective section modules at the top of this file
# The imports provide backward compatibility for existing code

# Export all imported models for backward compatibility
__all__ = [
    # Core enums and classes
    "SectionStatus",
    "RouterDirective",
    "SectionID",
    # Tiptap models
    "TiptapTextNode",
    "TiptapHardBreakNode",
    "TiptapInlineNode",
    "TiptapParagraphNode",
    "TiptapNode",
    "TiptapDocument",
    # Section models
    "SectionContent",
    "SectionState",
    "ContextPacket",
    "ValueCanvasData",
    "ChatAgentDecision",
    "ChatAgentOutput",
    "ValueCanvasState",
    "ValidationRule",
    "SectionTemplate",
    # Section-specific data models (imported from sections)
    "InterviewData",
    "ICPData",
    "PainData",
    "PainPoint",
    "DeepFearData",
    "PayoffsData",
    "PayoffPoint",
    "SignatureMethodData",
    "Principle",
    "MistakesData",
    "Mistake",
    "PrizeData",
    "ImplementationData",
] 