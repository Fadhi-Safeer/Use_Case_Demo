'use strict';

function escHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Determine pass/fail from a Yes/No result text, respecting use-case polarity.
 *
 * Gear   : Yes → PASS (green),  No → FAIL (red)
 * Weapon : Yes → FAIL (red),    No → PASS (green)   ← inverted
 * Custom : Yes → PASS (green),  No → FAIL (red)
 *
 * @returns {'pass'|'fail'|'unknown'}
 */
function parseResultState(resultText, useCase) {
  if (!resultText) return 'unknown';
  const t = resultText.toLowerCase().trim();
  const isYes = t === 'yes' || t.startsWith('yes');
  const isNo  = t === 'no'  || t.startsWith('no');

  if (!isYes && !isNo) return 'unknown';

  if (useCase === 'weapon') {
    return isYes ? 'fail' : 'pass';   // weapon present = danger
  }
  return isYes ? 'pass' : 'fail';     // gear present = pass; custom yes = pass
}

function resultStateBadge(resultState, useCase) {
  if (resultState === 'pass') {
    const label = useCase === 'weapon' ? 'CLEAR' : 'PASS';
    return `<span class="result-state-badge badge-pass"><i data-lucide="check-circle"></i> ${label}</span>`;
  }
  if (resultState === 'fail') {
    const label = useCase === 'weapon' ? 'THREAT' : 'FAIL';
    return `<span class="result-state-badge badge-fail"><i data-lucide="x-circle"></i> ${label}</span>`;
  }
  return `<span class="result-state-badge badge-unknown">—</span>`;
}

/**
 * Render the inner HTML of a result card.
 * @param {Object} job
 * @param {string} useCase - 'gear'|'weapon'|'custom'
 */
function renderCard(job, useCase) {
  const thumb = job.thumb
    ? `<img class="card-thumb" src="data:image/jpeg;base64,${job.thumb}" alt="frame">`
    : `<div class="card-thumb-ph">${escHtml(job.status)}</div>`;

  const elapsed = job.elapsed != null ? `<span class="ctag">${job.elapsed}s</span>` : '';
  const ts      = job.timestamp ? `<span class="ctag">${escHtml(job.timestamp)}</span>` : '';

  let bodyHtml = '';
  let stateBadge = '';

  if (job.status === 'queued' || job.status === 'processing') {
    bodyHtml = `<div class="card-result pending">Analyzing…</div>`;
    stateBadge = `<span class="ctag ctag-amber">${escHtml(job.status)}</span>`;
  } else if (job.status === 'cancelled') {
    bodyHtml = `<div class="card-result pending">Cancelled</div>`;
    stateBadge = `<span class="ctag">CANCELLED</span>`;
  } else if (job.status === 'error') {
    bodyHtml = `<div class="card-result error-text">${escHtml(job.result || '')}</div>`;
    stateBadge = `<span class="result-state-badge badge-fail">ERROR</span>`;
  } else {
    // Done — determine pass/fail
    const rs = parseResultState(job.result, useCase);
    stateBadge = resultStateBadge(rs, useCase);
    bodyHtml = `<div class="card-result">${escHtml(job.result || '')}</div>`;
  }

  return `
    <div class="card-top">
      ${thumb}
      <div class="card-meta">
        <div class="card-tags">
          ${stateBadge}
          ${elapsed}
          ${ts}
        </div>
      </div>
    </div>
    <div class="card-body">${bodyHtml}</div>`;
}

/**
 * Compute the CSS class for a completed card (pass/fail/unknown/error/queued/processing).
 */
function cardClass(job, useCase) {
  if (job.status === 'error')     return 'result-card error';
  if (job.status === 'cancelled') return 'result-card';
  if (job.status === 'queued' || job.status === 'processing') return 'result-card processing';
  const rs = parseResultState(job.result, useCase);
  return `result-card ${rs}`;
}

/**
 * Prepend a new card to a results list.
 */
function addCard(listEl, job, useCase) {
  const empty = listEl.querySelector('.empty-state');
  if (empty) empty.remove();

  const card = document.createElement('div');
  card.className = cardClass(job, useCase);
  card.id = 'card-' + job.id;
  card.innerHTML = renderCard(job, useCase);
  listEl.insertBefore(card, listEl.firstChild);
  lucide.createIcons();
}
