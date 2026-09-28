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


class TimingInterval(BaseModel):
    """Timestamp-only interval; lyric text is deliberately not exposed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)


class TrackTiming(BaseModel):
    """Provider-neutral timing metadata consumed by WaveCast arrangement."""

    model_config = ConfigDict(extra="forbid")

    source_duration_seconds: int = Field(ge=0)
    lyric_timestamps_available: bool = False
    lyric_lines: list[TimingInterval] = Field(default_factory=list)
    vocal_intervals: list[TimingInterval] = Field(default_factory=list)
