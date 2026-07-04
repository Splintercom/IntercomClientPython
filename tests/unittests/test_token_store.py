"""Tests for splintercomclient.token_store."""

import json
import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from splintercomclient.config import Config
from splintercomclient.token_store import CannotLoadTokensException, TokenStore


def _make_config(token_path):
    return Config(
        token_file_path=Path(token_path),
        oauth_client_id="test",
        oauth_client_secret="test",
        http_api_base_url="http://localhost",
        websocket_api_base_url="http://localhost",
    )


def _make_token_file(
    path,
    access_token="access123",
    refresh_token="refresh456",
    expiry=None,
    device_code="dev789",
):
    if expiry is None:
        expiry = (datetime.now(tz=UTC) + timedelta(hours=1)).timestamp()
    data = {
        "access": {"token_value": access_token, "expiry_time": expiry},
        "refresh": {"token_value": refresh_token},
        "device_code": device_code,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(data))


@pytest.fixture
def tmp_token_path(tmp_path):
    return str(tmp_path / "tokens.json")


class TestTokenStoreInit:
    def test_creates_token_file_if_missing(self, tmp_token_path):
        assert not os.path.exists(tmp_token_path)
        TokenStore(config=_make_config(tmp_token_path))
        assert os.path.exists(tmp_token_path)

    def test_existing_token_file_is_preserved(self, tmp_token_path):
        _make_token_file(tmp_token_path, access_token="existing-token")
        TokenStore(config=_make_config(tmp_token_path))
        data = json.loads(Path(tmp_token_path).read_text())
        assert data["access"]["token_value"] == "existing-token"


class TestVerifyTokenFilePath:
    def test_creates_parent_directory(self, tmp_token_path):
        deep = str(Path(tmp_token_path).parent / "sub" / "tokens.json")
        config = _make_config(deep)
        store = TokenStore(config=config, verify=False)
        result = store.verify_token_file_path()
        assert result is True
        assert os.path.isdir(Path(deep).parent)

    def test_file_created_with_600_permissions(self, tmp_token_path):
        config = _make_config(tmp_token_path)
        store = TokenStore(config=config, verify=False)
        store.verify_token_file_path()
        mode = os.stat(tmp_token_path).st_mode
        assert stat.S_IMODE(mode) == 0o600

    def test_wrong_permissions_raises_oserror(self, tmp_token_path):
        _make_token_file(tmp_token_path)
        os.chmod(tmp_token_path, 0o644)
        config = _make_config(tmp_token_path)
        store = TokenStore(config=config, verify=False)
        with pytest.raises(OSError, match="incorrect permissions"):
            store.verify_token_file_path()


class TestLoadTokens:
    def test_load_valid_tokens(self, tmp_token_path):
        _make_token_file(tmp_token_path)
        config = _make_config(tmp_token_path)
        store = TokenStore(config=config, verify=False)
        result = store.load_tokens()
        assert result["access"]["token_value"] == "access123"
        assert result["refresh"]["token_value"] == "refresh456"
        assert result["device_code"] == "dev789"

    def test_load_missing_keys_raises(self, tmp_token_path):
        p = Path(tmp_token_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"access": {}}))
        os.chmod(str(p), 0o600)
        config = _make_config(tmp_token_path)
        store = TokenStore(config=config, verify=False)
        with pytest.raises(CannotLoadTokensException):
            store.load_tokens()


class TestStoreTokens:
    def test_store_and_reload(self, tmp_token_path):
        config = _make_config(tmp_token_path)
        store = TokenStore(config=config)
        store.store_tokens(
            {"access_token": "new-access", "refresh_token": "new-refresh"},
            access_token_expiry=(datetime.now(tz=UTC) + timedelta(hours=2)).timestamp(),
            device_code="dev000",
        )
        result = store.load_tokens()
        assert result["access"]["token_value"] == "new-access"
        assert result["refresh"]["token_value"] == "new-refresh"
        assert result["device_code"] == "dev000"

    def test_store_overwrites_existing(self, tmp_token_path):
        _make_token_file(tmp_token_path, access_token="old")
        config = _make_config(tmp_token_path)
        store = TokenStore(config=config, verify=False)
        store.store_tokens(
            {"access_token": "replaced", "refresh_token": "replaced-refresh"},
            access_token_expiry=9999999999.0,
            device_code="newdev",
        )
        result = store.load_tokens()
        assert result["access"]["token_value"] == "replaced"


class TestCheckTokenExpiryDelta:
    def test_returns_timedelta(self, tmp_token_path):
        config = _make_config(tmp_token_path)
        store = TokenStore(config=config, verify=False)
        future = datetime.now().timestamp() + 3600
        delta = store.check_token_expiry_delta(future)
        assert isinstance(delta, timedelta)
