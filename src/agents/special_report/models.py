"""Pydantic models for Special Report Agent."""

from enum import Enum
from typing import Any, Dict, Literal, Optional
from uuid import UUID
import uuid

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field, field_validator


class SectionStatus(str, Enum):
    """Status of a section."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    DONE = "done"


class RouterDirective(str, Enum):
    """Router directive for navigation control."""
    STAY = "stay"
    NEXT = "next"
    MODIFY = "modify"  # Format: "modify:section_id"


class SpecialReportSection(str, Enum):
    """Special Report section identifiers following the 3-step process."""
    TOPIC_SELECTION = "topic_selection"
    CONTENT_DEVELOPMENT = "content_development"
    REPORT_STRUCTURE = "report_structure"
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


class TiptapDocument(BaseModel):
    """Tiptap document structure."""
    type: Literal["doc"] = "doc"
    content: list[TiptapParagraphNode] = Field(default_factory=list, max_length=30)


class SectionContent(BaseModel):
    """Content for a section."""
    content: TiptapDocument  # Rich text content in Tiptap JSON format
    plain_text: str | None = None  # Plain text version for LLM processing


class SectionState(BaseModel):
    """State of a single section."""
    section_id: SpecialReportSection
    content: SectionContent | None = None
    score: int | None = Field(None, ge=0, le=5)  # 0-5 rating
    status: SectionStatus = SectionStatus.PENDING


class ContextPacket(BaseModel):
    """Context packet for current section."""
    section_id: SpecialReportSection
    status: SectionStatus
    system_prompt: str
    draft: SectionContent | None = None
    validation_rules: dict[str, Any] | None = None


class TopicData(BaseModel):
    """Data for Special Report topic selection."""
    selected_topic: str | None = None
    headline_options: list[str] | None = Field(None, max_length=10)
    subtitle: str | None = None
    topic_confirmed: bool = False

class ContentData(BaseModel):
    """Data for the 4 thinking styles content development."""
    # Big Picture content
    trends: list[str] | None = Field(None, max_length=5)
    maxims: list[str] | None = Field(None, max_length=5) 
    metaphors: list[str] | None = Field(None, max_length=5)
    
    # Connection content
    personal_stories: list[str] | None = Field(None, max_length=5)
    client_stories: list[str] | None = Field(None, max_length=10)
    
    # Logic content
    visual_frameworks: list[str] | None = Field(None, max_length=5)
    proof_points: list[str] | None = Field(None, max_length=10)
    data_validation: list[str] | None = Field(None, max_length=5)
    
    # Practical content
    immediate_actions: list[str] | None = Field(None, max_length=10)
    quick_wins: list[str] | None = Field(None, max_length=5)

class ReportStructureData(BaseModel):
    """Data for the 7-step article structure."""
    attract_content: str | None = None
    disrupt_content: str | None = None
    inform_content: str | None = None
    recommend_content: str | None = None
    overcome_content: str | None = None
    reinforce_content: str | None = None
    invite_content: str | None = None

class SpecialReportData(BaseModel):
    """Complete Special Report data structure."""
    topic_data: TopicData = Field(default_factory=TopicData)
    content_data: ContentData = Field(default_factory=ContentData)
    report_structure: ReportStructureData = Field(default_factory=ReportStructureData)
    final_report: str | None = None  # Complete 5500-word report
    word_count: int | None = None


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


class SpecialReportState(MessagesState):
    """State for Special Report agent."""
    # User and document identification
    user_id: int = 1
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Navigation and progress
    current_section: SpecialReportSection = SpecialReportSection.TOPIC_SELECTION
    context_packet: ContextPacket | None = None
    section_states: dict[str, SectionState] = Field(default_factory=dict)
    router_directive: str = RouterDirective.NEXT  # Start by loading first section
    finished: bool = False

    # Special Report data
    canvas_data: SpecialReportData = Field(default_factory=SpecialReportData)

    # Memory management
    short_memory: list[BaseMessage] = Field(default_factory=list)

    # Agent output
    agent_output: ChatAgentOutput | None = None
    awaiting_user_input: bool = False
    is_awaiting_rating: bool = False

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
    """Template for a section."""
    section_id: SpecialReportSection
    name: str
    description: str
    system_prompt_template: str
    validation_rules: list[ValidationRule] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    next_section: SpecialReportSection | None = None


# Structured Output Models for Data Extraction

class TopicSelectionData(BaseModel):
    """Structured data for Topic Selection section."""
    selected_headline: str | None = Field(None, description="Final headline choice")
    subtitle: str | None = Field(None, description="Supporting subtitle")
    topic_rationale: str | None = Field(None, description="Why this topic works for their ICP")
    transformation_promise: str | None = Field(None, description="What transformation this promises")

class ContentDevelopmentData(BaseModel):
    """Structured data for Content Development section."""
    thinking_style_focus: str | None = Field(None, description="Primary thinking style for this client")
    key_stories: list[str] | None = Field(None, description="Selected stories for report", max_length=5)
    main_framework: str | None = Field(None, description="Primary visual framework to use")
    proof_elements: list[str] | None = Field(None, description="Validation elements selected", max_length=5)
    action_steps: list[str] | None = Field(None, description="Immediate actions for readers", max_length=5)

class ReportStructureData(BaseModel):
    """Structured data for Report Structure section.""" 
    section_summaries: dict[str, str] | None = Field(None, description="Summary of each 7-step section")
    key_transitions: list[str] | None = Field(None, description="Important section transitions", max_length=6)
    call_to_action: str | None = Field(None, description="Final CTA and next step")
    estimated_word_count: int | None = Field(None, description="Estimated total word count")