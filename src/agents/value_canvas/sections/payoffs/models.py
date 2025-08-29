"""Data models for the Payoffs section."""

from pydantic import BaseModel, Field


class PayoffPoint(BaseModel):
    """Structured data for a single payoff point."""
    objective: str | None = Field(None, description="What the client wants to achieve (1-3 words).")
    desire: str | None = Field(None, description="A description of what the client specifically wants (1-2 sentences).")
    without: str | None = Field(None, description="A statement that pre-handles common objections or concerns.")
    resolution: str | None = Field(None, description="A statement that directly resolves the corresponding pain symptom.")


class PayoffsData(BaseModel):
    """Structured data for the Payoffs section, with flattened fields matching prompts requirements."""
    # Payoff Point 1
    payoff1_objective: str | None = Field(None, description="What the client wants to achieve (1-3 words) for payoff 1.")
    payoff1_desire: str | None = Field(None, description="What the client specifically wants (1-2 sentences) for payoff 1.")
    payoff1_without: str | None = Field(None, description="Statement that pre-handles objections for payoff 1.")
    payoff1_resolution: str | None = Field(None, description="Statement that resolves the corresponding pain symptom 1.")
    
    # Payoff Point 2
    payoff2_objective: str | None = Field(None, description="What the client wants to achieve (1-3 words) for payoff 2.")
    payoff2_desire: str | None = Field(None, description="What the client specifically wants (1-2 sentences) for payoff 2.")
    payoff2_without: str | None = Field(None, description="Statement that pre-handles objections for payoff 2.")
    payoff2_resolution: str | None = Field(None, description="Statement that resolves the corresponding pain symptom 2.")
    
    # Payoff Point 3
    payoff3_objective: str | None = Field(None, description="What the client wants to achieve (1-3 words) for payoff 3.")
    payoff3_desire: str | None = Field(None, description="What the client specifically wants (1-2 sentences) for payoff 3.")
    payoff3_without: str | None = Field(None, description="Statement that pre-handles objections for payoff 3.")
    payoff3_resolution: str | None = Field(None, description="Statement that resolves the corresponding pain symptom 3.")
    
    # Optional: Keep list structure for compatibility
    payoffs: list[PayoffPoint] = Field(default_factory=list, description="Optional list structure for backward compatibility.", max_length=3)