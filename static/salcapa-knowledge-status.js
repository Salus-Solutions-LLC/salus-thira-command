/* Read-only view of the automatic SharePoint knowledge intake. */
viewTitles.knowledge_status = 'Knowledge Documents';
subtitles.knowledge_status = 'Find an uploaded document and see whether its original was verified and archived.';

function knowledgeStatusLabel(status) {
  if (status === 'Ingested and Verified') return 'Ready to reference';
  if (status === 'Pending Review') return 'Governed review required';
  if (status === 'Automatic Retry Required') return 'Processing will retry';
  if (status === 'Approved for Promotion') return 'Processing';
  return status || 'Processing';
}

function knowledgeReviewQueueRow(row) {
  const links = row.links || {};
  const available = [
    links.archived_original ? `<a href="${esc(links.archived_original)}" target="_blank" rel="noopener noreferrer">Open restricted archived original &gt;</a>` : '',
    links.library_copy ? `<a href="${esc(links.library_copy)}" target="_blank" rel="noopener noreferrer">Open restricted library copy &gt;</a>` : '',
  ].filter(Boolean).join(' ');
  return `<article class="card knowledge-item knowledge-review-item">
    <div class="section-title"><div><h3>${esc(row.source_name || 'Unnamed document')}</h3><p class="subtle">${esc(row.source_relative_path || 'Recorded intake source')}</p></div><strong>${esc(row.review_type)}</strong></div>
    <p><strong>Required next step:</strong> ${esc(row.next_action)}</p>
    <dl><dt>Target</dt><dd>${esc(row.target_folder || 'Not configured')}</dd>
      <dt>Extraction condition</dt><dd>${esc(row.failure_code || 'Extraction complete')}</dd>
      <dt>Destination evidence</dt><dd>${esc(row.destination_evidence)}</dd>
      <dt>Archive evidence</dt><dd>${esc(row.archive_evidence)}</dd>
      ${row.successor_match ? `<dt>Successor match</dt><dd>${esc(row.successor_match)} after ${Number(row.boundary_files_rechecked || 0).toLocaleString()} boundary files rechecked</dd>` : ''}
    </dl>
    <p class="subtle">This queue is read-only. It does not authorize research use, citation, assignment, release, or disclosure.</p>
    ${available ? `<div class="row-actions">${available}</div>` : '<p class="subtle">No verified review copy is available through this queue.</p>'}
  </article>`;
}

function knowledgeReviewQueue(queue) {
  const items = queue.items || [];
  const counts = queue.counts || {};
  return `<section class="card knowledge-review-hero"><h2>Governed review queue</h2>
    <p><strong>${items.length} records require human review.</strong> ${Number(counts.governed_extraction_review || 0)} require extraction review and ${Number(counts.unresolved_source_reconciliation || 0)} require source recovery or a governed unavailable-source exception.</p>
    <div class="notice"><strong>No automatic disposition.</strong> Protected Members cannot access this queue. Review evidence does not authorize research, teaching, citation, assignment, or release.</div></section>
    <div class="knowledge-list knowledge-review-list">${items.length ? items.map(knowledgeReviewQueueRow).join('') : '<div class="card">No governed Knowledge reviews are open.</div>'}</div>`;
}

function knowledgeStatusMetadata(row) {
  try {
    const classification = JSON.parse(row.classification_json || '{}');
    return classification.citation_metadata || {};
  } catch (_) { return {}; }
}

