"""Data models for the Prize section."""

from pydantic import BaseModel, Field


class PrizeData(BaseModel):
    """Structured data for the Prize section."""
    category: str | None = Field(None, description="The category of the prize (e.g., Identity-Based, Outcome-Based).")
    statement: str | None = Field(None, description="The 1-5 word prize statement.")