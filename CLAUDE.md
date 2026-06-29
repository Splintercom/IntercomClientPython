# Intercom ClientPython

Python device client that streams video from a camera to a remote viewer (browser) using WebRTC, authenticated via OAuth 2.0 Device Authorization Grant, with continuous telemetry reporting.

## Tech Stack

- **Python 3.14+** with **uv** package manager
- **aiortc** — WebRTC peer connection and media streaming
- **aioice** — ICE candidate handling (used internally by aiortc; `candidate_from_sdp` from `aiortc.sdp` parses ICE SDP strings)
- **OpenCV (cv2)** — Camera capture
- **websockets** — WebSocket signaling client
- **requests** — HTTP API calls for OAuth flow and telemetry

## Project Structure

```
ClientPython/
├── main.py                      # PiClient entry point
├── intercomclient/
│   ├── config.py                # Config dataclass (env vars)
│   ├── device_authorization.py  # OAuth device flow functions
│   ├── token_store.py           # Token persistence (JSON file, 0600 perms)
│   ├── camera_video_stream_track.py  # WebRTC video track (OpenCV capture)
│   └── telemetry.py             # TelemetryClient — posts events to API
├── pyproject.toml               # uv dependencies
└── Dockerfile.dev               # Dev image (bookworm-slim + OpenCV deps)
```

## Architecture

### Authentication (`intercomclient/device_authorization.py` + `intercomclient/token_store.py`)
- **OAuth 2.0 Device Code Grant** (`urn:ietf:params:oauth:grant-type:device_code`)
- `initiate_device_authorization()` — POSTs to `/oauth/device-authorization/` with device type/OS
- `poll_for_token()` — Polls `/oauth/token/` with device code until approved (timeout configurable via `MAX_POLLING_TIME_MINS`, default 5 min)
- `refresh_tokens()` — Refreshes access token using stored refresh token
- `TokenStore` — Stores access/refresh tokens + `device_code` to JSON file (permissions `0600`) at `~/.config/intercomclient/tokens.json`

### WebRTC Signaling (`main.py` — `PiClient`)
- Connects to WebSocket signaling server at `{WEBSOCKET_API_BASE_URL}/ws/live_stream/{device_code}/`
- Authenticates with OAuth2 Bearer token in `Authorization` header
- **Signaling loop** handles:
  - `offer` (from viewer) — Sets remote SDP, creates `CameraVideoStreamTrack`, generates SDP answer, sends it back
  - `candidate` — Receives ICE candidates; parsed with `candidate_from_sdp()` from `aiortc.sdp` (strips `candidate:` prefix; sets `sdpMid`/`sdpMLineIndex` manually as they are top-level message fields, not part of the SDP string)
  - `status` with `event: "peer_disconnected"` and `peer_type != "device"` — viewer disconnected; resets RTCPeerConnection in-place (signaling WS stays open) ready for the next offer
  - `icecandidate` events (local) — Sends locally-generated ICE candidates back through signaling server
- On WebRTC `connectionState == "connected"`, fires a `streaming` telemetry event
- On WebRTC `connectionState == "failed"`, fires an `error` telemetry event then resets the PC

### PC Lifecycle (`setup_peer_connection`)
- Nulls out `self.pc` **before** closing the old one — prevents stale `connectionstatechange` events from the closing PC from affecting the new connection
- Uses `if pc is not self.pc: return` guard in all event handlers to discard events from replaced PCs
- Signaling WebSocket is **never** closed by WebRTC state changes — only by unrecoverable signaling errors

### Video Capture (`intercomclient/camera_video_stream_track.py`)
- `CameraVideoStreamTrack` extends `aiortc.VideoStreamTrack`
- Uses `cv2.VideoCapture` to capture frames from camera source (default device `0`, configurable via `VIDEO_SOURCE`)
- Converts frames to `av.VideoFrame` (BGR24 format) with proper PTS/time_base timestamps
- `recv()` loops until a frame is captured (no recursion)
- `stop()` releases `VideoCapture` to avoid device handle leaks when the PC is replaced

### Telemetry (`intercomclient/telemetry.py` — `TelemetryClient`)
- `send(event, message="", level="INFO")` — synchronous; called via `asyncio.to_thread` from async contexts
- Reads the current access token and `device_code` from `TokenStore` on each call
- POSTs to `POST /api/v1/devices/{device_code}/telemetry/` with `Authorization: Bearer <token>`
- Failures are logged at DEBUG and silently ignored — telemetry never disrupts the signaling loop

**Events sent automatically:**

| Event | When |
|---|---|
| `connected` | Immediately after signaling WS connects and first PC is set up |
| `streaming` | WebRTC `connectionState` transitions to `"connected"` |
| `disconnected` | Viewer disconnects (`peer_disconnected` status message) |
| `connected` | After PC reset following viewer disconnect (ready for next viewer) |
| `error` (WARNING) | Camera unavailable when adding track |
| `error` (WARNING) | WebRTC `connectionState` transitions to `"failed"` |
| `error` (ERROR) | Exception propagates out of `signaling_loop` |
| `disconnected` | `shutdown()` called (SIGINT/SIGTERM) |
| `heartbeat` | Every 30 seconds from background `_heartbeat_loop` task |

### Configuration (`intercomclient/config.py`)
- All configurable via environment variables:
  - `HTTP_API_BASE_URL` — Backend API URL (default: `http://backend:8000`)
  - `WEBSOCKET_API_BASE_URL` — WebSocket URL (default: `ws://backend:8000`)
  - `VIDEO_SOURCE` — Camera device index (default: `0`)
  - `TOKEN_FILE_PATH` — Token file path (default: `~/.config/intercomclient/tokens.json`)
  - `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` — Fallback if `~/.config/intercom-api/oauth.json` not found
  - `MAX_POLLING_TIME_MINS` — Device auth polling timeout (default: `5`)
- Defaults: 320×240 resolution, 5 fps

### Entry Point (`main.py` → `main()`)
- Creates `PiClient` with `TelemetryClient` attached
- Registers SIGINT/SIGTERM handlers calling `shutdown()`
- `run()` starts the 30s heartbeat background task, then loops: ensure valid tokens → connect signaling → stream; sleeps 5s and retries on error

## Docker Dev Setup

```bash
# Start (from repo root)
docker compose up -d clientpython

# View logs
docker compose logs -f clientpython

# Rebuild after code changes
docker compose up -d --build clientpython
```

### Device Access
The container mounts `/dev/video0` from the host for camera access:
```yaml
devices:
  - /dev/video0:/dev/video0
```

### Service Dependency
`clientpython` depends on `utility` (healthy) — ensures device registration and token writing complete before the client starts.

### Shared Volumes
- `device_oauth_config` — OAuth credentials from `utility` (`~/.config/intercom-api/oauth.json`)
- `client_tokens` — Token file shared with `utility` (`~/.config/intercomclient/tokens.json`)

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `HTTP_API_BASE_URL` | `http://backend:8000` | Backend API base URL |
| `WEBSOCKET_API_BASE_URL` | `ws://backend:8000` | WebSocket base URL |
| `VIDEO_SOURCE` | `0` | Camera device index |
| `TOKEN_FILE_PATH` | `~/.config/intercomclient/tokens.json` | Token storage path |
| `OAUTH_CLIENT_ID` | from `oauth.json` | OAuth client ID |
| `OAUTH_CLIENT_SECRET` | from `oauth.json` | OAuth client secret |
| `MAX_POLLING_TIME_MINS` | `5` | Device auth polling timeout |

## `.envrc`

**Never modify `.envrc`.** It contains local-only developer environment config and must always reflect the developer's own setup.
