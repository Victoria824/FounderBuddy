"""Data models for the Implementation section."""

from pydantic import BaseModel, Field


class ImplementationData(BaseModel):
    """Structured data for the Implementation section."""
    next_steps: list[str] = Field(default_factory=list, description="List of next steps for implementation.")
    testing_approach: str | None = Field(None, description="Recommended approach for testing the Value Canvas.")
    refinement_timeline: str | None = Field(None, description="Suggested timeline for refinement based on market feedback.")