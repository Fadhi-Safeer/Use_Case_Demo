'use strict';

// ── Default prompts for reset ────────────────────────────────────────────────

const DEFAULTS = {
  num_predict:           512,
  max_image_size:        640,
  frame_interval:        3.0,
  job_timeout_seconds:   120,
  frame_timeout_seconds: 30,
  max_queue_size:        50,
  gear_system_prompt: "/no_think You are a construction site safety compliance inspector. Examine the image and determine if the visible worker is wearing required PPE: safety helmet or hard hat, and a high-visibility vest. Answer with exactly one word: Yes if all required visible gear is worn correctly, No if any item is missing or worn incorrectly.",
  gear_user_prompt:   "Is the worker wearing all required safety gear? Answer Yes or No only.",
  weapon_system_prompt: "/no_think You are a security surveillance AI monitoring a construction site. Examine the image carefully for any weapons or dangerous objects: knives, firearms, batons, blades, or similar threats. Answer with exactly one word: Yes if a weapon or dangerous object is visible, No if the scene appears safe.",
  weapon_user_prompt: "Is there a weapon or dangerous object visible in this image? Answer Yes or No only.",
  custom_system_prompt: "/no_think You are a visual analysis assistant. Examine the image carefully and answer the user's question. Be concise and direct. Prefer Yes or No answers when applicable.",
  show_duplicate_results: false,
};


// ── Tab switching ─────────────────────────────────────────────────────────────

function switchTab(tab) {
  // If switching away from a running tab — stop it first
  if (state.activeRunningTab && state.activeRunningTab !== tab) {
    _stopLiveForTab(state.activeRunningTab).catch(() => {});
  }

  document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-page').forEach(p => p.classList.add('hidden'));

  document.querySelector(`.nav-tab[data-tab="${tab}"]`).classList.add('active');
  document.getElementById(`tab-${tab}`).classList.remove('hidden');
  state.activeTab = tab;

  lucide.createIcons();
}


// ── Camera / status poll loop ─────────────────────────────────────────────────

async function pollLoop() {
  try {
    const s = await fetchStatus();
    const camOk = s.camera_ok;
    state.camera.ok = camOk;

    // Update all cam dots
    ['gear', 'weapon', 'custom'].forEach(uc => {
      const dot  = document.getElementById(`cam-dot-${uc}`);
      const text = document.getElementById(`cam-text-${uc}`);
      if (dot)  dot.className  = 'status-dot ' + (camOk ? 'cam-ok' : 'cam-err');
      if (text) text.textContent = camOk ? 'Camera OK' : 'No camera';
    });

    // Nav status pills
    const navDot  = document.getElementById('cam-dot');
    const navText = document.getElementById('cam-text');
    if (navDot)  navDot.className  = 'status-dot ' + (camOk ? 'cam-ok' : 'cam-err');
    if (navText) navText.textContent = camOk ? 'Camera' : 'No cam';

    const busy = s.live_mode;
    const procDot  = document.getElementById('proc-dot');
    const procText = document.getElementById('proc-text');
    if (procDot)  procDot.className  = 'status-dot ' + (busy ? 'busy' : 'idle');
    if (procText) procText.textContent = busy ? 'Analyzing…' : 'Idle';

    let homeHist = null;
    if (state.activeTab === 'home') {
      const h = await fetchHistory();
      homeHist = h.jobs || [];
    }
    updateHomePage(s, homeHist);

  } catch (_) { /* network hiccup */ }

  setTimeout(pollLoop, 1000);
}


// ── Alert sound (played in browser when alert_fired is true) ──────────────────

const alertSound = new Audio('/static/alert.wav');

// ── Results poll loops ────────────────────────────────────────────────────────

async function resultsLoop(useCase) {
  const ts = state.tabs[useCase];
  if (!ts.liveSessionId) return;

  try {
    const hist = await fetchHistory();
    const jobs = hist.jobs || [];

    // Show "analyzing" indicator if any entry for this session is in-flight
    const analyzing = document.getElementById(`${useCase}-analyzing`);
    if (analyzing) {
      const inFlight = jobs.some(
        j => j.session_id === ts.liveSessionId &&
             (j.status === 'processing' || j.status === 'queued')
      );
      analyzing.classList.toggle('visible', inFlight);
    }

    // Render all done/error/cancelled entries not yet shown, in capture order
    const listEl = document.getElementById(`results-list-${useCase}`);
    if (listEl) {
      const newJobs = jobs
        .filter(j => j.session_id === ts.liveSessionId &&
                     j.status !== 'queued' && j.status !== 'processing' &&
                     (j.seq_num || 0) > ts.lastSeenSeq)
        .sort((a, b) => (a.seq_num || 0) - (b.seq_num || 0));

      for (const job of newJobs) {
        ts.lastResult  = job.result;
        ts.lastSeenSeq = job.seq_num || ts.lastSeenSeq;
        ts.cardCount  += 1;
        addCard(listEl, job, useCase);
        if (job.alert_fired) {
          alertSound.play().catch(e => console.warn('Browser blocked audio:', e));
          const card = document.getElementById('card-' + job.id);
          if (card) card.classList.add('alert-fired');
        }
      }
    }
  } catch (_) { /* network hiccup */ }

  if (ts.liveSessionId) setTimeout(() => resultsLoop(useCase), 1000);
}


