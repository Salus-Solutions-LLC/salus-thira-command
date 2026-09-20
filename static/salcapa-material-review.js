/* Governed derived-material review. Human authority and source truth remain explicit. */
viewTitles.material_review='SalCAPA™ Information Review';
subtitles.material_review='Review source-derived text, search authorized material, and preserve what remains uncertain.';

let salcapaMaterialReviewData=null;

function materialReviewRows(items){
  return table(['Source','Derived representation','State','Lineage','Action'],items.map(item=>[
    `<strong>${esc(item.source_title)}</strong><br><span class="subtle">${esc(item.original_name)} · ${esc(item.material_kind)} · ${esc(item.sensitivity)}</span>`,
    `<span class="subtle">${esc(item.content_preview||'No extracted text')}</span>${item.truncated?'<br><strong>Preview is limited; the derived text was truncated by the safe-processing limit.</strong>':''}`,
    `<strong>${esc(item.review_status)}</strong><br><span class="subtle">${esc(item.confidence_status)}</span>`,
    `<code>${esc(String(item.source_sha256||'').slice(0,16))}…</code><br><span class="subtle">${esc(item.processor)} ${esc(item.processor_version)}</span>`,
    `<button class="btn secondary" type="button" onclick="openMaterialDerivative(${Number(item.id)})">Review details</button>`
  ]));
}

async function salcapaMaterialReview(){
  if(isProtectedMember()){
    $('#content').innerHTML='<div class="notice">Derived processing and analyst review are available only to authorized Salus personnel.</div>';
    return;
  }
  salcapaMaterialReviewData=await api('/api/material-processing/triage');
  const pending=salcapaMaterialReviewData.items.filter(item=>item.review_status==='Awaiting Human Review').length;
  $('#content').innerHTML=`<section class="card material-review-hero"><div class="section-title"><div><span>Governed source review</span><h2>Information Review</h2><p>Review what was derived from authorized source material without confusing extraction with evidence, intelligence, or a decision.</p></div><strong>${pending} awaiting review</strong></div><div class="notice"><strong>People retain authority.</strong><br>${esc(salcapaMaterialReviewData.guidance)} Human review does not establish that the source itself is true.</div><form id="material-search-form" class="material-search"><label>Search authorized derived text<input name="query" minlength="2" maxlength="200" required placeholder="Enter a word or phrase"></label><button class="btn" type="submit">Search information</button></form></section><div id="material-search-results" aria-live="polite"></div><section><div class="section-title"><div><h2>Review queue</h2><p class="subtle">Sensitivity and tenant boundaries apply before results reach this view.</p></div></div>${materialReviewRows(salcapaMaterialReviewData.items)}</section><div id="material-review-detail"></div>`;
  $('#material-search-form').onsubmit=searchMaterialDerivatives;
}

async function searchMaterialDerivatives(event){
  event.preventDefault();
  const query=new FormData(event.target).get('query');
  const data=await api(`/api/material-processing/search?q=${encodeURIComponent(query)}`);
  const rows=data.items.map(item=>[
    `<strong>${esc(item.source_title)}</strong><br><span class="subtle">${esc(item.original_name)}</span>`,
    esc(item.match_excerpt),
    `${esc(item.review_status)}<br><span class="subtle">${esc(item.confidence_status)}</span>`,
    `<button class="btn secondary" type="button" onclick="openMaterialDerivative(${Number(item.id)})">Review details</button>`
  ]);
  $('#material-search-results').innerHTML=`<section class="card"><div class="section-title"><div><h2>Search results</h2><p class="subtle">${esc(data.scope_note)}</p></div><strong>${rows.length} result${rows.length===1?'':'s'}</strong></div>${table(['Source','Matching context','Review state','Action'],rows)}</section>`;
}

async function materialGovernanceStatus(id){
  return api(`/api/salintel/research/material-derivatives/${Number(id)}/index-status`);
}

