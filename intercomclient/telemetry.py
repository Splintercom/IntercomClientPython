import logging

import requests

from .config import Config
from .token_store import TokenStore

LOG = logging.getLogger(__name__)


class TelemetryClient:
    def __init__(self, config: Config, token_store: TokenStore):
        self.config = config
        self.token_store = token_store

    def send(self, event: str, message: str = "", level: str = "INFO") -> None:
        try:
            tokens = self.token_store.load_tokens()
            access_token = tokens["access"]["token_value"]
            device_code = tokens["device_code"]
            url = f"{self.config.http_api_base_url}/api/v1/devices/{device_code}/telemetry/"
            requests.post(
                url,
                json={"event": event, "message": message, "level": level},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5,
            ).raise_for_status()
        except Exception as e:
            LOG.debug("Telemetry send failed (%s): %s", event, e)
