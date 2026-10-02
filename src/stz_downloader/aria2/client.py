"""Async JSON-RPC client for aria2.

See: https://aria2.github.io/manual/en/html/aria2c.html#rpc-interface
"""
from __future__ import annotations

import uuid
from typing import Any

import httpx


class Aria2Error(RuntimeError):
    pass


class Aria2Client:
    def __init__(self, rpc_url: str, secret: str):
        self.rpc_url = rpc_url
        self._token = f"token:{secret}"
        self._http = httpx.AsyncClient(timeout=15.0)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _call(self, method: str, *params: Any) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": method,
            # aria2 expects the secret token as the first param.
            "params": [self._token, *params],
        }
        resp = await self._http.post(self.rpc_url, json=payload)
        # aria2 returns the JSON-RPC error in the body even on HTTP 400, so
        # parse first and only fall back to raise_for_status if it isn't JSON.
        try:
            data = resp.json()
        except ValueError:
            resp.raise_for_status()
            raise
        if "error" in data:
            raise Aria2Error(data["error"].get("message", "unknown aria2 error"))
        return data["result"]

    # -- core operations -------------------------------------------------
    async def add_uri(
        self,
        uris: list[str],
        *,
        out: str | None = None,
        headers: dict[str, str] | None = None,
        cookies: str | None = None,
        referer: str | None = None,
        user_agent: str | None = None,
        connections: int | None = None,
    ) -> str:
        """Queue a download. Returns the GID. Passing the browser's request
        headers/cookies is what makes authenticated downloads work (the IDM
        trick). ``connections`` sets the number of parallel segments."""
        options: dict[str, Any] = {}
        if connections and connections > 0:
            # aria2 caps connections-per-server at 16.
            n = max(1, min(16, connections))
            options["split"] = str(n)
            options["max-connection-per-server"] = str(n)
        if out:
            options["out"] = out
        if referer:
            options["referer"] = referer
        if user_agent:
            options["user-agent"] = user_agent
        header_lines = [f"{k}: {v}" for k, v in (headers or {}).items()]
        if cookies:
            header_lines.append(f"Cookie: {cookies}")
        if header_lines:
            options["header"] = header_lines
        return await self._call("aria2.addUri", uris, options)

    async def add_uri_with_options(self, uris: list[str], options: dict[str, Any]) -> str:
        """``aria2.addUri`` with a ready-made options dict (used to re-queue)."""
        return await self._call("aria2.addUri", uris, options)

    async def remove(self, gid: str) -> str:
        return await self._call("aria2.remove", gid)

    async def remove_download_result(self, gid: str) -> str:
        """Remove a completed/errored/stopped download from memory."""
        return await self._call("aria2.removeDownloadResult", gid)

    async def remove_any(self, gid: str) -> str:
        """Cancel an active download, or clear a stopped/errored one.

        ``aria2.remove`` only works on active/waiting/paused entries; stopped
        ones must go through ``removeDownloadResult``."""
        try:
            return await self.remove(gid)
        except Aria2Error:
            return await self.remove_download_result(gid)

    async def purge_download_results(self) -> str:
        """Clear all stopped/completed/errored entries at once."""
        return await self._call("aria2.purgeDownloadResult")

    async def pause(self, gid: str) -> str:
        return await self._call("aria2.pause", gid)

    async def unpause(self, gid: str) -> str:
        return await self._call("aria2.unpause", gid)

    async def tell_status(self, gid: str, keys: list[str] | None = None) -> dict:
        return await self._call("aria2.tellStatus", gid, keys or [])

    async def tell_active(self, keys: list[str] | None = None) -> list[dict]:
        return await self._call("aria2.tellActive", keys or [])

    async def tell_waiting(self, offset: int = 0, num: int = 100) -> list[dict]:
        return await self._call("aria2.tellWaiting", offset, num)

    async def tell_stopped(self, offset: int = 0, num: int = 100) -> list[dict]:
        return await self._call("aria2.tellStopped", offset, num)

    async def get_global_stat(self) -> dict:
        return await self._call("aria2.getGlobalStat")

    async def get_option(self, gid: str) -> dict:
        """Return the mutable aria2 options for one download."""
        return await self._call("aria2.getOption", gid)

    async def change_option(self, gid: str, options: dict[str, Any]) -> str:
        """Apply options to an active, waiting, or paused download."""
        return await self._call("aria2.changeOption", gid, options)

    async def change_global_option(self, options: dict[str, Any]) -> str:
        """Apply mutable options shared by all downloads."""
        return await self._call("aria2.changeGlobalOption", options)
