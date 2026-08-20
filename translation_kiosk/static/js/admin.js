/**
 * Translation Kiosk — Admin Monitoring & Diagnostics Controller
 */
(function () {
  'use strict';

  const badgeWsStatus = document.getElementById('badge-ws-status');
  const uptimeDisplay = document.getElementById('uptime-display');

  const kpiTotalChunks = document.getElementById('kpi-total-chunks');
  const kpiTotalAudio = document.getElementById('kpi-total-audio');
  const kpiBypassRate = document.getElementById('kpi-bypass-rate');
  const kpiBypassSub = document.getElementById('kpi-bypass-sub');
  const kpiRepairsCount = document.getElementById('kpi-repairs-count');

  const gaugeWhisperBar = document.getElementById('gauge-whisper-bar');
  const statWhisperLast = document.getElementById('stat-whisper-last');
  const statWhisperAvg = document.getElementById('stat-whisper-avg');
  const statWhisperP95 = document.getElementById('stat-whisper-p95');
  const statWhisperMax = document.getElementById('stat-whisper-max');
  const canvasWhisper = document.getElementById('chart-whisper-sparkline');

  const gaugeQwenBar = document.getElementById('gauge-qwen-bar');
  const statQwenLast = document.getElementById('stat-qwen-last');
  const statQwenAvg = document.getElementById('stat-qwen-avg');
  const statQwenP95 = document.getElementById('stat-qwen-p95');
  const statQwenMax = document.getElementById('stat-qwen-max');
  const canvasQwen = document.getElementById('chart-qwen-sparkline');

  const diffLatestChunkInfo = document.getElementById('diff-latest-chunk-info');
  const stageRawText = document.getElementById('stage-raw-text');
  const stageStitchedText = document.getElementById('stage-stitched-text');
  const stageCorrectedText = document.getElementById('stage-corrected-text');
  const stageTranslatedText = document.getElementById('stage-translated-text');

  const logTableBody = document.getElementById('log-table-body');
  const btnPauseLog = document.getElementById('btn-pause-log');
  const btnClearLog = document.getElementById('btn-clear-log');
  const btnExportLog = document.getElementById('btn-export-log');
  const filterApiSelect = document.getElementById('filter-api-select');
  const inputLogSearch = document.getElementById('input-log-search');

  let ws = null;
  let isLogPaused = false;
  let allLogs = [];
  let whisperHistory = [];
  let qwenHistory = [];
  const MAX_HISTORY = 40;

  function getWebSocketUrl() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return proto + '//' + window.location.host + '/ws/admin';
  }

  function connect() {
    ws = new WebSocket(getWebSocketUrl());

    ws.onopen = function () {
      if (badgeWsStatus) {
        badgeWsStatus.className = 'badge-status';
        badgeWsStatus.innerHTML = '<span class="dot">●</span> Telemetry Connected';
      }
    };

    ws.onmessage = function (event) {
      try {
        handleMessage(JSON.parse(event.data));
      } catch (e) {
        console.error('Failed to parse admin WS message:', e);
      }
    };

    ws.onclose = function () {
      if (badgeWsStatus) {
        badgeWsStatus.className = 'badge-status disconnected';
        badgeWsStatus.innerHTML = '<span class="dot">●</span> Disconnected (Retrying...)';
      }
      setTimeout(connect, 2000);
    };

    ws.onerror = function (err) {
      console.error('Admin WS error:', err);
    };
  }

  function handleMessage(msg) {
    if (msg.type === 'admin_telemetry') {
      if (msg.stats) updateStats(msg.stats);
      if (msg.latest_chunk) updateChunk(msg.latest_chunk);
      if (msg.recent_logs && Array.isArray(msg.recent_logs)) {
        msg.recent_logs.forEach(addLogEntry);
      }
    } else if (msg.type === 'chunk_metrics') {
      updateChunk(msg);
    } else if (msg.type === 'api_log') {
      addLogEntry(msg);
    }
  }

  function updateStats(stats) {
    if (stats.uptime_seconds !== undefined && uptimeDisplay) {
      var up = Math.floor(stats.uptime_seconds);
      var h = Math.floor(up / 3600);
      var m = Math.floor((up % 3600) / 60);
      var s = up % 60;
      uptimeDisplay.textContent = 'Uptime: ' + h + 'h ' + m + 'm ' + s + 's';
    }

    if (stats.total_chunks_processed !== undefined && kpiTotalChunks) {
      kpiTotalChunks.textContent = stats.total_chunks_processed.toLocaleString();
    }
    if (stats.total_audio_seconds !== undefined && kpiTotalAudio) {
      kpiTotalAudio.textContent = stats.total_audio_seconds.toFixed(1) + 's';
    }
    if (stats.bypass_rate_pct !== undefined) {
      if (kpiBypassRate) kpiBypassRate.textContent = stats.bypass_rate_pct.toFixed(1) + '%';
      if (kpiBypassSub) kpiBypassSub.textContent = (stats.total_bypasses || 0) + ' requests bypassed LLM';
    }
    if (stats.boundary_corrections_count !== undefined && kpiRepairsCount) {
      kpiRepairsCount.textContent = stats.boundary_corrections_count.toLocaleString();
    }

    if (stats.whisper_latency) {
      if (statWhisperAvg) statWhisperAvg.textContent = Math.round(stats.whisper_latency.avg || 0);
      if (statWhisperP95) statWhisperP95.textContent = Math.round(stats.whisper_latency.p95 || 0);
      if (statWhisperMax) statWhisperMax.textContent = Math.round(stats.whisper_latency.max || 0);
    }

    if (stats.qwen_latency) {
      if (statQwenAvg) statQwenAvg.textContent = Math.round(stats.qwen_latency.avg || 0);
      if (statQwenP95) statQwenP95.textContent = Math.round(stats.qwen_latency.p95 || 0);
      if (statQwenMax) statQwenMax.textContent = Math.round(stats.qwen_latency.max || 0);
    }
  }

  function gaugeClass(lat, hotMs) {
    return 'gauge-bar-fill' + (lat > hotMs ? ' hot' : '');
  }

  function updateChunk(chunk) {
    var wLat = chunk.whisper_latency_ms || 0;
    var qLat = chunk.qwen_latency_ms || 0;

    if (statWhisperLast) statWhisperLast.textContent = Math.round(wLat);
    if (statQwenLast) statQwenLast.textContent = Math.round(qLat);

    var wPct = Math.min(100, Math.max(0, (wLat / 5000) * 100));
    if (gaugeWhisperBar) {
      gaugeWhisperBar.style.width = wPct + '%';
      gaugeWhisperBar.className = gaugeClass(wLat, 3000);
    }

    var qPct = Math.min(100, Math.max(0, (qLat / 8000) * 100));
    if (gaugeQwenBar) {
      gaugeQwenBar.style.width = qPct + '%';
      gaugeQwenBar.className = gaugeClass(qLat, 5000);
    }

    whisperHistory.push(wLat);
    if (whisperHistory.length > MAX_HISTORY) whisperHistory.shift();
    drawSparkline(canvasWhisper, whisperHistory, '#38bdf8', 5000);

    qwenHistory.push(qLat);
    if (qwenHistory.length > MAX_HISTORY) qwenHistory.shift();
    drawSparkline(canvasQwen, qwenHistory, '#a855f7', 8000);

    if (diffLatestChunkInfo) {
      diffLatestChunkInfo.textContent = 'Chunk #' + (chunk.chunk_id || '-') +
        ' | Lang: ' + (chunk.language_code || '-') +
        ' | E2E: ' + Math.round(chunk.e2e_latency_ms || 0) + 'ms';
    }

    if (stageRawText) stageRawText.textContent = chunk.naive_text || chunk.text_raw || chunk.raw_text || '—';
    if (stageStitchedText) stageStitchedText.textContent = chunk.sliding_window_text || chunk.text_window_retranscribed || chunk.stitched_text || '—';
    if (stageCorrectedText) stageCorrectedText.textContent = chunk.corrected_text || chunk.text_qwen_corrected || '—';
    if (stageTranslatedText) stageTranslatedText.textContent = chunk.translated_text || chunk.text_translated || chunk.english_translation || '—';
  }

  function drawSparkline(canvas, data, color, maxScale) {
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    var w = canvas.width = canvas.offsetWidth;
    var h = canvas.height = canvas.offsetHeight;

    ctx.clearRect(0, 0, w, h);
    if (data.length < 2) return;

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;

    var step = w / (MAX_HISTORY - 1);
    for (var i = 0; i < data.length; i++) {
      var x = i * step;
      var val = Math.min(maxScale, data[i]);
      var y = h - (val / maxScale) * (h - 8) - 4;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h - 1);
    ctx.lineTo(w, h - 1);
    ctx.stroke();
  }

  function addLogEntry(entry) {
    if (!entry) return;
    var exists = allLogs.some(function (l) {
      return l.timestamp === entry.timestamp && l.endpoint === entry.endpoint && l.latency_ms === entry.latency_ms;
    });
    if (exists) return;
    allLogs.unshift(entry);
    if (allLogs.length > 200) allLogs.pop();
    if (!isLogPaused) renderLogs();
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderLogs() {
    if (!logTableBody) return;
    var filterApi = (filterApiSelect && filterApiSelect.value || '').toLowerCase();
    var searchTerm = (inputLogSearch && inputLogSearch.value || '').toLowerCase().trim();

    var filtered = allLogs.filter(function (log) {
      var ep = (log.endpoint || '').toLowerCase();
      var status = log.status_code || 200;
      var isErr = status >= 400 || log.error;
      if (filterApi === 'whisper' && ep.indexOf('transcribe') === -1) return false;
      if (filterApi === 'qwen' && ep.indexOf('chat/completions') === -1) return false;
      if (filterApi === 'errors' && !isErr) return false;
      if (searchTerm) {
        var full = (ep + ' ' + (log.error || '') + ' ' + (log.request_preview || '')).toLowerCase();
        if (full.indexOf(searchTerm) === -1) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      logTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No matching logs.</td></tr>';
      return;
    }

    logTableBody.innerHTML = filtered.slice(0, 50).map(function (log) {
      var d = new Date((log.timestamp || Date.now() / 1000) * 1000);
      var timeStr = d.toTimeString().split(' ')[0] + '.' + String(d.getMilliseconds()).padStart(3, '0');
      var isErr = (log.status_code >= 400) || log.error;
      var statusClass = isErr ? 'err' : 'ok';
      var statusText = log.status_code ? String(log.status_code) : (isErr ? 'ERR' : 'OK');
      var epShort = (log.endpoint || '').split('/').slice(-2).join('/');
      var latency = log.latency_ms != null ? Math.round(log.latency_ms) : '-';
      var preview = log.error || log.response_preview || log.request_preview || '';
      return '<tr>' +
        '<td>' + escapeHtml(timeStr) + '</td>' +
        '<td><span style="color: #38bdf8;">' + escapeHtml(epShort) + '</span></td>' +
        '<td title="' + escapeHtml(log.endpoint || '') + '">' + escapeHtml(log.method || 'POST') + '</td>' +
        '<td><span class="status-tag ' + statusClass + '">' + escapeHtml(statusText) + '</span></td>' +
        '<td>' + escapeHtml(latency) + ' ms</td>' +
        '<td title="' + escapeHtml(preview) + '">' + escapeHtml(String(preview).slice(0, 80)) + '</td>' +
        '<td></td>' +
        '</tr>';
    }).join('');
  }

  if (btnPauseLog) {
    btnPauseLog.addEventListener('click', function () {
      isLogPaused = !isLogPaused;
      btnPauseLog.textContent = isLogPaused ? 'Resume' : 'Pause';
      if (!isLogPaused) renderLogs();
    });
  }
  if (btnClearLog) {
    btnClearLog.addEventListener('click', function () {
      allLogs = [];
      renderLogs();
    });
  }
  if (btnExportLog) {
    btnExportLog.addEventListener('click', function () {
      var stamp = new Date().toISOString().replace(/[:.]/g, '-');
      var dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(allLogs, null, 2));
      var a = document.createElement('a');
      a.setAttribute('href', dataStr);
      a.setAttribute('download', 'kiosk_telemetry_logs_' + stamp + '.json');
      document.body.appendChild(a);
      a.click();
      a.remove();
    });
  }
  if (filterApiSelect) filterApiSelect.addEventListener('change', renderLogs);
  if (inputLogSearch) inputLogSearch.addEventListener('input', renderLogs);

  connect();
})();
