// ViDow Browser-Helper — Popup Logic (Manifest V3, async/await only)

const VIDOW_SERVER = "http://127.0.0.1:8765";

const statusEl = document.getElementById("server-status");
const tabTitleEl = document.getElementById("tab-title");
const tabUrlEl = document.getElementById("tab-url");
const qualityEl = document.getElementById("ext-quality");
const codecEl = document.getElementById("ext-codec");
const btnSendPage = document.getElementById("btn-send-page");
const btnSkipAd = document.getElementById("btn-skip-ad");
const btnOpenDashboard = document.getElementById("btn-open-dashboard");
const streamsListEl = document.getElementById("streams-list");
const feedbackEl = document.getElementById("feedback");

let activeTab = null;
let serverSettings = {};

function setFeedback(text, isError = false) {
  feedbackEl.textContent = text;
  feedbackEl.style.color = isError ? "var(--danger)" : "var(--success)";
}

async function checkViDowServer() {
  try {
    const res = await fetch(`${VIDOW_SERVER}/api/status`);
    const data = await res.json();
    if (data.ok) {
      statusEl.textContent = "Verbunden";
      statusEl.style.color = "var(--success)";
      serverSettings = data.settings || {};
      if (serverSettings.quality) qualityEl.value = serverSettings.quality;
      if (serverSettings.codec) codecEl.value = serverSettings.codec;
      return true;
    }
  } catch (err) {
    statusEl.textContent = "Server offline";
    statusEl.style.color = "var(--danger)";
  }
  return false;
}

