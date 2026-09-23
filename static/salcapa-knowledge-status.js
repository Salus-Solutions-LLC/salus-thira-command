/* Read-only view of the automatic SharePoint knowledge intake. */
viewTitles.knowledge_status = 'Knowledge Documents';
subtitles.knowledge_status = 'Find an uploaded document and see whether its original was verified and archived.';

function knowledgeStatusLabel(status) {
  if (status === 'Ingested and Verified') return 'Ready to reference';
  if (status === 'Automatic Retry Required') return 'Processing will retry';
  if (status === 'Approved for Promotion') return 'Processing';
  return status || 'Processing';
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
  const data = await api('/api/integrations/m365/knowledge/candidates');
  const items = data.items || [];
  $('#content').innerHTML = `<section class="card knowledge-hero"><h2>Knowledge Documents</h2>
    <p>See what has been received, processed, verified, and archived. Processing retries automatically when it cannot complete.</p>
    <label>Find a document<input id="knowledge-filter" type="search" placeholder="Search by file name or category" autocomplete="off"></label>
    <p id="knowledge-count" class="subtle" aria-live="polite"></p></section>
    <div id="knowledge-list" class="knowledge-list" aria-live="polite"></div>`;
  const filter = $('#knowledge-filter');
  const show = () => {
    const q = filter.value.trim().toLocaleLowerCase();
    const visible = items.filter(row => `${row.source_name || ''} ${row.target_folder || ''}`.toLocaleLowerCase().includes(q));
    $('#knowledge-count').textContent = `${visible.length} document${visible.length === 1 ? '' : 's'} shown`;
    $('#knowledge-list').innerHTML = visible.length ? visible.map(knowledgeStatusRow).join('')
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
