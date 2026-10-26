"""Pydantic request/response models for the web API."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, model_validator


class CueIn(BaseModel):
    """A cue as edited in the browser (indices are re-assigned server-side)."""

    start: float = Field(ge=0, le=86400 * 24)
    end: float = Field(ge=0, le=86400 * 24)
    text: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def check_order(self) -> "CueIn":
        if self.end < self.start:
            raise ValueError("Cue 'end' must be greater than or equal to 'start'")
        return self


class SubtitleUpdate(BaseModel):
    cues: List[CueIn]


class JobCreated(BaseModel):
    job_id: str
