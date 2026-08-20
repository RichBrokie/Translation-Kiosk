/**
 * Translation Kiosk — Public View Frontend Controller
 * Captures PCM audio from the browser microphone and streams it over WebSocket.
 */
(function () {
  'use strict';

  const btnMaster = document.getElementById('btn-master');
  const btnMasterIcon = document.getElementById('btn-master-icon');
  const btnMasterText = document.getElementById('btn-master-text');
  const btnFullscreen = document.getElementById('btn-fullscreen');
  const statusMessage = document.getElementById('status-message');
  const badgeLangText = document.getElementById('badge-lang-text');
  const badgeLangIcon = document.getElementById('badge-lang-icon');
  const tagTranslationMode = document.getElementById('tag-translation-mode');

  const committedTranscript = document.getElementById('committed-transcript');
  const interimTranscript = document.getElementById('interim-transcript');
  const placeholderTranscript = document.getElementById('placeholder-transcript');
  const transcriptScrollContainer = document.getElementById('transcript-scroll-container');

  const translationContent = document.getElementById('translation-content');
  const placeholderTranslation = document.getElementById('placeholder-translation');
  const translationScrollContainer = document.getElementById('translation-scroll-container');

  const metricWhisper = document.getElementById('metric-whisper');
  const metricQwen = document.getElementById('metric-qwen');
  const metricE2E = document.getElementById('metric-e2e');

  const visualizerCanvas = document.getElementById('audio-visualizer');
  const visualizerCtx = visualizerCanvas ? visualizerCanvas.getContext('2d') : null;

  const LANG_FLAGS = {
    es: '🇪🇸', fr: '🇫🇷', de: '🇩🇪', zh: '🇨🇳', ar: '🇸🇦',
    ja: '🇯🇵', it: '🇮🇹', pt: '🇵🇹', ru: '🇷🇺', ko: '🇰🇷',
    hi: '🇮🇳', nl: '🇳🇱', tr: '🇹🇷', pl: '🇵🇱', sv: '🇸🇪',
    vi: '🇻🇳', uk: '🇺🇦', el: '🇬🇷', cs: '🇨🇿', en: '🇬🇧'
  };

  let appState = 'IDLE';
  let ws = null;
  let audioCtx = null;
  let mediaStream = null;
  let workletNode = null;
  let scriptProcessor = null;
  let analyserNode = null;
  let silentGain = null;
  let animationFrameId = null;
  let wsReconnectTimer = null;
  let sessionId = null;

  function getWebSocketUrl() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return proto + '//' + window.location.host + '/ws/audio';
  }

  function waitForSocket(timeoutMs) {
    return new Promise(function (resolve, reject) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }
      connectWebSocket();
      var started = Date.now();
      var timer = setInterval(function () {
        if (ws && ws.readyState === WebSocket.OPEN) {
          clearInterval(timer);
          resolve();
        } else if (Date.now() - started > timeoutMs) {
          clearInterval(timer);
          reject(new Error('WebSocket did not connect'));
        }
      }, 50);
    });
  }

  function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      ws = new WebSocket(getWebSocketUrl());
    } catch (err) {
      setStatus('WebSocket error: ' + err.message, 'var(--accent-rec)');
      return;
    }
    ws.binaryType = 'arraybuffer';

    ws.onopen = function () {
      if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
      }
      if (appState === 'IDLE') {
        setStatus('Ready — tap the button and speak', 'var(--text-secondary)');
      }
    };

    ws.onmessage = function (event) {
      try {
        handleServerMessage(JSON.parse(event.data));
      } catch (err) {
        console.error('[WS] Failed to parse message:', event.data, err);
      }
    };

    ws.onerror = function () {
      setStatus('WebSocket failed. If you used HTTPS, accept the certificate warning and reload.', 'var(--accent-rec)');
    };

    ws.onclose = function () {
      if (appState === 'RECORDING') {
        stopRecording();
      }
      if (!wsReconnectTimer) {
        wsReconnectTimer = setTimeout(connectWebSocket, 2000);
      }
    };
  }

  function handleServerMessage(msg) {
    switch (msg.type) {
      case 'language_detected':
        handleLanguageDetected(msg);
        break;
      case 'transcription_update':
        handleTranscriptionUpdate(msg);
        break;
      case 'translation_update':
        handleTranslationUpdate(msg);
        break;
      case 'status_update':
        setStatus(msg.message || 'Processing...');
        break;
      case 'error':
        setStatus('Error: ' + (msg.message || 'unknown'), 'var(--accent-rec)');
        break;
      default:
        break;
    }
  }

  function handleLanguageDetected(msg) {
    var code = (msg.language_code || 'en').toLowerCase();
    var name = msg.language_name || code.toUpperCase();
    var flag = LANG_FLAGS[code] || '🌐';

    if (badgeLangIcon) badgeLangIcon.textContent = flag;
    if (badgeLangText) badgeLangText.textContent = name + ' (' + code + ')';

    if (tagTranslationMode) {
      if (code === 'en') {
        tagTranslationMode.textContent = 'English Bypass (Direct)';
        tagTranslationMode.classList.add('direct-stream');
      } else {
        tagTranslationMode.textContent = 'Qwen 72B Translation';
        tagTranslationMode.classList.remove('direct-stream');
      }
    }
  }

  function handleTranscriptionUpdate(msg) {
    if (placeholderTranscript) placeholderTranscript.style.display = 'none';
    if (msg.text) {
      committedTranscript.textContent = msg.text;
      interimTranscript.textContent = '';
    } else if (msg.raw_chunk_text) {
      interimTranscript.textContent = msg.raw_chunk_text;
    }
    if (transcriptScrollContainer) {
      transcriptScrollContainer.scrollTop = transcriptScrollContainer.scrollHeight;
    }
  }

  function handleTranslationUpdate(msg) {
    if (placeholderTranslation) placeholderTranslation.style.display = 'none';

    if (msg.whisper_latency_ms) metricWhisper.textContent = Math.round(msg.whisper_latency_ms);
    if (msg.latency_ms !== undefined) metricQwen.textContent = Math.round(msg.latency_ms);
    if (msg.e2e_latency_ms !== undefined) metricE2E.textContent = Math.round(msg.e2e_latency_ms);

    if (!msg.translation) return;

    var chunkId = msg.chunk_id != null ? String(msg.chunk_id) : 'latest';
    var bubbleId = 'trans-chunk-' + chunkId;
    var targetBubble = document.getElementById(bubbleId);
    var timeStr = new Date().toTimeString().split(' ')[0];

    if (!targetBubble) {
      targetBubble = document.createElement('div');
      targetBubble.id = bubbleId;
      targetBubble.className = 'translation-item';

      var timeHeader = document.createElement('div');
      timeHeader.className = 'translation-time';
      timeHeader.textContent = '[' + timeStr + ']';

      var textBody = document.createElement('div');
      textBody.className = 'translation-text';
      textBody.textContent = msg.translation;

      targetBubble.appendChild(timeHeader);
      targetBubble.appendChild(textBody);
      translationContent.appendChild(targetBubble);
    } else {
      var existing = targetBubble.querySelector('.translation-text');
      if (existing) existing.textContent = msg.translation;
    }

    if (translationScrollContainer) {
      translationScrollContainer.scrollTop = translationScrollContainer.scrollHeight;
    }
  }

  function setStatus(text, color) {
    if (!statusMessage) return;
    statusMessage.textContent = text;
    statusMessage.style.color = color || 'var(--text-secondary)';
  }

  function setUIState(state) {
    appState = state;
    if (btnMaster) btnMaster.className = 'btn-control-master ' + state.toLowerCase();

    switch (state) {
      case 'IDLE':
        if (btnMasterIcon) btnMasterIcon.textContent = '🎙️';
        if (btnMasterText) btnMasterText.textContent = 'Touch to Start Speaking';
        if (btnMaster) btnMaster.disabled = false;
        setStatus('Ready — tap the button and speak.');
        break;
      case 'RECORDING':
        if (btnMasterIcon) btnMasterIcon.textContent = '⏹️';
        if (btnMasterText) btnMasterText.textContent = 'Stop Recording';
        if (btnMaster) btnMaster.disabled = false;
        setStatus('Listening... speak clearly in any language.', 'var(--accent-rec)');
        break;
      case 'PROCESSING':
        if (btnMasterIcon) btnMasterIcon.textContent = '⏳';
        if (btnMasterText) btnMasterText.textContent = 'Finalizing Translation...';
        if (btnMaster) btnMaster.disabled = true;
        setStatus('Finalizing recent speech...', 'var(--accent-proc)');
        break;
      case 'ERROR':
        if (btnMasterIcon) btnMasterIcon.textContent = '⚠️';
        if (btnMasterText) btnMasterText.textContent = 'Error — Tap to Retry';
        if (btnMaster) btnMaster.disabled = false;
        break;
    }
  }

  async function startRecording() {
    try {
      setStatus('Connecting...', 'var(--text-secondary)');
      await waitForSocket(4000);

      sessionId = 'sess_' + Math.random().toString(36).substring(2, 9);
      ws.send(JSON.stringify({
        type: 'session_start',
        session_id: sessionId,
        sample_rate: 16000,
        channels: 1
      }));

      committedTranscript.textContent = '';
      interimTranscript.textContent = '';
      translationContent.innerHTML = '';
      if (placeholderTranscript) placeholderTranscript.style.display = 'none';
      if (placeholderTranslation) placeholderTranslation.style.display = 'none';

      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        },
        video: false
      });

      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
      }
      var source = audioCtx.createMediaStreamSource(mediaStream);

      analyserNode = audioCtx.createAnalyser();
      analyserNode.fftSize = 64;
      source.connect(analyserNode);
      startVisualizer();

      silentGain = audioCtx.createGain();
      silentGain.gain.value = 0;

      var workletSuccess = false;
      if (audioCtx.audioWorklet) {
        try {
          await audioCtx.audioWorklet.addModule('/static/js/audio-worklet-processor.js');
          workletNode = new AudioWorkletNode(audioCtx, 'pcm-worklet-processor');
          workletNode.port.onmessage = function (e) {
            if (ws && ws.readyState === WebSocket.OPEN && appState === 'RECORDING') {
              ws.send(e.data);
            }
          };
          source.connect(workletNode);
          workletNode.connect(silentGain);
          silentGain.connect(audioCtx.destination);
          workletSuccess = true;
        } catch (workletErr) {
          console.warn('[Audio] AudioWorklet failed, falling back to ScriptProcessor:', workletErr);
        }
      }

      if (!workletSuccess) {
        var inSampleRate = audioCtx.sampleRate;
        var targetRate = 16000;
        var bufferSize = 4096;
        scriptProcessor = audioCtx.createScriptProcessor(bufferSize, 1, 1);
        scriptProcessor.onaudioprocess = function (e) {
          if (!(ws && ws.readyState === WebSocket.OPEN && appState === 'RECORDING')) return;
          var inputData = e.inputBuffer.getChannelData(0);
          var ratio = inSampleRate / targetRate;
          var outLength = Math.floor(inputData.length / ratio);
          var pcmBuffer = new Int16Array(outLength);
          for (var i = 0; i < outLength; i++) {
            var idx = Math.floor(i * ratio);
            var s = Math.max(-1, Math.min(1, inputData[idx]));
            pcmBuffer[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          ws.send(pcmBuffer.buffer);
        };
        source.connect(scriptProcessor);
        scriptProcessor.connect(silentGain);
        silentGain.connect(audioCtx.destination);
      }

      setUIState('RECORDING');
    } catch (err) {
      console.error('[Audio] Failed to start recording:', err);
      setUIState('ERROR');
      setStatus('Microphone/connection error: ' + (err.message || err), 'var(--accent-rec)');
    }
  }

  async function stopRecording() {
    setUIState('PROCESSING');

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'session_stop',
        session_id: sessionId
      }));
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach(function (t) { t.stop(); });
      mediaStream = null;
    }
    if (workletNode) {
      workletNode.disconnect();
      workletNode = null;
    }
    if (scriptProcessor) {
      scriptProcessor.disconnect();
      scriptProcessor = null;
    }
    if (silentGain) {
      silentGain.disconnect();
      silentGain = null;
    }
    if (audioCtx && audioCtx.state !== 'closed') {
      await audioCtx.close();
      audioCtx = null;
    }
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }
    clearVisualizer();

    setTimeout(function () {
      if (appState === 'PROCESSING') setUIState('IDLE');
    }, 1500);
  }

  function startVisualizer() {
    if (!visualizerCanvas || !visualizerCtx || !analyserNode) return;
    var bufferLength = analyserNode.frequencyBinCount;
    var dataArray = new Uint8Array(bufferLength);

    function draw() {
      if (appState !== 'RECORDING') {
        clearVisualizer();
        return;
      }
      animationFrameId = requestAnimationFrame(draw);
      analyserNode.getByteFrequencyData(dataArray);
      var width = visualizerCanvas.width = visualizerCanvas.offsetWidth;
      var height = visualizerCanvas.height = visualizerCanvas.offsetHeight;
      visualizerCtx.clearRect(0, 0, width, height);
      var barWidth = (width / bufferLength) * 2.2;
      var x = 0;
      for (var i = 0; i < bufferLength; i++) {
        var barHeight = (dataArray[i] / 255) * height;
        var gradient = visualizerCtx.createLinearGradient(0, height, 0, 0);
        gradient.addColorStop(0, '#2563eb');
        gradient.addColorStop(1, '#38bdf8');
        visualizerCtx.fillStyle = gradient;
        visualizerCtx.fillRect(x, height - barHeight, barWidth - 2, barHeight);
        x += barWidth;
      }
    }
    draw();
  }

  function clearVisualizer() {
    if (!visualizerCanvas || !visualizerCtx) return;
    visualizerCtx.clearRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(function (err) {
        console.warn('Fullscreen request error:', err);
      });
    } else if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  }

  if (btnMaster) {
    btnMaster.addEventListener('click', function () {
      if (appState === 'IDLE' || appState === 'ERROR') startRecording();
      else if (appState === 'RECORDING') stopRecording();
    });
  } else {
    setStatus('Kiosk button not found in the page HTML.', 'var(--accent-rec)');
  }

  if (btnFullscreen) {
    btnFullscreen.addEventListener('click', toggleFullscreen);
  }

  connectWebSocket();
})();
