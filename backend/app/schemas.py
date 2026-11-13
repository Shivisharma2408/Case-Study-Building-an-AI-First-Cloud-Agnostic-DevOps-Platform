from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IdeaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # The upper bound is enforced against Settings.max_idea_length in the route;
    # this hard ceiling protects the parser from absurd payloads.
    content: str = Field(min_length=1, max_length=10_000)

    @field_validator("content")
    @classmethod
    def no_control_characters(cls, value: str) -> str:
        if any(ord(ch) < 32 and ch not in "\n\t" for ch in value):
            raise ValueError("content must not contain control characters")
        return value


class IdeaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    created_at: datetime
