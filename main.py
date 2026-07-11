import asyncio
import json
import logging
import signal
from datetime import UTC, datetime, timedelta

import websockets
from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.sdp import candidate_from_sdp
from requests import HTTPError

from splintercomclient.camera_video_stream_track import (
    CameraVideoStreamTrack,
    SharedCameraSource,
)
from splintercomclient.config import Config
from splintercomclient.device_authorization import (
    initiate_device_authorization,
    poll_for_token,
    refresh_tokens,
)
from splintercomclient.otel import setup_telemetry
from splintercomclient.telemetry import TelemetryClient
from splintercomclient.token_store import TokenStatus, TokenStore
from splintercomclient.turn import fetch_turn_credentials

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("pi-client")


class PiClient:
    def __init__(self, config: Config):
        self.config = config
        self.token_store = TokenStore(config)
        self.telemetry = TelemetryClient(config, self.token_store)
        self.peer_connections: dict[str, RTCPeerConnection] = {}
        self.camera_tracks: dict[str, CameraVideoStreamTrack] = {}
        self._camera_source: SharedCameraSource | None = None
        self.pc = None
        self.ws = None
        self.running = True
        self.turn_credentials: dict | None = None

    # =========================
    # Token Management
    # =========================

    def check_token_status(self, tokens) -> TokenStatus:
        try:
            if tokens["access"]["token_value"] is None:
                return TokenStatus.MISSING
        except KeyError:
            return TokenStatus.MISSING

        if tokens["access"]["expiry_time"] < datetime.now(tz=UTC).timestamp():
            return TokenStatus.EXPIRED

        return TokenStatus.VALID

    async def ensure_valid_tokens(self):
        tokens = self.token_store.load_tokens()
        status = self.check_token_status(tokens)

        if status == TokenStatus.MISSING:
            LOG.info("No tokens found. Starting device authorization flow.")
            await asyncio.to_thread(self.device_authorization_flow)

        elif status == TokenStatus.EXPIRED:
            LOG.info("Access token expired. Attempting refresh.")
            await asyncio.to_thread(self.refresh_flow)

        else:
            expiry = datetime.fromtimestamp(tokens["access"]["expiry_time"], tz=UTC)
            LOG.info(
                "Access token valid, expires in %s",
                expiry - datetime.now(tz=UTC),
            )

    def device_authorization_flow(self):
        auth_response = initiate_device_authorization(self.config)
        print(auth_response)
        LOG.info("User code: %s", auth_response["user_code"])

        token_response = poll_for_token(
            self.config,
            auth_response["device_code"],
            interval=auth_response["interval"],
        )

        print(token_response)

        expiry = (
            datetime.now(tz=UTC) + timedelta(seconds=token_response["expires_in"])
        ).timestamp()

        self.token_store.store_tokens(
            {
                "access_token": token_response["access_token"],
                "refresh_token": token_response["refresh_token"],
            },
            device_code=auth_response["device_code"],
            access_token_expiry=expiry,
        )

    def refresh_flow(self):
        tokens = self.token_store.load_tokens()

        try:
            refresh_response = refresh_tokens(
                self.config,
                tokens["refresh"]["token_value"],
            )

        except HTTPError as e:
            LOG.error("Token refresh failed: %s", e)
            print(refresh_response)

        expiry = (
            datetime.now(tz=UTC) + timedelta(seconds=refresh_response["expires_in"])
        ).timestamp()

        self.token_store.store_tokens(
            {
                "access_token": refresh_response["access_token"],
                "refresh_token": refresh_response["refresh_token"],
            },
            access_token_expiry=expiry,
        )

    # =========================
    # WebRTC + Signaling
    # =========================

    def _build_ice_servers(self) -> list[RTCIceServer]:
        servers = [
            RTCIceServer(urls="stun:stun.l.google.com:19302"),
            RTCIceServer(urls="stun:stun1.l.google.com:19302"),
        ]
        creds = self.turn_credentials or {}
        turn_url = creds.get("url") or self.config.turn_url
        turn_username = creds.get("username") or self.config.turn_username
        turn_credential = creds.get("credential") or self.config.turn_credential
        if turn_url and turn_username and turn_credential:
            servers.append(
                RTCIceServer(
                    urls=turn_url,
                    username=turn_username,
                    credential=turn_credential,
                )
            )
        return servers

    def _get_or_create_camera_source(self) -> SharedCameraSource:
        if self._camera_source is None or not self._camera_source.capture.isOpened():
            self._camera_source = SharedCameraSource(self.config)
            self._camera_source.start()
        return self._camera_source

    async def _release_camera_if_idle(self) -> None:
        if not self.peer_connections and self._camera_source is not None:
            await self._camera_source.stop()
            self._camera_source = None

    async def setup_peer_connection(self, viewer_channel: str) -> RTCPeerConnection:
        old_track = self.camera_tracks.pop(viewer_channel, None)
        if old_track:
            old_track.stop()
        old_pc = self.peer_connections.pop(viewer_channel, None)
        if old_pc:
            await old_pc.close()

        pc = RTCPeerConnection(
            configuration=RTCConfiguration(iceServers=self._build_ice_servers())
        )
        self.peer_connections[viewer_channel] = pc

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if self.peer_connections.get(viewer_channel) is not pc:
                return
            state = pc.connectionState
            LOG.info("WebRTC state for %s: %s", viewer_channel, state)
            if state == "connected":
                await asyncio.to_thread(self.telemetry.send, "streaming")
            elif state == "failed":
                await asyncio.to_thread(
                    self.telemetry.send, "error", "WebRTC connection failed", "WARNING"
                )
                await self.setup_peer_connection(viewer_channel)
                self._register_ice_handler(viewer_channel)

        return pc

    def _register_ice_handler(self, viewer_channel: str):
        pc = self.peer_connections[viewer_channel]

        @pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if self.peer_connections.get(viewer_channel) is not pc:
                return
            if candidate is not None:
                LOG.info(
                    "ICE candidate generated for %s: %s", viewer_channel, candidate
                )
                await self.ws.send(
                    json.dumps(
                        {
                            "type": "candidate",
                            "candidate": candidate.candidate,
                            "sdpMid": candidate.sdpMid,
                            "sdpMLineIndex": candidate.sdpMLineIndex,
                            "viewer_channel": viewer_channel,
                        }
                    )
                )

    async def signaling_loop(self):
        token_store = self.token_store.load_tokens()
        access_token = token_store["access"]["token_value"]
        device_code = token_store["device_code"]

        self.turn_credentials = await asyncio.to_thread(
            fetch_turn_credentials, self.config.http_api_base_url, access_token
        )

        headers = {"Authorization": f"Bearer {access_token}"}

        base = self.config.websocket_api_base_url.rstrip("/")
        if "/ws/live_stream" not in base:
            base = f"{base}/ws/live_stream"
        websocket_url = f"{base}/{device_code}/"

        async with websockets.connect(
            websocket_url,
            additional_headers=headers,
        ) as ws:
            self.ws = ws
            LOG.info("Connected to signaling server")
            await asyncio.to_thread(self.telemetry.send, "connected")

            async for message in ws:
                data = json.loads(message)
                LOG.info("Received message: %s", data)

                if data["type"] == "offer":
                    viewer_channel = data.get("viewer_channel", "")
                    pc = await self.setup_peer_connection(viewer_channel)
                    self._register_ice_handler(viewer_channel)

                    await pc.setRemoteDescription(
                        RTCSessionDescription(
                            sdp=data["sdp"],
                            type="offer",
                        )
                    )

                    try:
                        camera_source = self._get_or_create_camera_source()
                        camera_track = CameraVideoStreamTrack(
                            camera_source, viewer_channel
                        )
                        self.camera_tracks[viewer_channel] = camera_track
                        pc.addTrack(camera_track)
                        LOG.info("Camera track added for viewer %s", viewer_channel)
                    except Exception as e:
                        LOG.warning(
                            "Camera unavailable (%s), sending answer without video", e
                        )
                        await asyncio.to_thread(
                            self.telemetry.send, "error", str(e), "WARNING"
                        )

                    answer = await pc.createAnswer()
                    await pc.setLocalDescription(answer)
                    await self.ws.send(
                        json.dumps(
                            {
                                "type": pc.localDescription.type,
                                "sdp": pc.localDescription.sdp,
                                "viewer_channel": viewer_channel,
                            }
                        )
                    )
                    LOG.info("Answer sent to viewer %s", viewer_channel)

                elif data["type"] in ("ice", "candidate") and data.get("candidate"):
                    viewer_channel = data.get("viewer_channel", "")
                    pc = self.peer_connections.get(viewer_channel)
                    if not pc:
                        LOG.warning(
                            "Received candidate for unknown viewer %s", viewer_channel
                        )
                        continue
                    sdp_str = data["candidate"]
                    if sdp_str.startswith("candidate:"):
                        sdp_str = sdp_str[len("candidate:") :]
                    ice_candidate = candidate_from_sdp(sdp_str)
                    ice_candidate.sdpMid = data.get("sdpMid")
                    ice_candidate.sdpMLineIndex = data.get("sdpMLineIndex")
                    await pc.addIceCandidate(ice_candidate)

                elif (
                    data["type"] == "status"
                    and data.get("event") == "peer_disconnected"
                    and data.get("peer_type") != "device"
                ):
                    viewer_channel = data.get("viewer_channel", "")
                    track = self.camera_tracks.pop(viewer_channel, None)
                    if track:
                        track.stop()
                    pc = self.peer_connections.pop(viewer_channel, None)
                    if pc:
                        await pc.close()
                    LOG.info("Viewer %s disconnected", viewer_channel)
                    await asyncio.to_thread(
                        self.telemetry.send, "disconnected", "Viewer disconnected"
                    )
                    await self._release_camera_if_idle()
                    if not self.peer_connections:
                        await asyncio.to_thread(self.telemetry.send, "connected")

    async def _cleanup_connections(self):
        for vc in list(self.peer_connections.keys()):
            track = self.camera_tracks.pop(vc, None)
            if track:
                track.stop()
            pc = self.peer_connections.pop(vc, None)
            if pc:
                await pc.close()
        if self._camera_source is not None:
            await self._camera_source.stop()
            self._camera_source = None

    # =========================
    # Lifecycle
    # =========================

    async def _heartbeat_loop(self):
        while self.running:
            await asyncio.sleep(30)
            await asyncio.to_thread(self.telemetry.send, "heartbeat")

    async def run(self):
        asyncio.create_task(self._heartbeat_loop())
        while self.running:
            try:
                await self.ensure_valid_tokens()
                await self.signaling_loop()
            except Exception as e:
                LOG.exception("Client error: %s", e)
                await asyncio.to_thread(self.telemetry.send, "error", str(e), "ERROR")
            finally:
                await self._cleanup_connections()
            if self.running:
                await asyncio.sleep(5)

    async def shutdown(self):
        LOG.info("Shutting down client...")
        self.running = False
        await asyncio.to_thread(
            self.telemetry.send, "disconnected", "Client shutting down"
        )

        await self._cleanup_connections()

        if self.pc:
            await self.pc.close()

        if self.ws:
            await self.ws.close()


# =========================
# Entrypoint
# =========================


async def main():
    setup_telemetry("splintercom-pi-client")
    config = Config()
    client = PiClient(config)

    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(client.shutdown()))

    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