// ── Start live ────────────────────────────────────────────────────────────────

async function doStart(useCase) {
  const btn = document.getElementById(`start-btn-${useCase}`);
  btn.disabled = true;

  // Stop any currently running tab
  if (state.activeRunningTab) {
    await _stopLiveForTab(state.activeRunningTab).catch(() => {});
  }

  // For custom, grab the typed prompt
  let userPrompt = '';
  if (useCase === 'custom') {
    userPrompt = document.getElementById('custom-prompt-input').value.trim();
    if (!userPrompt) {
      alert('Enter a prompt first.');
      btn.disabled = false;
      return;
    }
  }

  const interval = parseFloat(document.getElementById('s-interval').value || '3');

  try {
    const data = await startLive(useCase, userPrompt, interval);
    if (data.error) {
      alert(data.error);
      btn.disabled = false;
      return;
    }

    const ts = state.tabs[useCase];
    ts.liveSessionId  = data.job_id;
    ts.lastResult     = null;
    ts.lastSeenSeq    = 0;
    ts.cardCount      = 0;
    state.activeRunningTab = useCase;

    // Clear results list
    const listEl = document.getElementById(`results-list-${useCase}`);
    listEl.innerHTML = '<div class="empty-state">Waiting for first inference…</div>';

    // Show live prompt label
    const promptLabel = data.prompt || userPrompt;
    const short = promptLabel.length > 80 ? promptLabel.slice(0, 77) + '…' : promptLabel;
    const lp = document.getElementById(`${useCase}-live-prompt`);
    if (lp) lp.textContent = short;

    // Start video feed
    const img     = document.getElementById(`feed-img-${useCase}`);
    const offline = document.getElementById(`feed-offline-${useCase}`);
    img.style.display = 'block';
    offline.style.display = 'none';
    img.onerror = () => { img.style.display = 'none'; offline.style.display = 'flex'; };
    img.src = '/video_feed';

    // Switch screens
    document.getElementById(`${useCase}-prompt-screen`).classList.add('hidden');
    document.getElementById(`${useCase}-live-screen`).classList.remove('hidden');

    lucide.createIcons();
    resultsLoop(useCase);

  } catch (e) {
    alert('Request failed: ' + e.message);
    btn.disabled = false;
  }
}


// ── Stop live ─────────────────────────────────────────────────────────────────

async function doStop(useCase) {
  await _stopLiveForTab(useCase).catch(() => {});
}

async function _stopLiveForTab(useCase) {
  await stopLive().catch(() => {});

  const ts = state.tabs[useCase];
  ts.liveSessionId   = null;
  ts.lastResult      = null;
  ts.lastSeenSeq     = 0;
  ts.cardCount       = 0;
  state.activeRunningTab = null;

  // Stop video
  const img = document.getElementById(`feed-img-${useCase}`);
  if (img) { img.src = ''; img.style.display = 'none'; }
  const offline = document.getElementById(`feed-offline-${useCase}`);
  if (offline) offline.style.display = 'none';

  // Hide analyzing indicator
  const ind = document.getElementById(`${useCase}-analyzing`);
  if (ind) ind.classList.remove('visible');

  // Switch back to prompt screen
  document.getElementById(`${useCase}-live-screen`).classList.add('hidden');
  document.getElementById(`${useCase}-prompt-screen`).classList.remove('hidden');

  const btn = document.getElementById(`start-btn-${useCase}`);
  if (btn) btn.disabled = false;

  lucide.createIcons();
}


// ── Clear results ─────────────────────────────────────────────────────────────

function clearResults(useCase) {
  const listEl = document.getElementById(`results-list-${useCase}`);
  if (listEl) listEl.innerHTML = '<div class="empty-state">Waiting for first inference…</div>';
  state.tabs[useCase].lastResult  = null;
  state.tabs[useCase].lastSeenSeq = 0;
  state.tabs[useCase].cardCount   = 0;
}


// ── Settings page ─────────────────────────────────────────────────────────────

function loadSettingsIntoForm(data) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
  set('s-image-size',    data.max_image_size    || 640);
  set('s-num-predict',   data.num_predict       || 512);
  set('s-interval',      data.frame_interval    || 3);
  set('s-job-timeout',   data.job_timeout_seconds   || 120);
  set('s-frame-timeout', data.frame_timeout_seconds || 30);
  set('s-queue-size',    data.max_queue_size    || 50);
  const dupeEl = document.getElementById('s-show-dupes');
  if (dupeEl) dupeEl.checked = !!data.show_duplicate_results;
  state.showDuplicates = !!data.show_duplicate_results;
  set('s-gear-sys',      data.gear_system_prompt   || '');
  set('s-gear-user',     data.gear_user_prompt     || '');
  set('s-weapon-sys',    data.weapon_system_prompt || '');
  set('s-weapon-user',   data.weapon_user_prompt   || '');
  set('s-custom-sys',    data.custom_system_prompt || '');
}

