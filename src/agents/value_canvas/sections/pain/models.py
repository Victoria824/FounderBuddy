"""Data models for the Pain section."""

from pydantic import BaseModel, Field


class PainPoint(BaseModel):
    """Structured data for a single pain point."""
    symptom: str | None = Field(None, description="The observable problem or symptom of the pain (1-3 words).")
    struggle: str | None = Field(None, description="How this pain shows up in their daily work life (1-2 sentences).")
    cost: str | None = Field(None, description="The immediate, tangible cost of this pain.")
    consequence: str | None = Field(None, description="The long-term, future consequence if this pain is not solved.")


class PainData(BaseModel):
    """Structured data for the Pain section, containing three distinct pain points."""
    pain_points: list[PainPoint] = Field(description="A list of three distinct pain points.", max_length=3)