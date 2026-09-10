/* Governed source-review suggestions. Proposals remain distinct from authoritative records. */
let salcapaSuggestionReviewData={suggestions:[],comparisons:[]};

function sourceSuggestionRows(items){
  return table(['Source context','Proposed review aid','State','Review'],items.map(item=>{
    const alternatives=(item.alternatives||[]).length
      ?`<br><span class="subtle">Possible interpretations: ${item.alternatives.map(esc).join(' · ')}</span>`:'';
    const reviewed=item.review_status!=='Awaiting Human Review';
    const actions=!reviewed&&(accessState?.permissions||[]).includes('decide')
      ?`<button class="btn secondary" type="button" onclick="reviewSourceSuggestion(${Number(item.id)},'Human Reviewed')">Confirm review aid</button> <button class="btn secondary" type="button" onclick="reviewSourceSuggestion(${Number(item.id)},'Corrected')">Record correction</button> <button class="btn secondary" type="button" onclick="reviewSourceSuggestion(${Number(item.id)},'Rejected')">Reject</button>`
      :reviewed?`<button class="btn secondary" type="button" onclick="proposeSourceSuggestionLink(${Number(item.id)})">Propose governed link</button>`:'Review permission required';
    return [
      `<strong>${esc(item.source_title)}</strong><br><span class="subtle">${esc(item.suggestion_type)} · ${esc(item.source_text)}</span><details><summary>Source context and limits</summary><p>${esc(item.context_text)}</p><p>${esc(item.uncertainty_note)}</p></details>`,
      `<strong>${esc(item.current_value||item.proposed_value)}</strong>${alternatives}<br><span class="subtle">${esc(item.method)}</span>`,
      `<strong>${esc(item.review_status)}</strong><br><span class="subtle">${esc(item.confidence_status)}</span>`,
      actions,
    ];
  }));
}

function sourceComparisonRows(items){
  return table(['Sources','Comparison','Basis','Review'],items.map(item=>{
    const actions=item.review_status==='Awaiting Human Review'&&(accessState?.permissions||[]).includes('decide')
      ?`<button class="btn secondary" type="button" onclick="reviewSourceComparison(${Number(item.id)},'Human Reviewed')">Record review</button> <button class="btn secondary" type="button" onclick="reviewSourceComparison(${Number(item.id)},'Rejected')">Reject comparison</button>`
      :esc(item.review_status);
    return [
      `<strong>${esc(item.left_title)}</strong><br><span class="subtle">compared with</span><br><strong>${esc(item.right_title)}</strong>`,
      `<strong>${esc(item.comparison_class)}</strong><br><span class="subtle">${esc(item.similarity_band)}</span>`,
      `<details><summary>Why this was proposed</summary><p>${esc(item.support_summary)}</p><p>${esc(item.difference_summary)}</p><p>${esc(item.uncertainty_note)}</p></details>`,
      actions,
    ];
  }));
}

async function loadSourceSuggestions(){
  salcapaSuggestionReviewData=await api('/api/material-suggestions/triage');
  const anchor=$('#material-review-detail');
  if(!anchor)return;
  const pending=salcapaSuggestionReviewData.suggestions.filter(item=>item.review_status==='Awaiting Human Review').length;
  const comparisons=salcapaSuggestionReviewData.comparisons.filter(item=>item.review_status==='Awaiting Human Review').length;
  anchor.insertAdjacentHTML('beforebegin',`<section class="card source-review-aids"><div class="section-title"><div><span>Review aids</span><h2>Suggested references, dates, times, and locations</h2><p>${esc(salcapaSuggestionReviewData.guidance)}</p></div><strong>${pending} awaiting review</strong></div><div class="notice"><strong>People retain authority.</strong> Review the source context, uncertainty, and authorized references before accepting, correcting, or rejecting an aid.</div>${sourceSuggestionRows(salcapaSuggestionReviewData.suggestions)}</section><section class="card source-review-aids"><div class="section-title"><div><span>Duplicate review</span><h2>Source comparisons</h2><p>Open and compare the original records before deciding whether a similarity is useful.</p></div><strong>${comparisons} awaiting review</strong></div>${sourceComparisonRows(salcapaSuggestionReviewData.comparisons)}</section>`);
}

async function prepareMaterialSuggestions(id){
  const reason=prompt('Purpose for preparing source-review suggestions:');
  if(!reason)return;
  await api(`/api/material-processing/derivatives/${Number(id)}/review-suggestions`,{method:'POST',body:JSON.stringify({reason})});
  await salcapaMaterialReview();
}

async function reviewSourceSuggestion(id,status){
  const reason=prompt(`${status} basis. Record what you checked and any remaining uncertainty:`);
  if(!reason)return;
  let corrected_value='';
  if(status==='Corrected'){
    corrected_value=prompt('Corrected value. The initial proposal and correction history will remain preserved:')||'';
    if(!corrected_value)return;
  }
  await api(`/api/material-suggestions/${Number(id)}/review`,{method:'POST',body:JSON.stringify({status,reason,corrected_value})});
  await salcapaMaterialReview();
}

async function reviewSourceComparison(id,status){
  const reason=prompt(`${status} basis. Confirm which originals you compared and any limitations:`);
  if(!reason)return;
  await api(`/api/material-suggestions/comparisons/${Number(id)}/review`,{method:'POST',body:JSON.stringify({status,reason})});
  await salcapaMaterialReview();
}

async function proposeSourceSuggestionLink(id){
  const destination_product=prompt('Destination product: SalINTEL, SalTHIRA, SalCAPA, SalOPS, PROVE, Personnel Assessment, Facility Assessment, or Mission Map');
  if(!destination_product)return;
  const destination_type=prompt('Destination record type. This does not create the relationship:');
  if(!destination_type)return;
  const destination_id_text=prompt('Destination record number, or 0 when the destination authority must select it:','0');
  if(destination_id_text===null)return;
  const destination_id=Number(destination_id_text);
  if(!Number.isInteger(destination_id)||destination_id<0){alert('Enter a whole destination record number or 0.');return;}
  const purpose=prompt('Purpose for proposing this governed link:');
  if(!purpose)return;
  const result=await api(`/api/material-suggestions/${Number(id)}/governed-link-proposals`,{method:'POST',body:JSON.stringify({destination_product,destination_type,destination_id,purpose})});
  alert(`${result.status}. The destination authority must review this proposal before any authoritative relationship exists.`);
}

const salcapaMaterialReviewWithoutSourceSuggestions=salcapaMaterialReview;
salcapaMaterialReview=async function(){
  await salcapaMaterialReviewWithoutSourceSuggestions();
  if(!isProtectedMember())await loadSourceSuggestions();
};

const openMaterialDerivativeWithoutSuggestions=openMaterialDerivative;
openMaterialDerivative=async function(id){
  await openMaterialDerivativeWithoutSuggestions(id);
  if(isProtectedMember())return;
  const item=await api(`/api/material-processing/derivatives/${Number(id)}`);
  if(item.review_status==='Human Reviewed'&&(accessState?.permissions||[]).includes('write')){
    $('.material-review-detail .form-actions')?.remove();
    $('.material-review-detail').insertAdjacentHTML('beforeend','<div class="form-actions"><button class="btn" type="button" onclick="prepareMaterialSuggestions('+Number(id)+')">Prepare source-review suggestions</button></div><p class="subtle">This prepares review aids only. It does not establish identity, intelligence, a finding, monitoring, disclosure, authority, scope, or cost.</p>');
  }
};
