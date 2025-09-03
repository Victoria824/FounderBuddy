'''Pydantic models for Signature Pitch Agent.'''

from enum import Enum
from typing import Any, Literal
from uuid import UUID
import uuid

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field, field_validator


class SectionStatus(str, Enum):
    """Status of a Signature Pitch section."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class RouterDirective(str, Enum):
    """Router directive for navigation control."""
    STAY = "stay"
    NEXT = "next"
    MODIFY = "modify"  # Format: "modify:section_id"


class SignaturePitchSectionID(str, Enum):
    """Signature Pitch section identifiers."""
    # The 6 core Signature Pitch components
    ACTIVE_CHANGE = "active_change"         # The transformation you create
    SPECIFIC_WHO = "specific_who"          # The exact audience you serve
    OUTCOME_PRIZE = "outcome_prize"        # The compelling result they desire
    CORE_CREDIBILITY = "core_credibility"  # Proof you can deliver
    STORY_SPARK = "story_spark"           # A short narrative hook or example
    SIGNATURE_LINE = "signature_line"      # The concise pitch (90 seconds → 1 line)

    # Implementation/Export
    IMPLEMENTATION = "implementation"


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
    content: list[TiptapInlineNode] = Field(default_factory=list, max_length=50)
    attrs: dict[str, Any] | None = None


class TiptapNode(BaseModel):
    """Base Tiptap node structure."""
    type: str
    content: list[TiptapInlineNode] | None = Field(None, max_length=5)
    text: str | None = None
    attrs: dict[str, Any] | None = None
    marks: list[dict[str, Any]] | None = Field(None, max_length=2)


class TiptapDocument(BaseModel):
    """Tiptap document structure."""
    type: Literal["doc"] = "doc"
    content: list[TiptapParagraphNode] = Field(default_factory=list, max_length=30)


class SectionContent(BaseModel):
    """Content for a Signature Pitch section."""
    content: TiptapDocument  # Rich text content in Tiptap JSON format
    plain_text: str | None = None  # Plain text version for LLM processing


class SectionState(BaseModel):
    """State of a single Signature Pitch section."""
    section_id: SignaturePitchSectionID
    content: SectionContent | None = None
    satisfaction_feedback: str | None = None  # User's satisfaction feedback
    status: SectionStatus = SectionStatus.PENDING


class ContextPacket(BaseModel):
    """Context packet for current section."""
    section_id: SignaturePitchSectionID
    status: SectionStatus
    system_prompt: str
    draft: SectionContent | None = None
    validation_rules: dict[str, Any] | None = None


class SignaturePitchData(BaseModel):
    """Complete Signature Pitch data structure following the 6-component framework."""
    
    # Client Information
    client_name: str | None = None
    company_name: str | None = None
    industry: str | None = None
    
    # Active Change section
    active_change: str | None = None
    
    # Specific Who section
    specific_who: str | None = None
    target_audience: str | None = None
    
    # Outcome/Prize section
    outcome_prize: str | None = None
    compelling_result: str | None = None
    
    # Core Credibility section
    core_credibility: str | None = None
    proof_points: list[str] | None = None
    
    # Story Spark section
    story_spark: str | None = None
    narrative_hook: str | None = None
    
    # Signature Line section
    signature_line: str | None = None
    ninety_second_pitch: str | None = None
    
    # Overall Signature Pitch
    complete_pitch: str | None = None
    pitch_confidence: int | None = Field(None, ge=0, le=5)


class ChatAgentOutput(BaseModel):
    """Output from Chat Agent node."""

    reply: str = Field(..., description="Conversational response to the user.")
    router_directive: str = Field(
        ...,
        description="Navigation control: 'stay' to continue on the current section, 'next' to proceed to the next section, or 'modify:<section_id>' to jump to a specific section.",
    )
    is_requesting_rating: bool = Field(
        default=False,
        description="Set to true ONLY when your reply explicitly asks the user for a satisfaction rating."
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
            
        # Very minimal validation - just check for obviously broken structure
        if 'content' in v:
            content = v['content']
            if isinstance(content, dict) and 'content' in content:
                # Only check for extremely large content that could cause issues
                if len(content.get('content', [])) > 200:  # Much more lenient limit
                    raise ValueError("Section content extremely large - please reduce")
        
        return v


class SignaturePitchState(MessagesState):
    """State for Signature Pitch agent."""
    # User and document identification
    user_id: int = 1
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Navigation and progress
    current_section: SignaturePitchSectionID = SignaturePitchSectionID.ACTIVE_CHANGE
    context_packet: ContextPacket | None = None
    section_states: dict[str, SectionState] = Field(default_factory=dict)
    # On initial entry, Router should call get_context directly, so default to NEXT
    router_directive: str = RouterDirective.NEXT
    finished: bool = False

    # Signature Pitch data
    canvas_data: SignaturePitchData = Field(default_factory=SignaturePitchData)

    # Memory management
    short_memory: list[BaseMessage] = Field(default_factory=list)

    # Agent output
    agent_output: ChatAgentOutput | None = None
    # Flag indicating the agent has asked a question and is waiting for user's reply
    awaiting_user_input: bool = False
    is_awaiting_rating: bool = False # NEW: Explicit state to track if we're waiting for a rating

    # Error tracking
    error_count: int = 0
    last_error: str | None = None


class ValidationRule(BaseModel):
    """Validation rule for field input."""
    field_name: str
    rule_type: Literal["min_length", "max_length", "regex", "required", "choices"]
    value: Any
    error_message: str


class SectionTemplate(BaseModel):
    """Template for a Signature Pitch section."""
    section_id: SignaturePitchSectionID
    name: str
    description: str
    system_prompt_template: str
    validation_rules: list[ValidationRule] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    next_section: SignaturePitchSectionID | None = None


# --- Structured Output Models for Data Extraction ---

class ActiveChangeData(BaseModel):
    """Structured data for the Active Change component."""
    active_change: str | None = Field(None, description="The transformation you create.")
    change_description: str | None = Field(None, description="Detailed description of the change.")


class SpecificWhoData(BaseModel):
    """Structured data for the Specific Who component."""
    specific_who: str | None = Field(None, description="The exact audience you serve.")
    target_audience: str | None = Field(None, description="Detailed description of the target audience.")
    audience_characteristics: list[str] | None = Field(None, description="Key characteristics of the audience.")


class OutcomePrizeData(BaseModel):
    """Structured data for the Outcome/Prize component."""
    outcome_prize: str | None = Field(None, description="The compelling result they desire.")
    compelling_result: str | None = Field(None, description="Detailed description of the outcome.")
    value_proposition: str | None = Field(None, description="The unique value proposition.")


class CoreCredibilityData(BaseModel):
    """Structured data for the Core Credibility component."""
    core_credibility: str | None = Field(None, description="Proof you can deliver.")
    proof_points: list[str] | None = Field(None, description="Specific evidence of credibility.")
    achievements: list[str] | None = Field(None, description="Key achievements or results.")


class StorySparkData(BaseModel):
    """Structured data for the Story Spark component."""
    story_spark: str | None = Field(None, description="A short narrative hook or example.")
    narrative_hook: str | None = Field(None, description="The compelling story element.")
    example_case: str | None = Field(None, description="Concrete example or case study.")


class SignatureLineData(BaseModel):
    """Structured data for the Signature Line component."""
    signature_line: str | None = Field(None, description="The concise pitch (90 seconds → 1 line).")
    ninety_second_pitch: str | None = Field(None, description="The full 90-second pitch.")
    elevator_pitch: str | None = Field(None, description="The condensed elevator pitch version.")