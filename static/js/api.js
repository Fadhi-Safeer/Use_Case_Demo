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

async function startLive(prompt, interval_seconds) {
  const r = await fetch('/start_live', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, interval_seconds }),
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
