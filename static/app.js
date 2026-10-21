// ViDow — Frontend Application Logic

const els = {
  form: document.getElementById("download-form"),
  urlInput: document.getElementById("video-url"),
  btnPaste: document.getElementById("btn-paste"),
  btnAnalyze: document.getElementById("btn-analyze"),
  analyzeSpinner: document.getElementById("analyze-spinner"),
  analyzeBtnText: document.getElementById("analyze-btn-text"),
  analysisPanel: document.getElementById("analysis-panel"),
  analysisThumb: document.getElementById("analysis-thumb"),
  analysisExtractor: document.getElementById("analysis-extractor"),
  analysisDuration: document.getElementById("analysis-duration"),
  analysisAdBadge: document.getElementById("analysis-ad-badge"),
  analysisTitle: document.getElementById("analysis-title"),
  analysisAvail: document.getElementById("analysis-avail"),
  entriesContainer: document.getElementById("entries-container"),
  entriesList: document.getElementById("entries-list"),
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
  customTitleInput: document.getElementById("custom-title"),
  btnDownload: document.getElementById("btn-download"),
  jobsList: document.getElementById("jobs-list"),
  btnClearJobs: document.getElementById("btn-clear-jobs"),
  statusYtdlp: document.getElementById("status-ytdlp"),
  statusFfmpeg: document.getElementById("status-ffmpeg"),
  toastStack: document.getElementById("toast-stack"),
};

let currentAnalysis = null;
let toastCounter = 0;

function showToast(message, isError = false) {
  toastCounter += 1;
  const toastId = `vidow-toast-${toastCounter}`;
  const toast = document.createElement("div");
  toast.id = toastId;
  toast.setAttribute("popover", "manual");
  toast.className = "toast-popover";
  if (isError) {
    toast.style.borderColor = "var(--danger)";
  }

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
    toast.style.display = "flex";
  }

  setTimeout(() => {
    try {
      toast.hidePopover();
    } catch {}
    toast.remove();
  }, 4200);
}

function updateQualityModeUI() {
  const isAudio = els.qualitySelect.value === "audio";
  els.codecField.hidden = isAudio;
  els.containerField.hidden = isAudio;
  els.recodeRow.hidden = isAudio;
  els.audioFormatField.hidden = !isAudio;
}

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

