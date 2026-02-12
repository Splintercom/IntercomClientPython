from intercomclient.device_authorization import (
    initiate_device_authorization,
    poll_for_token,
    refresh_tokens,
)
from intercomclient.config import Config
import logging
from datetime import datetime, timedelta, UTC
from intercomclient.local_store import store_tokens, load_tokens

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)
config = Config()

authorization_response = initiate_device_authorization(config)
LOG.info(f"User code: {authorization_response['user_code']}")

token_response = poll_for_token(
    config,
    authorization_response["device_code"],
    interval=authorization_response["interval"],
)
print(token_response)

token_expiry = (
    datetime.now(tz=UTC) + timedelta(seconds=token_response["expires_in"])
).timestamp()

store_tokens(
    {
        "access_token": token_response["access_token"],
        "refresh_token": token_response["refresh_token"],
    },
    access_token_expiry=token_expiry,
)

refresh_token_response = refresh_tokens(config, load_tokens()["refresh"]["token_value"])

print(refresh_token_response)
