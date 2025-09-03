"""Models for implementation section."""

from pydantic import BaseModel, Field
from typing import Optional


class ImplementationData(BaseModel):
    """Data model for implementation section."""
    final_report: str | None = Field(None, description="Complete generated report content")
    word_count: int | None = Field(None, description="Final word count")
    export_url: str | None = Field(None, description="URL to download the report")
    generation_status: str | None = Field(None, description="Status of report generation")
    completion_timestamp: str | None = Field(None, description="When the report was completed")