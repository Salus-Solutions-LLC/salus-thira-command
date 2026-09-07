const personnelAssessmentState={recordId:null};
const personnelOrigins=['Chat Research','Human Investigator','Protected Member Input','Source Extraction','Analyst Assessment','Approved Partner Return'];
const personnelEpistemic=['Verified Fact','Reported Information','Reasonable Inference','Analyst Judgment','Hypothesis','Unresolved Allegation','Assumption','Contradiction','Information Gap','Unknown'];

function personnelStructured(item){
  if(item&&item.structured_detail)return item.structured_detail;
  try{return JSON.parse((item&&item.detail)||'{}');}catch(_error){return {};}
}
function personnelProgress(detail){
  const p=detail.progress||{total:0,addressed:0,open:0};
  const pct=p.total?Math.round((p.addressed/p.total)*100):0;
  return `<div class="personnel-progress" aria-label="${p.addressed} of ${p.total} research requirements addressed"><div style="width:${pct}%"></div></div><span class="subtle">${p.addressed} addressed · ${p.open} open · ${p.total} authorized</span>`;
}
function personnelChecklist(detail){
  return table(['Requirement','Authorized depth','Collection plan','Status'],(detail.checklist||[]).map(item=>{
    const d=personnelStructured(item);
    return [`<strong>${esc(d.checklist_key||item.title)}</strong><br><span class="subtle">${esc(d.category||'')}</span>`,`Tier ${esc(d.tier_required)}`,esc((d.collection_channels||[]).join(', ')),`<span class="personnel-state">${esc(item.plan_status||d.status||'Open')}</span>`];
  }));
}
function personnelCandidates(detail){
  return table(['Candidate','Authorized discriminators','Source / origin','Decision','Actions'],(detail.identity_candidates||[]).map(item=>{
    const d=personnelStructured(item),collision=(d.collision_with_item_ids||[]).length>0;
    const ids=Object.entries(d.identifiers||{}).map(([k,v])=>`${esc(k)}: ${esc(v)}`).join('<br>');
    const actions=['Match','Excluded','Ambiguous','Contradiction'].map(decision=>`<button class="btn secondary" onclick="decidePersonnelIdentity(${item.id},'${decision}')">${decision}</button>`).join(' ');
    return [`<strong>${esc(d.candidate_name||item.title)}</strong>${collision?'<br><span class="personnel-collision">◆ Same-name collision requires review</span>':''}`,ids||'No discriminator recorded',`${esc(d.origin_type||'')}<br><span class="subtle">Material ${esc(item.source_material_id||'not linked')}</span>`,esc(d.decision||'Unresolved'),actions];
  }));
}
function personnelFindings(detail){
  return table(['Knowledge state','Finding','Source assessment','Relevance'],(detail.findings||[]).map(item=>{
    const d=personnelStructured(item),flags=[];
    if(d.competing_resource_relevance)flags.push('Competing resources');
    if(d.insider_threat_relevance)flags.push('Insider-threat relevance');
    if(d.protective_intelligence_relevance)flags.push('Protective-intelligence relevance');
    return [`<span class="personnel-state">${esc(item.epistemic_state)}</span>`,`<strong>${esc(item.title)}</strong><br><span class="subtle">${esc(d.category||'')} · ${esc(d.origin_type||'')}</span><br>${esc(d.narrative||'')}`,`${esc(item.source_reliability)} / ${esc(item.information_confidence)}<br><span class="subtle">Material ${esc(item.source_material_id||'not linked')}</span>`,flags.map(x=>`<span class="personnel-tag">${esc(x)}</span>`).join('')||'None marked'];
  }));
}
function personnelPlanOptions(checklist,tier){
  return (checklist.tiers||[]).filter(row=>row.tier_required<=tier).map(row=>`<option value="${esc(row.key)}" data-category="${esc(row.category)}">${esc(row.key)} — ${esc(row.category)}</option>`).join('');
}
function personnelCompletionReadiness(detail){
  const readiness=detail.completion_readiness||{ready:false,blockers:['Completion readiness has not been evaluated.']};
  const items=(readiness.blockers||[]).map(item=>`<li>${esc(item)}</li>`).join('');
  return `<article class="card"><div class="section-title"><h3>Bounded-tier completion</h3><span class="personnel-state">${readiness.ready?'Ready for authorized completion':'Closure gates remain'}</span></div>${readiness.ready?'<p>The authorized plan, identity disposition, known-unknown record, and final human qualification satisfy the Personnel Assessment closure gate.</p>':`<p>Completion remains server-blocked until:</p><ul>${items}</ul>`}</article>`;
}
function personnelDetail(detail,checklist){
  const record=detail.investigation||{},tier=Number(detail.authorized_tier||0),hasPlan=(detail.checklist||[]).length>0;
  return `<section class="personnel-detail">
    <div class="section-title"><div><span class="component intel">SalINTEL™</span><h2>${esc(record.title||'Personnel Assessment')}</h2><p class="subtle">${esc(record.record_key||'')} · ${esc(record.subject_reference||'')}</p></div><button class="btn secondary" onclick="closePersonnelAssessment()">Close</button></div>
    <div class="personnel-status-grid"><div><span>Investigation depth</span><strong>${tier?`Tier ${tier}`:'Not authorized'}</strong></div><div><span>Identity resolution</span><strong>${esc(detail.identity_resolution_status)}</strong></div><div><span>Human qualification</span><strong>${esc(detail.qualification_status)}</strong></div><div><span>Disclosure</span><strong>${esc(detail.disclosure_status)}</strong></div></div>
    <div class="notice"><strong>Depth is not a safety rating.</strong><br>Tier ${tier||'authorization pending'} bounds investigative effort. Identity candidates, allegations, inferred associations, and Chat-derived content remain distinct from verified facts until governed Salus review.</div>
    <article class="card"><div class="section-title"><h3>Authorized research plan</h3><div>${tier&&!hasPlan?'<button class="btn" onclick="generatePersonnelPlan()">Generate bounded plan</button>':''}</div></div>${personnelProgress(detail)}${hasPlan?personnelChecklist(detail):'<p>No Personnel Assessment research plan has been generated. Tier authorization is required first.</p>'}</article>
    <div class="two-col grid"><article class="card"><h3>Add identity candidate</h3><form id="personnel-candidate-form"><label>Candidate name<input name="candidate_name" maxlength="240" required></label><label>Authorized discriminators <span class="subtle">one key=value per line</span><textarea name="identifiers" required placeholder="jurisdiction=NC\nemployer=Example Organization"></textarea></label><label>Origin<select name="origin_type">${personnelOrigins.map(x=>`<option>${esc(x)}</option>`).join('')}</select></label><label>Governed source material ID <span class="subtle">required before a Match decision</span><input name="source_material_id" type="number" min="1"></label><label>Narrative<textarea name="narrative" maxlength="8000" required></textarea></label><button class="btn">Add unresolved candidate</button></form></article>
    <article class="card"><h3>Add structured finding</h3><form id="personnel-finding-form"><label>Checklist requirement<select name="checklist_key" required>${personnelPlanOptions(checklist,tier)}</select></label><label>Knowledge state<select name="epistemic_state">${personnelEpistemic.map(x=>`<option>${esc(x)}</option>`).join('')}</select></label><label>Origin<select name="origin_type">${personnelOrigins.map(x=>`<option>${esc(x)}</option>`).join('')}</select></label><label>Title<input name="title" maxlength="240" required></label><label>Narrative<textarea name="narrative" maxlength="12000" required></textarea></label><div class="form-grid"><label>Source reliability<input name="source_reliability" maxlength="80" value="Not Assessed"></label><label>Information confidence<input name="information_confidence" maxlength="80" value="Not Assessed"></label><label>Governed source material ID<input name="source_material_id" type="number" min="1"></label></div><label>Relationship context<textarea name="relationship_context" maxlength="4000"></textarea></label><div class="personnel-checks"><label><input type="checkbox" name="competing_resource_relevance"> Competing-resource relevance</label><label><input type="checkbox" name="insider_threat_relevance"> Insider-threat relevance</label><label><input type="checkbox" name="protective_intelligence_relevance"> Protective-intelligence relevance</label></div><button class="btn">Add unqualified finding</button></form></article></div>
    <div class="section-title"><h3>Identity candidates</h3><span class="subtle">${detail.identity_collision?'◆ Collision remains reviewable':'No unresolved collision detected'}</span></div>${personnelCandidates(detail)}
    <div class="section-title"><h3>Structured findings</h3><span class="subtle">All new findings require human qualification</span></div>${personnelFindings(detail)}
    ${personnelCompletionReadiness(detail)}
    ${typeof salintelRelationshipPanel==='function'?salintelRelationshipPanel(record):''}
    <div class="form-actions personnel-governance"><button class="btn secondary" onclick="openPersonnelInDomainWorkspace()">Open governance and disclosure controls</button>${tier?`<button class="btn secondary" onclick="qualifySalintelInvestigation(${record.id})">Human qualification</button><button class="btn secondary" onclick="recommendSalintelTier(${record.id},true)">Recommend deeper tier</button>${detail.completion_readiness&&detail.completion_readiness.ready?`<button class="btn" onclick="completePersonnelTier(${record.id},${tier})">Complete authorized tier</button>`:''}`:''}</div>
  </section>`;
}
async function personnelAssessments(){
  if(isProtectedMember()){$('#content').innerHTML='<div class="notice"><strong>Salus investigative workspace</strong><br>Protected Members receive only conclusions, alerts, recommendations, and supporting detail explicitly qualified and released by authorized Salus personnel.</div>';return;}
  const [records,checklist]=await Promise.all([api('/api/salintel/investigations?domain_key=personnel-assessment'),api('/api/salintel/personnel-assessment/checklist')]);
  const detail=personnelAssessmentState.recordId?await api('/api/salintel/personnel-assessments/'+personnelAssessmentState.recordId):null;
  $('#content').innerHTML=`<section class="personnel-hero"><div><span class="component intel">SalINTEL™</span><h2>Personnel Assessment</h2><p>Resolve identity, investigate authorized professional and organizational context, preserve uncertainty, and produce evidence-grounded findings for human qualification.</p></div><div><strong>${records.length}</strong><span>governed records</span></div></section>
  <div class="notice"><strong>Lawful purpose and bounded scope apply.</strong><br>No unrestricted personal dossier, partisan scoring, guilt by association, automatic adverse finding, or silent expansion of tier or customer cost.</div>
  ${table(['Record','Subject','Status','Depth','Qualification','Action'],records.map(record=>[`<strong>${esc(record.title)}</strong><br><span class="subtle">${esc(record.record_key)}</span>`,esc(record.subject_reference),esc(record.status),record.authorized_tier?`Tier ${record.authorized_tier}`:'Not authorized',esc(record.qualification_status),`<button class="btn secondary" onclick="openPersonnelAssessment(${record.id})">Open assessment</button>`]))}
  ${detail?personnelDetail(detail,checklist):'<div class="card personnel-empty"><h3>Select a Personnel Assessment</h3><p>Open a governed record to work its authorized research plan, identity resolution, source-grounded findings, qualification, and tier recommendation.</p></div>'}`;
  const candidate=$('#personnel-candidate-form');if(candidate)candidate.onsubmit=submitPersonnelCandidate;
  const finding=$('#personnel-finding-form');if(finding)finding.onsubmit=submitPersonnelFinding;
  if(detail&&typeof loadSalintelRelationships==='function')await loadSalintelRelationships(detail.investigation);
}
async function openPersonnelAssessment(id){personnelAssessmentState.recordId=id;await personnelAssessments();}
function closePersonnelAssessment(){personnelAssessmentState.recordId=null;personnelAssessments();}
async function generatePersonnelPlan(){const reason=prompt('Governance basis for generating the authorized bounded research plan:');if(!reason)return;await api(`/api/salintel/personnel-assessments/${personnelAssessmentState.recordId}/research-plan`,{method:'POST',body:JSON.stringify({reason})});await personnelAssessments();}
function personnelIdentifiers(value){const result={};String(value||'').split(/\r?\n/).forEach(line=>{const at=line.indexOf('=');if(at>0){const key=line.slice(0,at).trim(),val=line.slice(at+1).trim();if(key&&val)result[key]=val;}});return result;}
async function submitPersonnelCandidate(event){event.preventDefault();const d=new FormData(event.target),body={candidate_name:d.get('candidate_name'),identifiers:personnelIdentifiers(d.get('identifiers')),origin_type:d.get('origin_type'),narrative:d.get('narrative')};if(d.get('source_material_id'))body.source_material_id=Number(d.get('source_material_id'));await api(`/api/salintel/personnel-assessments/${personnelAssessmentState.recordId}/identity-candidates`,{method:'POST',body:JSON.stringify(body)});await personnelAssessments();}
async function decidePersonnelIdentity(itemId,decision){const reason=prompt(`Human decision basis for ${decision}:`);if(!reason)return;await api(`/api/salintel/personnel-assessments/${personnelAssessmentState.recordId}/identity-candidates/${itemId}/decision`,{method:'POST',body:JSON.stringify({decision,reason})});await personnelAssessments();}
async function submitPersonnelFinding(event){event.preventDefault();const d=new FormData(event.target),select=event.target.querySelector('[name="checklist_key"]'),option=select.options[select.selectedIndex],body={checklist_key:d.get('checklist_key'),category:option.dataset.category,title:d.get('title'),narrative:d.get('narrative'),epistemic_state:d.get('epistemic_state'),origin_type:d.get('origin_type'),source_reliability:d.get('source_reliability'),information_confidence:d.get('information_confidence'),relationship_context:d.get('relationship_context'),competing_resource_relevance:d.get('competing_resource_relevance')==='on',insider_threat_relevance:d.get('insider_threat_relevance')==='on',protective_intelligence_relevance:d.get('protective_intelligence_relevance')==='on'};if(d.get('source_material_id'))body.source_material_id=Number(d.get('source_material_id'));await api(`/api/salintel/personnel-assessments/${personnelAssessmentState.recordId}/findings`,{method:'POST',body:JSON.stringify(body)});await personnelAssessments();}
async function completePersonnelTier(recordId,tier){const completion_statement=prompt(`Bounded Tier ${tier} completion statement:`);if(!completion_statement)return;const residual_unknowns=prompt('Residual unknowns, unavailable sources, stopping points, and follow-on requirements (state “None identified” when applicable):');if(residual_unknowns===null||!residual_unknowns.trim())return;await api(`/api/salintel/investigations/${recordId}/complete-tier`,{method:'POST',body:JSON.stringify({tier,completion_statement,residual_unknowns})});await personnelAssessments();}
function openPersonnelInDomainWorkspace(){salintelDomainUiState.recordId=personnelAssessmentState.recordId;salintelDomainUiState.domain='personnel-assessment';setView('salintel_domains');}

viewTitles.personnel_assessments=`${PRODUCT_TERMS.salintel.name} Personnel Assessment`;
subtitles.personnel_assessments='Resolve identity and investigate authorized personnel context with evidence, explicit uncertainty, and human qualification.';
const personnelBaseRender=render;
render=async function(){
  if(currentView==='personnel_assessments'){
    try{return await personnelAssessments();}
    catch(error){$('#content').innerHTML=`<div class="notice"><strong>Error</strong><br>${esc(error.message)}</div>`;return;}
  }
  return personnelBaseRender();
};
