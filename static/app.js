// ViDow 2.0 — Studio Frontend Application Logic

const els = {
  form: document.getElementById("download-form"),
  urlInput: document.getElementById("video-url"),
  btnPaste: document.getElementById("btn-paste"),
  btnAnalyze: document.getElementById("btn-analyze"),
  analyzeSpinner: document.getElementById("analyze-spinner"),
  analyzeIcon: document.getElementById("analyze-icon"),
  analyzeBtnText: document.getElementById("analyze-btn-text"),
  analysisPanel: document.getElementById("analysis-panel"),
  analysisThumb: document.getElementById("analysis-thumb"),
  analysisExtractor: document.getElementById("analysis-extractor"),
  analysisOrientation: document.getElementById("analysis-orientation"),
  analysisDuration: document.getElementById("analysis-duration"),
  analysisAdBadge: document.getElementById("analysis-ad-badge"),
  analysisTitle: document.getElementById("analysis-title"),
  analysisAvail: document.getElementById("analysis-avail"),
  tierChips: document.getElementById("tier-chips"),
  entriesContainer: document.getElementById("entries-container"),
  entriesList: document.getElementById("entries-list"),
  modeVideoBtn: document.getElementById("mode-video-btn"),
  modeAudioBtn: document.getElementById("mode-audio-btn"),
  qualitySelect: document.getElementById("quality-select"),
  codecField: document.getElementById("codec-field"),
  codecSelect: document.getElementById("codec-select"),
  containerField: document.getElementById("container-field"),
  containerSelect: document.getElementById("container-select"),
  audioFormatField: document.getElementById("audio-format-field"),
  audioFormatSelect: document.getElementById("audio-format-select"),
  recodeRow: document.getElementById("recode-row"),
  recodeCheckbox: document.getElementById("recode-checkbox"),
  outputDirInput: document.getElementById("output-dir"),
  btnPickFolder: document.getElementById("btn-pick-folder"),
  btnOpenFolder: document.getElementById("btn-open-folder"),
  recentDirs: document.getElementById("recent-dirs"),
  skipPrerollCheckbox: document.getElementById("skip-preroll-checkbox"),
  minDurationInput: document.getElementById("min-duration-input"),
  sponsorblockCheckbox: document.getElementById("sponsorblock-checkbox"),
  cookiesBrowserSelect: document.getElementById("cookies-browser-select"),
  protectionSummaryPill: document.getElementById("protection-summary-pill"),
  customTitleInput: document.getElementById("custom-title"),
  btnDownload: document.getElementById("btn-download"),
  jobsList: document.getElementById("jobs-list"),
  jobsCountBadge: document.getElementById("jobs-count-badge"),
  btnClearJobs: document.getElementById("btn-clear-jobs"),
  appVersion: document.getElementById("app-version"),
  statusYtdlp: document.getElementById("status-ytdlp"),
  statusFfmpeg: document.getElementById("status-ffmpeg"),
  systemThemeHint: document.getElementById("system-theme-hint"),
  toastStack: document.getElementById("toast-stack"),
};

let currentAnalysis = null;
let lastVideoQuality = "best";
let toastCounter = 0;

const DEFAULT_QUALITY_OPTIONS = Array.from(els.qualitySelect.options).map((opt) => ({
  value: opt.value,
  label: opt.textContent,
}));

// --- Theme Override (System / Light / Dark) ---
const colorSchemeMeta = document.querySelector('meta[name="color-scheme"]');
const darkMediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

function updateSystemThemeHint() {
  if (els.systemThemeHint) {
    els.systemThemeHint.textContent = darkMediaQuery.matches ? "(aktuell Dunkel)" : "(aktuell Hell)";
  }
}

function syncNativeWindowTheme(themeValue) {
  fetch("/api/window-theme", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ theme: themeValue }),
  }).catch(() => {});
}

function syncThemeControls() {
  let stored = null;
  try {
    stored = localStorage.getItem("color-scheme");
  } catch {}
  const activeVal = stored === "light" || stored === "dark" ? stored : "light dark";
  if (colorSchemeMeta) {
    colorSchemeMeta.content = activeVal;
  }
  for (const radio of document.querySelectorAll('input[name="theme_mode"]')) {
    radio.checked = radio.value === activeVal;
  }
  updateSystemThemeHint();
  syncNativeWindowTheme(activeVal);
}

