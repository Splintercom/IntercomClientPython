import json
import logging
import os
from .config import Config
import datetime
from enum import Enum

LOG = logging.getLogger(__name__)


class TokenStatus(Enum):
    VALID = 1
    EXPIRED = 2
    MISSING = 3
    EXPIRING = 4


class CannotLoadTokensException(Exception):
    pass


class TokenStore:
    """
    Class to manage token storage and access
    """

    def __init__(self, config: Config, verify=True):
        self.config = config

        if verify:
            self.verify_token_file_path()

    @classmethod
    def check_token_expiry_delta(cls, token_expiry_time) -> datetime.timedelta:
        current_time = datetime.datetime.now().timestamp()
        return datetime.timedelta(seconds=current_time - token_expiry_time)

    def load_tokens(self):
        self.verify_token_file_path()
        with open(self.config.token_file_path, "r") as token_file_handle:
            token_file_json = json.load(token_file_handle)
            try:
                access_token = token_file_json["access"]["token_value"]
                refresh_token = token_file_json["refresh"]["token_value"]
                access_token_expiry = token_file_json["access"]["expiry_time"]
                device_code = token_file_json["device_code"]

                return {
                    "access": {
                        "token_value": access_token,
                        "expiry_time": access_token_expiry,
                    },
                    "refresh": {"token_value": refresh_token},
                    "device_code": device_code,
                }

            except KeyError as e:
                error_message = f"Token file is missing keys, will assume empty {self.config.token_file_path}"
                raise CannotLoadTokensException(error_message) from e

    def store_tokens(self, tokens: dict[str, str], access_token_expiry, device_code):
        self.verify_token_file_path()

        data = {
            "access": {
                "token_value": tokens["access_token"],
                "expiry_time": access_token_expiry,
            },
            "refresh": {"token_value": tokens["refresh_token"]},
            "device_code": device_code,
        }
        with open(self.config.token_file_path, "w") as token_file_handle:
            token_file_handle.write(json.dumps(data))

    def verify_token_file_path(self) -> bool:
        token_file_path = self.config.token_file_path
        token_parent_dir_path = os.path.split(token_file_path)[0]
        # Check our dir path exists, and if not attempt to create it
        if not os.path.isdir(token_parent_dir_path):
            try:
                os.makedirs(token_parent_dir_path, exist_ok=True)
            except OSError as e:
                error_message = f"Error: could not find or create token file parent directory: {token_file_path}"
                raise OSError(error_message) from e

        # Check our file exists and has the correct permissions
        if not os.path.exists(token_file_path):
            token_fd = os.open(
                token_file_path,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                0o600,
            )
            example_file_outline = {
                "access": {"token_value": None, "expiry_time": None},
                "refresh": {"token_value": None},
                "device_code": None,
            }
            with os.fdopen(token_fd, "w") as file_handle:
                file_handle.write(json.dumps(example_file_outline))
        else:
            # If the file already exists, we want to check it has the correct permissions
            current_permissions = oct(os.stat(token_file_path).st_mode)[-3:]
            if current_permissions != "600":
                error_message = f"Error: token file has incorrect permissions: {token_file_path}, current permissions: {current_permissions}"
                raise OSError(error_message)

        return True
