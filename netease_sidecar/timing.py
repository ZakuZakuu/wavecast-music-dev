"""Timestamp-only lyric normalization for arrangement timing.

The sidecar intentionally drops lyric text. WaveCast only needs timing signals
for P0 narration placement, so lyric content never crosses this provider
boundary.
"""

from __future__ import annotations

import re
from typing import Any

from .models import TimingInterval

_TIMESTAMP = re.compile(r"\[(?P<minutes>\d{1,3}):(?P<seconds>\d{1,2}(?:\.\d{1,3})?)\]")


def normalize_lyric_timing(
    payload: dict[str, Any],
    *,
    duration_seconds: int,
) -> tuple[list[TimingInterval], list[TimingInterval]]:
    raw = _raw_lrc(payload)
    if not raw:
        return [], []

    starts = sorted(
        {
            round(minutes * 60 + seconds, 3)
            for minutes, seconds in _timestamps(raw)
            if minutes >= 0 and seconds >= 0
        }
    )
    if duration_seconds > 0:
        starts = [value for value in starts if value < duration_seconds]
    if not starts:
        return [], []

    lines: list[TimingInterval] = []
    for index, start in enumerate(starts):
        next_start = starts[index + 1] if index + 1 < len(starts) else None
        natural_end = start + 7.0
        if next_start is not None:
            end = min(natural_end, max(start, next_start - 0.15))
        elif duration_seconds > 0:
            end = min(float(duration_seconds), natural_end)
        else:
            end = natural_end
        if end <= start:
            end = start + 0.1
        lines.append(TimingInterval(start_seconds=start, end_seconds=round(end, 3)))

    return lines, _merge_vocals(lines)


def _raw_lrc(payload: dict[str, Any]) -> str | None:
    # Prefer line-level LRC. Word-level formats vary between upstreams and are
    # unnecessary for narration-safe timing windows.
    for key in ("lrc", "klyric"):
        value = payload.get(key)
        if isinstance(value, dict):
            lyric = value.get("lyric")
            if isinstance(lyric, str) and lyric.strip():
                return lyric
    lyric = payload.get("lyric")
    return lyric if isinstance(lyric, str) and lyric.strip() else None


def _timestamps(raw: str) -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    for line in raw.splitlines():
        for match in _TIMESTAMP.finditer(line):
            values.append(
                (
                    int(match.group("minutes")),
                    float(match.group("seconds")),
                )
            )
    return values


def _merge_vocals(lines: list[TimingInterval]) -> list[TimingInterval]:
    if not lines:
        return []
    merged: list[TimingInterval] = [lines[0]]
    for item in lines[1:]:
        current = merged[-1]
        if item.start_seconds - current.end_seconds <= 1.25:
            merged[-1] = TimingInterval(
                start_seconds=current.start_seconds,
                end_seconds=max(current.end_seconds, item.end_seconds),
            )
        else:
            merged.append(item)
    return merged
