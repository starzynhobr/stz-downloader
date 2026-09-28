const api = globalThis.browser ?? globalThis.chrome;
const NATIVE_HOST = "com.stzlabs.downloader";
const DEFAULTS = { enabled: true };

const $ = (id) => document.getElementById(id);

function msg(key) {
  return api.i18n.getMessage(key) || key;
}

function localize() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = msg(el.dataset.i18n);
  });
  document.title = msg("appName");
}

async function load() {
  const s = { ...DEFAULTS, ...(await api.storage.local.get(DEFAULTS)) };
  $("enabled").checked = s.enabled;
  ping();
}

async function ping() {
  const el = $("status");
  try {
    const response = await api.runtime.sendNativeMessage(NATIVE_HOST, { type: "status" });
    if (!response?.ok) throw new Error(response?.error || "offline");
    const j = response.result;
    el.textContent = j.aria2 ? msg("statusConnected") : msg("statusNoAria2");
    el.className = "status " + (j.aria2 ? "ok" : "bad");
  } catch {
    el.textContent = msg("statusOffline");
    el.className = "status bad";
  }
}

$("enabled").addEventListener("change", (e) =>
  api.storage.local.set({ enabled: e.target.checked })
);

localize();
load();