const themePopoverEl = document.getElementById("theme-popover");

for (const radio of document.querySelectorAll('input[name="theme_mode"]')) {
  radio.addEventListener("change", () => {
    const val = radio.value;
    if (colorSchemeMeta) {
      colorSchemeMeta.content = val;
    }
    try {
      if (val === "light dark") {
        localStorage.removeItem("color-scheme");
      } else {
        localStorage.setItem("color-scheme", val);
      }
    } catch {}
    syncNativeWindowTheme(val);
    if (themePopoverEl) {
      try {
        themePopoverEl.hidePopover();
      } catch {}
    }
  });
}

darkMediaQuery.addEventListener("change", () => {
  updateSystemThemeHint();
  if (!colorSchemeMeta || colorSchemeMeta.content === "light dark") {
    syncNativeWindowTheme("light dark");
  }
});
window.addEventListener("storage", (e) => {
  if (e.key === "color-scheme") {
    syncThemeControls();
  }
});
syncThemeControls();

// --- Quality Options & Tier Chips ---
function resetQualityOptions() {
  const prevValue = els.qualitySelect.value || "best";
  els.qualitySelect.innerHTML = "";
  for (const item of DEFAULT_QUALITY_OPTIONS) {
    const opt = document.createElement("option");
    opt.value = item.value;
    opt.textContent = item.label;
    els.qualitySelect.appendChild(opt);
  }
  if (Array.from(els.qualitySelect.options).some((o) => o.value === prevValue)) {
    els.qualitySelect.value = prevValue;
  } else {
    els.qualitySelect.value = "best";
  }
  if (els.tierChips) {
    els.tierChips.hidden = true;
    els.tierChips.innerHTML = "";
  }
}

function renderTierChips(tiers) {
  if (!els.tierChips) return;
  els.tierChips.innerHTML = "";
  if (!Array.isArray(tiers) || !tiers.length) {
    els.tierChips.hidden = true;
    return;
  }
  els.tierChips.hidden = false;

  const updateSelectedChip = () => {
    const cur = els.qualitySelect.value;
    for (const btn of els.tierChips.querySelectorAll(".tier-chip")) {
      btn.classList.toggle("is-selected", btn.dataset.quality === cur);
    }
  };

  for (const t of tiers) {
    if (!t || typeof t.quality !== "number") continue;
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "tier-chip";
    chip.dataset.quality = String(t.quality);
    chip.textContent =
      t.resolution && t.resolution !== `${t.quality}p`
        ? `${t.quality}p • ${t.resolution}`
        : `${t.quality}p`;
    chip.addEventListener("click", () => {
      els.qualitySelect.value = String(t.quality);
      lastVideoQuality = String(t.quality);
      updateQualityModeUI();
      updateSelectedChip();
    });
    els.tierChips.appendChild(chip);
  }
  updateSelectedChip();
}

function syncQualityOptionsWithAnalysis(info) {
  const tiers = Array.isArray(info?.available_tiers) ? info.available_tiers : [];
  if (!tiers.length) {
    resetQualityOptions();
    return;
  }

  const prevValue = els.qualitySelect.value || "best";
  const tierMap = new Map();
  for (const t of tiers) {
    if (t && typeof t.quality === "number") {
      tierMap.set(String(t.quality), t.resolution || `${t.quality}p`);
    }
  }

  const numericMap = new Map();
  for (const item of DEFAULT_QUALITY_OPTIONS) {
    if (/^\d+$/.test(item.value)) {
      const resLabel = tierMap.get(item.value);
      numericMap.set(
        Number(item.value),
        resLabel ? `✓ ${item.label} — ${resLabel}` : item.label
      );
    }
  }
  for (const [qStr, resLabel] of tierMap.entries()) {
    const qNum = Number(qStr);
    if (!numericMap.has(qNum)) {
      numericMap.set(qNum, `✓ Video-Stufe ${resLabel} (max. ${qNum}p)`);
    }
  }

  const sortedNumeric = Array.from(numericMap.entries()).sort((a, b) => b[0] - a[0]);
  els.qualitySelect.innerHTML = "";

  const bestOpt = document.createElement("option");
  bestOpt.value = "best";
  const topRes = tiers[0]?.resolution ? ` — ${tiers[0].resolution}` : "";
  bestOpt.textContent = `Beste verfügbare Qualität (Auto${topRes})`;
  els.qualitySelect.appendChild(bestOpt);

  for (const [qNum, label] of sortedNumeric) {
    const opt = document.createElement("option");
    opt.value = String(qNum);
    opt.textContent = label;
    els.qualitySelect.appendChild(opt);
  }

  const audioDef = DEFAULT_QUALITY_OPTIONS.find((o) => o.value === "audio");
  const audioOpt = document.createElement("option");
  audioOpt.value = "audio";
  audioOpt.textContent = audioDef ? audioDef.label : "Nur Audio extrahieren";
  els.qualitySelect.appendChild(audioOpt);

  if (Array.from(els.qualitySelect.options).some((o) => o.value === prevValue)) {
    els.qualitySelect.value = prevValue;
  } else {
    els.qualitySelect.value = "best";
  }

  renderTierChips(tiers);
}

