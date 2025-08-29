"""Data models for the Mistakes section."""

from pydantic import BaseModel, Field


class Mistake(BaseModel):
    """Structured data for a single mistake."""
    related_to: str = Field(description="The Signature Method principle this mistake is resolved by.")
    root_cause: str | None = Field(None, description="[Deprecated] The non-obvious reason this mistake keeps happening.")
    error_in_thinking: str | None = Field(None, description="The flawed belief that perpetuates the ICP's pain and is resolved by the related principle.")
    error_in_action: str | None = Field(None, description="The counterproductive action that feels right but creates more problems.")


class MistakesData(BaseModel):
    """Structured data for the Mistakes section."""
    mistakes: list[Mistake] = Field(description="A list of method-based mistakes, one for each Signature Method principle.", max_length=10)