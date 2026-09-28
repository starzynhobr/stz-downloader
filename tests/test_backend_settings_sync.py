"""The UI must converge on the server's settings even when its one-shot load
at startup fails.

Regression: the bridge takes a couple of seconds to come up (it reconciles the
aria2 process first), while the Backend loaded settings exactly once, right
away. When that call lost the race it was never retried, so every
settings-driven feature stayed silently off -- the clipboard watcher never
started and the app looked simply broken.
"""
import time
from unittest.mock import Mock

import pytest

pytest.importorskip("PySide6.QtCore")

from stz_downloader.ui.backend import LIVE_UPDATE_TIMEOUT_SECONDS, _Worker


def _worker():
    return _Worker("http://127.0.0.1:9999")


def test_settings_in_payload_are_published():
    w = _worker()
    seen = []
    w.settingsLoaded.connect(seen.append)

    w._emit_downloads({"items": [], "settings": {"clipboard_enabled": True}})

    assert seen == [{"clipboard_enabled": True}]


def test_unchanged_settings_are_not_republished_every_tick():
    w = _worker()
    seen = []
    w.settingsLoaded.connect(seen.append)

    for _ in range(3):
        w._emit_downloads({"items": [], "settings": {"clipboard_enabled": True}})

    assert len(seen) == 1


def test_changed_settings_are_republished():
    w = _worker()
    seen = []
    w.settingsLoaded.connect(seen.append)

    w._emit_downloads({"items": [], "settings": {"clipboard_enabled": False}})
    w._emit_downloads({"items": [], "settings": {"clipboard_enabled": True}})

    assert seen == [{"clipboard_enabled": False}, {"clipboard_enabled": True}]


def test_payload_without_settings_is_harmless():
    """Older payloads, or a partial one, must not clear what we know."""
    w = _worker()
    seen = []
    w.settingsLoaded.connect(seen.append)

    w._emit_downloads({"items": [], "settings": {"clipboard_enabled": True}})
    w._emit_downloads({"items": []})

    assert len(seen) == 1
    assert w._known_settings == {"clipboard_enabled": True}


def test_recovery_after_a_failed_startup_load():
    """The exact failure: begin()'s load never happened, so nothing is known
    until the first broadcast arrives."""
    w = _worker()
    seen = []
    w.settingsLoaded.connect(seen.append)

    assert w._known_settings is None  # startup load lost the race
    w._emit_downloads({"items": [], "settings": {"clipboard_enabled": True}})

    assert seen == [{"clipboard_enabled": True}]


def test_watchdog_does_not_poll_while_websocket_is_fresh():
    w = _worker()
    w._ws_connected = True
    w._last_live_update = time.monotonic()
    w._poll = Mock()

    w._watch_live_updates()

    w._poll.assert_not_called()


def test_watchdog_polls_when_websocket_stalls():
    w = _worker()
    w._ws_connected = True
    w._last_live_update = time.monotonic() - LIVE_UPDATE_TIMEOUT_SECONDS - 0.1
    w._poll = Mock()

    w._watch_live_updates()

    w._poll.assert_called_once_with()


def test_watchdog_polls_while_websocket_is_disconnected():
    w = _worker()
    w._ws_connected = False
    w._poll = Mock()

    w._watch_live_updates()

    w._poll.assert_called_once_with()
