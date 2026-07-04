"""Shared test fixtures.

Guarantees that splintercomclient modules are never imported before
the test environment is fully controlled. This is critical because
Config evaluates os.getenv() at class-definition time.
"""

import sys

import pytest

# These are the only env vars that splintercomclient.config reads at import time.
# We ensure they're absent BEFORE any splintercomclient import happens.
_SENSITIVE_ENV_KEYS = [
    "VIDEO_SOURCE",
    "TOKEN_FILE_PATH",
    "HTTP_API_BASE_URL",
    "WEBSOCKET_API_BASE_URL",
    "MAX_POLLING_TIME_MINS",
    "OAUTH_CLIENT_ID",
    "OAUTH_CLIENT_SECRET",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove all splintercom-related env vars before each test.

    Uses monkeypatch so the cleanup is automatic and scoped.
    Also removes previously-imported splintercomclient modules so they
    get fresh-imported with the cleaned env.
    """
    for key in _SENSITIVE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    # Remove cached splintercomclient modules so they re-import fresh
    to_remove = [
        mod
        for mod in sys.modules
        if mod.startswith("splintercomclient") or mod == "main"
    ]
    for mod in to_remove:
        del sys.modules[mod]

    yield

    # Cleanup after test too
    to_remove = [
        mod
        for mod in sys.modules
        if mod.startswith("splintercomclient") or mod == "main"
    ]
    for mod in to_remove:
        del sys.modules[mod]
