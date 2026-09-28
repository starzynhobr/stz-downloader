// stz downloader — browser integration (Chrome + Firefox/Floorp).
//
// Strategy (the "IDM" behaviour): when the browser starts a download, we
// cancel + erase it from the browser and hand the URL (with cookies, referer
// and user-agent) through the registered Native Messaging host, which finds
// the dynamically allocated local bridge and feeds aria2.
//
// The bridge owns the interception settings (the file-type filter, master
// toggle). We fetch them and decide *before* cancelling the browser download,
// so that filtered-out files still download normally in the browser.

// Cross-browser API alias. Firefox exposes promise-based `browser.*`;
// Chrome exposes `chrome.*` (promise-based in MV3 when no callback is given).
const api = globalThis.browser ?? globalThis.chrome;
const NATIVE_HOST = "com.stzlabs.downloader";

const DEFAULTS = {
  enabled: true, // local quick on/off (popup)
};

function msg(key) {
  return api.i18n.getMessage(key) || key;
}

async function getLocal() {
  const s = await api.storage.local.get(DEFAULTS);
  return { ...DEFAULTS, ...s };
}

async function nativeRequest(type, payload) {
  const response = await api.runtime.sendNativeMessage(NATIVE_HOST, { type, payload });
  if (!response?.ok) throw new Error(response?.error || "native host unavailable");
  return response.result;
}

// Cache the bridge settings briefly so we don't fetch on every event.
let _cfg = null;
let _cfgAt = 0;
async function bridgeSettings() {
  if (_cfg && Date.now() - _cfgAt < 8000) return _cfg;
  try {
    _cfg = await nativeRequest("settings");
    _cfgAt = Date.now();
  } catch (e) {
    /* keep stale cache or null */
  }
  return _cfg;
}

function extensionOf(name) {
  const clean = (name || "").toLowerCase().split("?")[0].split("#")[0];
  const dot = clean.lastIndexOf(".");
  return dot >= 0 ? clean.slice(dot) : "";
}

// Decide whether to intercept, using the bridge's filter. If the bridge is
// unreachable we default to intercepting (the POST will then just fail and we
// fall back to the browser).
function shouldIntercept(cfg, name, url) {
  if (!cfg) return true;
  if (!cfg.intercept_enabled) return false;
  if (cfg.intercept_all) return true;
  const ext = extensionOf(name) || extensionOf(url);
  if (!ext) return false; // no extension and not "intercept all" -> leave it
  return (cfg.extensions || []).some((e) => e.toLowerCase() === ext);
}

async function buildCookieHeader(url) {
  try {
    const cookies = await api.cookies.getAll({ url });
    return cookies.map((c) => `${c.name}=${c.value}`).join("; ");
  } catch (e) {
    return "";
  }
}

async function sendToBridge(item, fromBrowser) {
  const url = item.finalUrl || item.url;
  const cookies = await buildCookieHeader(url);
  const payload = {
    url,
    filename: item.filename ? item.filename.split(/[\\/]/).pop() : undefined,
    referer: item.referrer || undefined,
    user_agent: navigator.userAgent,
    cookies: cookies || undefined,
    headers: {},
    filesize: item.fileSize > 0 ? item.fileSize : item.totalBytes > 0 ? item.totalBytes : 0,
    from_browser: !!fromBrowser,
  };
  await nativeRequest("download", payload);
}

async function flashBadge() {
  api.action.setBadgeText({ text: "↓" });
  api.action.setBadgeBackgroundColor({ color: "#4c8dff" });
  setTimeout(() => api.action.setBadgeText({ text: "" }), 1500);
}

api.downloads.onCreated.addListener(async (item) => {
  const { enabled } = await getLocal();
  if (!enabled) return;
  if (item.state === "complete") return; // already done (e.g. from cache)

  const cfg = await bridgeSettings();
  if (!shouldIntercept(cfg, item.filename, item.finalUrl || item.url)) return;

  try {
    await sendToBridge(item, true);
    // Hand-off succeeded: stop the browser's own download.
    await api.downloads.cancel(item.id);
    await api.downloads.erase({ id: item.id });
    flashBadge();
  } catch (e) {
    // Bridge offline / refused: let the browser download normally.
    console.warn("stz-downloader bridge unavailable, falling back:", e);
  }
});

// Right-click "Baixar com stz downloader" forces interception regardless of filter.
api.runtime.onInstalled.addListener(() => {
  api.contextMenus.create({
    id: "stz-download-link",
    title: msg("contextMenuDownload"),
    contexts: ["link", "video", "audio", "image"],
  });
});

api.contextMenus.onClicked.addListener(async (info) => {
  const url = info.linkUrl || info.srcUrl;
  if (!url) return;
  try {
    await sendToBridge({ url, referrer: info.pageUrl }, true);
    flashBadge();
  } catch (e) {
    console.warn("stz-downloader send failed:", e);
  }
});
