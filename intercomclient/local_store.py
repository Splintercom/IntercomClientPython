import json
from .config import Config


def load_tokens():
    with open(Config.token_file_path, "r") as token_file_handle:
        return json.load(token_file_handle)


def store_tokens(tokens: dict[str, str], access_token_expiry):
    data = {
        "access": {
            "token_value": tokens["access_token"],
            "expiry_time": access_token_expiry,
        },
        "refresh": {"token_value": tokens["refresh_token"]},
    }
    with open(Config.token_file_path, "w") as token_file_handle:
        token_file_handle.write(json.dumps(data))
