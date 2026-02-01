from dataclasses import dataclass
from typing import Tuple
import logging


@dataclass()
class Config:
    segment_duration: int = 60
    fps: int = 5
    resolution: Tuple[int, int] = (320, 240)
    s3_bucket_name: str = "segment-uploads"
    debug_mode: bool = True
    video_source: int = 0
    output_dir_path: str = "/tmp/intercom_videos"
    fourcc: str = "XVID"
    video_format: str = "avi"


logging.basicConfig(level=logging.DEBUG if Config.debug_mode else logging.INFO)
