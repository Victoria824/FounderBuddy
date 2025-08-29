"""Data models for the Signature Method section."""

from pydantic import BaseModel, Field


class Principle(BaseModel):
    """A single principle within the Signature Method."""
    name: str | None = Field(None, description="The name of the principle (2-4 words).")
    description: str | None = Field(None, description="A brief description of what the principle means in practice (1-2 sentences).")


class SignatureMethodData(BaseModel):
    """Structured data for the Signature Method section."""
    method_name: str | None = Field(None, description="A memorable name for the method (2-4 words).")
    sequenced_principles: list[str] | None = Field(None, description="Ordered list of principle names.", max_length=6)
    principle_descriptions: dict[str, str] | None = Field(None, description="Descriptions for each principle, keyed by principle name.")
    # Keep original structure for compatibility
    principles: list[Principle] = Field(default_factory=list, description="Optional list structure for backward compatibility.", max_length=6)