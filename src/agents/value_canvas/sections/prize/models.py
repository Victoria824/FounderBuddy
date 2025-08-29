"""Data models for the Prize section."""

from pydantic import BaseModel, Field


class PrizeData(BaseModel):
    """Structured data for the Prize section."""
    prize_statement: str | None = Field(None, description="The 1-5 word prize statement.")