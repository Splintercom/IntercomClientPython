"""Tests for main.PiClient."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from splintercomclient.config import Config


def _make_config(**overrides):
    defaults = dict(
        oauth_client_id="test",
        oauth_client_secret="test",
        http_api_base_url="http://localhost",
        websocket_api_base_url="http://localhost",
    )
    defaults.update(overrides)
    return Config(**defaults)


class TestCheckTokenStatus:
    def test_valid_token(self):
        from main import PiClient

        future = datetime.now(tz=UTC) + timedelta(hours=1)
        tokens = {
            "access": {"token_value": "tok123", "expiry_time": future.timestamp()},
            "refresh": {"token_value": "ref456"},
        }
        assert PiClient(_make_config()).check_token_status(tokens).name == "VALID"

    def test_expired_token(self):
        from main import PiClient

        past = datetime.now(tz=UTC) - timedelta(hours=1)
        tokens = {
            "access": {"token_value": "tok123", "expiry_time": past.timestamp()},
            "refresh": {"token_value": "ref456"},
        }
        assert PiClient(_make_config()).check_token_status(tokens).name == "EXPIRED"

    def test_missing_token_value_none(self):
        from main import PiClient

        tokens = {
            "access": {"token_value": None, "expiry_time": 9999999999.0},
            "refresh": {"token_value": "ref456"},
        }
        assert PiClient(_make_config()).check_token_status(tokens).name == "MISSING"

    def test_missing_access_key(self):
        from main import PiClient

        tokens = {"refresh": {"token_value": "ref456"}}
        assert PiClient(_make_config()).check_token_status(tokens).name == "MISSING"

    def test_missing_token_value_key(self):
        from main import PiClient

        tokens = {
            "access": {"expiry_time": 9999999999.0},
            "refresh": {"token_value": "ref456"},
        }
        assert PiClient(_make_config()).check_token_status(tokens).name == "MISSING"


class TestPiClientStartup:
    def test_init_creates_token_store(self):
        from main import PiClient
        from splintercomclient.token_store import TokenStore

        client = PiClient(_make_config())
        assert isinstance(client.token_store, TokenStore)
        assert client.running is True
        assert client.pc is None

    def test_shutdown_sets_running_false(self):
        from main import PiClient

        client = PiClient(_make_config())
        asyncio.run(client.shutdown())
        assert client.running is False

    def test_shutdown_closes_peer_connection(self):
        from main import PiClient

        client = PiClient(_make_config())
        client.pc = MagicMock()
        client.pc.close = AsyncMock()
        asyncio.run(client.shutdown())
        client.pc.close.assert_called_once()

    def test_shutdown_closes_websocket(self):
        from main import PiClient

        client = PiClient(_make_config())
        client.ws = MagicMock()
        client.ws.close = AsyncMock()
        asyncio.run(client.shutdown())
        client.ws.close.assert_called_once()
