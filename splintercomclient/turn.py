import logging

import requests

LOG = logging.getLogger(__name__)


def fetch_turn_credentials(http_api_base_url: str, access_token: str) -> dict | None:
    try:
        resp = requests.get(
            f"{http_api_base_url}/api/v1/users/turn-credentials/",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("turn_credentials")
    except Exception as e:
        LOG.warning("Failed to fetch TURN credentials: %s", e)
        return None
