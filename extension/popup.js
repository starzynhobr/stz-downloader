const api = globalThis.browser ?? globalThis.chrome;
const DEFAULTS = { bridge: "http://127.0.0.1:8765", enabled: true };

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
  $("bridge").value = s.bridge;
  ping(s.bridge);
}

async function ping(bridge) {
  const el = $("status");
  try {
    const r = await fetch(`${bridge}/api/health`);
    const j = await r.json();
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
$("bridge").addEventListener("change", (e) => {
  api.storage.local.set({ bridge: e.target.value });
  ping(e.target.value);
});

localize();
load();