// --- Toast Notifications ---
function showToast(message, isError = false) {
  toastCounter += 1;
  const toastId = `vidow-toast-${toastCounter}`;
  const toast = document.createElement("div");
  toast.id = toastId;
  toast.setAttribute("popover", "manual");
  toast.className = isError ? "toast-popover toast-error" : "toast-popover";

  const msgSpan = document.createElement("span");
  msgSpan.textContent = message;

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "btn btn-ghost btn-sm";
  closeBtn.setAttribute("popovertarget", toastId);
  closeBtn.setAttribute("popovertargetaction", "hide");
  closeBtn.textContent = "✕";
  closeBtn.addEventListener("click", () => {
    try {
      toast.hidePopover();
    } catch {}
    toast.remove();
  });

  toast.append(msgSpan, closeBtn);
  els.toastStack.appendChild(toast);

  try {
    toast.showPopover();
  } catch {
    toast.classList.add("toast-fallback");
  }

  setTimeout(() => {
    try {
      toast.hidePopover();
    } catch {}
    toast.remove();
  }, 4200);
}

function updateProtectionSummary() {
  if (!els.protectionSummaryPill) return;
  const parts = [];
  if (els.skipPrerollCheckbox.checked) parts.push("Ad-Schutz");
  if (els.sponsorblockCheckbox.checked) parts.push("SponsorBlock");
  if (els.cookiesBrowserSelect.value && els.cookiesBrowserSelect.value !== "none") {
    parts.push(`${els.cookiesBrowserSelect.value}-Cookies`);
  }
  els.protectionSummaryPill.textContent = parts.length ? parts.join(" • ") : "Filter aus";
}

function updateQualityModeUI() {
  const isAudio = els.qualitySelect.value === "audio";
  if (!isAudio) {
    lastVideoQuality = els.qualitySelect.value || "best";
  }
  els.codecField.hidden = isAudio;
  els.containerField.hidden = isAudio;
  els.recodeRow.hidden = isAudio;
  els.audioFormatField.hidden = !isAudio;

  if (els.modeVideoBtn && els.modeAudioBtn) {
    els.modeVideoBtn.classList.toggle("is-active", !isAudio);
    els.modeAudioBtn.classList.toggle("is-active", isAudio);
  }
  if (els.tierChips && !els.tierChips.hidden) {
    const cur = els.qualitySelect.value;
    for (const btn of els.tierChips.querySelectorAll(".tier-chip")) {
      btn.classList.toggle("is-selected", btn.dataset.quality === cur);
    }
  }
}

els.modeVideoBtn?.addEventListener("click", () => {
  if (els.qualitySelect.value === "audio") {
    els.qualitySelect.value = lastVideoQuality === "audio" ? "best" : lastVideoQuality;
    updateQualityModeUI();
  }
});

els.modeAudioBtn?.addEventListener("click", () => {
  if (els.qualitySelect.value !== "audio") {
    lastVideoQuality = els.qualitySelect.value || "best";
    els.qualitySelect.value = "audio";
    updateQualityModeUI();
  }
});

