"""Tests for splintercomclient.config.

The conftest.py autouse fixture guarantees that splintercom-related env vars
are removed and modules are re-imported fresh before each test.
"""

from pathlib import Path


def _config_cls(**overrides):
    """Import Config fresh and return an instance."""
    from splintercomclient.config import Config

    return Config(**overrides)


class TestConfigDefaults:
    """Dataclass field defaults when no env vars are set."""

    def test_default_resolution(self):
        assert _config_cls().resolution == (320, 240)

    def test_default_target_fps(self):
        assert _config_cls().target_fps == 5

    def test_default_video_source(self):
        assert _config_cls().video_source == 0

    def test_default_output_dir(self):
        assert _config_cls().output_dir_path == "/tmp/splintercom_videos"

    def test_default_fourcc(self):
        assert _config_cls().fourcc == "XVID"

    def test_default_video_format(self):
        assert _config_cls().video_format == "avi"

    def test_default_segment_duration(self):
        assert _config_cls().segment_duration == 60

    def test_default_oauth_scope(self):
        assert _config_cls().oauth_scope == "openid email profile"

    def test_default_max_polling_time_mins(self):
        assert _config_cls().max_polling_time_mins == 5

    def test_default_token_file_path(self):
        # Without TOKEN_FILE_PATH env, default is the Path("~...") — NOT expanded
        # since the default is constructed via Path(...).expanduser() but only
        # if TOKEN_FILE_PATH env var is set. Otherwise the raw default is used.
        # The field default when TOKEN_FILE_PATH is unset:
        # Path(os.getenv("TOKEN_FILE_PATH", "~/.config/splintercomclient/tokens.json")).expanduser()
        # With empty string from getenv fallback: Path("~/.config/...").expanduser()
        assert (
            _config_cls().token_file_path
            == Path("~/.config/splintercomclient/tokens.json").expanduser()
        )

    def test_default_oauth_credentials_are_wrong(self, tmp_path, monkeypatch):
        # Point HOME to a tmp path so no real oauth.json is found,
        # and no OAUTH_CLIENT_ID/SECRET env vars are set.
        monkeypatch.setenv("HOME", str(tmp_path))
        assert _config_cls().oauth_client_id == "wrong"
        assert _config_cls().oauth_client_secret == "wrong"

    def test_custom_resolution(self):
        assert _config_cls(resolution=(640, 480)).resolution == (640, 480)

    def test_custom_target_fps(self):
        assert _config_cls(target_fps=30).target_fps == 30

    def test_custom_video_source(self):
        assert _config_cls(video_source=2).video_source == 2


class TestConfigEnvOverrides:
    def test_env_override_video_source(self, monkeypatch):
        monkeypatch.setenv("VIDEO_SOURCE", "1")
        assert _config_cls().video_source == 1

    def test_env_override_max_polling(self, monkeypatch):
        monkeypatch.setenv("MAX_POLLING_TIME_MINS", "10")
        assert _config_cls().max_polling_time_mins == 10

    def test_env_override_websocket_url(self, monkeypatch):
        monkeypatch.setenv("WEBSOCKET_API_BASE_URL", "wss://prod.example.com/ws")
        assert _config_cls().websocket_api_base_url == "wss://prod.example.com/ws"

    def test_env_override_http_api_url(self, monkeypatch):
        monkeypatch.setenv("HTTP_API_BASE_URL", "https://api.example.com")
        assert _config_cls().http_api_base_url == "https://api.example.com"

    def test_env_override_oauth_credentials(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("OAUTH_CLIENT_ID", "my-id")
        monkeypatch.setenv("OAUTH_CLIENT_SECRET", "my-secret")
        assert _config_cls().oauth_client_id == "my-id"
        assert _config_cls().oauth_client_secret == "my-secret"

    def test_env_override_token_file_path(self, monkeypatch):
        monkeypatch.setenv("TOKEN_FILE_PATH", "/tmp/custom-tokens.json")
        assert _config_cls().token_file_path == Path("/tmp/custom-tokens.json")


class TestLoadOauthCredentials:
    def test_returns_defaults_when_no_file_no_env(self, tmp_path, monkeypatch):
        from splintercomclient.config import load_oauth_credentials

        monkeypatch.setenv("HOME", str(tmp_path))
        assert not (tmp_path / ".config" / "splintercom-api" / "oauth.json").exists()
        client_id, client_secret = load_oauth_credentials()
        assert client_id == "wrong"
        assert client_secret == "wrong"

    def test_reads_from_credentials_file(self, tmp_path, monkeypatch):
        from splintercomclient.config import load_oauth_credentials

        creds_dir = tmp_path / ".config" / "splintercom-api"
        creds_dir.mkdir(parents=True)
        (creds_dir / "oauth.json").write_text(
            '{"client_id": "from-file-id", "client_secret": "from-file-secret"}'
        )
        monkeypatch.setenv("HOME", str(tmp_path))
        client_id, client_secret = load_oauth_credentials()
        assert client_id == "from-file-id"
        assert client_secret == "from-file-secret"

    def test_env_var_used_when_file_missing(self, tmp_path, monkeypatch):
        from splintercomclient.config import load_oauth_credentials

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("OAUTH_CLIENT_ID", "env-id")
        monkeypatch.setenv("OAUTH_CLIENT_SECRET", "env-secret")
        client_id, client_secret = load_oauth_credentials()
        assert client_id == "env-id"
        assert client_secret == "env-secret"

    def test_file_takes_precedence_over_env(self, tmp_path, monkeypatch):
        from splintercomclient.config import load_oauth_credentials

        creds_dir = tmp_path / ".config" / "splintercom-api"
        creds_dir.mkdir(parents=True)
        (creds_dir / "oauth.json").write_text(
            '{"client_id": "file-id", "client_secret": "file-secret"}'
        )
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("OAUTH_CLIENT_ID", "env-id")
        monkeypatch.setenv("OAUTH_CLIENT_SECRET", "env-secret")
        client_id, client_secret = load_oauth_credentials()
        assert client_id == "file-id"
        assert client_secret == "file-secret"

    def test_missing_keys_in_file_returns_wrong(self, tmp_path, monkeypatch):
        from splintercomclient.config import load_oauth_credentials

        creds_dir = tmp_path / ".config" / "splintercom-api"
        creds_dir.mkdir(parents=True)
        (creds_dir / "oauth.json").write_text('{"other": "data"}')
        monkeypatch.setenv("HOME", str(tmp_path))
        client_id, client_secret = load_oauth_credentials()
        assert client_id == "wrong"
        assert client_secret == "wrong"
