"""Tests for device_authorization module.

Note: initiate_device_authorization and refresh_tokens use Config.oauth_client_id
(the class-level default) rather than the instance attribute. Tests that verify
the client_id sent to the API should match whatever Config.oauth_client_id
resolves to after a fresh import (which is "wrong" when no env vars are set).
"""

from unittest.mock import MagicMock, patch

import pytest

from splintercomclient.config import Config


class TestInitiateDeviceAuthorization:
    def test_success_returns_json(self):
        with (
            patch(
                "splintercomclient.device_authorization.get_os_info",
                return_value="Linux-5.15",
            ),
            patch(
                "splintercomclient.device_authorization.get_device_type",
                return_value="aarch64",
            ),
            patch("splintercomclient.device_authorization.requests.post") as mock_post,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "device_code": "dev123",
                "user_code": "ABCD-EFGH",
                "verification_uri": "http://api.test/verify",
                "interval": 5,
            }
            mock_post.return_value = mock_resp

            config = Config(http_api_base_url="http://api.test")
            from splintercomclient.device_authorization import (
                initiate_device_authorization,
            )

            result = initiate_device_authorization(config)
            assert result["device_code"] == "dev123"
            assert result["user_code"] == "ABCD-EFGH"

    def test_sends_correct_form_data(self):
        with (
            patch(
                "splintercomclient.device_authorization.get_os_info",
                return_value="Linux-5.15",
            ),
            patch(
                "splintercomclient.device_authorization.get_device_type",
                return_value="aarch64",
            ),
            patch("splintercomclient.device_authorization.requests.post") as mock_post,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {}
            mock_post.return_value = mock_resp

            config = Config(http_api_base_url="http://api.test")
            from splintercomclient.device_authorization import (
                initiate_device_authorization,
            )

            initiate_device_authorization(config)
            data = mock_post.call_args.kwargs["data"]
            # initiate_device_authorization uses Config.oauth_client_id (class attr)
            assert data["client_id"] == Config.oauth_client_id
            assert data["device_type"] == "aarch64"
            assert data["device_os"] == "Linux-5.15"
            assert data["scope"] == "profile email"

    def test_non_200_raises_runtime_error(self):
        with (
            patch(
                "splintercomclient.device_authorization.get_os_info",
                return_value="Linux",
            ),
            patch(
                "splintercomclient.device_authorization.get_device_type",
                return_value="arm",
            ),
            patch("splintercomclient.device_authorization.requests.post") as mock_post,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 400
            mock_resp.json.return_value = {
                "error": "invalid_client",
                "error_description": "bad client",
            }
            mock_resp.text = "bad client"
            mock_post.return_value = mock_resp

            from splintercomclient.device_authorization import (
                initiate_device_authorization,
            )

            config = Config(http_api_base_url="http://api.test")
            with pytest.raises(RuntimeError, match="Device authorization failed"):
                initiate_device_authorization(config)


class TestPollForToken:
    def test_pending_then_success(self):
        with (
            patch("splintercomclient.device_authorization.requests.post") as mock_post,
            patch("splintercomclient.device_authorization.sleep") as mock_sleep,
        ):
            pending_resp = MagicMock()
            pending_resp.json.return_value = {"error": "authorization_pending"}

            success_resp = MagicMock()
            success_resp.json.return_value = {
                "access_token": "access-123",
                "refresh_token": "refresh-456",
                "expires_in": 3600,
            }

            mock_post.side_effect = [pending_resp, success_resp]

            from splintercomclient.device_authorization import poll_for_token

            config = Config(http_api_base_url="http://api.test")
            result = poll_for_token(config, "dev-code", interval=5)
            assert result["access_token"] == "access-123"
            assert mock_sleep.call_count == 2

    def test_immediate_success(self):
        with (
            patch("splintercomclient.device_authorization.requests.post") as mock_post,
            patch("splintercomclient.device_authorization.sleep") as mock_sleep,
        ):
            success_resp = MagicMock()
            success_resp.json.return_value = {
                "access_token": "tok",
                "refresh_token": "ref",
                "expires_in": 3600,
            }
            mock_post.return_value = success_resp

            from splintercomclient.device_authorization import poll_for_token

            config = Config(http_api_base_url="http://api.test")
            result = poll_for_token(config, "dev-code", interval=5)
            assert result["access_token"] == "tok"
            mock_sleep.assert_called_once_with(5)


class TestRefreshTokens:
    def test_success(self):
        with patch("splintercomclient.device_authorization.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 7200,
            }
            mock_post.return_value = mock_resp

            from splintercomclient.device_authorization import refresh_tokens

            config = Config(http_api_base_url="http://api.test")
            result = refresh_tokens(config, "old-refresh-token")
            assert result["access_token"] == "new-access"

    def test_sends_correct_data(self):
        with patch("splintercomclient.device_authorization.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {}
            mock_post.return_value = mock_resp

            from splintercomclient.device_authorization import refresh_tokens

            config = Config(http_api_base_url="http://api.test")
            refresh_tokens(config, "my-refresh-token")
            data = mock_post.call_args.kwargs["data"]
            assert data["grant_type"] == "refresh_token"
            # refresh_tokens also uses Config.oauth_client_id (class attr)
            assert data["client_id"] == Config.oauth_client_id
            assert data["refresh_token"] == "my-refresh-token"
