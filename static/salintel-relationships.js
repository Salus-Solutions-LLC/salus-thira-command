/* Governed SalINTEL™ cross-domain relationship and where-used workspace. */
const salintelRelationshipState={recordId:null,records:[],types:[],outgoing:[],incoming:[]};
function salintelRelationshipPanel(record){
  if(!record||!record.id)return '';
  return `<section class="salintel-relationship-workspace" id="salintel-relationship-workspace" data-record-id="${record.id}">
    <div class="section-title"><div><h3>Enterprise relationships & where used</h3><p class="subtle">Governed references connect SalINTEL™ records without duplicating source material or authorizing disclosure.</p></div><span class="personnel-state" id="salintel-relationship-count">Loading…</span></div>
    <div class="two-col grid">
      <article class="card"><h4>Add governed relationship</h4><form id="salintel-relationship-form">
        <label>Related SalINTEL™ record<select name="target_investigation_id" required><option value="">Loading authorized records…</option></select></label>
        <label>Relationship type<select name="relationship_type" required><option value="">Loading registry policy…</option></select></label>
        <label>Origin<select name="origin_type"><option>Human Analyst</option><option>Chat Suggestion</option><option>Source Extraction</option><option>Approved Partner Return</option></select></label>
        <label>Rationale<textarea name="rationale" maxlength="8000" required></textarea></label>
        <div class="form-grid"><label>Source reliability<input name="source_reliability" maxlength="80" value="Not Assessed"></label><label>Information confidence<input name="information_confidence" maxlength="80" value="Not Assessed"></label><label>Governed source material ID<input name="source_material_id" type="number" min="1"></label></div>
        <div class="personnel-checks"><label><input type="checkbox" name="possible_duplicate"> Possible duplicate</label><label><input type="checkbox" name="competing_resource"> Competing-resource condition</label><label><input type="checkbox" name="source_conflict"> Source conflict or contradiction</label></div>
        <button class="btn">Add for human review</button>
      </form></article>
      <article class="card"><h4>Enterprise relationship search</h4><form id="salintel-relationship-search-form"><label>Subject, record, rationale, or type<input name="q" maxlength="240"></label><label>Relationship type<select name="relationship_type"><option value="">All governed types</option></select></label><button class="btn secondary">Search governed knowledge</button></form><div id="salintel-relationship-search-results" class="relationship-search-results"><p class="subtle">Search is tenant- and sensitivity-scoped for authorized Salus personnel.</p></div></article>
    </div>
    <div id="salintel-relationship-results"><p class="subtle">Loading relationship lineage…</p></div>
  </section>`;
}
function salintelRelationshipLabel(row,direction){
  const peer=direction==='outgoing'?row.target:row.source;
  const arrow=direction==='outgoing'?'→':'←';
  const flags=[];
  if(row.cross_engagement)flags.push('Cross-engagement');
  if(row.competing_resource)flags.push('Competing resources');
  if(row.source_conflict)flags.push('Source conflict');
  if(row.possible_duplicate)flags.push('Possible duplicate');
  return [`<strong>${esc(arrow)} ${esc(peer?.title||'Unavailable record')}</strong><br><span class="subtle">${esc(peer?.domain_key||'')} · ${esc(peer?.subject_reference||'')}</span>`,`<strong>${esc(row.relationship_type)}</strong><br>${esc(row.rationale)}`,`${esc(row.origin_type)}<br><span class="subtle">${esc(row.source_reliability)} / ${esc(row.information_confidence)}</span>`,`${esc(row.review_status)}<br><span class="subtle">${row.member_visible?'Released to this Protected Member':'Salus controlled'}</span>`,`${flags.map(x=>`<span class="personnel-tag">${esc(x)}</span>`).join('')||'None'}<div class="relationship-actions">${row.review_status==='Suggested'?`<button class="btn secondary" onclick="reviewSalintelRelationship(${row.source.id},${row.id},'Qualified')">Qualify</button><button class="btn secondary" onclick="reviewSalintelRelationship(${row.source.id},${row.id},'Rejected')">Reject</button>`:''}${row.review_status==='Qualified'?`<button class="btn secondary" onclick="discloseSalintelRelationship(${row.source.id},${row.id},${row.member_visible?'false':'true'})">${row.member_visible?'Return to Salus control':'Approve tenant release'}</button>`:''}</div>`];
}
async function loadSalintelRelationships(record){
  if(!record||!record.id)return;
  salintelRelationshipState.recordId=record.id;
  const [whereUsed,records,typeResult]=await Promise.all([
    api(`/api/salintel/investigations/${record.id}/relationships`),
    api('/api/salintel/investigations'),
    api(`/api/salintel/relationship-types/${encodeURIComponent(record.domain_key)}`),
  ]);
  salintelRelationshipState.records=records.filter(row=>row.id!==record.id);
  salintelRelationshipState.types=typeResult.relationship_types||[];
  salintelRelationshipState.outgoing=whereUsed.outgoing||[];
  salintelRelationshipState.incoming=whereUsed.incoming||[];
  const root=$('#salintel-relationship-workspace');if(!root)return;
  $('#salintel-relationship-count').textContent=`${whereUsed.where_used_count} governed reference${whereUsed.where_used_count===1?'':'s'}`;
  const target=root.querySelector('[name="target_investigation_id"]');
  target.innerHTML='<option value="">Choose an authorized record</option>'+salintelRelationshipState.records.map(row=>`<option value="${row.id}">${esc(row.title)} — ${esc(row.domain_key)}</option>`).join('');
  root.querySelectorAll('[name="relationship_type"]').forEach(select=>{const all=select.closest('#salintel-relationship-search-form');select.innerHTML=(all?'<option value="">All governed types</option>':'<option value="">Choose a governed type</option>')+salintelRelationshipState.types.map(value=>`<option>${esc(value)}</option>`).join('');});
  $('#salintel-relationship-results').innerHTML=`<div class="section-title"><h4>Outgoing relationships</h4><span class="subtle">${salintelRelationshipState.outgoing.length} from this record</span></div>${table(['Related record','Relationship','Provenance','Governance','Flags & actions'],salintelRelationshipState.outgoing.map(row=>salintelRelationshipLabel(row,'outgoing')))}<div class="section-title"><h4>Incoming / where used</h4><span class="subtle">${salintelRelationshipState.incoming.length} references to this record</span></div>${table(['Related record','Relationship','Provenance','Governance','Flags & actions'],salintelRelationshipState.incoming.map(row=>salintelRelationshipLabel(row,'incoming')))}`;
  $('#salintel-relationship-form').onsubmit=submitSalintelRelationship;
  $('#salintel-relationship-search-form').onsubmit=searchSalintelRelationships;
}
async function submitSalintelRelationship(event){
  event.preventDefault();const d=new FormData(event.target),body={target_investigation_id:Number(d.get('target_investigation_id')),relationship_type:d.get('relationship_type'),rationale:d.get('rationale'),origin_type:d.get('origin_type'),source_reliability:d.get('source_reliability'),information_confidence:d.get('information_confidence'),possible_duplicate:d.get('possible_duplicate')==='on',competing_resource:d.get('competing_resource')==='on',source_conflict:d.get('source_conflict')==='on'};
  if(d.get('source_material_id'))body.source_material_id=Number(d.get('source_material_id'));
  await api(`/api/salintel/investigations/${salintelRelationshipState.recordId}/relationships`,{method:'POST',body:JSON.stringify(body)});await personnelAssessments();
}
async function reviewSalintelRelationship(sourceId,itemId,status){
  const reason=prompt(`Human ${status.toLowerCase()} basis for this relationship:`);if(!reason)return;
  await api(`/api/salintel/investigations/${sourceId}/relationships/${itemId}/review`,{method:'POST',body:JSON.stringify({status,reason})});await personnelAssessments();
}
async function discloseSalintelRelationship(sourceId,itemId,approved_for_tenant){
  const reason=prompt(approved_for_tenant?'Disclosure basis for this Protected Member:':'Reason for returning this relationship to Salus control:');if(!reason)return;
  await api(`/api/salintel/investigations/${sourceId}/relationships/${itemId}/disclosure`,{method:'POST',body:JSON.stringify({approved_for_tenant,reason})});await personnelAssessments();
}
async function searchSalintelRelationships(event){
  event.preventDefault();const d=new FormData(event.target),params=new URLSearchParams();if(d.get('q'))params.set('q',d.get('q'));if(d.get('relationship_type'))params.set('relationship_type',d.get('relationship_type'));
  const result=await api('/api/salintel/relationship-search?'+params.toString());
  $('#salintel-relationship-search-results').innerHTML=result.results.length?table(['Source','Relationship','Target'],result.results.map(row=>[`<strong>${esc(row.source.title)}</strong><br><span class="subtle">${esc(row.source.domain_key)}</span>`,`<strong>${esc(row.relationship_type)}</strong><br>${esc(row.rationale)}`,`<strong>${esc(row.target.title)}</strong><br><span class="subtle">${esc(row.target.domain_key)}</span>`])):'<p class="subtle">No authorized relationship matched this search.</p>';
}
