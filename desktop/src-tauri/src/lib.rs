//! Desktop shell for STZ Downloader.
//!
//! The Python bridge (FastAPI + aria2) stays the engine. This shell starts it
//! headless, tells the web UI where it listens, and owns the window chrome the
//! old Qt UI had: tray icon, close-to-tray and single instance.

mod clipboard;

use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, RunEvent, WindowEvent};

/// The backend process this shell started, if it started one.
struct Backend(Mutex<Option<Child>>);

/// What the bridge publishes in `runtime.json` (see `runtime.py`).
#[derive(Deserialize)]
struct RuntimeFile {
    host: String,
    port: u16,
    token: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct BridgeInfo {
    pub(crate) base_url: String,
    pub(crate) token: String,
}

fn runtime_path() -> Option<PathBuf> {
    let base = std::env::var_os("LOCALAPPDATA").or_else(|| std::env::var_os("APPDATA"))?;
    Some(PathBuf::from(base).join("stz-downloader").join("runtime.json"))
}

/// Where the running bridge listens. The UI retries until this succeeds and
/// the bridge answers, which also covers a stale file from a previous run.
#[tauri::command]
fn bridge_info() -> Result<BridgeInfo, String> {
    read_bridge_info()
}

pub(crate) fn read_bridge_info() -> Result<BridgeInfo, String> {
    let path = runtime_path().ok_or("no per-user data directory")?;
    let text = std::fs::read_to_string(&path).map_err(|_| "bridge not running yet".to_string())?;
    let rt: RuntimeFile = serde_json::from_str(&text).map_err(|e| e.to_string())?;
    Ok(BridgeInfo {
        base_url: format!("http://{}:{}", rt.host, rt.port),
        token: rt.token,
    })
}

/// The command that runs the bridge headless.
///
/// Debug builds use the repository's virtualenv (override with STZ_PYTHON);
/// release builds expect the frozen engine (`stz-engine.exe`) next to this
/// executable.
fn backend_command() -> Command {
    let mut cmd = if cfg!(debug_assertions) {
        let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..");
        let python = std::env::var_os("STZ_PYTHON")
            .map(PathBuf::from)
            .unwrap_or_else(|| repo.join(".venv").join("Scripts").join("python.exe"));
        let mut c = Command::new(python);
        c.args(["-m", "stz_downloader", "--headless"]).current_dir(repo);
        c
    } else {
        // The frozen engine runs headless whatever its arguments say.
        let exe = std::env::current_exe().expect("current exe");
        let mut c = Command::new(exe.with_file_name("stz-engine.exe"));
        c.arg("--headless");
        c
    };
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd
}

fn show_main(app: &AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.unminimize();
        let _ = win.show();
        let _ = win.set_focus();
    }
}

fn stop_backend(app: &AppHandle) {
    if let Some(mut child) = app.state::<Backend>().0.lock().unwrap().take() {
        let _ = child.kill();
        let _ = child.wait();
    }
}

pub fn run() {
    tauri::Builder::default()
        // Must be registered first: a second launch just focuses this one.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show_main(app)))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .manage(Backend(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![bridge_info])
        .setup(|app| {
            // If a bridge is already running (another copy, or the old Qt app),
            // the headless process hands off to it and exits; the UI then finds
            // that bridge through runtime.json all the same.
            match backend_command().spawn() {
                Ok(child) => *app.state::<Backend>().0.lock().unwrap() = Some(child),
                Err(e) => eprintln!("could not start the backend: {e}"),
            }

            let show = MenuItem::with_id(app, "show", "Open STZ Downloader", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            TrayIconBuilder::with_id("main")
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("STZ Downloader")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => show_main(app),
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        show_main(tray.app_handle());
                    }
                })
                .build(app)?;

            clipboard::spawn_watcher();

            // Launched at login: stay in the tray until the user opens it.
            if !std::env::args().any(|a| a == "--minimized") {
                show_main(app.handle());
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            // Closing the window keeps downloads running in the tray.
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building the app")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                stop_backend(app);
            }
        });
}
