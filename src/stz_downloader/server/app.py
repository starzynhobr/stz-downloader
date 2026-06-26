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
  WS   /ws                      <- UI subscribes to live updates

Bound to 127.0.0.1 only. CORS is opened for browser-extension origins.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
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
    extensions: list[str] | None = None
    connections: int | None = None


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
            if not clients:
                continue
            try:
                payload = {
                    "type": "downloads",
                    "items": await _snapshot(),
                    "pending": list(pending.values()),
                    "global": await _global_stat(),
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
        return {
            "items": await _snapshot(),
            "pending": list(pending.values()),
            "global": await _global_stat(),
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
