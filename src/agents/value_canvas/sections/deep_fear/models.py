"""Data models for the Deep Fear section."""

from pydantic import BaseModel, Field


class DeepFearData(BaseModel):
    """Structured data for the Deep Fear section."""
    deep_fear: str | None = Field(None, description="The private doubt or self-question the client has that they rarely voice.")
    golden_insight: str | None = Field(None, description="A surprising truth about the ICP's deepest motivation that they may not have realized.")