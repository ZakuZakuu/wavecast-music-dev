# WaveCast music-dev NetEase sidecar

This is a temporary local development service for testing WaveCast's provider
boundary with NetEase-compatible catalog data. It is intentionally separate
from the WaveCast repository and does not vendor an upstream implementation.

The data path is:

```text
WaveCast (:8000) -> this sidecar (:3101) -> local NetEase-compatible upstream (:3000)
```

The sidecar owns the upstream HTTP adapter and deterministic normalization. It
does not contain WaveCast intelligence, recommendation logic, credentials, or
an audio proxy. It only returns a URL when the upstream explicitly returns a
lawfully playable/preview asset; it never manufactures a URL or bypasses DRM,
paywalls, login, region restrictions, or subscriptions.

## Local startup

### 1. Start the canonical NetEase-compatible upstream

WaveCast's current canonical development/deployment upstream is
[NeteaseCloudMusicApiEnhanced/api-enhanced](https://github.com/NeteaseCloudMusicApiEnhanced/api-enhanced),
pinned by `Dockerfile.upstream` to commit
`a8c781fd64faab17fedfd46e0615a2609307f163` (v4.40.1). Railway's
`netease-upstream` service builds this same Dockerfile, so local validation
should prefer it over cloning a different NetEase API implementation.

```bash
docker build -f Dockerfile.upstream -t wavecast-netease-upstream .
docker run --rm -p 3000:3000 wavecast-netease-upstream
```

When parity with a deployed environment matters, mirror that environment's
upstream variables (for example `ENABLE_RANDOM_CN_IP`,
`ENABLE_GENERAL_UNBLOCK`, and `ENABLE_FLAC`) rather than inventing new
credentials.

#### Known cold-start bootstrap log

The pinned upstream bootstraps its own anonymous device state and XEAPI
encryption state. `xeapi public key` is **not** a WaveCast credential or a
developer secret and should not be manually supplied.

At this pinned commit, cold startup can log:

```text
Generated Random Chinese IP: ...
Successfully registered anonimous token, deviceId: ...
Error: xeapi public key is missing
```

This message is expected from the upstream's bootstrap ordering: the first
anonymous registration attempt uses XEAPI before `generateConfig()` has
finished fetching and caching the XEAPI public-key state. The error is caught;
the process then fetches the key automatically and continues startup. A healthy
boot proceeds to:

```text
Server started successfully @ http://localhost:3000
```

Do **not** treat the single `xeapi public key is missing` line as proof that
the process exited, and do not add a login, cookie, or hand-written XEAPI key
just to suppress it. If port 3000 is not listening, capture the complete log
after that line plus the actual process exit code; the fatal cause is elsewhere.

Also note that `Generated Random Chinese IP` is printed because the pinned
upstream always creates a candidate Chinese IP during `generateConfig()`.
That log alone does not prove `ENABLE_RANDOM_CN_IP=true`; the environment
variable controls whether requests default to using that generated IP.

### 2. Start this sidecar

```bash
cp .env.example .env
uv run --env-file .env uvicorn netease_sidecar.app:app --host 127.0.0.1 --port 3101
```

### 3. Point WaveCast at the sidecar

In WaveCast's `.env` use:

```dotenv
NETEASE_MUSIC_API_BASE_URL=http://127.0.0.1:3101
```

No NetEase credential belongs in WaveCast. If the chosen upstream needs a
cookie or login for a separate development scenario, keep that configuration
in the upstream's own environment and follow its terms. The sidecar does not
print or forward such credentials to browser clients.

For a remotely hosted upstream, prefer a private network or HTTPS reverse proxy.
If that proxy requires `Authorization: Bearer <token>`, set
`NETEASE_UPSTREAM_BEARER_TOKEN` on the sidecar. The token is sent only on
sidecar -> upstream requests and is never returned by WaveCast-facing endpoints
or included in safe error messages.

## Endpoints

- `GET /health`
- `GET /ready` -> performs one bounded, metadata-only upstream catalog probe;
  returns 200 only when the configured upstream catalog path responds. `/health`
  remains process liveness and never contacts the upstream. Readiness failures
  return a safe 502/504 response without upstream payloads or credentials.
- `GET /search?query=<text>&limit=<n>` -> `{ "tracks": [...] }`
- `GET /tracks/{id}` -> one normalized track
- `GET /tracks/{id}/timing` -> duration plus timestamp-only lyric/vocal intervals; lyric text is never exposed
- `GET /tracks/{id}/playback` -> `{ "data": { "playback_url": ... }, "playable": ... }`

The upstream adapter uses the conventional `/cloudsearch`, `/song/detail`,
`/song/url/v1`, and optional `/lyric` endpoints. Timing enrichment is
best-effort: if lyrics are unavailable, the sidecar still returns duration-only
timing metadata. Raw lyric text is intentionally discarded at this boundary.
Replacing the local upstream should only require a narrow adapter change in
`netease_sidecar/upstream.py` and, if needed, a normalizer adjustment. Generic
WaveCast fields stay provider-neutral.

## Validation

```bash
uv run pytest
uv run ruff check .
uv run mypy
```

The test suite uses mocked HTTP only. No live NetEase, DeepSeek, Exa, Tavily,
MiniMax, or full-episode probe is run by this project. Fujii Kaze examples in
fixtures (`藤井風`, `何なんw`, `死ぬのがいいわ`) are data-only cases; whether a
real upstream resolves them and provides playback depends on that separately
running service and is not assumed by CI.

This sidecar is a development seam, not the final production music provider.
If WaveCast later gains a first-party TME/QQ integration, the intended
follow-up is a replaceable `TmeMusicProvider`; this project may then become
unused.
