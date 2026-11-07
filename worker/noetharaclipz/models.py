import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Edit(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    version: Literal[1] = 1
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    ratio: Literal["9:16", "16:9", "1:1", "4:5"] = "9:16"
    crop_x: float = Field(default=0.5, ge=0, le=1)
    crop_y: float = Field(default=0.5, ge=0, le=1)
    volume: float = Field(default=1, ge=0, le=2)
    captions: bool = True
    caption_style: Literal["Bold pop", "Karaoke", "Minimal", "Neon"] = "Bold pop"
    caption_size: int = Field(default=28, ge=16, le=72)
    caption_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9a-fA-F]{6}$")
    caption_overrides: dict[str, str] = Field(default_factory=dict)
    font: Literal["Bricolage Grotesque", "Instrument Sans", "Mono"] = "Instrument Sans"

    @model_validator(mode="after")
    def bounds(self):
        if not 0 < self.end - self.start <= 60:
            raise ValueError("Clip must be 0–60 seconds")
        if any(len(v) > 500 for v in self.caption_overrides.values()):
            raise ValueError("Caption too long")
        return self


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    category: Literal["Clutch", "Funny", "Hype", "Reaction", "Tutorial", "Other"]
    score: int = Field(ge=0, le=100)
    explanation: str = Field(min_length=1, max_length=2000)
    visual_evidence: str = Field(min_length=1, max_length=2000)


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(max_length=4000)
    highlights: list[Candidate] = Field(max_length=12)


def rank_candidates(candidates, duration):
    """Reject invalid timestamps, then suppress substantial duplicate intervals."""
    selected = []
    for c in sorted(candidates, key=lambda c: c.score, reverse=True):
        if not (
            math.isfinite(c.start)
            and math.isfinite(c.end)
            and 0 <= c.start < c.end <= duration
            and c.end - c.start <= 60
        ):
            continue
        if any(
            max(0, min(c.end, x.end) - max(c.start, x.start))
            / min(c.end - c.start, x.end - x.start)
            > 0.6
            for x in selected
        ):
            continue
        selected.append(c)
    return selected[:5]
