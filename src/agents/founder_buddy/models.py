"""Pydantic models for Founder Buddy Agent."""

import uuid
from typing import Any

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field, field_validator

from .enums import RouterDirective, SectionID, SectionStatus
from .sections.base_prompt import SectionTemplate, ValidationRule


class TiptapTextNode(BaseModel):
    """Tiptap text node."""
    type: str = "text"
    text: str
    marks: list[dict[str, Any]] | None = Field(None, max_length=5)


class TiptapParagraphNode(BaseModel):
    """Tiptap paragraph node."""
    type: str = "paragraph"
    content: list[TiptapTextNode] = Field(default_factory=list, max_length=50)
    attrs: dict[str, Any] | None = None


class TiptapDocument(BaseModel):
    """Tiptap document structure."""
    type: str = "doc"
    content: list[TiptapParagraphNode] = Field(default_factory=list, max_length=30)


class SectionContent(BaseModel):
    """Content for a Founder Buddy section."""
    content: TiptapDocument  # Rich text content in Tiptap JSON format
    plain_text: str | None = None  # Plain text version for LLM processing


class SectionState(BaseModel):
    """State of a single Founder Buddy section."""
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


class FounderBuddyData(BaseModel):
    """Complete Founder Buddy data structure."""
    # Mission section data
    mission_description: str | None = None
    vision_statement: str | None = None
    target_audience: str | None = None
    
    # Idea section data
    product_description: str | None = None
    core_value_proposition: str | None = None
    key_features: list[str] = Field(default_factory=list)
    differentiation: str | None = None
    
    # Team & Traction section data
    team_members: list[dict[str, str]] = Field(default_factory=list)
    key_milestones: list[str] = Field(default_factory=list)
    traction_metrics: dict[str, Any] = Field(default_factory=dict)
    
    # Investment Plan section data
    funding_amount: str | None = None
    funding_use: str | None = None
    valuation: str | None = None
    exit_strategy: str | None = None


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
    should_save_content: bool = Field(
        False,
        description="Whether the AI just presented a summary that should be saved. True when presenting section summary for user review, False when still collecting information.",
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
    should_save_content: bool = Field(
        False,
        description="Whether the AI just presented a summary that should be saved. True when presenting section summary for user review, False when still collecting information.",
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


class FounderBuddyState(MessagesState):
    """State for Founder Buddy agent."""
    # User and document identification
    user_id: int = 1
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Navigation and progress
    current_section: SectionID = SectionID.MISSION
    context_packet: ContextPacket | None = None
    section_states: dict[str, SectionState] = Field(default_factory=dict)
    router_directive: str = RouterDirective.NEXT
    finished: bool = False

    # Founder Buddy data
    founder_data: FounderBuddyData = Field(default_factory=FounderBuddyData)

    # Memory management
    short_memory: list[BaseMessage] = Field(default_factory=list)

    # Agent output
    agent_output: ChatAgentOutput | None = None
    awaiting_user_input: bool = False
    awaiting_satisfaction_feedback: bool = False

    # Error tracking
    error_count: int = 0
    last_error: str | None = None
    
    # Business plan
    business_plan: str | None = None
    should_generate_business_plan: bool = False


__all__ = [
    "SectionStatus",
    "RouterDirective",
    "SectionID",
    "TiptapDocument",
    "SectionContent",
    "SectionState",
    "ContextPacket",
    "FounderBuddyData",
    "ChatAgentDecision",
    "ChatAgentOutput",
    "FounderBuddyState",
    "ValidationRule",
    "SectionTemplate",
]