async function initStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (!data.ok) return;

    els.statusYtdlp.textContent = `yt-dlp ${data.yt_dlp_version}`;
    if (data.ffmpeg_available) {
      els.statusFfmpeg.textContent = "ffmpeg bereit";
      els.statusFfmpeg.className = "pill pill-ok";
    } else {
      const tip = data.platform === "win32" ? "winget install Gyan.FFmpeg" : "brew install ffmpeg";
      els.statusFfmpeg.textContent = `ffmpeg fehlt (${tip})`;
      els.statusFfmpeg.className = "pill pill-warn";
    }

    window.vidowFileManagerLabel = data.file_manager_label || (data.platform === "win32" ? "Explorer" : "Finder");
    if (els.btnOpenFolder) {
      els.btnOpenFolder.textContent = `Im ${window.vidowFileManagerLabel} zeigen`;
      els.btnOpenFolder.title = `Aktuellen Ordner im ${window.vidowFileManagerLabel} öffnen`;
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

    // Unterstützt direkten Aufruf per Query-Parameter (?url=...) von der Browser-Erweiterung
    const params = new URLSearchParams(window.location.search);
    const paramUrl = params.get("url");
    if (paramUrl) {
      els.urlInput.value = paramUrl;
      await handleAnalyze();
    }
  } catch (err) {
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
  els.analyzeBtnText.textContent = "Analysiere…";

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

    if (info.thumbnail) {
      els.analysisThumb.src = info.thumbnail;
      els.analysisThumb.hidden = false;
    } else {
      els.analysisThumb.hidden = true;
    }

    if (info.ad_filtered_count > 0) {
      els.analysisAdBadge.hidden = false;
      els.analysisAdBadge.textContent = `🛡️ ${info.ad_filtered_count} Werbe-Clip(s) erkannt & abgewählt`;
    } else {
      els.analysisAdBadge.hidden = true;
    }

    const heightsText = (info.available_heights || []).length
      ? `Verfügbare Auflösungen: ${info.available_heights.map((h) => `${h}p`).join(", ")}`
      : "Stream-Auflösung wird automatisch gewählt";
    const codecsText = (info.available_codecs || []).length
      ? ` • Nativ vorhandene Codecs: ${info.available_codecs.map((c) => c.toUpperCase()).join(", ")}`
      : "";
    els.analysisAvail.textContent = `${heightsText}${codecsText}`;

    // Falls mehrere Einträge auf der Seite gefunden wurden
    const entries = info.entries || [];
    if (entries.length > 1) {
      els.entriesContainer.hidden = false;
      els.entriesList.innerHTML = "";
      for (const entry of entries) {
        const row = document.createElement("label");
        row.className = `entry-item ${entry.is_suspected_ad ? "is-ad" : ""}`;

        const left = document.createElement("div");
        left.style.display = "flex";
        left.style.alignItems = "center";
        left.style.gap = "0.5rem";

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

    showToast("Video erfolgreich analysiert!");
  } catch (err) {
    showToast("Fehler bei der Analyse der URL.", true);
  } finally {
    els.btnAnalyze.disabled = false;
    els.analyzeSpinner.hidden = true;
    els.analyzeBtnText.textContent = "Prüfen & Vorschau";
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
      showToast(`${checkedEntries.length} Download(s) gestartet!`);
    } else {
      const data = await startDownloadForUrl(url);
      if (!data.ok) {
        showToast(data.error || "Download konnte nicht gestartet werden.", true);
        return;
      }
      showToast("Download gestartet!");
    }
    await fetchJobs();
  } catch (err) {
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
      showToast(`Speicherort gewählt: ${data.path}`);
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
  if (!jobs.length) {
    els.jobsList.innerHTML =
      '<p class="empty-state">Noch keine Downloads gestartet. Füge links eine URL ein!</p>';
    return;
  }

  els.jobsList.innerHTML = "";
  for (const job of jobs) {
    const item = document.createElement("div");
    const statusClass =
      job.status === "completed"
        ? "job-Completed"
        : job.status === "error" || job.status === "cancelled"
        ? "job-Error"
        : "";
    item.className = `job-item ${statusClass}`;

    const top = document.createElement("div");
    top.className = "job-top";

    const title = document.createElement("div");
    title.className = "job-title";
    title.textContent = job.title || job.url;

    const badge = document.createElement("span");
    badge.className = `badge ${
      job.status === "completed"
        ? "badge-success"
        : job.status === "error"
        ? "badge-ad"
        : ""
    }`;
    const qLabel = job.quality === "audio" ? "Audio" : job.quality === "best" ? "Beste" : `${job.quality}p`;
    badge.textContent = `${qLabel} • ${(job.container || "mp4").toUpperCase()}`;

    top.append(title, badge);

    const meta = document.createElement("div");
    meta.className = "job-meta";
    meta.textContent = `${job.status_text} • ${job.downloaded_formatted || "0 B"} / ${
      job.total_formatted || "—"
    } • Speed: ${job.speed_formatted || "—"} • ETA: ${job.eta_formatted || "—"}`;

    const track = document.createElement("div");
    track.className = "progress-track";
    const fill = document.createElement("div");
    fill.className = "progress-fill";
    fill.style.width = `${Math.min(100, Math.max(0, job.progress || 0))}%`;
    track.appendChild(fill);

    const actions = document.createElement("div");
    actions.className = "job-actions";

    const dirSpan = document.createElement("span");
    dirSpan.style.color = "var(--muted)";
    dirSpan.textContent = job.filename || job.output_dir || "";

    const btnGroup = document.createElement("div");
    btnGroup.style.display = "flex";
    btnGroup.style.gap = "0.4rem";

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
      revealBtn.textContent = `📂 Im ${fm} zeigen`;
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
