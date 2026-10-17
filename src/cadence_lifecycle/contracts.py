"""Explicit contracts for independent lifecycle evaluation."""
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ContractViolationError(ValueError):
    """Input is not eligible for a defensible lifecycle calculation."""

class LifecycleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    decision_year: int = Field(ge=2020, le=2200)
    horizon_years: int = Field(default=30, ge=1, le=100)
    real_discount_rate: float = Field(default=0.03, gt=-1, le=1)
    base_dollar_year: int = Field(ge=1900, le=2200)
    hazard_method_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    maintenance_enabled: bool = False
    salvage_enabled: bool = False
    contents_enabled: bool = False
    downtime_enabled: bool = False
    debris_brick_wood_enabled: bool = False
    debris_concrete_steel_enabled: bool = False
    building_enabled: bool = True
    @model_validator(mode="after")
    def check(self):
        if self.base_dollar_year > self.decision_year:
            raise ValueError("base_dollar_year cannot be after decision_year")
        return self

REQUIRED_ASSET = {"asset_id", "option_id", "decision_year", "material_id", "initial_rul_years", "new_eul_years", "replacement_cost_real", "roof_area_sqft"}

def require_columns(df, required, label):
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ContractViolationError(f"{label} missing columns: {missing}")

def require_unique(df, keys, label):
    require_columns(df, keys, label)
    if df.select(keys).unique().height != df.height:
        raise ContractViolationError(f"{label} has duplicate keys {keys}")
