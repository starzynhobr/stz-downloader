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
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..aria2 import Aria2Client, Aria2Manager
from ..config import Config
from ..settings import SettingsStore

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
    clipboard_enabled: bool | None = None
    disk_guard_enabled: bool | None = None
    disk_reserve_mb: int | None = None
    start_with_windows: bool | None = None
    minimize_to_tray: bool | None = None


class ClipboardRequest(BaseModel):
    url: str


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


def _url_extension(url: str) -> str:
    """Extension of the file a URL points at, lowercased, query stripped."""
    name = url.split("?", 1)[0].split("#", 1)[0].rsplit("/", 1)[-1]
    return ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""


def _normalize(item: dict) -> dict:
    files = item.get("files") or []
    path = files[0].get("path") if files else ""
    total = int(item.get("totalLength", 0) or 0)
    done = int(item.get("completedLength", 0) or 0)
    return {
        "gid": item.get("gid"),
        "status": item.get("status"),
        "name": (path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]) if path else "",
        "total": total,
        "completed": done,
        "speed": int(item.get("downloadSpeed", 0) or 0),
        "progress": (done / total) if total else 0.0,
        "error": item.get("errorMessage", ""),
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
        subprocess.Popen(["explorer", f"/select,{path}"])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


def create_app(cfg: Config) -> FastAPI:
    app = FastAPI(title="stz-downloader bridge")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # local-only server; extension origins vary
        allow_methods=["*"],
        allow_headers=["*"],
    )

    manager = Aria2Manager(cfg.aria2, cfg.downloads.resolve_directory())
    client = Aria2Client(cfg.aria2.rpc_url, cfg.aria2.rpc_secret)
    store = SettingsStore()
    clients: set[WebSocket] = set()
    pending: dict[str, dict] = {}  # id -> pending download awaiting confirmation
    # Disk guard bookkeeping: which downloads *we* paused, so a resume only
    # touches those and never revives something the user paused by hand.
    guard_state: dict = {"tripped": False, "paused_gids": []}
    # Bumped by /api/focus. A second launch asks the running instance to come
    # to the front instead of opening another window; the UI watches this
    # counter in the broadcast rather than needing a channel of its own.
    focus_state: dict = {"count": 0}

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

    @app.on_event("startup")
    async def _startup() -> None:
        manager.start()
        app.state.broadcaster = asyncio.create_task(_broadcast_loop())

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        app.state.broadcaster.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.broadcaster
        await client.aclose()
        manager.stop()

    async def _snapshot() -> list[dict]:
        active = await client.tell_active(PROGRESS_KEYS)
        waiting = await client.tell_waiting(0, 100)
        stopped = await client.tell_stopped(0, 100)
        return [_normalize(i) for i in (*active, *waiting, *stopped)]

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
        return {"ok": True, "aria2": manager.is_running()}

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
        return store.update(patch.model_dump(exclude_none=True)).model_dump()

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
        }

    @app.post("/api/downloads/{gid}/pause")
    async def pause(gid: str) -> dict:
        return {"gid": await client.pause(gid)}

    @app.post("/api/downloads/{gid}/resume")
    async def resume(gid: str) -> dict:
        return {"gid": await client.unpause(gid)}

    @app.post("/api/downloads/{gid}/cancel")
    async def cancel(gid: str) -> dict:
        return {"gid": await client.remove_any(gid)}

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
        return {"result": await client.purge_download_results()}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
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