function loadPromptPreviews(data) {
  const gp = document.getElementById('gear-prompt-preview');
  const wp = document.getElementById('weapon-prompt-preview');
  if (gp) gp.textContent = data.gear_user_prompt   || '—';
  if (wp) wp.textContent = data.weapon_user_prompt || '—';
}

async function saveSettings() {
  const val = id => document.getElementById(id).value;
  const payload = {
    max_image_size:        parseInt(val('s-image-size')),
    num_predict:           parseInt(val('s-num-predict')),
    frame_interval:        parseFloat(val('s-interval')),
    job_timeout_seconds:   parseInt(val('s-job-timeout')),
    frame_timeout_seconds: parseInt(val('s-frame-timeout')),
    max_queue_size:        parseInt(val('s-queue-size')),
    show_duplicate_results: document.getElementById('s-show-dupes').checked,
    gear_system_prompt:    val('s-gear-sys'),
    gear_user_prompt:      val('s-gear-user'),
    weapon_system_prompt:  val('s-weapon-sys'),
    weapon_user_prompt:    val('s-weapon-user'),
    custom_system_prompt:  val('s-custom-sys'),
  };

  try {
    const data = await postSettings(payload);
    state.showDuplicates = !!data.show_duplicate_results;
    loadPromptPreviews(data);
    showToast();
  } catch (e) {
    alert('Save failed: ' + e.message);
  }
}

function resetSettings() {
  loadSettingsIntoForm(DEFAULTS);
}

function showToast() {
  const t = document.getElementById('settings-toast');
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2200);
}


// ── Home page update ──────────────────────────────────────────────────────────

function updateHomePage(statusData, historyJobs) {
  const camEl = document.getElementById('home-camera-val');
  if (camEl) {
    const ok = statusData.camera_ok;
    camEl.textContent = ok ? 'Online' : 'Offline';
    camEl.className   = 'home-status-val ' + (ok ? 'online' : 'offline');
  }

  if (historyJobs) {
    const vlmEl = document.getElementById('home-vlm-val');
    if (vlmEl) {
      const hasError = historyJobs.some(j => j.result && j.result.startsWith('[ERROR]'));
      vlmEl.textContent = hasError ? 'Unreachable' : 'Online';
      vlmEl.className   = 'home-status-val ' + (hasError ? 'offline' : 'online');
    }

    const latEl = document.getElementById('home-latency-val');
    if (latEl) {
      const done = historyJobs.filter(j => j.status === 'done' && j.elapsed != null);
      const last = done.length ? done[done.length - 1] : null;
      latEl.textContent = last ? `${last.elapsed} s` : '—';
    }
  }
}


// ── Init ──────────────────────────────────────────────────────────────────────

function init() {
  // Stop any orphaned session from previous visit
  fetch('/stop_live', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  }).catch(() => {});

  // Load settings from backend → populate form + prompt previews
  fetchSettings().then(data => {
    loadSettingsIntoForm(data);
    loadPromptPreviews(data);
  }).catch(() => {
    loadSettingsIntoForm(DEFAULTS);
    loadPromptPreviews(DEFAULTS);
  });

  // Tab buttons
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Start buttons
  ['gear', 'weapon', 'custom'].forEach(uc => {
    document.getElementById(`start-btn-${uc}`)
      .addEventListener('click', () => doStart(uc));
    document.getElementById(`stop-btn-${uc}`)
      .addEventListener('click', () => doStop(uc));
  });

  // Improve prompt button (custom tab only)
  document.getElementById('improve-prompt-btn').addEventListener('click', async () => {
    const textarea = document.getElementById('custom-prompt-input');
    const rawPrompt = textarea.value.trim();
    if (!rawPrompt) return;
    const btn = document.getElementById('improve-prompt-btn');
    btn.disabled = true;
    btn.innerText = 'Improving…';
    try {
      const improved = await improvePrompt(rawPrompt);
      textarea.value = improved;
    } catch (e) {
      alert(e.message);
    } finally {
      btn.disabled = false;
      btn.innerText = 'Improve';
    }
  });

  // Settings page
  document.getElementById('settings-save-btn').addEventListener('click', saveSettings);
  document.getElementById('settings-reset-btn').addEventListener('click', resetSettings);

  // Stop on page unload
  window.addEventListener('beforeunload', () => {
    navigator.sendBeacon('/stop_live', '{}');
  });

  state.activeTab = 'home';
  pollLoop();
  lucide.createIcons();
}

document.addEventListener('DOMContentLoaded', init);
