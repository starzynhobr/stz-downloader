"""Launch-at-login registration.

Windows only for now: a value under HKCU's Run key. Per-user rather than
machine-wide (HKLM) so enabling it never needs elevation, and disabling it
cannot leave an entry behind that the user has no rights to remove.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "STZ Downloader"


def supported() -> bool:
    return sys.platform == "win32"


def launch_command() -> str:
    """The command Windows should run at login, quoted for the registry."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # Running from source: prefer pythonw so login doesn't flash a console.
    exe = Path(sys.executable)
    windowless = exe.with_name("pythonw.exe")
    interpreter = windowless if windowless.exists() else exe
    return f'"{interpreter}" -m stz_downloader'


def is_enabled() -> bool:
    if not supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError as exc:  # noqa: BLE001
        log.warning("Could not read the autostart entry: %s", exc)
        return False


def apply(enabled: bool) -> bool:
    """Add or remove the entry. Returns the state actually achieved.

    Never raises: failing to register at login must not take the app down.
    """
    if not supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                command = launch_command()
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
                log.info("Autostart enabled: %s", command)
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                    log.info("Autostart disabled")
                except FileNotFoundError:
                    pass  # already absent
        return enabled
    except OSError as exc:  # noqa: BLE001
        log.warning("Could not write the autostart entry: %s", exc)
        return is_enabled()
