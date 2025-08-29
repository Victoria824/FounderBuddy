"""Data models for the Pain section."""

from pydantic import BaseModel, Field


class PainPoint(BaseModel):
    """Structured data for a single pain point."""
    symptom: str | None = Field(None, description="The observable problem or symptom of the pain (1-3 words).")
    struggle: str | None = Field(None, description="How this pain shows up in their daily work life (1-2 sentences).")
    cost: str | None = Field(None, description="The immediate, tangible cost of this pain.")
    consequence: str | None = Field(None, description="The long-term, future consequence if this pain is not solved.")


class PainData(BaseModel):
    """Structured data for the Pain section, with flattened fields matching prompts requirements."""
    # Pain Point 1
    pain1_symptom: str | None = Field(None, description="The observable problem (1-3 words) for pain point 1.")
    pain1_struggle: str | None = Field(None, description="How pain 1 shows up in their daily work life (1-2 sentences).")
    pain1_cost: str | None = Field(None, description="The immediate, tangible cost of pain 1.")
    pain1_consequence: str | None = Field(None, description="The long-term consequence if pain 1 is not solved.")
    
    # Pain Point 2
    pain2_symptom: str | None = Field(None, description="The observable problem (1-3 words) for pain point 2.")
    pain2_struggle: str | None = Field(None, description="How pain 2 shows up in their daily work life (1-2 sentences).")
    pain2_cost: str | None = Field(None, description="The immediate, tangible cost of pain 2.")
    pain2_consequence: str | None = Field(None, description="The long-term consequence if pain 2 is not solved.")
    
    # Pain Point 3
    pain3_symptom: str | None = Field(None, description="The observable problem (1-3 words) for pain point 3.")
    pain3_struggle: str | None = Field(None, description="How pain 3 shows up in their daily work life (1-2 sentences).")
    pain3_cost: str | None = Field(None, description="The immediate, tangible cost of pain 3.")
    pain3_consequence: str | None = Field(None, description="The long-term consequence if pain 3 is not solved.")
    
    # Optional: Keep list structure for compatibility
    pain_points: list[PainPoint] = Field(default_factory=list, description="Optional list structure for backward compatibility.", max_length=3)