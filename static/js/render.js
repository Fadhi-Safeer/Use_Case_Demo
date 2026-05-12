'use strict';

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function statusTagClass(status) {
  return 'ctag ctag-status-' + status;
}

function renderCard(job) {
  const thumb = job.thumb
    ? `<img class="card-thumb" src="data:image/jpeg;base64,${job.thumb}" alt="frame">`
    : `<div class="card-thumb-ph">${escHtml(job.status)}</div>`;

  const elapsed = job.elapsed != null ? `<span class="ctag">${job.elapsed}s</span>` : '';
  const ts      = job.timestamp ? `<span class="ctag">${escHtml(job.timestamp)}</span>` : '';

  let bodyHtml = '';
  if (job.status === 'queued') {
    bodyHtml = `<div class="card-result pending">Waiting in queue…</div>`;
  } else if (job.status === 'processing') {
    bodyHtml = `<div class="card-result pending">Analyzing…</div>`;
  } else if (job.status === 'error') {
    bodyHtml = `<div class="card-result error">${escHtml(job.result || '')}</div>`;
  } else {
    bodyHtml = `<div class="card-result">${escHtml(job.result || '')}</div>`;
  }

  return `
    <div class="card-top">
      ${thumb}
      <div class="card-meta">
        <div class="card-prompt" title="${escHtml(job.prompt)}">${escHtml(job.prompt)}</div>
        <div class="card-tags">
          <span class="${statusTagClass(job.status)}">${escHtml(job.status)}</span>
          ${elapsed}
          ${ts}
        </div>
      </div>
    </div>
    <div class="card-body">${bodyHtml}</div>`;
}

function addPendingCard(job_id, prompt) {
  const empty = document.getElementById('empty-state');
  if (empty) empty.remove();

  const card = document.createElement('div');
  card.className = 'result-card queued';
  card.id = 'card-' + job_id;
  card.innerHTML = renderCard({ id: job_id, status: 'queued', prompt, thumb: null, elapsed: null, timestamp: null });

  const list = document.getElementById('results-list');
  list.insertBefore(card, list.firstChild);
  state.pendingCards[job_id] = true;
}

function updateCard(job) {
  const card = document.getElementById('card-' + job.id);
  if (!card) return;

  // Save open state of any <details> inside before replacing innerHTML
  const openDetails = new Set();
  card.querySelectorAll('details').forEach((d, i) => { if (d.open) openDetails.add(i); });

  card.className = 'result-card ' + job.status;
  card.innerHTML = renderCard(job);

  // Restore open state
  card.querySelectorAll('details').forEach((d, i) => { if (openDetails.has(i)) d.open = true; });

  if (job.status === 'done' || job.status === 'error') {
    delete state.pendingCards[job.id];
  }
}