async function sendToViDow(targetUrl, title) {
  setFeedback("Sende an ViDow…");
  try {
    const payload = {
      url: targetUrl,
      title: title || (activeTab ? activeTab.title : "Video"),
      quality: qualityEl.value,
      codec: codecEl.value,
      container: "mp4",
      output_dir: serverSettings.output_dir || "~/Downloads/ViDow",
      skip_preroll_ads: true,
      headers: activeTab?.url ? { Referer: activeTab.url } : {},
    };
    const res = await fetch(`${VIDOW_SERVER}/api/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.ok) {
      setFeedback("✓ Download in ViDow gestartet!");
    } else {
      setFeedback(data.error || "Fehler beim Starten.", true);
    }
  } catch (err) {
    setFeedback("ViDow-Server nicht erreichbar (Starte ViDow.command).", true);
  }
}

async function scanDomStreamsInTab(tabId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId, allFrames: true },
      world: "MAIN",
      func: () => {
        const found = [];
        const adRe = /(doubleclick|googlesyndication|imasdk|smartclip|fwmrm|adnxs|spotx|teads|vast|vmap|preroll|midroll)/i;
        const add = (url, label) => {
          if (!url || typeof url !== "string" || !url.startsWith("http")) return;
          if (adRe.test(url)) return;
          if (!found.some((x) => x.url === url)) {
            found.push({ url, type: label });
          }
        };

        // 1. Prüfe window.flashvars_* (PornHub & diverse Tube-Player legen dort alle Qualitätsstufen ab)
        for (const key of Object.keys(window)) {
          if (key.startsWith("flashvars_")) {
            const fv = window[key];
            if (fv && Array.isArray(fv.mediaDefinitions)) {
              for (const md of fv.mediaDefinitions) {
                if (md && md.videoUrl) {
                  const q = Array.isArray(md.quality) ? "HLS" : `${md.quality || ""}p`;
                  add(md.videoUrl, `${(md.format || "STREAM").toUpperCase()} ${q}`.trim());
                }
              }
            }
          }
        }

        // 2. Prüfe <video> und <source> Elemente im DOM
        for (const v of document.querySelectorAll("video, video source")) {
          const src = v.currentSrc || v.src;
          if (src && src.startsWith("http")) {
            add(src, "HTML5");
          }
        }

        // 3. Prüfe bereits geladene Netzwerk-Ressourcen im Tab (Performance API)
        for (const entry of performance.getEntriesByType("resource")) {
          const m = entry.name.match(/\.(m3u8|mpd|mp4|webm)(\?|$)/i);
          if (m) {
            add(entry.name, m[1].toUpperCase());
          }
        }

        return found;
      },
    });

    const combined = [];
    for (const frameResult of results || []) {
      for (const item of frameResult.result || []) {
        if (!combined.some((x) => x.url === item.url)) {
          combined.push(item);
        }
      }
    }
    return combined;
  } catch (err) {
    return [];
  }
}

async function loadTabAndStreams() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;
    activeTab = tab;
    tabTitleEl.textContent = tab.title || "Aktuelle Webseite";
    tabUrlEl.textContent = tab.url || "";

    const key = `streams_${tab.id}`;
    const stored = await chrome.storage.session.get(key);
    const swStreams = Array.isArray(stored[key]) ? stored[key] : [];
    const domStreams = tab.id ? await scanDomStreamsInTab(tab.id) : [];

    const streams = [...domStreams];
    for (const s of swStreams) {
      if (!streams.some((x) => x.url === s.url)) {
        streams.push(s);
      }
    }

    if (streams.length === 0) {
      streamsListEl.innerHTML =
        '<div class="tab-url">Noch keine direkten .m3u8/.mp4 Streams erkannt. Starte das Video kurz im Tab!</div>';
      return;
    }

    streamsListEl.innerHTML = "";
    for (const item of streams) {
      const row = document.createElement("div");
      row.className = "stream-item";

      const urlDiv = document.createElement("div");
      urlDiv.className = "stream-url";
      urlDiv.title = item.url;
      urlDiv.textContent = `[${item.type}] ${item.url}`;

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn-mini";
      btn.textContent = "Laden";
      btn.addEventListener("click", async () => {
        await sendToViDow(item.url, activeTab?.title || "Stream");
      });

      row.append(urlDiv, btn);
      streamsListEl.appendChild(row);
    }
  } catch (err) {
    console.error("[ViDow Popup] Fehler beim Laden des Tabs:", err);
  }
}

btnSendPage.addEventListener("click", async () => {
  if (!activeTab?.url) {
    setFeedback("Keine gültige Tab-URL gefunden.", true);
    return;
  }
  await sendToViDow(activeTab.url, activeTab.title);
});

btnSkipAd.addEventListener("click", async () => {
  if (!activeTab?.id) return;
  try {
    await chrome.scripting.executeScript({
      target: { tabId: activeTab.id, allFrames: true },
      func: () => {
        const skipSelectors = [
          ".ytp-ad-skip-button",
          ".ytp-ad-skip-button-modern",
          ".ytp-skip-ad-button",
          "[class*='skip-ad']",
          "[class*='skipAd']",
          "[id*='skip-ad']",
        ];
        for (const sel of skipSelectors) {
          const btn = document.querySelector(sel);
          if (btn instanceof HTMLElement) btn.click();
        }
        const videos = document.querySelectorAll("video");
        for (const v of videos) {
          if (Number.isFinite(v.duration) && v.duration > 0 && v.duration < 180) {
            v.muted = true;
            v.playbackRate = 16;
            v.currentTime = Math.max(0, v.duration - 0.1);
          }
        }
      },
    });
    setFeedback("⚡ Pre-Roll-Werbung im Tab vorgespult!");
  } catch (err) {
    setFeedback("Konnte auf dieser Seite nicht vorspulen.", true);
  }
});

btnOpenDashboard.addEventListener("click", async () => {
  const target = activeTab?.url
    ? `${VIDOW_SERVER}/?url=${encodeURIComponent(activeTab.url)}`
    : VIDOW_SERVER;
  await chrome.tabs.create({ url: target });
});

(async () => {
  await checkViDowServer();
  await loadTabAndStreams();
})();
