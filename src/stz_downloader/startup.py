"""Windows startup registration for STZ Downloader."""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    import winreg
else:
    winreg = None  # type: ignore[assignment]

APP_RUN_NAME = "STZ Downloader"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_SCRIPT_NAME = "STZ Downloader.cmd"


def _windowsapps_family_from_exe(executable: Path) -> str | None:
    for part in executable.parts:
        match = re.fullmatch(r"(stz-downloader)_\d+\.\d+\.\d+\.\d+_x64__(.+)", part)
        if match:
            return f"{match.group(1)}_{match.group(2)}"
    return None


def startup_command() -> str:
    executable = Path(sys.executable).resolve()
    if not getattr(sys, "frozen", False):
        return f'"{executable}" -m stz_downloader --minimized'
    return f'"{executable}" --minimized'


def _startup_script_path() -> Path:
    return (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / STARTUP_SCRIPT_NAME
    )


def _startup_script_content() -> str:
    launch = f'start "" {startup_command()}'
    return f"@echo off\n{launch}\n"


def _delete_run_key_value() -> None:
    if sys.platform != "win32":
        return
    if winreg is None:
        return

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, APP_RUN_NAME)
    except FileNotFoundError:
        pass
    except OSError as exc:
        logging.warning("Could not remove Windows Run startup value: %s", exc)


def set_start_with_windows(enabled: bool) -> None:
    if sys.platform != "win32":
        return

    script_path = _startup_script_path()
    if enabled:
        try:
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(_startup_script_content(), encoding="utf-8")
            _delete_run_key_value()
        except OSError as exc:
            logging.warning("Could not register Windows startup script %s: %s", script_path, exc)
        return

    try:
        script_path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        logging.warning("Could not remove Windows startup script %s: %s", script_path, exc)
    _delete_run_key_value()


def start_with_windows_enabled() -> bool:
    if sys.platform != "win32":
        return False
    return _startup_script_path().exists()
