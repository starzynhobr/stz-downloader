"""User-editable runtime settings, persisted as JSON.

Distinct from ``config.py`` (static startup config in TOML). These are the
things the gear/drawer in the UI changes and the browser extension reads to
decide what to intercept: interception toggle, auto-start, and the file-type
filter.

Stored at ``%APPDATA%/stz-downloader/settings.json``.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from .config import user_config_dir

# IDM-like default categories (extensions worth grabbing). Images and tiny
# inline assets are intentionally left out so they still open in the browser.
DEFAULT_EXTENSIONS = [
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso",
    ".exe", ".msi", ".dmg", ".deb", ".rpm", ".apk",
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv",
    ".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
]


class Settings(BaseModel):
    intercept_enabled: bool = True       # master on/off for the extension
    auto_start: bool = False             # if False, browser downloads ask first
    intercept_all: bool = False          # ignore the filter and grab everything
    extensions: list[str] = Field(default_factory=lambda: list(DEFAULT_EXTENSIONS))
    connections: int = 8                 # default segments for new downloads
    # Total download bandwidth shared by every active item. aria2 uses bytes
    # per second; zero is its native representation for "unlimited".
    download_limit_bps: int = Field(default=0, ge=0)

    # Watch the clipboard and offer to grab copied links. Off by default: it
    # means reading everything the user copies, so it must be a deliberate
    # choice. Only URLs matching the filter above are ever acted on, and
    # non-matching clipboard content is never stored or logged.
    clipboard_enabled: bool = False

    # Pause every active download when the destination volume is about to run
    # out, instead of letting aria2 hit ENOSPC. With --continue=true a paused
    # download resumes byte-exact once space is freed, so nothing is lost.
    disk_guard_enabled: bool = True
    disk_reserve_mb: int = 2048          # keep this much free for the OS

    start_with_windows: bool = False     # HKCU Run entry, see autostart.py
    # Closing the window hides it to the tray instead of quitting, so the
    # bridge keeps serving the browser extension and downloads keep running.
    minimize_to_tray: bool = True
    # Look for a newer release on GitHub at startup and every few hours.
    # Installing always waits for the user to click "Update".
    auto_update_check: bool = True


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (user_config_dir() / "settings.json")
        self.settings = self._load()

    def _load(self) -> Settings:
        if self.path.exists():
            try:
                return Settings(**json.loads(self.path.read_text("utf-8")))
            except Exception:  # corrupt/old file -> fall back to defaults
                pass
        return Settings()

    def update(self, changes: dict) -> Settings:
        data = self.settings.model_dump()
        # only apply known keys that were actually provided
        for k, v in changes.items():
            if k in data and v is not None:
                data[k] = v
        self.settings = Settings(**data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.settings.model_dump(), indent=2), "utf-8")
        return self.settings
