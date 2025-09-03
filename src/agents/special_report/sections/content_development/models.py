"""Models for content_development section."""

from pydantic import BaseModel, Field
from typing import Optional


class ContentDevelopmentData(BaseModel):
    """Data model for content_development section."""
    thinking_style_focus: str | None = Field(None, description="Primary thinking style for this client")
    key_stories: list[str] | None = Field(None, description="Selected stories for report", max_length=5)
    main_framework: str | None = Field(None, description="Primary visual framework to use")
    proof_elements: list[str] | None = Field(None, description="Validation elements selected", max_length=5)
    action_steps: list[str] | None = Field(None, description="Immediate actions for readers", max_length=5)
    
    # Thinking style specific content
    big_picture_elements: list[str] | None = Field(None, max_length=5, description="Trends, maxims, metaphors")
    connection_elements: list[str] | None = Field(None, max_length=5, description="Stories and case studies")
    logic_elements: list[str] | None = Field(None, max_length=5, description="Frameworks and proof points")
    practical_elements: list[str] | None = Field(None, max_length=5, description="Action steps and quick wins")