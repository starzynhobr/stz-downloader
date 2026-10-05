"""Local HTTP/WebSocket bridge.

Both the browser extension and the QML UI talk to this server:

  POST /api/download            <- extension/UI posts a download here
  GET  /api/downloads           <- UI polls list + pending confirmations
  POST /api/downloads/{gid}/...   pause | resume | cancel
  POST /api/downloads/purge      clear finished
  GET  /api/settings            <- extension reads the intercept filter
  PUT  /api/settings            <- UI (drawer) edits settings
  GET  /api/pending             <- pending confirmations
  POST /api/pending/{id}/...      confirm | cancel
  POST /api/clipboard           <- UI offers a copied URL (filtered here)
  POST /api/focus               <- a second launch asks the UI to show itself
  WS   /ws                      <- UI subscribes to live updates

Bound to 127.0.0.1 only. CORS is opened for browser-extension origins.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .. import autostart
from ..aria2 import Aria2Client, Aria2Manager
from ..aria2.client import Aria2Error
from ..config import Config
from ..settings import SettingsStore
from ..updater import Updater, UpdateError

PROGRESS_KEYS = [
    "gid",
    "status",
    "totalLength",
    "completedLength",
    "downloadSpeed",
    "files",
    "errorMessage",
]


# Statuses whose remaining bytes still have a claim on the disk.
UNFINISHED = ("active", "waiting", "paused")

# A clipboard hit has to look like a real file URL, not any old text with
# "http" in it. Kept deliberately strict to avoid acting on prose.
URL_RE = re.compile(r"^https?://[^\s<>\"']+$", re.IGNORECASE)


class DownloadRequest(BaseModel):
    url: str
    filename: str | None = None
    referer: str | None = None
    user_agent: str | None = None
    cookies: str | None = None
    headers: dict[str, str] = {}
    connections: int | None = None  # None => use settings default
    filesize: int = 0
    from_browser: bool = False  # browser downloads may need confirmation


class ConfirmRequest(BaseModel):
    connections: int | None = None
    filename: str | None = None


class SettingsPatch(BaseModel):
    intercept_enabled: bool | None = None
    auto_start: bool | None = None
    intercept_all: bool | None = None
    minimize_to_tray: bool | None = None
    start_with_windows: bool | None = None
    extensions: list[str] | None = None
    connections: int | None = None
    download_limit_bps: int | None = None
    clipboard_enabled: bool | None = None
    disk_guard_enabled: bool | None = None
    disk_reserve_mb: int | None = None
    start_with_windows: bool | None = None
    auto_update_check: bool | None = None
    minimize_to_tray: bool | None = None


class ClipboardRequest(BaseModel):
    url: str


class SpeedLimitRequest(BaseModel):
    # Zero removes the limit, matching aria2's option semantics.
    bytes_per_second: int


def _committed_bytes(items: list[dict]) -> int:
    """Additional disk every unfinished download still needs.

    Checking one download against free space doesn't compose: two 150 GB
    downloads each fit in 200 GB free, but together they don't. Summing what
    the whole queue still needs is the only figure that catches that.

    The subtlety is that "still needs" is not ``total - completed``. A
    segmented download writes at high offsets immediately -- with 8 connections
    the last one starts near the end of the file -- and NTFS zero-fills
    everything up to that point. So a download that has fetched 90 MB of a
    4 GB file has *already* taken 4 GB of disk. Counting the remaining 3.9 GB
    again would double-count and raise a false alarm.

    So each item's claim is measured against what its file already occupies
    (``onDisk``), falling back to ``completed`` when the file can't be stat'ed.
    Downloads whose size the server never reported (``total == 0``) contribute
    nothing, so the result is a lower bound rather than a guarantee.
    """
    total_needed = 0
    for i in items:
        if i.get("status") not in UNFINISHED:
            continue
        total = int(i.get("total", 0))
        # Whichever is larger is what the volume has already absorbed.
        absorbed = max(int(i.get("completed", 0)), int(i.get("onDisk", 0)))
        total_needed += max(0, total - absorbed)
    return total_needed


def _with_on_disk_sizes(items: list[dict]) -> list[dict]:
    """Annotate each unfinished item with the size its file already occupies."""
    out = []
    for i in items:
        if i.get("status") in UNFINISHED and i.get("path"):
            try:
                i = {**i, "onDisk": os.path.getsize(i["path"])}
            except OSError:  # not created yet, or on a volume we can't read
                pass
        out.append(i)
    return out


# aria2 error codes worth retrying: unknown (TLS handshake drops land here),
# timeout, network problem, DNS failure, temporary server overload. aria2's own
# --max-tries does not cover all of these (a TLS failure ends the download), so
# the bridge re-queues them itself and aria2 resumes from the partial file.
TRANSIENT_ERROR_CODES = {"1", "2", "6", "19", "29"}
RETRY_DELAY_SECONDS = 5.0
# Origins of the Tauri desktop UI: production (Windows serves the bundle from
# http://tauri.localhost) and the Vite dev server.
TAURI_ORIGINS = ["http://tauri.localhost", "tauri://localhost", "http://localhost:1420"]
MAX_AUTO_RETRIES = 30
_RETRY_OPTION_KEYS = (
    "dir",
    "header",
    "referer",
    "user-agent",
    "split",
    "max-connection-per-server",
    "max-download-limit",
)


def _url_extension(url: str) -> str:
    """Extension of the file a URL points at, lowercased, query stripped."""
    name = url.split("?", 1)[0].split("#", 1)[0].rsplit("/", 1)[-1]
    return ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""


def _normalize(item: dict) -> dict:
    files = item.get("files") or []
    path = files[0].get("path") if files else ""
    name = (path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]) if path else ""
    if not name and files and files[0].get("uris"):
        # Failed before the server named the file: show the URL's last segment.
        uri = files[0]["uris"][0].get("uri", "")
        name = uri.split("?", 1)[0].split("#", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    total = int(item.get("totalLength", 0) or 0)
    done = int(item.get("completedLength", 0) or 0)
    return {
        "gid": item.get("gid"),
        "status": item.get("status"),
        "name": name,
        "total": total,
        "completed": done,
        "speed": int(item.get("downloadSpeed", 0) or 0),
        "progress": (done / total) if total else 0.0,
        "error": item.get("errorMessage", ""),
        "errorCode": str(item.get("errorCode", "") or ""),
        "path": path,
    }


def _open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _reveal_path(path: Path) -> None:
    if sys.platform == "win32":
        # Explorer needs quotes around the path only. Passing a list makes
        # subprocess quote the entire /select argument when it contains spaces.
        subprocess.Popen(f'explorer.exe /select,"{path.resolve()}"')
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


def create_app(
    cfg: Config, auth_token: str | None = None, updater: Updater | None = None
) -> FastAPI:
    manager = Aria2Manager(cfg.aria2, cfg.downloads.resolve_directory())
    client = Aria2Client(cfg.aria2.rpc_url, cfg.aria2.rpc_secret)
    store = SettingsStore()
    updater = updater or Updater()
    clients: set[WebSocket] = set()
    pending: dict[str, dict] = {}  # id -> pending download awaiting confirmation
    # Hydrated once from aria2 for restored downloads and updated whenever the
    # user changes a limit. This avoids one getOption RPC per item every tick.
    download_limits: dict[str, int] = {}
    # Disk guard bookkeeping: which downloads *we* paused, so a resume only
    # touches those and never revives something the user paused by hand.
    guard_state: dict = {"tripped": False, "paused_gids": []}
    # Bumped by /api/focus. A second launch asks the running instance to come
    # to the front instead of opening another window; the UI watches this
    # counter in the broadcast rather than needing a channel of its own.
    focus_state: dict = {"count": 0}
    browser_downloads: dict = {"count": 0}
    # Auto-retry bookkeeping, keyed by file path so attempts accumulate across
    # the new gid each re-queue gets: {"attempts": int, "due": monotonic}.
    retry_state: dict[str, dict] = {}

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        manager.start()
        app.state.limit_applier = asyncio.create_task(_restore_global_limit())
        app.state.broadcaster = asyncio.create_task(_broadcast_loop())
        app.state.update_checker = asyncio.create_task(
            updater.run_periodic(lambda: store.settings.auto_update_check)
        )
        try:
            yield
        finally:
            app.state.update_checker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await app.state.update_checker
            app.state.limit_applier.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await app.state.limit_applier
            app.state.broadcaster.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await app.state.broadcaster
            await client.aclose()
            manager.stop()

    app = FastAPI(title="stz-downloader bridge", lifespan=lifespan)

    @app.middleware("http")
    async def authenticate_local_client(request: Request, call_next):
        if auth_token and request.url.path.startswith("/api/"):
            supplied = request.headers.get("Authorization", "")
            expected = f"Bearer {auth_token}"
            if not secrets.compare_digest(supplied, expected):
                return JSONResponse({"detail": "unauthorized local client"}, status_code=401)
        return await call_next(request)

    # The Tauri desktop UI is a web page on its own origin. Added after the auth
    # middleware so it wraps it: CORS preflights carry no token and must be
    # answered before authentication runs.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=TAURI_ORIGINS,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    async def _start(req: DownloadRequest) -> str:
        n = req.connections or store.settings.connections
        return await client.add_uri(
            [req.url],
            out=req.filename,
            headers=req.headers,
            cookies=req.cookies,
            referer=req.referer,
            user_agent=req.user_agent,
            connections=n,
        )

    async def _restore_global_limit() -> None:
        """Apply the persisted limit once aria2's RPC socket is ready."""
        for _ in range(50):
            try:
                await client.change_global_option({
                    "max-overall-download-limit": str(store.settings.download_limit_bps)
                })
                return
            except Exception:
                await asyncio.sleep(0.1)

    async def _item_limit(gid: str) -> int:
        if gid not in download_limits:
            try:
                options = await client.get_option(gid)
                download_limits[gid] = int(options.get("max-download-limit", 0) or 0)
            except Exception:
                # aria2 may still be starting; leave it uncached so the next
                # snapshot retries instead of displaying unlimited forever.
                return 0
        return download_limits[gid]

    async def _snapshot() -> list[dict]:
        active = await client.tell_active(PROGRESS_KEYS)
        waiting = await client.tell_waiting(0, 100)
        stopped = await client.tell_stopped(0, 100)
        items = [_normalize(i) for i in (*active, *waiting, *stopped)]
        limits = await asyncio.gather(*(_item_limit(i["gid"]) for i in items))
        return [{**item, "speedLimit": limit} for item, limit in zip(items, limits)]

    async def _global_stat() -> dict:
        stat = await client.get_global_stat()
        return {
            "downloadSpeed": int(stat.get("downloadSpeed", 0) or 0),
            "numActive": int(stat.get("numActive", 0) or 0),
        }

    def _disk_report(items: list[dict]) -> dict:
        """Free space on the download volume vs. what the queue still needs."""
        target = cfg.downloads.resolve_directory()
        try:
            usage = shutil.disk_usage(target if target.exists() else target.anchor)
        except OSError:  # volume unavailable (unplugged drive, etc.)
            return {"available": False}

        committed = _committed_bytes(_with_on_disk_sizes(items))
        reserve = max(0, store.settings.disk_reserve_mb) * 1024 * 1024
        usable = max(0, usage.free - reserve)
        return {
            "available": True,
            "path": str(target),
            "free": usage.free,
            "reserve": reserve,
            "committed": committed,
            # How much more disk the queue needs than it can possibly get.
            "shortfall": max(0, committed - usable),
            "guardTripped": guard_state["tripped"],
        }

    async def _disk_guard(items: list[dict], disk: dict) -> None:
        """Pause everything before the volume fills, and resume once it hasn't.

        Letting aria2 hit ENOSPC works (``--continue=true`` means a retry costs
        no bytes) but it surfaces as a hard error and the user has to notice
        and act. Stopping just above the floor keeps the queue in a state that
        resumes cleanly.
        """
        if not store.settings.disk_guard_enabled or not disk.get("available"):
            return
        reserve = disk["reserve"]
        free = disk["free"]

        if not guard_state["tripped"] and free <= reserve:
            gids = [i["gid"] for i in items if i.get("status") == "active"]
            for gid in gids:
                with contextlib.suppress(Exception):
                    await client.pause(gid)
            if gids:
                guard_state["tripped"] = True
                guard_state["paused_gids"] = gids
        # Only resume once there is real headroom again, so a download that
        # immediately re-fills the disk doesn't thrash pause/resume.
        elif guard_state["tripped"] and free > reserve * 2:
            for gid in guard_state["paused_gids"]:
                with contextlib.suppress(Exception):
                    await client.unpause(gid)
            guard_state["tripped"] = False
            guard_state["paused_gids"] = []

    async def _download_path(gid: str) -> Path:
        item = await client.tell_status(gid, ["files"])
        files = item.get("files") or []
        raw_path = files[0].get("path") if files else ""
        if not raw_path:
            raise HTTPException(404, "download path not found")
        path = Path(raw_path)
        if not path.exists():
            raise HTTPException(404, "download file not found")
        return path

    async def _requeue(gid: str) -> str | None:
        """Start a stopped download again as a new aria2 entry.

        Keeps its URL, headers (cookies), referer, connections and limit, and
        writes to the same file so aria2 continues the partial download.
        Returns the new gid, or None when there is no URL to retry.
        """
        status = await client.tell_status(gid, ["files"])
        files = status.get("files") or [{}]
        uris = list(dict.fromkeys(u["uri"] for u in files[0].get("uris", [])))
        if not uris:
            return None
        old = await client.get_option(gid)
        options = {k: old[k] for k in _RETRY_OPTION_KEYS if k in old}
        path = files[0].get("path") or ""
        name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if name:
            # Same file name and no renaming, so aria2 continues the partial
            # file instead of starting a "name(1).ext" copy.
            options["out"] = name
        options["continue"] = "true"
        options["auto-file-renaming"] = "false"
        new_gid = await client.add_uri_with_options(uris, options)
        if gid in download_limits:
            download_limits[new_gid] = download_limits.pop(gid)
        with contextlib.suppress(Exception):
            await client.remove_download_result(gid)
        return new_gid

    async def _auto_retry(items: list[dict]) -> None:
        """Re-queue downloads that died on a transient network error."""
        now = time.monotonic()
        for item in items:
            key = item["path"] or item["gid"]
            if item["status"] == "complete":
                retry_state.pop(key, None)
                continue
            if item["status"] != "error" or item.get("errorCode") not in TRANSIENT_ERROR_CODES:
                continue
            state = retry_state.setdefault(key, {"attempts": 0, "due": None})
            if state["attempts"] >= MAX_AUTO_RETRIES:
                continue
            if state["due"] is None:
                state["due"] = now + RETRY_DELAY_SECONDS
                continue
            if now < state["due"]:
                continue
            if await _requeue(item["gid"]) is None:
                continue
            state["attempts"] += 1
            state["due"] = None

    async def _broadcast_loop() -> None:
        while True:
            await asyncio.sleep(1.0)
            # The guard runs whether or not anyone is watching: in --headless
            # mode the extension queues downloads with no UI attached, and
            # gating this on connected clients left the disk unprotected
            # exactly when nobody was there to notice it filling up.
            try:
                items = await _snapshot()
                disk = _disk_report(items)
                await _disk_guard(items, disk)
                await _auto_retry(items)
            except Exception:  # aria2 may be momentarily unavailable
                continue
            if not clients:
                continue
            try:
                payload = {
                    "type": "downloads",
                    "items": items,
                    "pending": list(pending.values()),
                    "global": await _global_stat(),
                    "disk": disk,
                    # Ships with every tick so the UI converges on the real
                    # settings even if its one-shot load at startup lost the
                    # race against the bridge coming up.
                    "settings": store.settings.model_dump(),
                    "focus": focus_state["count"],
                    "browserDownloads": browser_downloads["count"],
                    "update": updater.snapshot(),
                }
            except Exception:  # aria2 may be momentarily unavailable
                continue
            dead = set()
            for ws in clients:
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead.add(ws)
            clients.difference_update(dead)

    @app.get("/api/health")
    async def health() -> dict:
        return {
            "ok": True,
            "app": "stz-downloader",
            "protocol": 1,
            "aria2": manager.is_running(),
        }

    @app.post("/api/focus")
    async def focus() -> dict:
        """Ask the running UI to show itself (second-launch handoff)."""
        focus_state["count"] += 1
        return {"ok": True, "focus": focus_state["count"]}

    # -- settings -------------------------------------------------------
    @app.get("/api/settings")
    async def get_settings() -> dict:
        return store.settings.model_dump()

    @app.put("/api/settings")
    async def put_settings(patch: SettingsPatch) -> dict:
        changes = patch.model_dump(exclude_none=True)
        if "start_with_windows" in changes and autostart.supported():
            # Store what Windows actually accepted, not just what was asked.
            changes["start_with_windows"] = autostart.apply(changes["start_with_windows"])
        if "download_limit_bps" in changes:
            limit = changes["download_limit_bps"]
            if limit < 0:
                raise HTTPException(422, "speed limit cannot be negative")
            # Persist first. If aria2 is still opening its RPC socket, the
            # retry task reads this new value and applies it as soon as the
            # engine is ready instead of losing the user's setting.
            updated = store.update(changes)
            try:
                await client.change_global_option({
                    "max-overall-download-limit": str(limit)
                })
            except Exception:
                if app.state.limit_applier.done():
                    app.state.limit_applier = asyncio.create_task(_restore_global_limit())
            return updated.model_dump()
        return store.update(changes).model_dump()

    # -- downloads ------------------------------------------------------
    @app.post("/api/download")
    async def add_download(req: DownloadRequest) -> dict:
        # Browser downloads honour auto_start; manual adds always start now.
        if req.from_browser and not store.settings.auto_start:
            pid = uuid.uuid4().hex
            pending[pid] = {
                "id": pid,
                "url": req.url,
                "name": req.filename or req.url.rsplit("/", 1)[-1].split("?")[0],
                "size": req.filesize,
                "referer": req.referer,
                "user_agent": req.user_agent,
                "cookies": req.cookies,
                "headers": req.headers,
            }
            return {"pending": pid}
        gid = await _start(req)
        if req.from_browser:
            browser_downloads["count"] += 1
        return {"gid": gid, "started": True}

    @app.post("/api/clipboard")
    async def clipboard_hit(req: ClipboardRequest) -> dict:
        """Offer a URL copied to the clipboard, IDM-style.

        Always routes through the confirmation queue even when ``auto_start``
        is on: that setting is about downloads the user already initiated in
        the browser. Silently downloading whatever lands on the clipboard
        would be a nasty surprise.
        """
        url = req.url.strip()
        if not store.settings.clipboard_enabled:
            return {"accepted": False, "reason": "disabled"}
        if not URL_RE.match(url):
            return {"accepted": False, "reason": "not-a-url"}
        if not store.settings.intercept_all:
            if _url_extension(url) not in store.settings.extensions:
                return {"accepted": False, "reason": "filtered"}
        # The only de-duplication left is against a prompt that is still on
        # screen. Remembering the last URL forever meant copying the same link
        # a second time -- a deliberate, repeatable action -- did nothing.
        if any(p["url"] == url for p in pending.values()):
            return {"accepted": False, "reason": "already-pending"}

        pid = uuid.uuid4().hex
        pending[pid] = {
            "id": pid,
            "url": url,
            "name": url.rsplit("/", 1)[-1].split("?")[0],
            "size": 0,  # unknown until aria2 fetches the headers
            "referer": None,
            "user_agent": None,
            "cookies": None,
            "headers": {},
            "source": "clipboard",
        }
        return {"accepted": True, "pending": pid}

    @app.get("/api/pending")
    async def list_pending() -> dict:
        return {"pending": list(pending.values())}

    @app.post("/api/pending/{pid}/confirm")
    async def confirm_pending(pid: str, body: ConfirmRequest) -> dict:
        p = pending.pop(pid, None)
        if not p:
            raise HTTPException(404, "pending not found")
        req = DownloadRequest(
            url=p["url"],
            filename=body.filename or p["name"],
            referer=p.get("referer"),
            user_agent=p.get("user_agent"),
            cookies=p.get("cookies"),
            headers=p.get("headers") or {},
            connections=body.connections,
        )
        return {"gid": await _start(req), "started": True}

    @app.post("/api/pending/{pid}/cancel")
    async def cancel_pending(pid: str) -> dict:
        pending.pop(pid, None)
        return {"ok": True}

    @app.get("/api/downloads")
    async def list_downloads() -> dict:
        items = await _snapshot()
        return {
            "items": items,
            "pending": list(pending.values()),
            "global": await _global_stat(),
            "disk": _disk_report(items),
            "settings": store.settings.model_dump(),
            "focus": focus_state["count"],
            "browserDownloads": browser_downloads["count"],
        }

    @app.post("/api/downloads/{gid}/pause")
    async def pause(gid: str) -> dict:
        return {"gid": await client.pause(gid)}

    @app.post("/api/downloads/{gid}/resume")
    async def resume(gid: str) -> dict:
        return {"gid": await client.unpause(gid)}

    @app.post("/api/downloads/{gid}/cancel")
    async def cancel(gid: str) -> dict:
        result = await client.remove_any(gid)
        download_limits.pop(gid, None)
        return {"gid": result}

    @app.post("/api/downloads/{gid}/speed-limit")
    async def set_speed_limit(gid: str, body: SpeedLimitRequest) -> dict:
        if body.bytes_per_second < 0:
            raise HTTPException(422, "speed limit cannot be negative")
        try:
            await client.change_option(
                gid, {"max-download-limit": str(body.bytes_per_second)}
            )
        except Aria2Error as exc:
            # aria2 only changes options on active, waiting or paused items.
            raise HTTPException(409, f"download cannot be changed: {exc}") from exc
        download_limits[gid] = body.bytes_per_second
        return {
            "gid": gid,
            "bytes_per_second": body.bytes_per_second,
        }

    # -- self-update ----------------------------------------------------
    @app.get("/api/update")
    async def update_state() -> dict:
        return updater.snapshot()

    @app.post("/api/update/check")
    async def update_check() -> dict:
        return await updater.check()

    @app.post("/api/update/install")
    async def update_install() -> dict:
        try:
            return await updater.install()
        except UpdateError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/downloads/{gid}/restart")
    async def restart_download(gid: str) -> dict:
        """Start a cancelled or failed download again, IDM-style."""
        try:
            status = await client.tell_status(gid, ["status"])
        except Aria2Error as exc:
            raise HTTPException(404, "download not found") from exc
        if status.get("status") not in ("error", "removed"):
            raise HTTPException(409, "only cancelled or failed downloads can be restarted")
        new_gid = await _requeue(gid)
        if new_gid is None:
            raise HTTPException(409, "download has no URL to restart from")
        return {"gid": new_gid, "started": True}

    @app.post("/api/downloads/{gid}/open")
    async def open_download(gid: str) -> dict:
        _open_path(await _download_path(gid))
        return {"ok": True}

    @app.post("/api/downloads/{gid}/reveal")
    async def reveal_download(gid: str) -> dict:
        _reveal_path(await _download_path(gid))
        return {"ok": True}

    @app.post("/api/downloads/purge")
    async def purge() -> dict:
        result = await client.purge_download_results()
        download_limits.clear()
        return {"result": result}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        if auth_token:
            # Browsers cannot set headers on a WebSocket, so the web UI sends
            # the token as a query parameter instead.
            supplied = ws.headers.get("Authorization", "")
            if not supplied and ws.query_params.get("token"):
                supplied = f"Bearer {ws.query_params['token']}"
            if not secrets.compare_digest(supplied, f"Bearer {auth_token}"):
                await ws.close(code=1008, reason="unauthorized local client")
                return
        await ws.accept()
        clients.add(ws)
        try:
            while True:
                await ws.receive_text()  # keepalive / ignore
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(ws)

    return app
