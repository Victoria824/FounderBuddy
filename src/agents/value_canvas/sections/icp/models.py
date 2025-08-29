"""Data models for the ICP section."""

from pydantic import BaseModel, Field


class ICPData(BaseModel):
    """Structured data for the Ideal Client Persona (ICP) section, based on the new structured template."""
    role_identity: str | None = Field(None, description="The primary role or identity of the ICP (e.g., 'Founder', 'Stay at home mum').")
    context_scale: str | None = Field(None, description="The scale or context of their role (e.g., 'fast growth tech companies', 'Family of 4').")
    industry_sector: str | None = Field(None, description="The industry or sector they operate in.")
    gender: str | None = Field(None, description="The gender of the ICP.")
    age_range: str | None = Field(None, description="The typical age range of the ICP (e.g., '35-50').")
    income_level: str | None = Field(None, description="Income, budget level, or company revenue.")
    country_region: str | None = Field(None, description="The country or region where the ICP is based.")
    location_setting: str | None = Field(None, description="The typical living or working setting (e.g., 'urban', 'suburban', 'rural').")
    primary_interests: str | None = Field(None, description="Primary interests or values of the ICP.")
    lifestyle_indicators: list[str] = Field(default_factory=list, description="Specific lifestyle indicators that show their values (e.g., 'Drives a luxury european car', 'Plays golf').")