function renderRecentDirs(dirs = []) {
  els.recentDirs.innerHTML = "";
  for (const dir of dirs) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "dir-chip";
    chip.textContent = dir;
    chip.title = `Speicherort setzen auf: ${dir}`;
    chip.addEventListener("click", () => {
      els.outputDirInput.value = dir;
    });
    els.recentDirs.appendChild(chip);
  }
}

function setStatusPillText(pillEl, label, isOk = true) {
  if (!pillEl) return;
  pillEl.className = isOk ? "pill pill-ok" : "pill pill-warn";
  pillEl.innerHTML = "";
  const dot = document.createElement("span");
  dot.className = "status-dot";
  dot.setAttribute("aria-hidden", "true");
  const txt = document.createElement("span");
  txt.textContent = label;
  pillEl.append(dot, txt);
}

async function initStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (!data.ok) return;

    if (els.appVersion && data.version) {
      els.appVersion.textContent = `v${data.version}`;
    }

    setStatusPillText(els.statusYtdlp, `yt-dlp ${data.yt_dlp_version}`, true);
    if (data.ffmpeg_available) {
      const ffLabel = data.ffmpeg_bundled ? "ffmpeg integriert" : "ffmpeg bereit";
      setStatusPillText(els.statusFfmpeg, ffLabel, true);
    } else {
      const tip = data.platform === "win32" ? "winget install Gyan.FFmpeg" : "brew install ffmpeg";
      setStatusPillText(els.statusFfmpeg, `ffmpeg fehlt (${tip})`, false);
    }

    window.vidowFileManagerLabel =
      data.file_manager_label || (data.platform === "win32" ? "Explorer" : "Finder");
    if (els.btnOpenFolder) {
      els.btnOpenFolder.textContent = `Im ${window.vidowFileManagerLabel} zeigen`;
      els.btnOpenFolder.title = `Aktuellen Zielordner im ${window.vidowFileManagerLabel} öffnen`;
    }
    if (data.default_output_dir && els.outputDirInput) {
      els.outputDirInput.placeholder = data.default_output_dir;
    }
    if (data.platform !== "darwin") {
      const safariOpt = document.getElementById("cookie-opt-safari");
      if (safariOpt) safariOpt.remove();
    } else {
      const ffOpt = els.cookiesBrowserSelect?.querySelector('option[value="firefox"]');
      if (ffOpt) ffOpt.textContent = "Mozilla Firefox";
    }
    if (els.btnPaste) {
      els.btnPaste.title =
        data.platform === "darwin"
          ? "URL aus Zwischenablage einfügen (⌘V)"
          : "URL aus Zwischenablage einfügen (Strg+V)";
    }

    const s = data.settings || {};
    if (s.output_dir) els.outputDirInput.value = s.output_dir;
    if (s.quality) els.qualitySelect.value = s.quality;
    if (s.codec) els.codecSelect.value = s.codec;
    if (s.container) els.containerSelect.value = s.container;
    if (s.audio_format) els.audioFormatSelect.value = s.audio_format;
    if (typeof s.skip_preroll_ads === "boolean") {
      els.skipPrerollCheckbox.checked = s.skip_preroll_ads;
    }
    if (typeof s.min_duration === "number") {
      els.minDurationInput.value = String(s.min_duration);
    }
    if (typeof s.sponsorblock === "boolean") {
      els.sponsorblockCheckbox.checked = s.sponsorblock;
    }
    if (s.cookies_browser) {
      els.cookiesBrowserSelect.value = s.cookies_browser;
    }
    renderRecentDirs(s.recent_dirs || []);
    updateQualityModeUI();
    updateProtectionSummary();

    if (data.output_dir_warning) {
      showToast(data.output_dir_warning, false);
    }

    const params = new URLSearchParams(window.location.search);
    const paramUrl = params.get("url");
    if (paramUrl) {
      els.urlInput.value = paramUrl;
      await handleAnalyze();
    }
  } catch {
    showToast("Verbindung zum lokalen ViDow-Server fehlgeschlagen.", true);
  }
}

