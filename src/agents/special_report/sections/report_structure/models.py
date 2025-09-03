"""Models for report_structure section."""

from pydantic import BaseModel, Field
from typing import Optional


class ReportStructureData(BaseModel):
    """Data model for report_structure section."""
    attract_content: str | None = Field(None, description="Attract section content outline")
    disrupt_content: str | None = Field(None, description="Disrupt section content outline")
    inform_content: str | None = Field(None, description="Inform section content outline")
    recommend_content: str | None = Field(None, description="Recommend section content outline")
    overcome_content: str | None = Field(None, description="Overcome section content outline")
    reinforce_content: str | None = Field(None, description="Reinforce section content outline")
    invite_content: str | None = Field(None, description="Invite section content outline")
    
    # Additional structure elements
    section_summaries: dict[str, str] | None = Field(None, description="Summary of each 7-step section")
    key_transitions: list[str] | None = Field(None, description="Important section transitions", max_length=6)
    call_to_action: str | None = Field(None, description="Final CTA and next step")
    estimated_word_count: int | None = Field(None, description="Estimated total word count")