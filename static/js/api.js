'use strict';

async function fetchStatus() {
  const r = await fetch('/status');
  return r.json();
}

async function fetchHistory() {
  const r = await fetch('/history');
  return r.json();
}

async function fetchSettings() {
  const r = await fetch('/settings');
  return r.json();
}

async function postSettings(data) {
  const r = await fetch('/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return r.json();
}

/**
 * @param {string} useCase  - 'gear' | 'weapon' | 'custom'
 * @param {string} prompt   - user prompt (only used for 'custom')
 * @param {number} interval - seconds between frames
 */
async function startLive(useCase, prompt, interval) {
  const r = await fetch('/start_live', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ use_case: useCase, prompt, interval_seconds: interval }),
  });
  return r.json();
}

async function stopLive() {
  const r = await fetch('/stop_live', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  return r.json();
}
