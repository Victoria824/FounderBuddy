"""Pydantic models for Value Canvas Agent."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class SectionStatus(str, Enum):
    """Status of a Value Canvas section."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    MODIFY = "modify"
    GENERATED = "generated"


class RouterDirective(str, Enum):
    """Router directive for navigation control."""
    STAY = "stay"
    NEXT = "next"
    MODIFY = "modify"  # Format: "modify:section_id"


class SectionID(str, Enum):
    """Value Canvas section identifiers."""
    # Initial Interview
    INTERVIEW = "interview"
    
    # Core Value Canvas Sections (9 total)
    ICP = "icp"  # Ideal Customer Persona
    PAIN_1 = "pain_1"
    PAIN_2 = "pain_2"
    PAIN_3 = "pain_3"
    PAYOFF_1 = "payoff_1"
    PAYOFF_2 = "payoff_2"
    PAYOFF_3 = "payoff_3"
    SIGNATURE_METHOD = "signature_method"
    MISTAKES = "mistakes"
    PRIZE = "prize"
    
    # Deep Fear (internal understanding)
    DEEP_FEAR = "deep_fear"
    
    # Implementation/Export
    IMPLEMENTATION = "implementation"


class TiptapNode(BaseModel):
    """Base Tiptap node structure."""
    type: str
    content: Optional[List[Dict[str, Any]]] = None
    text: Optional[str] = None
    attrs: Optional[Dict[str, Any]] = None
    marks: Optional[List[Dict[str, Any]]] = None


class TiptapDocument(BaseModel):
    """Tiptap document structure."""
    type: Literal["doc"] = "doc"
    content: List[TiptapNode] = Field(default_factory=list)


class SectionContent(BaseModel):
    """Content for a Value Canvas section."""
    content: TiptapDocument  # Rich text content in Tiptap JSON format
    plain_text: Optional[str] = None  # Plain text version for LLM processing


class SectionState(BaseModel):
    """State of a single Value Canvas section."""
    id: UUID
    user_id: UUID
    doc_id: UUID
    section_id: SectionID
    content: Optional[SectionContent] = None
    score: Optional[int] = Field(None, ge=0, le=5)  # 0-5 rating
    status: SectionStatus = SectionStatus.PENDING
    updated_at: Optional[str] = None  # ISO timestamp


class ContextPacket(BaseModel):
    """Context packet for current section."""
    section_id: SectionID
    status: SectionStatus
    system_prompt: str
    draft: Optional[SectionContent] = None
    section_template: Optional[str] = None
    validation_rules: Optional[Dict[str, Any]] = None


class ValueCanvasData(BaseModel):
    """Complete Value Canvas data structure."""
    # Initial interview data
    client_name: Optional[str] = None
    preferred_name: Optional[str] = None
    company_name: Optional[str] = None
    industry: Optional[str] = None
    standardized_industry: Optional[str] = None
    specialty: Optional[str] = None
    career_highlight: Optional[str] = None
    client_outcomes: Optional[str] = None
    awards_media: Optional[str] = None
    published_content: Optional[Dict[str, Any]] = None
    specialized_skills: Optional[str] = None
    notable_partners: Optional[str] = None
    
    # ICP data
    icp_standardized_role: Optional[str] = None
    icp_demographics: Optional[str] = None
    icp_geography: Optional[str] = None
    icp_nickname: Optional[str] = None
    icp_affinity: Optional[str] = None
    icp_affordability: Optional[str] = None
    icp_impact: Optional[str] = None
    icp_access: Optional[str] = None
    
    # Pain points (3)
    pain1_symptom: Optional[str] = None
    pain1_struggle: Optional[str] = None
    pain1_cost: Optional[str] = None
    pain1_consequence: Optional[str] = None
    
    pain2_symptom: Optional[str] = None
    pain2_struggle: Optional[str] = None
    pain2_cost: Optional[str] = None
    pain2_consequence: Optional[str] = None
    
    pain3_symptom: Optional[str] = None
    pain3_struggle: Optional[str] = None
    pain3_cost: Optional[str] = None
    pain3_consequence: Optional[str] = None
    
    # Deep Fear
    deep_fear: Optional[str] = None
    
    # Payoffs (3)
    payoff1_objective: Optional[str] = None
    payoff1_desire: Optional[str] = None
    payoff1_without: Optional[str] = None
    payoff1_resolution: Optional[str] = None
    
    payoff2_objective: Optional[str] = None
    payoff2_desire: Optional[str] = None
    payoff2_without: Optional[str] = None
    payoff2_resolution: Optional[str] = None
    
    payoff3_objective: Optional[str] = None
    payoff3_desire: Optional[str] = None
    payoff3_without: Optional[str] = None
    payoff3_resolution: Optional[str] = None
    
    # Signature Method
    method_name: Optional[str] = None
    sequenced_principles: Optional[List[str]] = None
    principle_descriptions: Optional[Dict[str, str]] = None
    
    # Mistakes
    mistakes: Optional[List[Dict[str, Any]]] = None
    
    # Prize
    prize_category: Optional[str] = None
    prize_statement: Optional[str] = None
    refined_prize: Optional[str] = None


class ChatAgentOutput(BaseModel):
    """Output from Chat Agent node."""
    reply: str  # Response to user
    router_directive: str  # Navigation control
    score: Optional[int] = Field(None, ge=0, le=5)  # Section score
    section_update: Optional[SectionContent] = None  # Content update


class ValueCanvasState(MessagesState):
    """State for Value Canvas agent."""
    # User and document identification
    user_id: str
    doc_id: str
    
    # Navigation and progress
    current_section: SectionID = SectionID.INTERVIEW
    context_packet: Optional[ContextPacket] = None
    section_states: Dict[str, SectionState] = Field(default_factory=dict)
    router_directive: str = RouterDirective.STAY
    finished: bool = False
    
    # Value Canvas data
    canvas_data: ValueCanvasData = Field(default_factory=ValueCanvasData)
    
    # Memory management
    short_memory: List[BaseMessage] = Field(default_factory=list)
    
    # Agent output
    agent_output: Optional[ChatAgentOutput] = None
    
    # Error tracking
    error_count: int = 0
    last_error: Optional[str] = None


class ValidationRule(BaseModel):
    """Validation rule for field input."""
    field_name: str
    rule_type: Literal["min_length", "max_length", "regex", "required", "choices"]
    value: Any
    error_message: str


class SectionTemplate(BaseModel):
    """Template for a Value Canvas section."""
    section_id: SectionID
    name: str
    description: str
    system_prompt_template: str
    validation_rules: List[ValidationRule] = Field(default_factory=list)
    required_fields: List[str] = Field(default_factory=list)
    next_section: Optional[SectionID] = None