function knowledgeStatusRow(row) {
  const ready = row.status === 'Ingested and Verified' && !!row.source_archived_at;
  const metadata = knowledgeStatusMetadata(row);
  const sourceName = esc(row.source_name || 'Unnamed document');
  const where = esc(row.target_folder || 'Classification pending');
  const hash = esc(row.source_sha256 || '');
  const sourceDate = esc(metadata.source_created_at || metadata.source_modified_at || row.source_modified_at || 'Not recorded');
  const author = esc((Array.isArray(metadata.authors) ? metadata.authors.join(', ') : '') || row.source_owner || 'Not recorded');
  const citation = esc(metadata.citation_key || (hash ? `sha256:${hash}` : 'Not available yet'));
  const originalLink = ready && /^https:\/\//i.test(row.source_archive_web_url || '')
    ? `<a href="${esc(row.source_archive_web_url)}" target="_blank" rel="noopener noreferrer">Open archived original &gt;</a>` : '';
  const copyLink = ready && /^https:\/\//i.test(row.destination_web_url || '')
    ? `<a href="${esc(row.destination_web_url)}" target="_blank" rel="noopener noreferrer">Open library copy &gt;</a>` : '';
  return `<article class="card knowledge-item">
    <div class="section-title"><div><h3>${sourceName}</h3><p class="subtle">${where}</p></div><strong>${esc(knowledgeStatusLabel(row.status))}</strong></div>
    <p class="subtle">Author: ${author} · Document date: ${sourceDate}</p>
    <details><summary>Source and citation details</summary>
      <dl><dt>Citation key</dt><dd><code>${citation}</code></dd>
      <dt>Original SHA-256</dt><dd><code>${hash || 'Not available yet'}</code></dd>
      <dt>Processing status</dt><dd>${esc(row.status || 'Pending')}</dd>
      <dt>Original archived</dt><dd>${ready ? esc(row.source_archived_at) : 'Not yet verified and archived'}</dd></dl>
      <p class="subtle">The original hash identifies the source for citations. A SharePoint preview may render Office files differently from their verified original bytes.</p>
      <div class="row-actions">${originalLink} ${copyLink}</div>
    </details>
  </article>`;
}

async function knowledgeStatusView() {
  if (currentRole !== 'System Administrator' || isProtectedMember()) {
    $('#content').innerHTML = '<div class="notice">Knowledge intake status is available to authorized Salus administrators.</div>';
    return;
  }
  $('#content').innerHTML = '<section class="card"><h2>Knowledge Documents</h2><p>Checking automatically processed uploads…</p></section>';
  let data, reviewQueue;
  try {
    [data, reviewQueue] = await Promise.all([
      api('/api/integrations/m365/knowledge/candidates'),
      api('/api/integrations/m365/knowledge/review-queue'),
    ]);
  } catch (_) {
    $('#content').innerHTML = '<div class="notice" role="alert">Knowledge document status is unavailable right now. Please try again later.</div>';
    return;
  }
  const items = data.items || [];
  $('#content').innerHTML = `${knowledgeReviewQueue(reviewQueue)}<section class="card knowledge-hero"><h2>Knowledge Documents</h2>
    <p>See what has been received, processed, verified, and archived. Processing retries automatically when it cannot complete.</p>
    <label>Find a document<input id="knowledge-filter" type="search" placeholder="Search by file name or category" autocomplete="off"></label>
    <p id="knowledge-count" class="subtle" aria-live="polite"></p></section>
    <div id="knowledge-list" class="knowledge-list" aria-live="polite"></div>`;
  const filter = $('#knowledge-filter');
  const show = () => {
    const q = filter.value.trim().toLocaleLowerCase();
    const visible = items.filter(row => `${row.source_name || ''} ${row.target_folder || ''}`.toLocaleLowerCase().includes(q));
    const page = visible.slice(0, 100);
    $('#knowledge-count').textContent = `${page.length} of ${visible.length} matching document${visible.length === 1 ? '' : 's'} shown${visible.length > 100 ? ' · refine the search to find older items' : ''}`;
    $('#knowledge-list').innerHTML = visible.length ? page.map(knowledgeStatusRow).join('')
      : '<div class="card">No documents match this name or category.</div>';
  };
  filter.addEventListener('input', show);
  show();
}

const renderBeforeKnowledgeStatus = render;
render = async function() {
  const link = document.querySelector('#nav [data-view="knowledge_status"]');
  if (link) link.hidden = currentRole !== 'System Administrator' || isProtectedMember();
  if (currentView === 'knowledge_status') return knowledgeStatusView();
  const result = await renderBeforeKnowledgeStatus();
  if (link) link.hidden = currentRole !== 'System Administrator' || isProtectedMember();
  return result;
};
