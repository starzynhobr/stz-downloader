//! IDM-style clipboard capture: a link copied anywhere is offered to the
//! bridge, which applies the file-type filter and queues a confirmation.
//!
//! The clipboard is only read while the user has the setting on, and only when
//! Windows reports a new copy. Whatever is already on the clipboard when
//! watching starts is the baseline, so turning the feature on never offers
//! something copied an hour ago, while copying the same link again does.

use std::thread;
use std::time::{Duration, Instant};

use crate::{read_bridge_info, BridgeInfo};

/// Bumped by Windows on every copy, even of identical text.
#[cfg(windows)]
fn copy_counter() -> u32 {
    #[link(name = "user32")]
    unsafe extern "system" {
        fn GetClipboardSequenceNumber() -> u32;
    }
    unsafe { GetClipboardSequenceNumber() }
}

#[cfg(not(windows))]
fn copy_counter() -> u32 {
    0
}

const POLL: Duration = Duration::from_millis(700);
const SETTINGS_REFRESH: Duration = Duration::from_secs(3);

fn agent() -> ureq::Agent {
    ureq::AgentBuilder::new().timeout(Duration::from_secs(3)).build()
}

fn clipboard_enabled(agent: &ureq::Agent, bridge: &BridgeInfo) -> bool {
    agent
        .get(&format!("{}/api/settings", bridge.base_url))
        .set("Authorization", &format!("Bearer {}", bridge.token))
        .call()
        .ok()
        .and_then(|r| r.into_json::<serde_json::Value>().ok())
        .and_then(|v| v.get("clipboard_enabled").and_then(|b| b.as_bool()))
        .unwrap_or(false)
}

fn offer(agent: &ureq::Agent, bridge: &BridgeInfo, url: &str) {
    let _ = agent
        .post(&format!("{}/api/clipboard", bridge.base_url))
        .set("Authorization", &format!("Bearer {}", bridge.token))
        .send_json(serde_json::json!({ "url": url }));
}

fn looks_like_link(text: &str) -> bool {
    let t = text.trim();
    (t.starts_with("http://") || t.starts_with("https://") || t.starts_with("ftp://"))
        && !t.contains(char::is_whitespace)
}

pub fn spawn_watcher() {
    thread::spawn(|| {
        let agent = agent();
        let mut clipboard: Option<arboard::Clipboard> = None;
        let mut enabled = false;
        let mut checked = Instant::now() - SETTINGS_REFRESH;
        let mut seen: Option<u32> = None;

        loop {
            thread::sleep(POLL);
            let Ok(bridge) = read_bridge_info() else { continue };

            if checked.elapsed() >= SETTINGS_REFRESH {
                let now_enabled = clipboard_enabled(&agent, &bridge);
                if now_enabled && !enabled {
                    seen = Some(copy_counter()); // baseline: ignore what's there now
                }
                enabled = now_enabled;
                checked = Instant::now();
            }
            if !enabled {
                clipboard = None;
                continue;
            }

            let counter = copy_counter();
            if seen == Some(counter) {
                continue;
            }
            if clipboard.is_none() {
                clipboard = arboard::Clipboard::new().ok();
            }
            let Some(cb) = clipboard.as_mut() else { continue };
            // Either no text (an image, files) or another app holds the
            // clipboard open; arboard already retries the latter briefly.
            seen = Some(counter);
            let Ok(text) = cb.get_text() else { continue };
            if looks_like_link(&text) {
                offer(&agent, &bridge, text.trim());
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::looks_like_link;

    #[test]
    fn only_single_urls_count_as_links() {
        assert!(looks_like_link("https://example.com/a.zip"));
        assert!(looks_like_link("  http://x.org/file.iso \n"));
        assert!(!looks_like_link("see https://example.com/a.zip"));
        assert!(!looks_like_link("just some text"));
        assert!(!looks_like_link("javascript:alert(1)"));
    }
}
