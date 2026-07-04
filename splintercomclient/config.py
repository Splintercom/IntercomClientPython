import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


def load_oauth_credentials():
    """Load OAuth credentials from ~/.config/splintercom-api/oauth.json"""
    config_file = Path("~/.config/splintercom-api/oauth.json").expanduser()

    if config_file.exists():
        with open(config_file, "r") as f:
            creds = json.load(f)
            return creds.get("client_id", "wrong"), creds.get("client_secret", "wrong")

    # Fallback to environment variable if file doesn't exist
    return os.getenv("OAUTH_CLIENT_ID", "wrong"), os.getenv(
        "OAUTH_CLIENT_SECRET", "wrong"
    )


@dataclass()
class Config:
    segment_duration: int = 60
    target_fps: int = 5
    resolution: Tuple[int, int] = (320, 240)
    debug_mode: bool = True
    video_source: int = int(os.getenv("VIDEO_SOURCE", 0))
    output_dir_path: str = "/tmp/splintercom_videos"
    fourcc: str = "XVID"
    video_format: str = "avi"
    oauth_scope: str = "openid email profile"
    oauth_grant: str = "urn:ietf:params:oauth:grant-type:device_code"
    oauth_client_id: str = load_oauth_credentials()[0]
    oauth_client_secret: str = load_oauth_credentials()[1]
    token_file_path: Path = Path(
        os.getenv("TOKEN_FILE_PATH", "~/.config/splintercomclient/tokens.json")
    ).expanduser()
    http_api_base_url: str = os.getenv("HTTP_API_BASE_URL", "wrong")
    websocket_api_base_url: str = os.getenv("WEBSOCKET_API_BASE_URL", "wrong")
    max_polling_time_mins: int = int(os.getenv("MAX_POLLING_TIME_MINS", 5))
    turn_url: str | None = os.getenv("TURN_URL")
    turn_username: str | None = os.getenv("TURN_USERNAME")
    turn_credential: str | None = os.getenv("TURN_CREDENTIAL")


logging.basicConfig(level=logging.DEBUG if Config.debug_mode else logging.INFO)
