import asyncio
import logging

import av
import cv2
from aiortc import VideoStreamTrack

from splintercomclient.config import Config

LOG = logging.getLogger(__name__)


class SharedCameraSource:
    """Single cv2.VideoCapture shared across all active peer connections.

    Runs a background loop that reads frames and fans them out to per-viewer
    queues. Each CameraVideoStreamTrack subscribes with a unique key and
    reads exclusively from its own queue.
    """

    def __init__(self, config: Config) -> None:
        self.capture = cv2.VideoCapture(config.video_source)
        LOG.info("Opened shared camera: source=%s", config.video_source)
        if not self.capture.isOpened():
            raise ValueError(f"Unable to open video source: {config.video_source}")
        self._target_fps = config.target_fps
        self._subscribers: dict[str, asyncio.Queue] = {}
        self._task: asyncio.Task | None = None

    def subscribe(self, key: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=4)
        self._subscribers[key] = q
        LOG.info("Camera subscriber added: %s (%d total)", key, len(self._subscribers))
        return q

    def unsubscribe(self, key: str) -> None:
        self._subscribers.pop(key, None)
        LOG.info(
            "Camera subscriber removed: %s (%d total)", key, len(self._subscribers)
        )

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.get_event_loop().create_task(self._read_loop())

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.capture.isOpened():
            self.capture.release()
        LOG.info("Shared camera closed")

    async def _read_loop(self) -> None:
        delay = 1.0 / self._target_fps
        while True:
            ret, frame = self.capture.read()
            if ret:
                for q in list(self._subscribers.values()):
                    if q.full():
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    try:
                        q.put_nowait(frame)
                    except asyncio.QueueFull:
                        pass
            else:
                await asyncio.sleep(delay)
            # Yield to the event loop between frames so other coroutines
            # aren't starved while capture.read() blocks briefly.
            await asyncio.sleep(0)


class CameraVideoStreamTrack(VideoStreamTrack):
    """Per-viewer video track backed by a shared camera source."""

    def __init__(self, source: SharedCameraSource, viewer_key: str) -> None:
        super().__init__()
        self._source = source
        self._viewer_key = viewer_key
        self._queue = source.subscribe(viewer_key)

    def stop(self) -> None:
        super().stop()
        self._source.unsubscribe(self._viewer_key)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = await self._queue.get()
        av_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        av_frame.pts = pts
        av_frame.time_base = time_base
        return av_frame
