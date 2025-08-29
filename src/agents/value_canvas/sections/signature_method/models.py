"""Data models for the Signature Method section."""

from pydantic import BaseModel, Field


class Principle(BaseModel):
    """A single principle within the Signature Method."""
    name: str | None = Field(None, description="The name of the principle (2-4 words).")
    description: str | None = Field(None, description="A brief description of what the principle means in practice (1-2 sentences).")


class SignatureMethodData(BaseModel):
    """Structured data for the Signature Method section."""
    method_name: str | None = Field(None, description="A memorable name for the method (2-4 words).")
    principles: list[Principle] = Field(description="A list of 4-6 core principles that form the method.", max_length=6)