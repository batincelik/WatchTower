import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from watchtower.models import CheckStatus, MonitorType


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    monitor_type: MonitorType
    interval_seconds: int = Field(default=300, ge=60, le=2_592_000)
    browser_enabled: bool = False
    selector: str | None = Field(default=None, max_length=1000)
    ignore_selectors: list[str] = Field(default_factory=list, max_length=50)
    ignore_regexes: list[str] = Field(default_factory=list, max_length=20)
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    change_threshold: Decimal = Field(default=Decimal("0"), ge=0, le=100)

    @field_validator("ignore_regexes")
    @classmethod
    def bound_patterns(cls, patterns: list[str]) -> list[str]:
        if any(len(pattern) > 500 for pattern in patterns):
            raise ValueError("Ignore regex patterns are limited to 500 characters")
        return patterns

    @model_validator(mode="after")
    def selector_required(self) -> "MonitorCreate":
        if self.monitor_type in {MonitorType.ELEMENT, MonitorType.PRICE} and not self.selector:
            raise ValueError("selector is required for element and price monitors")
        return self


class MonitorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    url: str
    monitor_type: MonitorType
    enabled: bool
    interval_seconds: int
    browser_enabled: bool
    selector: str | None
    ignore_selectors: list[str]
    ignore_regexes: list[str]
    timeout_seconds: int
    change_threshold: Decimal
    last_checked_at: datetime | None
    next_check_at: datetime | None
    created_at: datetime


class CheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    monitor_id: uuid.UUID
    status: CheckStatus
    scheduled_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    http_status: int | None
    duration_ms: int | None
    error_code: str | None
    error_message: str | None
    changed: bool
    change_score: Decimal | None
