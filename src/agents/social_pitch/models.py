'''Pydantic models for Value Canvas Agent.'''

from enum import Enum
from typing import Any, Literal
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field, field_validator


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
    content: list[TiptapInlineNode] = Field(default_factory=list, max_length=50)
    attrs: dict[str, Any] | None = None


class TiptapNode(BaseModel):
    """Base Tiptap node structure."""
    type: str
    content: list[TiptapInlineNode] | None = Field(None, max_length=50)
    text: str | None = None
    attrs: dict[str, Any] | None = None
    marks: list[dict[str, Any]] | None = Field(None, max_length=5)


class TiptapDocument(BaseModel):
    """Tiptap document structure."""
    type: Literal["doc"] = "doc"
    content: list[TiptapParagraphNode] = Field(default_factory=list, max_length=20)


class SectionContent(BaseModel):
    """Content for a Value Canvas section."""
    content: TiptapDocument  # Rich text content in Tiptap JSON format
    plain_text: str | None = None  # Plain text version for LLM processing


class SectionState(BaseModel):
    """State of a single Value Canvas section."""
    id: UUID
    user_id: UUID
    doc_id: UUID
    section_id: SectionID
    content: SectionContent | None = None
    score: int | None = Field(None, ge=0, le=5)  # 0-5 rating
    status: SectionStatus = SectionStatus.PENDING
    updated_at: str | None = None  # ISO timestamp


class ContextPacket(BaseModel):
    """Context packet for current section."""
    section_id: SectionID
    status: SectionStatus
    system_prompt: str
    draft: SectionContent | None = None
    section_template: str | None = None
    validation_rules: dict[str, Any] | None = None


class ValueCanvasData(BaseModel):
    """Complete Value Canvas data structure."""
    # Basic information from initial interview
    client_name: str | None = None
    preferred_name: str | None = None  # 添加昵称字段
    company_name: str | None = None
    industry: str | None = None
    standardized_industry: str | None = None
    specialty: str | None = None
    career_highlight: str | None = None
    client_outcomes: str | None = None
    awards_media: str | None = None
    published_content: str | None = None
    published_content_types: str | None = None  # 添加发布内容类型字段
    specialized_skills: str | None = None
    notable_partners: str | None = None

    # ICP data
    icp_standardized_role: str | None = None
    icp_demographics: str | None = None
    icp_geography: str | None = None
    icp_nickname: str | None = None
    icp_affinity: str | None = None
    icp_affordability: str | None = None
    icp_impact: str | None = None
    icp_access: str | None = None

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


class ChatAgentOutput(BaseModel):
    """Output from Chat Agent node."""

    reply: str = Field(..., description="Conversational response to the user.")
    router_directive: str = Field(
        ...,
        description="Navigation control: 'stay' to continue on the current section, 'next' to proceed to the next section, or 'modify:<section_id>' to jump to a specific section.",
    )
    score: int | None = Field(
        None, ge=0, le=5, description="Satisfaction score (0-5) if user provided one."
    )
    section_update: SectionContent | None = Field(
        None,
        description="Tiptap JSON object containing the complete summary for the current section. This should only be included when the section is complete and ready to be saved.",
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
        """Validate section_update to prevent infinite loops and empty content."""
        if v and v.content:
            # Limit document content array size  
            if len(v.content.content) > 50:
                raise ValueError("Section content too large - maximum 50 paragraph nodes allowed")
            
            # Check each paragraph node
            for para_node in v.content.content:
                if para_node.content and len(para_node.content) > 100:
                    raise ValueError("Paragraph content too large - maximum 100 inline nodes allowed")
                
                # Check for empty inline nodes
                for inline_node in para_node.content:
                    if hasattr(inline_node, 'type') and inline_node.type == 'text':
                        if not hasattr(inline_node, 'text') or not inline_node.text.strip():
                            raise ValueError("Empty text nodes not allowed")
        return v


class ValueCanvasState(MessagesState):
    """State for Value Canvas agent."""
    # User and document identification
    user_id: int = 1
    doc_id: str = "studio-doc"

    # Navigation and progress
    current_section: SectionID = SectionID.INTERVIEW
    context_packet: ContextPacket | None = None
    section_states: dict[str, SectionState] = Field(default_factory=dict)
    # 初次进入希望 Router 直接调用 get_context，所以默认 NEXT
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
    """Structured data for the Ideal Client Persona (ICP) section."""
    nickname: str | None = Field(None, description="A short, memorable nickname for the ICP.")
    role_and_sector: str | None = Field(None, description="The ICP's professional role and the sector they operate in.")
    demographics: str | None = Field(None, description="Key demographic information about the ICP (e.g., age, income, family status).")
    geography: str | None = Field(None, description="The geographic location where the ICP is typically found.")
    affinity: str | None = Field(None, description="Assessment of whether you would enjoy working with this ICP.")
    affordability: str | None = Field(None, description="Assessment of the ICP's ability to afford premium pricing.")
    impact: str | None = Field(None, description="Assessment of the potential significance of your solution's impact on the ICP.")
    access: str | None = Field(None, description="Assessment of how easily you can reach and connect with this ICP.")


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