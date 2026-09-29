from __future__ import annotations

from pydantic import BaseModel

from app.strategies.models import NamedValue


class NamedValueSchema(BaseModel):
    name: str
    value: float

    @classmethod
    def from_domain(cls, value: NamedValue) -> "NamedValueSchema":
        return cls(name=value.name, value=value.value)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
