from pydantic import BaseModel, Field, field_validator

class TransactionIn(BaseModel):
    transaction_id: str
    transaction_dt: float = Field(..., description="seconds since reference epoch")
    transaction_amt: float = Field(..., gt=0)
    card1: int
    card2: int | None = None
    card3: int | None = None
    card5: int | None = None
    addr1: int | None = None
    raw_features: dict[str, float | str | None] = Field(default_factory=dict)

    @field_validator("transaction_amt")
    @classmethod
    def sane_amount(cls, v: float) -> float:
        if v > 10_000_000:
            raise ValueError("transaction_amt implausibly large — check upstream data")
        return v

    def uid_key(self) -> str:
        """Must match training-time uid construction exactly — see features/offline.py."""
        return f"{self.card1}_{self.card2}_{self.card3}_{self.card5}_{self.addr1}"

class ExplanationItem(BaseModel):
    feature: str
    contribution: float

class ThresholdUpdate(BaseModel):
    threshold: float

class ScoreResponse(BaseModel):
    transaction_id: str
    fraud_probability: float
    flagged: bool
    threshold_used: float
    reasons: list[ExplanationItem]
    model_version: str