async function handleAnalyze() {
  const url = els.urlInput.value.trim();
  if (!url) {
    showToast("Bitte zuerst eine Video-URL einfügen.", true);
    els.urlInput.focus();
    return;
  }

  els.btnAnalyze.disabled = true;
  els.analyzeSpinner.hidden = false;
  if (els.analyzeIcon) els.analyzeIcon.hidden = true;
  els.analyzeBtnText.textContent = "Prüfe…";

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        cookies_browser: els.cookiesBrowserSelect.value,
        min_duration: els.skipPrerollCheckbox.checked
          ? Number(els.minDurationInput.value || 0)
          : 0,
      }),
    });
    const data = await res.json();
    if (!data.ok) {
      showToast(data.error || "Analyse fehlgeschlagen.", true);
      return;
    }

    const info = data.analysis;
    currentAnalysis = info;
    els.analysisPanel.hidden = false;
    els.analysisTitle.textContent = info.title || "Video gefunden";
    els.analysisExtractor.textContent = info.extractor || "Stream";
    els.analysisDuration.textContent = `Dauer: ${info.duration_formatted || "—"}`;

    if (els.analysisOrientation) {
      els.analysisOrientation.hidden = false;
      els.analysisOrientation.textContent = info.is_vertical ? "Hochformat 9:16" : "Querformat";
    }

    if (info.thumbnail) {
      els.analysisThumb.src = info.thumbnail;
      els.analysisThumb.classList.toggle("is-vertical", Boolean(info.is_vertical));
      els.analysisThumb.width = info.is_vertical ? 72 : 160;
      els.analysisThumb.height = info.is_vertical ? 128 : 90;
      els.analysisThumb.hidden = false;
    } else {
      els.analysisThumb.hidden = true;
    }

    if (info.ad_filtered_count > 0) {
      els.analysisAdBadge.hidden = false;
      els.analysisAdBadge.textContent = `${info.ad_filtered_count} Werbe-Clip(s) gefiltert`;
    } else {
      els.analysisAdBadge.hidden = true;
    }

    const tiers = Array.isArray(info.available_tiers) ? info.available_tiers : [];
    const heightsText = tiers.length
      ? `Qualitätsstufen: ${tiers.map((t) => `${t.quality}p`).join(", ")}`
      : (info.available_heights || []).length
      ? `Qualitätsstufen: ${info.available_heights.map((h) => `${h}p`).join(", ")}`
      : "Beste Stream-Auflösung wird automatisch gewählt";
    const codecsText = (info.available_codecs || []).length
      ? ` • Codecs: ${info.available_codecs.map((c) => c.toUpperCase()).join(", ")}`
      : "";
    els.analysisAvail.textContent = `${heightsText}${codecsText}`;
    syncQualityOptionsWithAnalysis(info);

    const entries = info.entries || [];
    if (entries.length > 1) {
      els.entriesContainer.hidden = false;
      els.entriesList.innerHTML = "";
      for (const entry of entries) {
        const row = document.createElement("label");
        row.className = `entry-item ${entry.is_suspected_ad ? "is-ad" : ""}`;

        const left = document.createElement("div");
        left.className = "entry-left";

        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.className = "entry-checkbox";
        cb.checked = !entry.is_suspected_ad;
        cb.dataset.url = entry.direct_url || entry.url;
        cb.dataset.title = entry.title || "";

        const titleSpan = document.createElement("span");
        titleSpan.textContent = `${entry.title} (${entry.duration_formatted})`;

        left.append(cb, titleSpan);

        const right = document.createElement("span");
        if (entry.is_suspected_ad) {
          right.className = "badge badge-ad";
          right.textContent = `Werbung: ${entry.ad_reason}`;
        } else {
          right.className = "badge badge-success";
          right.textContent = "Hauptvideo";
        }

        row.append(left, right);
        els.entriesList.appendChild(row);
      }
    } else {
      els.entriesContainer.hidden = true;
      els.entriesList.innerHTML = "";
    }

    showToast("Stream analysiert – Qualitätsstufen bereit.");
  } catch {
    showToast("Fehler bei der Analyse der URL.", true);
  } finally {
    els.btnAnalyze.disabled = false;
    els.analyzeSpinner.hidden = true;
    if (els.analyzeIcon) els.analyzeIcon.hidden = false;
    els.analyzeBtnText.textContent = "Vorschau";
  }
}

