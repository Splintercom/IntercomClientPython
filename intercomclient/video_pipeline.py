from datetime import datetime
import cv2
import logging
import os
import json
import time
from pathlib import Path
from intercomclient.config import Config

LOG = logging.getLogger(__name__)


class VideoPipeline:
    def __init__(self, config=Config):
        self.config = config
        self.capture = None
        self.frame_count = 0

    def init_camera(self, source=0) -> cv2.VideoCapture:
        source = source or self.config.video_source
        self.capture = cv2.VideoCapture(source)
        if not self.capture.isOpened():
            raise ValueError("Unable to open video source")

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.resolution[0])
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.resolution[1])

        ret, frame = self.capture.read()
        if not ret:
            LOG.error("Cannot read from camera")
            raise RuntimeError("Cannot read from camera")

        return self.capture

    def init_writer(self, segment_number, output_dir_path=None) -> cv2.VideoWriter:
        if not output_dir_path:
            output_dir_path = self.config.output_dir_path

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        Path(output_dir_path).mkdir(parents=True, exist_ok=True)

        filename = (
            f"segment_{timestamp}_{segment_number:04d}.{self.config.video_format}"
        )
        output_file_path = os.path.join(output_dir_path, filename)

        fourcc = cv2.VideoWriter_fourcc(*self.config.fourcc)
        self.writer = cv2.VideoWriter(
            output_file_path, fourcc, self.config.fps, self.config.resolution
        )

        if not self.writer.isOpened():
            LOG.error("Cannot open video writer")
            raise RuntimeError("Cannot open video writer")

        return self.writer

    def capture_frame(self):
        """Capture single frame with timestamp"""
        ret, frame = self.capture.read()
        if not ret:
            LOG.warning("Failed to capture frame")
            return None

        # Add timestamp overlay
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame,
            timestamp,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),  # Green text
            2,
        )

        return frame

    def save_metadata(self, filepath, motion_events=None):
        """Save metadata JSON for the segment"""
        metadata = {
            "filename": os.path.basename(filepath),
            "camera_id": "pi-01",
            "start_time": self.segment_start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": self.config.segment_duration,
            "resolution": f"{self.config.resolution[0]}x{self.config.resolution[1]}",
            "fps": self.config.fps,
            "total_frames": self.frame_count,
            "motion_events": motion_events or [],
            "file_size_bytes": os.path.getsize(filepath)
            if os.path.exists(filepath)
            else 0,
        }

        metadata_path = filepath.replace(f".{self.config['video_format']}", ".json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    def record_segment(self, segment_number, max_frames=None):
        writer = self.init_writer(segment_number)
        if not writer:
            raise RuntimeError("Writer not initialized")

        segment_start = datetime.now()

        def continue_recording():
            duration_complete = (
                datetime.now() - segment_start
            ).seconds < self.config.segment_duration
            frames_complete = (self.frame_count < max_frames) if max_frames else False

            return duration_complete or frames_complete

        try:
            while continue_recording():
                frame = self.capture_frame()
                if frame is not None:
                    self.writer.write(frame)
                    self.frame_count += 1

                time.sleep(1 / self.config.fps)
                LOG.debug(
                    f"Recording segment {segment_number}, frame {self.frame_count}"
                )

        except Exception as e:
            raise e

        finally:
            self.writer.release()
            self.save_metadata()
