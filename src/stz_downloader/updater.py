"""Self-update from GitHub Releases.

The bridge asks GitHub for the latest release, and when it is newer than the
running build it offers the desktop installer. Installing downloads it,
verifies its SHA-256 and runs it silently; the installer stops the app,
replaces the files and starts it again.

Integrity: GitHub publishes a SHA-256 digest for every release asset, and the
build also uploads a ``SHA256SUMS.txt``. Every hash that is available must
match the downloaded file, and at least one must be available -- an installer
that cannot be verified is never run.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import httpx

from . import __version__
from .runtime import runtime_dir

log = logging.getLogger(__name__)

REPO = "starzynhobr/stz-downloader"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
# Testing hook: point the updater at another feed with the same JSON shape.
FEED_ENV = "STZ_UPDATE_FEED"
INSTALLER_RE = re.compile(r"-desktop-setup\.exe$", re.IGNORECASE)
CHECKSUMS_NAME = "SHA256SUMS.txt"
ENGINE_EXE = "stz-engine.exe"
CHECK_INTERVAL_SECONDS = 6 * 3600
FIRST_CHECK_DELAY_SECONDS = 15


def parse_version(text: str) -> tuple[int, ...]:
    """'v0.1.10' -> (0, 1, 10). Anything unparsable sorts as oldest."""
    numbers = re.findall(r"\d+", text.split("-", 1)[0])
    return tuple(int(n) for n in numbers) if numbers else (0,)


def is_newer(candidate: str, current: str) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def parse_checksums(text: str) -> dict[str, str]:
    """``sha256sum`` format: '<hex>  <name>' (optionally '*<name>')."""
    sums: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*$", line)
        if match:
            sums[match.group(2)] = match.group(1).lower()
    return sums


def can_self_update() -> bool:
    """Only the installed desktop build knows how to replace itself."""
    return (
        sys.platform == "win32"
        and getattr(sys, "frozen", False)
        and Path(sys.executable).name.lower() == ENGINE_EXE
    )


class UpdateError(RuntimeError):
    pass


@dataclass
class UpdateState:
    current: str = __version__
    supported: bool = field(default_factory=can_self_update)
    # idle | checking | downloading | verifying | installing | error
    status: str = "idle"
    available: bool = False
    version: str = ""
    notes: str = ""
    page_url: str = ""
    progress: float = 0.0
    error: str = ""
    checked_at: float = 0.0


@dataclass
class _Release:
    version: str
    notes: str
    page_url: str
    asset_name: str
    asset_url: str
    size: int
    expected: list[str]  # every known SHA-256 for the installer


class Updater:
    def __init__(
        self,
        download_dir: Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.state = UpdateState()
        self._release: _Release | None = None
        self._dir = download_dir or (runtime_dir() / "updates")
        self._transport = transport  # tests swap in httpx.MockTransport
        self._busy = asyncio.Lock()

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            transport=self._transport,
            headers={"User-Agent": f"stz-downloader/{__version__}"},
        )

    async def _fetch(self, url: str) -> httpx.Response:
        async with self._client(20.0) as client:
            return await client.get(url, headers={"Accept": "application/vnd.github+json"})

    def snapshot(self) -> dict:
        return asdict(self.state)

    async def check(self) -> dict:
        if self.state.status in ("downloading", "verifying", "installing"):
            return self.snapshot()
        self.state.status, self.state.error = "checking", ""
        try:
            response = await self._fetch(os.environ.get(FEED_ENV) or LATEST_URL)
            response.raise_for_status()
            release = response.json()
            version = str(release.get("tag_name", "")).lstrip("v")
            asset = next(
                (a for a in release.get("assets", []) if INSTALLER_RE.search(a.get("name", ""))),
                None,
            )
            self.state.checked_at = time.time()
            self.state.available = bool(asset) and is_newer(version, __version__)
            self.state.version = version
            self.state.notes = str(release.get("body") or "")[:4000]
            self.state.page_url = str(release.get("html_url") or "")
            self._release = None
            if self.state.available and asset:
                expected = []
                digest = str(asset.get("digest") or "")
                if digest.lower().startswith("sha256:"):
                    expected.append(digest.split(":", 1)[1].lower())
                sums_asset = next(
                    (a for a in release.get("assets", []) if a.get("name") == CHECKSUMS_NAME), None
                )
                if sums_asset:
                    sums = await self._fetch(sums_asset["browser_download_url"])
                    sums.raise_for_status()
                    listed = parse_checksums(sums.text).get(asset["name"])
                    if listed:
                        expected.append(listed)
                self._release = _Release(
                    version=version,
                    notes=self.state.notes,
                    page_url=self.state.page_url,
                    asset_name=asset["name"],
                    asset_url=asset["browser_download_url"],
                    size=int(asset.get("size") or 0),
                    expected=expected,
                )
            self.state.status = "idle"
        except Exception as exc:  # noqa: BLE001 -- offline is normal, just report it
            log.info("Update check failed: %s", exc)
            self.state.status, self.state.error = "error", f"check failed: {exc}"
        return self.snapshot()

    async def download_and_verify(self) -> Path:
        release = self._release
        if not release:
            raise UpdateError("no update available")
        if not release.expected:
            raise UpdateError("the release publishes no SHA-256 for the installer")
        if len(set(release.expected)) > 1:
            raise UpdateError("the published SHA-256 values disagree")

        self._dir.mkdir(parents=True, exist_ok=True)
        target = self._dir / release.asset_name
        partial = target.with_suffix(target.suffix + ".part")
        digest = hashlib.sha256()
        self.state.status, self.state.progress, self.state.error = "downloading", 0.0, ""
        async with self._client(60.0) as client:
            async with client.stream("GET", release.asset_url) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length") or release.size or 0)
                done = 0
                with open(partial, "wb") as out:
                    async for chunk in response.aiter_bytes(1 << 16):
                        out.write(chunk)
                        digest.update(chunk)
                        done += len(chunk)
                        if total:
                            self.state.progress = done / total

        self.state.status = "verifying"
        actual = digest.hexdigest()
        if actual != release.expected[0]:
            partial.unlink(missing_ok=True)
            raise UpdateError(f"SHA-256 mismatch: expected {release.expected[0]}, got {actual}")
        os.replace(partial, target)
        log.info("Update %s downloaded and verified (sha256 %s)", release.version, actual)
        return target

    async def install(self) -> dict:
        if not self.state.supported:
            raise UpdateError("this build cannot update itself; download it from the release page")
        if self._busy.locked():
            return self.snapshot()
        async with self._busy:
            try:
                installer = await self.download_and_verify()
                self.state.status = "installing"
                launch_installer(installer)
            except Exception as exc:
                self.state.status, self.state.error = "error", str(exc)
                if isinstance(exc, UpdateError):
                    raise
                raise UpdateError(f"update failed: {exc}") from exc
        return self.snapshot()

    def clean_downloads(self) -> None:
        """Drop installers from earlier updates; by now they have run."""
        for leftover in self._dir.glob("*.exe*"):
            try:
                leftover.unlink()
            except OSError:  # still running or locked; next start will get it
                pass

    async def run_periodic(self, enabled: Callable[[], bool]) -> None:
        self.clean_downloads()
        await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
        while True:
            if enabled():
                await self.check()
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def launch_installer(installer: Path) -> None:
    """Run the installer silently, outside this process tree.

    The installer kills ``stz-engine.exe`` with ``taskkill /T``, which would
    also kill its own process if it were our child. ``cmd /c start`` hands it
    to a short-lived parent, so it survives and finishes the update; the
    ``/AUTOUPDATE=1`` switch makes it start the app again afterwards.
    """
    command = installer_command(installer)
    subprocess.Popen(  # noqa: S603 -- fixed arguments, verified file
        command, creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True
    )


def installer_command(installer: Path) -> str:
    # `start` takes the first quoted argument as a window title, hence "".
    return (
        f'cmd.exe /c start "" "{installer}" '
        "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /AUTOUPDATE=1"
    )
