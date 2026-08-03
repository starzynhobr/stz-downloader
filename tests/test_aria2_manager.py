from pathlib import Path

import pytest

from stz_downloader.aria2.manager import Aria2Manager, _normalize_option
from stz_downloader.config import Aria2Config


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1M", "1048576"),
        ("1m", "1048576"),
        ("1048576", "1048576"),
        ("1K", "1024"),
        ("2G", "2147483648"),
        ("16", "16"),
        ("true", "true"),
        ("none", "none"),
        ("1.1.1.1,8.8.8.8", "1.1.1.1,8.8.8.8"),
    ],
)
def test_normalize_option(raw, expected):
    assert _normalize_option(raw) == expected


def test_size_suffix_is_not_a_config_change(monkeypatch):
    """aria2 reports --min-split-size=1M back as 1048576. Comparing raw
    strings would restart a healthy process on every single launch."""
    cfg = Aria2Config(extra_args=["--min-split-size=1M", "--file-allocation=none"])
    m = Aria2Manager(cfg, Path(r"C:\Downloads"))
    monkeypatch.setattr(
        m,
        "_rpc",
        lambda *a, **k: {
            "min-split-size": "1048576",
            "file-allocation": "none",
            "dir": r"C:\Downloads",
        },
    )
    assert m._existing_matches_config() is True


def _manager(extra_args):
    cfg = Aria2Config(extra_args=list(extra_args))
    return Aria2Manager(cfg, Path(r"C:\Downloads"))


def test_desired_options_maps_cli_args_to_aria2_option_names():
    m = _manager(["--file-allocation=none", "--split=16", "--continue=true"])
    assert m._desired_options() == {
        "dir": r"C:\Downloads",
        "file-allocation": "none",
        "split": "16",
        "continue": "true",
    }


def test_desired_options_skips_rpc_and_session_plumbing():
    """Those describe the process, not download behaviour -- never a reason
    to restart a healthy aria2."""
    m = _manager(["--rpc-secret=abc", "--save-session=x.txt", "--file-allocation=none"])
    assert m._desired_options() == {
        "dir": r"C:\Downloads",
        "file-allocation": "none",
    }


def test_desired_options_ignores_valueless_flags():
    m = _manager(["--enable-rpc", "--file-allocation=none"])
    assert "enable-rpc" not in m._desired_options()


def test_stale_option_is_detected(monkeypatch):
    """The exact bug: a running aria2 still on prealloc after the config
    changed to none. It must be reported as a mismatch."""
    m = _manager(["--file-allocation=none"])
    monkeypatch.setattr(
        m, "_rpc", lambda *a, **k: {"file-allocation": "prealloc", "dir": r"C:\Downloads"}
    )
    assert m._existing_matches_config() is False


def test_matching_options_are_left_alone(monkeypatch):
    m = _manager(["--file-allocation=none"])
    monkeypatch.setattr(
        m, "_rpc", lambda *a, **k: {"file-allocation": "none", "dir": r"C:\Downloads"}
    )
    assert m._existing_matches_config() is True


def test_options_aria2_does_not_report_are_not_a_mismatch(monkeypatch):
    m = _manager(["--some-future-option=1", "--file-allocation=none"])
    monkeypatch.setattr(
        m, "_rpc", lambda *a, **k: {"file-allocation": "none", "dir": r"C:\Downloads"}
    )
    assert m._existing_matches_config() is True


def test_unreachable_aria2_is_left_alone(monkeypatch):
    """A process we can't authenticate against isn't ours to kill."""
    def boom(*a, **k):
        raise RuntimeError("Unauthorized")

    m = _manager(["--file-allocation=none"])
    monkeypatch.setattr(m, "_rpc", boom)
    assert m._existing_matches_config() is True


def test_start_replaces_stale_instance_only_once(monkeypatch):
    """Guard against a restart loop when an option never compares equal."""
    m = _manager(["--file-allocation=none"])
    calls = {"shutdown": 0, "spawn": 0}

    monkeypatch.setattr(m, "_rpc_port_is_open", lambda: True)
    monkeypatch.setattr(m, "_existing_matches_config", lambda: False)
    monkeypatch.setattr(m, "_shutdown_existing", lambda: (calls.__setitem__("shutdown", calls["shutdown"] + 1), True)[1])

    def fake_spawn():
        calls["spawn"] += 1

    # Stop start() before it really launches a process.
    monkeypatch.setattr(
        "stz_downloader.aria2.manager.subprocess.Popen",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("no binary")),
    )

    for _ in range(3):
        try:
            m.start()
        except FileNotFoundError:
            fake_spawn()

    assert calls["shutdown"] == 1, "stale instance replaced more than once"
    assert calls["spawn"] == 1, "respawn attempted after the first replacement"