async function startDownloadForUrl(targetUrl, titleOverride = "") {
  const payload = {
    url: targetUrl,
    title: titleOverride || (currentAnalysis ? currentAnalysis.title : ""),
    thumbnail: currentAnalysis ? currentAnalysis.thumbnail : null,
    output_dir: els.outputDirInput.value.trim(),
    quality: els.qualitySelect.value,
    codec: els.codecSelect.value,
    container: els.containerSelect.value,
    audio_format: els.audioFormatSelect.value,
    recode_if_needed: els.recodeCheckbox.checked,
    skip_preroll_ads: els.skipPrerollCheckbox.checked,
    min_duration: els.skipPrerollCheckbox.checked
      ? Number(els.minDurationInput.value || 0)
      : 0,
    sponsorblock: els.sponsorblockCheckbox.checked,
    cookies_browser: els.cookiesBrowserSelect.value,
    custom_title: els.customTitleInput.value.trim(),
  };

  const res = await fetch("/api/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

els.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = els.urlInput.value.trim();
  if (!url) {
    showToast("Bitte gib eine Video-URL ein.", true);
    els.urlInput.focus();
    return;
  }

  const checkedEntries = Array.from(
    els.entriesList.querySelectorAll(".entry-checkbox:checked")
  );

  els.btnDownload.disabled = true;
  try {
    if (!els.entriesContainer.hidden && checkedEntries.length > 0) {
      for (const cb of checkedEntries) {
        await startDownloadForUrl(cb.dataset.url || url, cb.dataset.title || "");
      }
      showToast(`${checkedEntries.length} Download(s) zur Warteschlange hinzugefügt.`);
    } else {
      const data = await startDownloadForUrl(url);
      if (!data.ok) {
        showToast(data.error || "Download konnte nicht gestartet werden.", true);
        return;
      }
      showToast("Download gestartet!");
    }
    await fetchJobs();
  } catch {
    showToast("Fehler beim Starten des Downloads.", true);
  } finally {
    els.btnDownload.disabled = false;
  }
});

els.btnPaste.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/clipboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (data.ok && data.text) {
      els.urlInput.value = data.text.trim();
      showToast("URL aus Zwischenablage eingefügt.");
      return;
    }
    const text = await navigator.clipboard.readText();
    if (text) {
      els.urlInput.value = text.trim();
      showToast("URL aus Zwischenablage eingefügt.");
    }
  } catch {
    els.urlInput.focus();
  }
});

els.btnAnalyze.addEventListener("click", handleAnalyze);
els.qualitySelect.addEventListener("change", updateQualityModeUI);
els.skipPrerollCheckbox.addEventListener("change", updateProtectionSummary);
els.sponsorblockCheckbox.addEventListener("change", updateProtectionSummary);
els.cookiesBrowserSelect.addEventListener("change", updateProtectionSummary);

els.urlInput.addEventListener("input", () => {
  if (currentAnalysis) {
    currentAnalysis = null;
    els.analysisPanel.hidden = true;
    resetQualityOptions();
  }
});

els.btnPickFolder.addEventListener("click", async () => {
  els.btnPickFolder.disabled = true;
  try {
    const res = await fetch("/api/pick-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (data.ok && data.path) {
      els.outputDirInput.value = data.path;
      if (data.settings?.recent_dirs) {
        renderRecentDirs(data.settings.recent_dirs);
      }
      showToast(`Zielordner gesetzt: ${data.path}`);
    }
  } catch {
    showToast("Ordnerdialog konnte nicht geöffnet werden.", true);
  } finally {
    els.btnPickFolder.disabled = false;
  }
});

els.btnOpenFolder.addEventListener("click", async () => {
  await fetch("/api/open-folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: els.outputDirInput.value.trim() }),
  });
});

