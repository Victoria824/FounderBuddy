"""Data models for the ICP section."""

from pydantic import BaseModel, Field


class ICPData(BaseModel):
    """Structured data for the Ideal Client Persona (ICP) section, matching the 10 required fields from prompts."""
    icp_nickname: str | None = Field(None, description="A compelling 2-4 word nickname based on their role/situation.")
    icp_role_identity: str | None = Field(None, description="Their primary role or life situation.")
    icp_context_scale: str | None = Field(None, description="What describes their situation size/scope (company size, team size, funding, etc.).")
    icp_industry_sector_context: str | None = Field(None, description="The industry/sector they work in AND a key insight about that sector.")
    icp_demographics: str | None = Field(None, description="Gender, age range, income/budget level, geographic location.")
    icp_interests: str | None = Field(None, description="3 specific interests (primary, secondary, tertiary).")
    icp_values: str | None = Field(None, description="2 lifestyle indicators that show their values.")
    icp_golden_insight: str | None = Field(None, description="A profound insight about their buying motivations.")
    icp_buying_triggers: str | None = Field(None, description="The 3 moments, pressures, or events that push this ICP from 'thinking about it' to taking action.")
    icp_red_flags: str | None = Field(None, description="The attitudes, messages, or sales tactics that repel this ICP or make them shut down.")