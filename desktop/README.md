# STZ Downloader — desktop (Tauri)

React + Tailwind UI in a Tauri shell. The Python bridge (FastAPI + aria2) is
unchanged: the shell starts it with `--headless`, reads `runtime.json` to find
its port and token, and the UI talks to it over HTTP + WebSocket.

```
Tauri shell (Rust) ── spawns ──► python -m stz_downloader --headless
   │  tray, close-to-tray,             │ writes %LOCALAPPDATA%\stz-downloader\runtime.json
   │  single instance                  ▼
   └─ WebView (React) ── HTTP/WS + token ──► bridge ──► aria2c
```

## Run

Needs the repo's `.venv` set up (see the top-level README), Node 20+ and Rust.

```bash
cd desktop
npm install
npx tauri dev
```

Debug builds run the backend from `../.venv` (override with `STZ_PYTHON`).
Release builds expect the frozen `stz-engine.exe` next to the shell's exe.

To work on the UI in a normal browser, start the bridge yourself
(`python -m stz_downloader --headless`), copy `port` and `token` from
`runtime.json`, and run `npm run dev` with `VITE_BRIDGE_URL=http://127.0.0.1:<port>`
and `VITE_BRIDGE_TOKEN=<token>`.

## Build the installer

```powershell
.\scripts\build_installer.ps1 -Desktop
```

Produces `dist\stz-downloader-<version>-desktop-setup.exe` (the same Inno
installer as the Qt build, so upgrades, the native host and uninstall work the
same). The installed folder holds:

| File | Role |
|---|---|
| `stz-downloader.exe` | Tauri shell: UI, tray, clipboard watcher, single instance |
| `stz-engine.exe` | headless bridge + aria2, no Qt |
| `stz-downloader-native-host.exe` | browser Native Messaging helper |

The native host launches `stz-downloader.exe` when a browser download
arrives with the app closed, and "Start with Windows" registers it with
`--minimized`.