function materialGovernanceActions(item,status){
  if(item.review_status!=='Human Reviewed')return '';
  if(status.eligible_for_indexing&&(accessState?.permissions||[]).includes('write')){
    return `<div class="material-governance-step"><h3>2. Authorize research indexing</h3><p>Index the human-reviewed derivative as a tenant- and clearance-scoped SalINTEL source aid. This does not establish source truth or create a finding.</p><button class="btn" type="button" onclick="indexMaterialDerivative(${Number(item.id)})">Index for SalINTEL research</button></div>`;
  }
  if(status.indexed){
    const routed=status.routes||[];
    return `<div class="material-governance-step"><h3>2. SalINTEL source aid</h3><p><strong>${esc(status.index_key)}</strong> · ${esc(status.evidence_status)}</p><p>This indexed aid does not establish source truth and remains subject to attribution, sensitivity, and human judgment.</p><div class="material-route-history">${routed.length?routed.map(route=>`<p><strong>${esc(route.route_key)}</strong> · Assessment #${Number(route.assessment_id)} · ${esc(route.evidence_status)}</p>`).join(''):'<p>Not routed to SalTHIRA.</p>'}</div>${(accessState?.permissions||[]).includes('decide')? `<button class="btn" type="button" onclick="routeMaterialDerivative(${Number(item.id)},${Number(status.index_id)})">Route to active SalTHIRA assessment</button>`:''}</div>`;
  }
  return '<div class="notice">This derivative is not eligible for indexing.</div>';
}

async function openMaterialDerivative(id){
  const [item,status]=await Promise.all([
    api(`/api/material-processing/derivatives/${Number(id)}`),
    materialGovernanceStatus(id)
  ]);
  const action=item.review_status==='Awaiting Human Review'&&(accessState?.permissions||[]).includes('decide')
    ?`<div class="material-governance-step"><h3>1. Human source comparison</h3><p>Compare the derived representation with the governed source and record limitations.</p><div class="form-actions"><button class="btn" type="button" onclick="reviewMaterialDerivative(${Number(id)},'Human Reviewed')">Record human review</button><button class="btn secondary" type="button" onclick="reviewMaterialDerivative(${Number(id)},'Rejected')">Reject derived representation</button></div></div>`:'';
  $('#material-review-detail').innerHTML=`<article class="card material-review-detail" tabindex="-1"><div class="section-title"><div><span>${esc(item.derivative_key)}</span><h2>${esc(item.source_title)}</h2></div><strong>${esc(item.review_status)}</strong></div><dl><div><dt>Exact source hash</dt><dd><code>${esc(item.source_sha256)}</code></dd></div><div><dt>Derived-content hash</dt><dd><code>${esc(item.content_sha256)}</code></dd></div><div><dt>Method</dt><dd>${esc(item.extraction_method)}</dd></div><div><dt>Processor</dt><dd>${esc(item.processor)} ${esc(item.processor_version)}</dd></div><div><dt>Uncertainty</dt><dd>${esc(item.uncertainty_note)}</dd></div></dl><h3>Derived text</h3><pre>${esc(item.content_text)}</pre><div class="notice"><strong>Authority remains with people.</strong><br>${esc(item.authority_note)} Indexing and routing remain separate authorized actions.</div>${action}${materialGovernanceActions(item,status)}</article>`;
  const detail=$('.material-review-detail');detail.scrollIntoView({behavior:'smooth',block:'start'});detail.focus({preventScroll:true});
}

async function indexMaterialDerivative(id){
  const basis=prompt('Indexing basis. Confirm why this human-reviewed derivative is appropriate as a SalINTEL research source aid:');
  if(!basis)return;
  await api(`/api/salintel/research/material-derivatives/${Number(id)}/index`,{method:'POST',body:JSON.stringify({basis})});
  await openMaterialDerivative(id);
}

async function routeMaterialDerivative(id,indexId){
  const assessment=await getActiveAssessment();
  if(!assessment){alert('Select or create an active SalTHIRA assessment before routing evidence.');return;}
  const title=prompt('Evidence title for the active SalTHIRA assessment:');
  if(!title)return;
  const routingBasis=prompt('Routing basis. Explain why this attributed source aid is relevant for evidence review:');
  if(!routingBasis)return;
  const result=await api(`/api/salthira/material-index/${Number(indexId)}/route-evidence`,{method:'POST',body:JSON.stringify({
    assessment_id:Number(assessment.id),title,evidence_type:'Governed Source Aid',
    reliability:'Medium',routing_basis:routingBasis
  })});
  alert(`Routed as ${result.evidence_status}. No finding, risk conclusion, recommendation, or decision was created.`);
  await openMaterialDerivative(id);
}

async function reviewMaterialDerivative(id,status){
  const reason=prompt(`${status} basis. Confirm what was compared with the source and any limitations:`);
  if(!reason)return;
  await api(`/api/material-processing/derivatives/${Number(id)}/review`,{method:'POST',body:JSON.stringify({status,reason})});
  await salcapaMaterialReview();
}

const salcapaRenderWithoutMaterialReview=render;
render=async function(){if(currentView==='material_review')return salcapaMaterialReview();return salcapaRenderWithoutMaterialReview();};
