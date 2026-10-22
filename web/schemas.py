"""Pydantic request/response models for the web API."""
from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

_PUSHABLE_FILES = frozenset({"srt", "vtt", "video"})
_GH_REPO_RE = re.compile(r"^[\w.\-]+/[\w.\-]+$")
_GH_BRANCH_RE = re.compile(r"^[\w.\-]+(?:/[\w.\-]+)*$")
_GH_FOLDER_RE = re.compile(r"^[\w.\- ]*(?:/[\w.\- ]*)*$")


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


class GitHubPushRequest(BaseModel):
    """Push a job's generated files to a GitHub repository (single commit)."""

    job_id: str = Field(min_length=1, max_length=200)
    repo: str = Field(min_length=3, max_length=200)  # "owner/name"
    branch: str = Field(default="main", min_length=1, max_length=200)
    folder: str = Field(default="", max_length=300)
    files: List[str] = Field(default_factory=lambda: ["srt", "vtt"])
    message: str = Field(default="", max_length=500)
    token: str = Field(default="", max_length=500)
    bom: Optional[bool] = None  # None → job's own utf-8-sig option

    @field_validator("repo")
    @classmethod
    def validate_repo(cls, value: str) -> str:
        value = value.strip().removeprefix("https://github.com/").removesuffix(".git").strip("/")
        if not _GH_REPO_RE.match(value):
            raise ValueError("repo must look like 'owner/name'")
        return value

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, value: str) -> str:
        value = value.strip()
        if not _GH_BRANCH_RE.match(value):
            raise ValueError("branch contains unsupported characters")
        return value

    @field_validator("folder")
    @classmethod
    def validate_folder(cls, value: str) -> str:
        value = value.strip().strip("/")
        if ".." in value or not _GH_FOLDER_RE.match(value):
            raise ValueError("folder contains unsupported characters")
        return value

    @field_validator("files")
    @classmethod
    def validate_files(cls, value: List[str]) -> List[str]:
        cleaned = [f.strip().lower() for f in value if f and f.strip()]
        if not cleaned:
            raise ValueError("choose at least one file to push")
        unknown = [f for f in cleaned if f not in _PUSHABLE_FILES]
        if unknown:
            raise ValueError(f"unsupported file(s): {', '.join(unknown)}")
        # preserve order, drop duplicates
        return list(dict.fromkeys(cleaned))

    @field_validator("token")
    @classmethod
    def strip_token(cls, value: str) -> str:
        return value.strip()


class JobCreated(BaseModel):
    job_id: str
