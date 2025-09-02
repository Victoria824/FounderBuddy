"""Data models for the Pain-Payoff Symmetry section."""

from pydantic import BaseModel, Field


class PainPayoffSymmetryData(BaseModel):
    """Structured data for the Pain-Payoff Symmetry analysis section."""
    
    # The 5 Golden Insights presented to the user
    golden_insight_1: str | None = Field(
        None,
        description="First golden insight about pain-payoff symmetry"
    )
    golden_insight_2: str | None = Field(
        None,
        description="Second golden insight about pain-payoff symmetry"
    )
    golden_insight_3: str | None = Field(
        None,
        description="Third golden insight about pain-payoff symmetry"
    )
    golden_insight_4: str | None = Field(
        None,
        description="Fourth golden insight about pain-payoff symmetry"
    )
    golden_insight_5: str | None = Field(
        None,
        description="Fifth golden insight about pain-payoff symmetry"
    )
    
    # Track section completion
    insights_presented: bool | None = Field(
        None,
        description="Whether all 5 insights have been presented"
    )
    user_ready_to_proceed: bool | None = Field(
        None,
        description="Whether user indicated readiness to continue"
    )