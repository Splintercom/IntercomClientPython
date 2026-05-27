# Intercom ClientPython

A Python client that streams video from a camera to a remote receiver (intercom/monitor) using WebRTC, authenticated via OAuth 2.0 Device Authorization Grant.

## Architecture

### Authentication (`intercomclient/device_authorization.py` + `intercomclient/token_store.py`)
- **OAuth 2.0 Device Code Grant** (`urn:ietf:params:oauth:grant-type:device_code`)
- `initiate_device_authorization()` — POSTs to `/oauth/device-authorization/` with device type/OS, receives `device_code` + `user_code` for user approval
- `poll_for_token()` — Polls `/oauth/token/` with the device code until user approves (times out after 5 minutes)
- `refresh_tokens()` — Refreshes access token using stored refresh token
- `TokenStore` — Securely stores access/refresh tokens to a JSON file (permissions `0600`) at `~/.config/intercomclient/tokens.json`

### WebRTC Signaling (`main.py` — `PiClient`)
- Connects to WebSocket signaling server at `{WEBSOCKET_API_BASE_URL}/ws/live_stream/{device_code}/`
- Authenticates with Bearer token header
- **Signaling loop** handles:
  - `offer` — Sets remote SDP, creates `CameraVideoStreamTrack`, generates SDP answer, sends it back
  - `ice` — Receives ICE candidates from remote peer via signaling server
  - `icecandidate` events — Sends locally-generated ICE candidates back through signaling server
- Handles connection lifecycle: shutdown on `failed`/`closed`, retry on errors with 5s backoff

### Video Capture (`intercomclient/camera_video_stream_track.py`)
- `CameraVideoStreamTrack` extends `aiortc.VideoStreamTrack`
- Uses OpenCV (`cv2.VideoCapture`) to capture frames from camera source (default device `0`)
- Converts frames to `av.VideoFrame` (BGR24 format) with proper PTS/time_base timestamps
- Retries silently on capture failure

### Configuration (`intercomclient/config.py`)
- All configurable via environment variables: `HTTP_API_BASE_URL`, `WEBSOCKET_API_BASE_URL`, `VIDEO_SOURCE`, `TOKEN_FILE_PATH`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`
- OAuth credentials can come from `~/.config/intercom-api/oauth.json` or env vars
- Defaults: 320×240 resolution, 5 fps, XVID codec

### Entry Point (`main.py` → `main()`)
- Creates `PiClient`, registers SIGINT/SIGTERM handlers, runs client in a loop ensuring valid tokens and maintaining the WebRTC connection

## `.envrc`

**Never modify `.envrc`.** It contains local-only developer environment config (API URLs, credentials, etc.) and must always reflect the developer's own setup. It is not part of the shared codebase and should never be changed by Claude.
