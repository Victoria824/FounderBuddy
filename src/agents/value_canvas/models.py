'''Pydantic models for Value Canvas Agent.'''

from enum import Enum
from typing import Any, Literal
from uuid import UUID
import uuid

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field, field_validator


class SectionStatus(str, Enum):
    """Status of a Value Canvas section."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class RouterDirective(str, Enum):
    """Router directive for navigation control."""
    STAY = "stay"
    NEXT = "next"
    MODIFY = "modify"  # Format: "modify:section_id"


class SectionID(str, Enum):
    """Value Canvas section identifiers."""
    # Initial Interview
    INTERVIEW = "interview"

    # Core Value Canvas Sections (7 total according to document)
    ICP = "icp"  # Ideal Customer Persona
    PAIN = "pain"  # The Pain (contains 3 pain points)
    DEEP_FEAR = "deep_fear"  # The Deep Fear
    PAYOFFS = "payoffs"  # The Payoffs (contains 3 payoff points)
    SIGNATURE_METHOD = "signature_method"  # Signature Method
    MISTAKES = "mistakes"  # The Mistakes
    PRIZE = "prize"  # The Prize

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
    """Content for a Value Canvas section."""
    content: TiptapDocument  # Rich text content in Tiptap JSON format
    plain_text: str | None = None  # Plain text version for LLM processing


class SectionState(BaseModel):
    """State of a single Value Canvas section."""
    section_id: SectionID
    content: SectionContent | None = None
    score: int | None = Field(None, ge=0, le=5)  # 0-5 rating
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
    is_requesting_rating: bool = Field(
        default=False,
        description="Set to true ONLY when the previous reply explicitly asked the user for a 0-5 rating."
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
    """Template for a Value Canvas section."""
    section_id: SectionID
    name: str
    description: str
    system_prompt_template: str
    validation_rules: list[ValidationRule] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    next_section: SectionID | None = None


# --- Structured Output Models for Data Extraction ---

class InterviewData(BaseModel):
    """A data structure to hold extracted information from the user interview."""
    
    client_name: str | None = Field(
        None, 
        description="The user's full name. Exclude any mention of a preferred name."
    )
    preferred_name: str | None = Field(
        None, 
        description="The user's preferred name or nickname, often found in parentheses."
    )
    company_name: str | None = Field(
        None, 
        description="The name of the user's company."
    )
    industry: str | None = Field(
        None, 
        description="The industry the user works in."
    )
    specialty: str | None = Field(
        None, 
        description="The user's specialty or 'zone of genius'."
    )
    career_highlight: str | None = Field(
        None, 
        description="A career achievement the user is proud of."
    )
    client_outcomes: str | None = Field(
        None, 
        description="The typical results or outcomes clients get from working with the user."
    )
    specialized_skills: str | None = Field(
        None, 
        description="Specific skills or qualifications the user mentioned."
    )


class ICPData(BaseModel):
    """Structured data for the Ideal Client Persona (ICP) section, based on the new structured template."""
    role_identity: str | None = Field(None, description="The primary role or identity of the ICP (e.g., 'Founder', 'Stay at home mum').")
    context_scale: str | None = Field(None, description="The scale or context of their role (e.g., 'fast growth tech companies', 'Family of 4').")
    industry_sector: str | None = Field(None, description="The industry or sector they operate in.")
    gender: str | None = Field(None, description="The gender of the ICP.")
    age_range: str | None = Field(None, description="The typical age range of the ICP (e.g., '35-50').")
    income_level: str | None = Field(None, description="Income, budget level, or company revenue.")
    country_region: str | None = Field(None, description="The country or region where the ICP is based.")
    location_setting: str | None = Field(None, description="The typical living or working setting (e.g., 'urban', 'suburban', 'rural').")
    primary_interests: str | None = Field(None, description="Primary interests or values of the ICP.")
    lifestyle_indicators: list[str] = Field(default_factory=list, description="Specific lifestyle indicators that show their values (e.g., 'Drives a luxury european car', 'Plays golf').")


class PainPoint(BaseModel):
    """Structured data for a single pain point."""
    symptom: str | None = Field(None, description="The observable problem or symptom of the pain (1-3 words).")
    struggle: str | None = Field(None, description="How this pain shows up in their daily work life (1-2 sentences).")
    cost: str | None = Field(None, description="The immediate, tangible cost of this pain.")
    consequence: str | None = Field(None, description="The long-term, future consequence if this pain is not solved.")


class PainData(BaseModel):
    """Structured data for the Pain section, containing three distinct pain points."""
    pain_points: list[PainPoint] = Field(description="A list of three distinct pain points.", max_length=3)


class DeepFearData(BaseModel):
    """Structured data for the Deep Fear section."""
    deep_fear: str | None = Field(None, description="The private doubt or self-question the client has that they rarely voice.")


class PayoffPoint(BaseModel):
    """Structured data for a single payoff point."""
    objective: str | None = Field(None, description="What the client wants to achieve (1-3 words).")
    desire: str | None = Field(None, description="A description of what the client specifically wants (1-2 sentences).")
    without: str | None = Field(None, description="A statement that pre-handles common objections or concerns.")
    resolution: str | None = Field(None, description="A statement that directly resolves the corresponding pain symptom.")


class PayoffsData(BaseModel):
    """Structured data for the Payoffs section, containing three distinct payoff points."""
    payoffs: list[PayoffPoint] = Field(description="A list of three distinct payoff points that mirror the pain points.", max_length=3)


class Principle(BaseModel):
    """A single principle within the Signature Method."""
    name: str | None = Field(None, description="The name of the principle (2-4 words).")
    description: str | None = Field(None, description="A brief description of what the principle means in practice (1-2 sentences).")


class SignatureMethodData(BaseModel):
    """Structured data for the Signature Method section."""
    method_name: str | None = Field(None, description="A memorable name for the method (2-4 words).")
    principles: list[Principle] = Field(description="A list of 4-6 core principles that form the method.", max_length=6)


class Mistake(BaseModel):
    """Structured data for a single mistake."""
    related_to: str = Field(description="The pain point or method principle this mistake is related to.")
    root_cause: str | None = Field(None, description="The non-obvious reason this mistake keeps happening.")
    error_in_thinking: str | None = Field(None, description="The flawed belief that makes the problem worse.")
    error_in_action: str | None = Field(None, description="What they do that feels right but creates more problems.")


class MistakesData(BaseModel):
    """Structured data for the Mistakes section."""
    mistakes: list[Mistake] = Field(description="A list of mistakes related to pain points and method principles.", max_length=10)


class PrizeData(BaseModel):
    """Structured data for the Prize section."""
    category: str | None = Field(None, description="The category of the prize (e.g., Identity-Based, Outcome-Based).")
    statement: str | None = Field(None, description="The 1-5 word prize statement.") 