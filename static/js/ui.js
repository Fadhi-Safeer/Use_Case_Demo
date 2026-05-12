'use strict';

const LIVE_DEFAULTS = {
  max_image_size: 480,
  num_predict: 512,
  interval_seconds: 3,
  system_prompt: "/no_think You are analyzing a webcam frame. Focus only on hands and objects they grip. Ignore background. Answer in minimum words.",
};

async function doStartLive() {
  const prompt = document.getElementById('prompt-input').value.trim();
  if (!prompt) { alert('Enter a prompt first.'); return; }

  const interval = parseInt(document.getElementById('ps-interval').value, 10);
  const max_image_size = parseInt(document.getElementById('ps-image-size').value, 10);
  const num_predict = parseInt(document.getElementById('ps-num-predict').value, 10);
  if (num_predict < 10) { alert('Max tokens must be at least 10.'); return; }
  const system_prompt = document.getElementById('ps-system-prompt').value.trim()
    || LIVE_DEFAULTS.system_prompt;
  const btn = document.getElementById('start-btn');
  btn.disabled = true;

  try {
    await postSettings({ num_predict, max_image_size, system_prompt });
    const data = await startLive(prompt, interval);
    if (data.error) { alert(data.error); btn.disabled = false; return; }

    state.liveJobId = data.job_id;
    state.lastLiveResult = null;
    state.liveCardCount = 0;

    // Clear previous session cards
    const list = document.getElementById('results-list');
    list.innerHTML = '<div id="empty-state">Waiting for first inference\u2026</div>';

    // Set prompt labels in header and results panel
    const short = prompt.length > 60 ? prompt.slice(0, 57) + '…' : prompt;
    document.getElementById('header-prompt-text').textContent = short;
    document.getElementById('active-prompt-label').textContent = prompt;

    // Switch screens
    document.getElementById('prompt-screen').classList.add('hidden');
    document.getElementById('live-screen').classList.remove('hidden');

    // Start video feed
    const img = document.getElementById('feed-img');
    const offline = document.getElementById('feed-offline');
    img.style.display = 'block';
    offline.style.display = 'none';
    img.onerror = () => { img.style.display = 'none'; offline.style.display = 'flex'; };
    img.src = '/video_feed';

    // Re-render Lucide icons now that live-screen is visible
    lucide.createIcons();

    // Start live results loop
    liveResultsLoop();
  } catch (e) {
    alert('Request failed: ' + e.message);
    btn.disabled = false;
  }
}

async function doStopLive() {
  try { await stopLive(); } catch (e) { /* ignore network errors */ } finally {
    state.liveJobId = null;
    state.lastLiveResult = null;
    state.liveCardCount = 0;

    const indicator = document.getElementById('analyzing-indicator');
    if (indicator) indicator.style.display = 'none';

    // Stop video feed
    const img = document.getElementById('feed-img');
    img.src = '';
    img.style.display = '';
    document.getElementById('feed-offline').style.display = 'none';

    // Clear results list
    document.getElementById('results-list').innerHTML =
      '<div id="empty-state">Waiting for first inference…</div>';

    // Clear pending cards tracker
    Object.keys(state.pendingCards).forEach(k => delete state.pendingCards[k]);

    // Re-enable start button
    document.getElementById('start-btn').disabled = false;

    // Switch screens
    document.getElementById('live-screen').classList.add('hidden');
    document.getElementById('prompt-screen').classList.remove('hidden');
  }
}

async function pollLoop() {
  try {
    const statusData = await fetchStatus();

    // Camera dot — update on both screens
    const camOk = statusData.camera_ok;
    const camDot = document.getElementById('cam-dot');
    const camText = document.getElementById('cam-text');
    const camDotP = document.getElementById('cam-dot-prompt');
    const camTextP = document.getElementById('cam-text-prompt');

    if (camOk) {
      if (camDot) camDot.className = 'status-dot cam-ok';
      if (camText) camText.textContent = 'Camera';
      if (camDotP) camDotP.className = 'status-dot cam-ok';
      if (camTextP) camTextP.textContent = 'Camera OK';
    } else {
      if (camDot) camDot.className = 'status-dot cam-err';
      if (camText) camText.textContent = 'No camera';
      if (camDotP) camDotP.className = 'status-dot cam-err';
      if (camTextP) camTextP.textContent = 'No camera';
    }

    // Processing dot
    const busy = statusData.processing !== null || statusData.live_mode;
    const procDot = document.getElementById('proc-dot');
    const procText = document.getElementById('proc-text');
    if (procDot) procDot.className = 'status-dot ' + (busy ? 'busy' : 'idle');
    if (procText) procText.textContent = busy ? 'Analyzing…' : 'Idle';

  } catch (e) { /* network hiccup */ }

  setTimeout(pollLoop, 1000);
}

