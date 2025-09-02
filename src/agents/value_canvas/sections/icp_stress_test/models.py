"""Data models for the ICP Stress Test section."""

from pydantic import BaseModel, Field


class ICPStressTestData(BaseModel):
    """Structured data for the ICP Stress Test section."""
    
    # Individual stress test scores (0-5 scale)
    can_influence_score: int | None = Field(
        None, 
        ge=0, 
        le=5,
        description="Score for ability to influence the ICP (0-5)"
    )
    like_working_with_score: int | None = Field(
        None, 
        ge=0, 
        le=5,
        description="Score for enjoyment working with the ICP (0-5)"
    )
    afford_premium_score: int | None = Field(
        None, 
        ge=0, 
        le=5,
        description="Score for ICP's ability to afford premium pricing (0-5)"
    )
    decision_maker_score: int | None = Field(
        None, 
        ge=0, 
        le=5,
        description="Score for ICP being the decision maker (0-5)"
    )
    significant_transformation_score: int | None = Field(
        None, 
        ge=0, 
        le=5,
        description="Score for ability to deliver significant transformation (0-5)"
    )
    
    # Aggregate results
    total_score: int | None = Field(
        None, 
        ge=0, 
        le=25,
        description="Total stress test score (sum of all 5 scores)"
    )
    passed_threshold: bool | None = Field(
        None,
        description="Whether the ICP passed the 14/25 minimum threshold"
    )
    
    # Insights and refinements
    golden_insight: str | None = Field(
        None,
        description="A surprising refinement to their ICP to test in the market"
    )
    icp_refinements: str | None = Field(
        None,
        description="Documented refinements made to the ICP during stress testing"
    )
    
    # Track if ICP was updated
    icp_updated: bool | None = Field(
        None,
        description="Whether the original ICP was modified during stress testing"
    )