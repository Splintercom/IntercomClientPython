import asyncio
import json
import logging
import signal
from datetime import datetime, timedelta, UTC

import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription

from intercomclient.config import Config
from intercomclient.token_store import TokenStore, TokenStatus
from intercomclient.device_authorization import (
    initiate_device_authorization,
    poll_for_token,
    refresh_tokens,
)
from intercomclient.camera_video_stream_track import CameraVideoStreamTrack

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("pi-client")


class PiClient:
    def __init__(self, config: Config):
        self.config = config
        self.token_store = TokenStore(config)
        self.pc: RTCPeerConnection | None = None
        self.ws = None
        self.running = True

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

        refresh_response = refresh_tokens(
            self.config,
            tokens["refresh"]["token_value"],
        )

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

    async def setup_peer_connection(self):
        self.pc = RTCPeerConnection()

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            LOG.info("WebRTC state: %s", self.pc.connectionState)
            if self.pc.connectionState in ("failed", "closed"):
                await self.shutdown()

        camera_track = CameraVideoStreamTrack(self.config)
        self.pc.addTrack(camera_track)

    async def signaling_loop(self):
        token_store = self.token_store.load_tokens()
        access_token = token_store["access"]["token_value"]
        device_code = token_store["device_code"]

        headers = {"Authorization": f"Bearer {access_token}"}

        websocket_url = f"{self.config.websocket_api_base_url}/{device_code}/"

        async with websockets.connect(
            websocket_url,
            additional_headers=headers,
        ) as ws:
            self.ws = ws
            LOG.info("Connected to signaling server")

            await self.setup_peer_connection()

            # Create offer
            # offer = await self.pc.createOffer()
            # await self.pc.setLocalDescription(offer)

            # await ws.send(
            #     json.dumps(
            #         {
            #             "type": "offer",
            #             "sdp": self.pc.localDescription.sdp,
            #         }
            #     )
            # )

            async for message in ws:
                data = json.loads(message)
                print(f"Received message: {data}")

                if data["type"] == "offer":
                    try:
                        await self.pc.setRemoteDescription(
                            RTCSessionDescription(
                                sdp=data["sdp"],
                                type=data["type"],
                            )
                        )
                        print("Remote description set successfully")
                    except Exception as e:
                        print("setRemoteDescription failed:", e)
                        raise

                    camera_track = CameraVideoStreamTrack(self.config)
                    await self.pc.addTrack(camera_track)

                    print("Sending answer...")
                    answer = await self.pc.createAnswer()
                    await self.pc.setLocalDescription(answer)
                    await self.ws.send_json(
                        {
                            "type": self.pc.localDescription.type,
                            "sdp": self.pc.localDescription.sdp,
                        }
                    )

                elif data["type"] == "ice":
                    await self.pc.addIceCandidate(data["candidate"])

    # =========================
    # Lifecycle
    # =========================

    async def run(self):
        while self.running:
            try:
                await self.ensure_valid_tokens()
                await self.signaling_loop()
            except Exception as e:
                LOG.exception("Client error: %s", e)
                await asyncio.sleep(5)

    async def shutdown(self):
        LOG.info("Shutting down client...")
        self.running = False

        if self.pc:
            await self.pc.close()

        if self.ws:
            await self.ws.close()


# =========================
# Entrypoint
# =========================


async def main():
    config = Config()
    client = PiClient(config)

    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(client.shutdown()))

    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