async function liveResultsLoop() {
  if (!state.liveJobId) return;
  try {
    const histData = await fetchHistory();
    const job = (histData.jobs || []).find(j => j.id === state.liveJobId);
    if (job) {
      if (job.status === 'done' && job.result !== state.lastLiveResult) {
        state.lastLiveResult = job.result;
        state.liveCardCount += 1;
        const newId = state.liveJobId + '-' + state.liveCardCount;
        const list = document.getElementById('results-list');
        const empty = document.getElementById('empty-state');
        if (empty) empty.remove();
        const card = document.createElement('div');
        card.className = 'result-card done';
        card.id = 'card-' + newId;
        card.innerHTML = renderCard({
          id: newId,
          status: 'done',
          prompt: job.prompt,
          result: job.result,
          elapsed: job.elapsed,
          thumb: job.thumb,
          timestamp: job.timestamp,
        });
        list.insertBefore(card, list.firstChild);
        lucide.createIcons();
      }
      const indicator = document.getElementById('analyzing-indicator');
      if (indicator) {
        indicator.style.display = (job.status === 'processing' || job.status === 'queued') ? 'flex' : 'none';
      }
    }
  } catch (e) { /* network hiccup */ }
  if (state.liveJobId) setTimeout(liveResultsLoop, 1000);
}

function clearLiveResults() {
  const list = document.getElementById('results-list');
  list.innerHTML = '<div id="empty-state">Waiting for first inference\u2026</div>';
  state.lastLiveResult = null;
  state.liveCardCount = 0;
}

function setPreset(btn, text) {
  if (state.activePreset) state.activePreset.classList.remove('active');
  state.activePreset = btn;
  btn.classList.add('active');
  document.getElementById('prompt-input').value = text;
}

function togglePromptSettings() {
  const panel = document.getElementById('prompt-settings-panel');
  const btn = document.getElementById('prompt-settings-btn');
  const open = panel.style.display === 'block';
  panel.style.display = open ? 'none' : 'block';
  btn.classList.toggle('open', !open);
}

function resetPromptSettings() {
  document.getElementById('ps-image-size').value = '480';
  document.getElementById('ps-num-predict').value = '512';
  document.getElementById('ps-interval').value = '3';
  document.getElementById('ps-system-prompt').value = LIVE_DEFAULTS.system_prompt;
}

function init() {
  // Load current system prompt from backend
  fetchSettings().then(data => {
    const el = document.getElementById('ps-system-prompt');
    el.value = data.system_prompt || LIVE_DEFAULTS.system_prompt;
  }).catch(() => {
    document.getElementById('ps-system-prompt').value = LIVE_DEFAULTS.system_prompt;
  });

  // Stop any orphaned live session from a previous page visit
  fetch('/stop_live', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  }).catch(() => { });

  // Preset buttons
  document.getElementById('preset-describe').addEventListener('click', function () {
    setPreset(this, 'Describe what you see in this scene in short sentence.');
  });
  document.getElementById('preset-read').addEventListener('click', function () {
    setPreset(this, 'Read and transcribe every text, label, sign, or writing visible. List each one exactly as written.');
  });
  document.getElementById('preset-count').addEventListener('click', function () {
    setPreset(this, 'Count every distinct object or person visible. Give a total number and a breakdown by category.');
  });

  // Deactivate preset on manual typing
  document.getElementById('prompt-input').addEventListener('input', () => {
    if (state.activePreset) {
      state.activePreset.classList.remove('active');
      state.activePreset = null;
    }
  });

  // Start / stop
  document.getElementById('start-btn').addEventListener('click', doStartLive);
  document.getElementById('stop-btn').addEventListener('click', doStopLive);

  // Prompt screen settings
  document.getElementById('prompt-settings-btn').addEventListener('click', togglePromptSettings);
  document.getElementById('ps-reset-btn').addEventListener('click', resetPromptSettings);

  document.addEventListener('click', function (e) {
    const panel = document.getElementById('prompt-settings-panel');
    const btn = document.getElementById('prompt-settings-btn');
    if (!panel || !btn) return;
    if (panel.style.display !== 'block') return;
    if (!panel.contains(e.target) && !btn.contains(e.target)) {
      panel.style.display = 'none';
      btn.classList.remove('open');
    }
  });

  // Stop live mode if user refreshes/closes/navigates away
  window.addEventListener('beforeunload', () => {
    navigator.sendBeacon('/stop_live', '{}');
  });

  pollLoop();
  lucide.createIcons();
}

document.addEventListener('DOMContentLoaded', init);
