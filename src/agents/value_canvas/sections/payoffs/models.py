"""Data models for the Payoffs section."""

from pydantic import BaseModel, Field


class PayoffPoint(BaseModel):
    """Structured data for a single payoff point."""
    objective: str | None = Field(None, description="What the client wants to achieve (1-3 words).")
    desire: str | None = Field(None, description="A description of what the client specifically wants (1-2 sentences).")
    without: str | None = Field(None, description="A statement that pre-handles common objections or concerns.")
    resolution: str | None = Field(None, description="A statement that directly resolves the corresponding pain symptom.")


class PayoffsData(BaseModel):
    """Structured data for the Payoffs section, containing three distinct payoff points."""
    payoffs: list[PayoffPoint] = Field(description="A list of three distinct payoff points that mirror the pain points.", max_length=3)