els.btnClearJobs.addEventListener("click", async () => {
  await fetch("/api/jobs/clear", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  await fetchJobs();
});

async function fetchJobs() {
  try {
    const res = await fetch("/api/jobs");
    const data = await res.json();
    if (!data.ok) return;
    renderJobs(data.jobs || []);
  } catch {}
}

function renderJobs(jobs) {
  const activeCount = jobs.filter(
    (j) => j.status === "queued" || j.status === "downloading" || j.status === "processing"
  ).length;
  if (els.jobsCountBadge) {
    els.jobsCountBadge.textContent =
      activeCount > 0 ? `${activeCount} aktiv` : `${jobs.length} gesamt`;
    els.jobsCountBadge.className = activeCount > 0 ? "badge badge-brand" : "badge";
  }

  if (!jobs.length) {
    els.jobsList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7 10 12 15 17 10"></polyline>
            <line x1="12" y1="15" x2="12" y2="3"></line>
          </svg>
        </div>
        <p class="empty-title">Bereit für deinen ersten Download</p>
        <p class="empty-sub">Füge links eine Video-URL ein – ViDow lädt Quer- und Hochkantvideos in jeder gewünschten Qualitätsstufe.</p>
      </div>`;
    return;
  }

  els.jobsList.innerHTML = "";
  for (const job of jobs) {
    const item = document.createElement("article");
    const statusClass =
      job.status === "completed"
        ? "job-Completed"
        : job.status === "error" || job.status === "cancelled"
        ? "job-Error"
        : "";
    item.className = `job-item ${statusClass}`;

    const top = document.createElement("div");
    top.className = "job-top";

    const lead = document.createElement("div");
    lead.className = "job-lead";

    if (job.thumbnail) {
      const thumb = document.createElement("img");
      thumb.className = "job-thumb";
      thumb.src = job.thumbnail;
      thumb.alt = "";
      thumb.width = 48;
      thumb.height = 32;
      thumb.loading = "lazy";
      lead.appendChild(thumb);
    }

    const title = document.createElement("div");
    title.className = "job-title";
    title.textContent = job.title || job.url;
    lead.appendChild(title);

    const badge = document.createElement("span");
    badge.className = `badge ${
      job.status === "completed"
        ? "badge-success"
        : job.status === "error"
        ? "badge-ad"
        : "badge-brand"
    }`;
    const qLabel =
      job.quality === "audio" ? "Audio" : job.quality === "best" ? "Beste" : `${job.quality}p`;
    const resSuffix =
      job.resolution && job.quality !== "audio" && job.resolution !== `${job.quality}p`
        ? ` (${job.resolution})`
        : "";
    badge.textContent = `${qLabel}${resSuffix} • ${(job.container || "mp4").toUpperCase()}`;

    top.append(lead, badge);

    const meta = document.createElement("div");
    meta.className = "job-meta";
    meta.textContent = `${job.status_text} • ${job.downloaded_formatted || "0 B"} / ${
      job.total_formatted || "—"
    } • ${job.speed_formatted || "—"} • ETA: ${job.eta_formatted || "—"}`;

    const track = document.createElement("div");
    track.className = "progress-track";
    const fill = document.createElement("div");
    fill.className = "progress-fill";
    fill.style.setProperty("--progress-pct", `${Math.min(100, Math.max(0, job.progress || 0))}%`);
    track.appendChild(fill);

    const actions = document.createElement("div");
    actions.className = "job-actions";

    const dirSpan = document.createElement("span");
    dirSpan.className = "job-dir";
    dirSpan.textContent = job.filename || job.output_dir || "";

    const btnGroup = document.createElement("div");
    btnGroup.className = "job-btn-group";

    if (job.status === "downloading" || job.status === "queued" || job.status === "processing") {
      const cancelBtn = document.createElement("button");
      cancelBtn.type = "button";
      cancelBtn.className = "btn btn-ghost btn-sm";
      cancelBtn.textContent = "Abbrechen";
      cancelBtn.addEventListener("click", async () => {
        await fetch("/api/jobs/cancel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: job.id }),
        });
        await fetchJobs();
      });
      btnGroup.appendChild(cancelBtn);
    }

    if (job.status === "completed") {
      const revealBtn = document.createElement("button");
      revealBtn.type = "button";
      revealBtn.className = "btn btn-secondary btn-sm";
      const fm = window.vidowFileManagerLabel || "Ordner";
      revealBtn.textContent = `Im ${fm} zeigen`;
      revealBtn.addEventListener("click", async () => {
        await fetch("/api/open-folder", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: job.filepath || job.output_dir }),
        });
      });
      btnGroup.appendChild(revealBtn);
    }

    actions.append(dirSpan, btnGroup);
    item.append(top, meta, track, actions);
    els.jobsList.appendChild(item);
  }
}

initStatus();
fetchJobs();
setInterval(fetchJobs, 1200);
