import asyncio
import json
from aiortc import RTCPeerConnection, RTCSessionDescription
from intercomclient.token_store import TokenStore
from intercomclient.config import Config
import websockets


async def test_frame():
    pc = RTCPeerConnection()
    config = Config()
    device_code = TokenStore(config, verify=False).load_tokens()["device_code"]
    websocket_api_url = f"{config.websocket_api_base_url}/{device_code}/"

    # # Optionally add a dummy track if server expects one
    # class DummyTrack(VideoStreamTrack):
    #     async def recv(self):
    #         # just return None for testing
    #         return None

    # pc.addTrack(DummyTrack())

    async with websockets.connect(websocket_api_url) as ws:
        # Create offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        await ws.send(json.dumps({"type": "offer", "sdp": pc.localDescription.sdp}))

        # Wait for answer from server
        async for message in ws:
            print(f"Test client - Received message: {message}")
            data = json.loads(message)
            if data["type"] == "answer":
                await pc.setRemoteDescription(
                    RTCSessionDescription(sdp=data["sdp"], type="answer")
                )
            elif data["type"] == "ice":
                await pc.addIceCandidate(data["candidate"])

        print("WebRTC handshake done!")

        # Wait for first frame from server
        @pc.on("track")
        def on_track(track):
            print(f"Track received: {track.kind}")
            if track.kind == "video":
                # grab a single frame
                async def grab_frame():
                    frame = await track.recv()
                    print(f"Received frame: {frame}")
                    await pc.close()
                    return frame

                asyncio.create_task(grab_frame())

        # Keep the event loop alive until frame is received
        await asyncio.sleep(5)


asyncio.run(test_frame())
