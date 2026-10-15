// ViDow Browser-Helper — Manifest V3 Service Worker
// Speichert gefundene Video-Streams pro Tab in chrome.storage.session (keine globalen Variablen)

const AD_URL_REGEX = /(doubleclick\.net|googlesyndication\.com|imasdk\.googleapis\.com|smartclip\.net|fwmrm\.net|adnxs\.com|spotxchange\.com|teads\.tv|pubmatic\.com|rubiconproject\.com|2mdn\.net|innovid\.com|[/_.-](vast|vmap|preroll|midroll|adserver|adbreak)[/_.-]?)/i;
const STREAM_URL_REGEX = /\.(m3u8|mpd|mp4|webm|m4v|mov)(\?|$)/i;

async function recordStreamForTab(tabId, streamUrl, streamType) {
  if (tabId < 0) return;
  if (AD_URL_REGEX.test(streamUrl)) return;

  try {
    const key = `streams_${tabId}`;
    const stored = await chrome.storage.session.get(key);
    const list = Array.isArray(stored[key]) ? stored[key] : [];

    // Duplikate vermeiden
    if (list.some((item) => item.url === streamUrl)) return;

    list.unshift({
      url: streamUrl,
      type: streamType,
      timestamp: Date.now(),
    });

    const trimmed = list.slice(0, 15);
    await chrome.storage.session.set({ [key]: trimmed });
    await chrome.action.setBadgeText({ tabId, text: String(trimmed.length) });
    await chrome.action.setBadgeBackgroundColor({ tabId, color: "#2563eb" });
  } catch (err) {
    console.error("[ViDow SW] Fehler beim Speichern des Streams:", err);
  }
}

chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    if (details.tabId < 0) return;
    const url = details.url || "";
    if (! url.startsWith("http")) return;

    const match = url.match(STREAM_URL_REGEX);
    if (match) {
      const ext = match[1].toUpperCase();
      // Ignoriere winzige Video-Segmente (.ts / .m4s), erfasse nur Manifeste (.m3u8/.mpd) oder Vollvideos (.mp4/.webm)
      recordStreamForTab(details.tabId, url, ext);
    }
  },
  { urls: ["<all_urls>"] }
);

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo) => {
  if (changeInfo.status === "loading" && changeInfo.url) {
    try {
      const key = `streams_${tabId}`;
      await chrome.storage.session.remove(key);
      await chrome.action.setBadgeText({ tabId, text: "" });
    } catch (err) {
      console.error("[ViDow SW] Fehler beim Zurücksetzen des Tabs:", err);
    }
  }
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
  try {
    await chrome.storage.session.remove(`streams_${tabId}`);
  } catch (err) {
    console.error("[ViDow SW] Fehler beim Aufräumen des Tabs:", err);
  }
});
