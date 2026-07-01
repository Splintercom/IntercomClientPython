# Intercom Python Client

Python device client that authenticates via OAuth2 device flow, streams camera video over WebRTC, and sends telemetry to the Intercom API.

## Tech Stack

- **Python 3.14+**, **uv**
- **aiortc** (WebRTC), **OpenCV** (camera capture), **websockets** (signaling), **requests** (HTTP)

## Development

```bash
# From the repo root (recommended)
docker compose up -d clientpython

# Logs
docker compose logs -f clientpython

# Rebuild after code changes
docker compose up -d --build clientpython
```

Requires `/dev/video0` on the host (mapped into the container). Tokens and OAuth config are shared with the `utility` service via Docker volumes.

## Camera Architecture

A single `SharedCameraSource` opens `cv2.VideoCapture` once and fans frames to per-viewer `asyncio.Queue`s. Each `CameraVideoStreamTrack` subscribes with a unique viewer key. This supports multiple simultaneous viewers without attempting to re-open the device. The camera is released when all viewers disconnect, and re-opened on the next connection.

## CI/CD

Push to `master` triggers two workflows:

**`build-docker.yml`** — builds and pushes `docker.kmanning.ie:5000/intercom-python-client:{latest,sha,version}` (ARM runner)

**`build-deb.yml`** — runs pytest, then builds a native ARM64 binary with Nuitka and packages it as a `.deb` for Raspberry Pi installation. Uploads the artifact with 30-day retention.

Both workflows send a structured event to Honeycomb (`github-actions` dataset) at job completion — requires `HONEYCOMB_API_KEY` GitHub secret.

## Installation on Raspberry Pi (from .deb)

```bash
sudo dpkg -i intercom-client_<version>_arm64.deb

# Configure
sudo nano /etc/intercom-client/env

# Enable and start
sudo systemctl enable --now intercom-client
```
