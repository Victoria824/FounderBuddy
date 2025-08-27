'''Pydantic models for Mission Pitch Agent.'''

from enum import Enum
from typing import Any, Literal
from uuid import UUID
import uuid

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field, field_validator


class SectionStatus(str, Enum):
    """Status of a Mission Pitch section."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class RouterDirective(str, Enum):
    """Router directive for navigation control."""
    STAY = "stay"
    NEXT = "next"
    MODIFY = "modify"  # Format: "modify:section_id"


class MissionSectionID(str, Enum):
    """Mission Pitch section identifiers."""
    # The 6 core Mission Pitch components
    HIDDEN_THEME = "hidden_theme"           # 1-sentence recurring life pattern
    PERSONAL_ORIGIN = "personal_origin"     # Early memory that shaped worldview
    BUSINESS_ORIGIN = "business_origin"     # "This should be a business" moment
    MISSION = "mission"                     # Clear change statement for whom
    THREE_YEAR_VISION = "three_year_vision" # Believable exciting milestone
    BIG_VISION = "big_vision"              # Aspirational future passing Selfless Test

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
    """Content for a Mission Pitch section."""
    content: TiptapDocument  # Rich text content in Tiptap JSON format
    plain_text: str | None = None  # Plain text version for LLM processing


class SectionState(BaseModel):
    """State of a single Mission Pitch section."""
    section_id: MissionSectionID
    content: SectionContent | None = None
    score: int | None = Field(None, ge=0, le=5)  # 0-5 rating
    status: SectionStatus = SectionStatus.PENDING


class ContextPacket(BaseModel):
    """Context packet for current section."""
    section_id: MissionSectionID
    status: SectionStatus
    system_prompt: str
    draft: SectionContent | None = None
    validation_rules: dict[str, Any] | None = None


class MissionPitchData(BaseModel):
    """Complete Mission Pitch data structure following the 6-component framework."""
    
    # Hidden Theme section
    theme_rant: str | None = None
    theme_1sentence: str | None = None
    theme_confidence: int | None = Field(None, ge=0, le=5)
    
    # Personal Origin section
    personal_origin_age: int | None = None
    personal_origin_setting: str | None = None
    personal_origin_key_moment: str | None = None
    personal_origin_link_to_theme: str | None = None
    
    # Business Origin section
    business_origin_pattern: str | None = None
    business_origin_story: str | None = None
    business_origin_evidence: str | None = None
    
    # Mission section
    mission_statement: str | None = None
    
    # 3-Year Vision section
    three_year_milestone: str | None = None
    three_year_metrics: dict | None = None
    
    # Big Vision section
    big_vision: str | None = None
    big_vision_selfless_test_passed: bool | None = None
    
    # Overall Mission Pitch
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
        description="Set to true ONLY when your reply explicitly asks the user for a 0-5 rating."
    )
    score: int | None = Field(
        None, ge=0, le=5, description="Satisfaction score (0-5) if user provided one."
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


class MissionPitchState(MessagesState):
    """State for Mission Pitch agent."""
    # User and document identification
    user_id: int = 1
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Navigation and progress
    current_section: MissionSectionID = MissionSectionID.HIDDEN_THEME
    context_packet: ContextPacket | None = None
    section_states: dict[str, SectionState] = Field(default_factory=dict)
    # On initial entry, Router should call get_context directly, so default to NEXT
    router_directive: str = RouterDirective.NEXT
    finished: bool = False

    # Mission Pitch data
    canvas_data: MissionPitchData = Field(default_factory=MissionPitchData)

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
    """Template for a Mission Pitch section."""
    section_id: MissionSectionID
    name: str
    description: str
    system_prompt_template: str
    validation_rules: list[ValidationRule] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    next_section: MissionSectionID | None = None


# --- Structured Output Models for Data Extraction ---

class HiddenThemeData(BaseModel):
    """Structured data for the Hidden Theme component."""
    theme_rant: str | None = Field(None, description="The user's 2-3 minute rant about their recurring pattern.")
    theme_1sentence: str | None = Field(None, description="The distilled 1-sentence theme.")
    theme_confidence: int | None = Field(None, ge=0, le=5, description="User's confidence in the theme (0-5).")


class PersonalOriginData(BaseModel):
    """Structured data for the Personal Origin component."""
    personal_origin_age: int | None = Field(None, description="Exact age when the formative memory occurred.")
    personal_origin_setting: str | None = Field(None, description="Where and in what context the memory took place.")
    personal_origin_key_moment: str | None = Field(None, description="What specifically happened or what they did.")
    personal_origin_link_to_theme: str | None = Field(None, description="How this moment connects to their Hidden Theme.")


class BusinessOriginData(BaseModel):
    """Structured data for the Business Origin component."""
    business_origin_pattern: str | None = Field(None, description="The pattern they noticed (inbound demand, personal solution, market gap, etc.).")
    business_origin_story: str | None = Field(None, description="The specific moment when they realized 'this should be a business'.")
    business_origin_evidence: str | None = Field(None, description="Evidence that people would actually pay for this solution.")


class MissionData(BaseModel):
    """Structured data for the Mission component."""
    mission_statement: str | None = Field(None, description="The complete mission statement in 'My mission is to [change] for [who] so they can [outcome]' format.")


class ThreeYearVisionData(BaseModel):
    """Structured data for the 3-Year Vision component."""
    three_year_milestone: str | None = Field(None, description="The believable, exciting milestone they want to achieve in 3 years.")
    three_year_metrics: dict | None = Field(None, description="Specific metrics or indicators for the 3-year vision.")


class BigVisionData(BaseModel):
    """Structured data for the Big Vision component."""
    big_vision: str | None = Field(None, description="The aspirational future change they want to create in the world.")
    big_vision_selfless_test_passed: bool | None = Field(None, description="Whether the vision passes the selfless test (they'd be happy even if someone else achieved it).")