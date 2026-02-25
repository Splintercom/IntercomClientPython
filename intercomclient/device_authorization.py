from .device import get_device_type, get_os_info
from .config import Config
from time import sleep
from datetime import datetime, timedelta
import requests


def initiate_device_authorization(config: Config) -> dict:
    client_id = Config.oauth_client_id
    device_type = get_device_type()
    device_os = get_os_info()
    url = f"{config.http_api_base_url}/oauth/device-authorization/"

    api_response = requests.post(
        url,
        data={
            "client_id": client_id,
            "device_type": device_type,
            "device_os": device_os,
            "scope": "profile email",
        },
    )
    return api_response.json()


def poll_for_token(config: Config, device_code: str, interval: int) -> dict:
    client_id = config.oauth_client_id

    continue_polling = True
    polling_end_time = datetime.now() + timedelta(minutes=config.max_polling_time_mins)
    url = f"{config.http_api_base_url}/oauth/token/"
    while continue_polling:
        if datetime.now() > polling_end_time:
            continue_polling = False
            break
        sleep(interval)
        post_data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": client_id,
        }
        api_response = requests.post(
            url,
            data=post_data,
        )
        resp_json = api_response.json()
        if "error" in resp_json and resp_json["error"] == "authorization_pending":
            continue
        else:
            return api_response.json()

    return api_response.json()


def refresh_tokens(config: Config, refresh_token) -> dict:
    client_id = Config.oauth_client_id
    url = f"{config.http_api_base_url}/oauth/token/"

    api_response = requests.post(
        url,
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
        },
    )

    return api_response.json()
