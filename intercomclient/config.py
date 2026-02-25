from dataclasses import dataclass
from typing import Tuple
from pathlib import Path
import logging
import os


@dataclass()
class Config:
    segment_duration: int = 60
    target_fps: int = 5
    resolution: Tuple[int, int] = (320, 240)
    debug_mode: bool = True
    video_source: int = int(os.getenv("VIDEO_SOURCE", 0))
    output_dir_path: str = "/tmp/intercom_videos"
    fourcc: str = "XVID"
    video_format: str = "avi"
    oauth_scope: str = "openid email profile"
    oauth_grant: str = "urn:ietf:params:oauth:grant-type:device_code"
    oauth_client_id: str = os.getenv("OAUTH_CLIENT_ID", "wrong")
    token_file_path: Path = Path(
        os.getenv("TOKEN_FILE_PATH", "~/.config/intercomclient/tokens.json")
    ).expanduser()
    http_api_base_url: str = os.getenv("HTTP_API_BASE_URL", "wrong")
    websocket_api_base_url: str = os.getenv("WEBSOCKET_API_BASE_URL", "wrong")
    max_polling_time_mins: int = int(os.getenv("MAX_POLLING_TIME_MINS", 5))


logging.basicConfig(level=logging.DEBUG if Config.debug_mode else logging.INFO)
