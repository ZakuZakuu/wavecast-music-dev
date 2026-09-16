"""Conservative normalization from NetEase-compatible payloads."""

from __future__ import annotations

import math
from typing import Any

from .models import NormalizedTrack


def normalize_search(payload: dict[str, Any]) -> list[NormalizedTrack]:
    return [track for item in track_items(payload) if (track := normalize_track(item)) is not None]


def normalize_track_payload(payload: dict[str, Any]) -> NormalizedTrack | None:
    items = track_items(payload)
    return normalize_track(items[0]) if items else None


def playback_url(payload: dict[str, Any]) -> str | None:
    """Return only a URL the upstream explicitly supplied; never manufacture one."""

    for item in _playback_items(payload):
        value = _string(item.get("playback_url") or item.get("stream_url") or item.get("url"))
        if value:
            return value
    return None


def track_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Find track arrays in common NetEase-compatible response envelopes."""

    for key in ("result", "data", "tracks", "results", "songs"):
        value = payload.get(key)
        if isinstance(value, dict):
            nested = _track_list(value)
            if nested:
                return nested
        elif isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if _looks_like_track(payload):
        return [payload]
    return []


def normalize_track(item: dict[str, Any]) -> NormalizedTrack | None:
    track_id = _identifier(item.get("id") or item.get("track_id") or item.get("track_ref"))
    title = _string(item.get("title") or item.get("name"))
    artist = _artist(item)
    if not track_id or not title or not artist:
        return None

    duration_seconds = _duration_seconds(item)
    url = _string(item.get("playback_url") or item.get("stream_url") or item.get("url"))
    explicit_playable = item.get("playable")
    playable = bool(explicit_playable) if isinstance(explicit_playable, bool) else bool(url)
    return NormalizedTrack(
        id=track_id,
        title=title,
        artist=artist,
        duration_seconds=duration_seconds,
        playable=playable,
        album=_album(item),
        playback_url=url,
    )


def _track_list(value: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("songs", "tracks", "results", "data"):
        nested = value.get(key)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        if isinstance(nested, dict) and _looks_like_track(nested):
            return [nested]
    return [value] if _looks_like_track(value) else []


def _playback_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if any(key in payload for key in ("url", "playback_url", "stream_url")):
        return [payload]
    for key in ("data", "result", "results", "tracks"):
        value = payload.get(key)
        if isinstance(value, dict):
            return _playback_items(value)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _looks_like_track(value: dict[str, Any]) -> bool:
    has_id = bool(_identifier(value.get("id") or value.get("track_id") or value.get("track_ref")))
    return has_id and bool(_string(value.get("name") or value.get("title")))


def _artist(item: dict[str, Any]) -> str | None:
    direct = _string(item.get("artist"))
    if direct:
        return direct
    for key in ("ar", "artists"):
        value = item.get(key)
        if isinstance(value, list):
            names = [
                _string(entry.get("name") if isinstance(entry, dict) else entry) for entry in value
            ]
            joined = ", ".join(name for name in names if name)
            if joined:
                return joined
        if isinstance(value, dict):
            direct = _string(value.get("name") or value.get("artist"))
            if direct:
                return direct
    return None


def _album(item: dict[str, Any]) -> str | None:
    value = item.get("album") or item.get("al")
    if isinstance(value, dict):
        return _string(value.get("name") or value.get("title"))
    return _string(value)


def _duration_seconds(item: dict[str, Any]) -> int:
    if item.get("duration_seconds") is not None:
        return _whole_seconds(item.get("duration_seconds"))
    for key in ("duration_ms", "dt"):
        if item.get(key) is not None:
            return _milliseconds(item.get(key))
    value = item.get("duration")
    if isinstance(value, (int, float, str)):
        number = _number(value)
        if number is not None:
            return _milliseconds(number) if number > 1000 else max(0, round(number))
    return 0


def _milliseconds(value: object) -> int:
    number = _number(value)
    return max(0, round(number / 1000)) if number is not None else 0


def _whole_seconds(value: object) -> int:
    number = _number(value)
    return max(0, round(number)) if number is not None else 0


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def _string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _identifier(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    return _string(value)
