import cv2
import logging
from intercomclient.config import Config
from aiortc import VideoStreamTrack
import av
import asyncio

LOG = logging.getLogger(__name__)


class CameraVideoStreamTrack(VideoStreamTrack):
    def __init__(self, config=Config):
        self.config = config
        self.target_fps = config.target_fps
        self.capture = cv2.VideoCapture(config.video_source)
        if not self.capture.isOpened():
            raise ValueError("Unable to open video source")
        self.segment_number = 0
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        ret, frame = self.capture.read()
        if not ret:
            await asyncio.sleep(1 / self.target_fps)
            return await self.recv()

        frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        return frame
