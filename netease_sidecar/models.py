"""Provider-neutral response models exposed by the sidecar."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NormalizedTrack(BaseModel):
    """The intentionally small shape consumed by WaveCast's sidecar adapter."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str
    artist: str
    duration_seconds: int = Field(ge=0)
    playable: bool = False
    album: str | None = None
    playback_url: str | None = None

