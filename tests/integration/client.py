import os

os.environ["QT_QPA_PLATFORM"] = "xcb"

import asyncio
import json

import cv2
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription

from intercomclient.config import Config
from intercomclient.token_store import TokenStore


class TestClient:
    def __init__(self):
        self.pc = RTCPeerConnection()
        self.pc.addTransceiver("video", direction="recvonly")
        self.config = Config()
        self.output_dir = "/tmp/intercom_client_testing/frames/"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        self.device_code = TokenStore(self.config, verify=False).load_tokens()[
            "device_code"
        ]
        self.access_token = TokenStore(self.config, verify=False).load_tokens()[
            "access"
        ]["token_value"]
        self.websocket_api_url = (
            f"{self.config.websocket_api_base_url}/{self.device_code}/"
        )
        self.remote_video = None

    async def show_frame(self, frame):
        await asyncio.to_thread(cv2.imshow, "Remote CCTV Feed", frame)

    async def display_remote_video(self):
        print("Displaying remote video track...")
        track = self.remote_video
        self.frame_count = 0
        while True:
            track = self.remote_video
            if track is None:
                await asyncio.sleep(1)
                print("Waiting for remote video track to be available...")
                continue
            print("Waiting for video frame...")
            frame = await track.recv()  # receive an AV frame
            print("Video frame received, converting to OpenCV format...")
            img = frame.to_ndarray(format="bgr24")  # convert to OpenCV format
            print("Displaying video frame...")
            frame_path = os.path.join(self.output_dir, "frame.jpg")
            if self.frame_count % 3 == 0:  # every 3rd frame
                cv2.imwrite(frame_path, img)
            self.frame_count += 1

    async def test_frame(self):
        @self.pc.on("track")
        async def on_track(track):
            print("Track received:", track.kind)

            if track.kind == "video":
                self.remote_video = track

        additional_headers = {"Authorization": f"Bearer {self.access_token}"}
        async with websockets.connect(
            self.websocket_api_url, additional_headers=additional_headers
        ) as ws:
            # Create offer
            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)

            await ws.send(
                json.dumps({"type": "offer", "sdp": self.pc.localDescription.sdp})
            )

            # Wait for answer from server
            async for message in ws:
                print(f"Test client - Received message: {message}")
                data = json.loads(message)
                if data["type"] == "answer":
                    await self.pc.setRemoteDescription(
                        RTCSessionDescription(sdp=data["sdp"], type="answer")
                    )
                elif data["type"] == "ice":
                    await self.pc.addIceCandidate(data["candidate"])
            print("WebRTC handshake done!")

            # Keep the event loop alive until frame is received
            await asyncio.sleep(5)


async def main():
    test_client = TestClient()

    signaling_task = asyncio.create_task(test_client.test_frame())
    display_task = asyncio.create_task(test_client.display_remote_video())

    await asyncio.gather(signaling_task, display_task)


asyncio.run(main())
