"""Models for topic_selection section."""

from pydantic import BaseModel, Field
from typing import Optional


class TopicSelectionData(BaseModel):
    """Data model for topic_selection section."""
    selected_topic: str | None = Field(None, description="Final headline choice")
    subtitle: str | None = Field(None, description="Supporting subtitle")
    topic_rationale: str | None = Field(None, description="Why this topic works for their ICP")
    transformation_promise: str | None = Field(None, description="What transformation this promises")
    headline_options: list[str] | None = Field(None, max_length=10, description="Generated headline options")
    topic_confirmed: bool = Field(False, description="Whether the topic has been confirmed")