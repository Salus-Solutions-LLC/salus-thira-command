/* Chat-led, source-truthful SalINTEL™ research workspace. */
const salintelResearchState={recordId:null,data:null};
const salintelResearchOutcomes={
  'Chat Research':['Accessed','Unavailable','Requires Human Collection','Requires Protected Member Input','Requires Partner Authorization'],
  'Salus Human Investigator':['Human Collection Received','Requires Human Collection','Unavailable'],
  'Protected Member / Form':['Protected Member Input Received','Requires Protected Member Input','Unavailable'],
  'Document / Material':['Document / Material Received','Unavailable','Requires Human Collection','Requires Protected Member Input'],
  'Prior SalCAPA Context':['Prior SalCAPA Context Reused','Unavailable'],
  'Approved Partner Return':['Approved Partner Return Received','Requires Partner Authorization','Unavailable']
};
function salintelResearchPanel(record){
  if(!record||!record.id)return '';
  return `<section class="salintel-research-workspace" id="salintel-research-workspace" data-record-id="${record.id}"><div class="section-title"><div><h3>Chat-led research & mixed-source collection</h3><p class="subtle">Plan, research, reconcile, and preserve what Chat accessed, what remains unavailable, and what requires human, member, material, or authorized partner collection.</p></div><span class="personnel-state" id="salintel-research-status">Loading…</span></div><div id="salintel-research-content"><p class="subtle">Loading governed research state…</p></div></section>`;
}
function salintelResearchTaskRows(tasks){
  return table(['Task','Contributor','Truth status','Action'],tasks.map(task=>[
    `<strong>${esc(task.task_key)}</strong><br>${esc(task.question)}${task.checklist_key?`<br><span class="subtle">${esc(task.checklist_key)}</span>`:''}`,
    `<span class="research-contributor">${esc(task.contributor)}</span>`,
    task.results.length?task.results.map(result=>`<span class="research-outcome">${esc(result.structured_detail.outcome)}</span>`).join(' '):'<span class="subtle">No result recorded</span>',
    `<button class="btn secondary" onclick="recordSalintelResearchResult('${esc(task.task_key)}','${esc(task.contributor)}')">Record disposition</button>`
  ]));
}
function salintelResearchSourceRows(results){
  return table(['Outcome','Source or requirement','Attribution','Assessment'],results.map(result=>{
    const d=result.structured_detail||{};
    return [`<span class="research-outcome">${esc(d.outcome)}</span>`,`<strong>${esc(d.source_title)}</strong><br>${esc(d.notes)}${d.source_locator?`<br><span class="subtle">${esc(d.source_locator)}</span>`:''}`,`${esc(d.authorized_contributor)}<br><span class="subtle">Recorded by ${esc(d.recorded_by)} · ${esc(d.acquired_or_recorded_at)}</span>`,`${esc(result.source_reliability)} / ${esc(result.information_confidence)}<br><span class="subtle">Material ${esc(result.source_material_id||'not applicable')}</span>`];
  }));
}
function salintelResearchProductRows(products){
  return table(['Product','Research truth','Review','Actions'],products.map(product=>{
    const d=product.structured_detail||{};
    return [`<strong>${esc(product.title)}</strong><br>${esc(d.executive_summary)}`,`${(d.sources_actually_accessed||[]).length} accessed · ${(d.unavailable_source_results||[]).length} unavailable · ${(d.collection_requirements||[]).length} collection requirements<br><span class="subtle">Tier recommendation does not authorize scope or cost.</span>`,`<span class="research-outcome">${esc(d.review_status)}</span><br><span class="subtle">${esc(d.reviewed_by||'Human review pending')}</span>`,d.review_status==='Awaiting Human Review'?`<button class="btn secondary" onclick="reviewSalintelResearchProduct(${product.id},'Analyst Reviewed')">Mark reviewed</button> <button class="btn secondary" onclick="reviewSalintelResearchProduct(${product.id},'Qualified')">Qualify</button> <button class="btn secondary" onclick="reviewSalintelResearchProduct(${product.id},'Rejected')">Reject</button>`:'No pending action'];
  }));
}
function salintelResearchSynthesisForm(data){
  if(!data.ready_for_synthesis)return '<div class="notice"><strong>Synthesis remains blocked.</strong><br>Every authorized task needs a truthful disposition and Chat must actually access at least one governed source.</div>';
  const accessed=data.source_results.filter(result=>result.structured_detail?.outcome==='Accessed');
  return `<article class="card"><h4>Create tier-specific Chat research product</h4><form id="salintel-research-product-form"><label>Executive summary<textarea name="executive_summary" maxlength="12000" required></textarea></label><label>Primary finding<textarea name="statement" maxlength="8000" required></textarea></label><div class="form-grid"><label>Knowledge state<select name="epistemic_state"><option>Reported Information</option><option>Reasonable Inference</option><option>Hypothesis</option><option>Contradiction</option><option>Information Gap</option><option>Unknown</option></select></label><label>Source-result citation<select name="source_result_id"><option value="">No source citation</option>${accessed.map(result=>`<option value="${result.id}">${esc(result.structured_detail.source_title)}</option>`).join('')}</select></label><label>Information confidence<input name="information_confidence" maxlength="80" value="Not Assessed"></label></div><label>Contradictions<textarea name="contradictions" maxlength="8000"></textarea></label><label>Known unknowns, unavailable sources, and collection requirements<textarea name="known_unknowns" maxlength="8000" required></textarea></label><label>Protective, risk, or operational implications <span class="subtle">recommendations only; no automatic handoff</span><textarea name="implications" maxlength="8000"></textarea></label><label>Bounded completion statement<textarea name="completion_statement" maxlength="8000" required></textarea></label><label class="research-check"><input type="checkbox" name="deeper_tier_recommended"> Recommend a separately authorized deeper investigation tier</label><label>Recommendation reason<textarea name="deeper_tier_reason" maxlength="4000"></textarea></label><button class="btn">Submit for Salus human review</button></form></article>`;
}
async function loadSalintelResearch(record){
  if(!record||!record.id)return;salintelResearchState.recordId=record.id;
  const data=await api(`/api/salintel/investigations/${record.id}/research`);salintelResearchState.data=data;
  const root=$('#salintel-research-workspace');if(!root)return;
  $('#salintel-research-status').textContent=data.plan?`${data.progress.dispositioned} of ${data.progress.total} tasks dispositioned`:'Plan not authorized';
  if(!data.plan){$('#salintel-research-content').innerHTML='<div class="notice"><strong>No Chat-led research plan is authorized.</strong><br>The server will derive a bounded, versioned plan from the authorized tier and domain checklist. It cannot change tier, price, partner use, or disclosure.</div><button class="btn" onclick="authorizeSalintelResearchPlan()">Authorize bounded research plan</button>';return;}
  $('#salintel-research-content').innerHTML=`<div class="research-metrics"><div><span>Authorized tier</span><strong>Tier ${data.plan.structured_detail.authorized_tier}</strong></div><div><span>Plan version</span><strong>${esc(data.plan.structured_detail.plan_version)}</strong></div><div><span>Chat sources accessed</span><strong>${data.progress.chat_sources_accessed}</strong></div><div><span>Open tasks</span><strong>${data.progress.open}</strong></div></div><div class="notice"><strong>Source-access truth applies.</strong><br>Accessed sources require captured governed material and a locator. Unavailable sources remain unavailable—not negative findings. Human, member, and partner work stays separately attributable.</div><div class="section-title"><h4>Authorized collection and research plan</h4><span class="subtle">Tier depth is not risk severity</span></div>${salintelResearchTaskRows(data.tasks)}<div class="section-title"><h4>Source-access and collection ledger</h4><span class="subtle">Original bytes are reused by reference</span></div>${salintelResearchSourceRows(data.source_results)}${salintelResearchSynthesisForm(data)}<div class="section-title"><h4>Tier research products</h4><span class="subtle">Human qualification remains separate</span></div>${salintelResearchProductRows(data.products)}`;
  const form=$('#salintel-research-product-form');if(form)form.onsubmit=submitSalintelResearchProduct;
}
async function authorizeSalintelResearchPlan(){const reason=prompt('Salus authorization basis for this bounded Chat, human, member, material, and partner-aware research plan:');if(!reason)return;await api(`/api/salintel/investigations/${salintelResearchState.recordId}/research-plans`,{method:'POST',body:JSON.stringify({reason})});await personnelAssessments();}
async function recordSalintelResearchResult(taskKey,contributor){
  const allowed=salintelResearchOutcomes[contributor]||['Unavailable'];const outcome=prompt(`Choose the truthful outcome for ${contributor}:\n${allowed.join(' | ')}`,allowed[0]);if(!outcome||!allowed.includes(outcome))return;
  const source_title=prompt('Source title, unavailable source, or collection requirement:');if(!source_title)return;
  const notes=prompt('What was actually accessed, learned, unavailable, or assigned?');if(!notes)return;
  const body={task_key:taskKey,outcome,source_title,notes};
  if(outcome==='Accessed')body.source_locator=prompt('Exact source locator or citation:')||'';
  if(['Accessed','Human Collection Received','Protected Member Input Received','Document / Material Received','Approved Partner Return Received'].includes(outcome)){const material=prompt('Governed linked material ID:');if(!material)return;body.source_material_id=Number(material);}
  if(outcome==='Prior SalCAPA Context Reused'){const related=prompt('Governed related investigation ID:');if(!related)return;body.related_investigation_id=Number(related);}
  await api(`/api/salintel/investigations/${salintelResearchState.recordId}/research-plans/${salintelResearchState.data.plan.id}/source-results`,{method:'POST',body:JSON.stringify(body)});await personnelAssessments();
}
async function submitSalintelResearchProduct(event){event.preventDefault();const d=new FormData(event.target),sourceId=d.get('source_result_id'),epistemic=d.get('epistemic_state'),ids=sourceId?[Number(sourceId)]:[];if(epistemic==='Reported Information'&&!ids.length){alert('Reported Information requires a source-result citation.');return;}const body={executive_summary:d.get('executive_summary'),findings:[{statement:d.get('statement'),epistemic_state:epistemic,source_result_ids:ids,information_confidence:d.get('information_confidence'),implications:d.get('implications')}],contradictions:d.get('contradictions'),known_unknowns:d.get('known_unknowns'),implications:d.get('implications'),completion_statement:d.get('completion_statement'),deeper_tier_recommended:d.get('deeper_tier_recommended')==='on',deeper_tier_reason:d.get('deeper_tier_reason')};await api(`/api/salintel/investigations/${salintelResearchState.recordId}/research-plans/${salintelResearchState.data.plan.id}/products`,{method:'POST',body:JSON.stringify(body)});await personnelAssessments();}
async function reviewSalintelResearchProduct(productId,status){const reason=prompt(`Salus human ${status.toLowerCase()} basis:`);if(!reason)return;await api(`/api/salintel/investigations/${salintelResearchState.recordId}/research-products/${productId}/review`,{method:'POST',body:JSON.stringify({status,reason})});await personnelAssessments();}
