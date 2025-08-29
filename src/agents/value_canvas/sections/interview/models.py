"""Data models for the Interview section."""

from pydantic import BaseModel, Field


class InterviewData(BaseModel):
    """A data structure to hold extracted information from the user interview."""
    
    client_name: str | None = Field(
        None, 
        description="The user's full name. Exclude any mention of a preferred name."
    )
    preferred_name: str | None = Field(
        None, 
        description="The user's preferred name or nickname, often found in parentheses."
    )
    company_name: str | None = Field(
        None, 
        description="The name of the user's company."
    )
    industry: str | None = Field(
        None, 
        description="The industry the user works in."
    )
    specialty: str | None = Field(
        None, 
        description="The user's specialty or 'zone of genius'."
    )
    career_highlight: str | None = Field(
        None, 
        description="A career achievement the user is proud of."
    )
    client_outcomes: str | None = Field(
        None, 
        description="The typical results or outcomes clients get from working with the user."
    )
    specialized_skills: str | None = Field(
        None, 
        description="Specific skills or qualifications the user mentioned."
    )