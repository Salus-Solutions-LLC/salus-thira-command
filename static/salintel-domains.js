let salintelDomainUiState={domain:'',status:'',tier:'',epistemic:'',phase:'',recordId:null};
const salintelEpistemicStates=['Verified Fact','Reported Information','Reasonable Inference','Analyst Judgment','Hypothesis','Unresolved Allegation','Assumption','Contradiction','Information Gap','Unknown'];
const salintelPhases=['Prevention','Protection','Mitigation','Response','Recovery'];

function salintelOption(value,label,current){
  return `<option value="${esc(value)}" ${String(value)===String(current)?'selected':''}>${esc(label)}</option>`;
}
function salintelTierLabel(value){return value?`Tier ${esc(value)}`:'Not authorized';}
function salintelDomainName(catalog,key){return (catalog.find(row=>row.domain_key===key)||{}).display_name||key;}
function salintelRecordActions(record){
  const buttons=[`<button class="btn secondary" onclick="selectSalintelInvestigation(${record.id})">Open</button>`];
  if(record.authorized_tier===0)buttons.push(`<button class="btn" onclick="selectSalintelInvestigation(${record.id},true)">Authorize tier</button>`);
  return buttons.join(' ');
}
function salintelDetail(record,catalog){
  if(!record)return '<div class="card salintel-empty"><h2>Select an investigation</h2><p>Open a governed record to review scope, sources, analysis, unresolved questions, disclosure, and version history.</p></div>';
  const scope=record.authorized_scope||{},lenses=scope.investigative_lenses||[],items=record.items||[];
  const gaps=items.filter(item=>['Information Gap','Unknown','Contradiction'].includes(item.epistemic_state));
  const events=record.events||[],links=record.material_links||[];
  const controls=record.authorized_tier?`
    <button class="btn secondary" onclick="qualifySalintelInvestigation(${record.id})">Human qualification</button>
    <button class="btn secondary" onclick="completeSalintelTier(${record.id},${record.authorized_tier})">Complete authorized tier</button>
    <button class="btn secondary" onclick="recommendSalintelTier(${record.id},${record.deeper_tier_recommended?'false':'true'})">${record.deeper_tier_recommended?'Withdraw deeper-tier recommendation':'Recommend deeper tier'}</button>
    <button class="btn secondary" onclick="decideSalintelDisclosure(${record.id},${record.disclosure_status==='Approved for Tenant'?'false':'true'})">${record.disclosure_status==='Approved for Tenant'?'Return to Salus internal':'Approve for Protected Member'}</button>`:'';
  return `<div class="salintel-detail">
    <div class="section-title"><div><span class="component intel">SalINTEL</span><h2>${esc(record.title)}</h2><p class="subtle">${esc(record.record_key)} · ${esc(salintelDomainName(catalog,record.domain_key))}</p></div><button class="btn secondary" onclick="closeSalintelInvestigation()">Close detail</button></div>
    <div class="salintel-status-grid"><div><span>Status</span><strong>${esc(record.status)}</strong></div><div><span>Depth</span><strong>${salintelTierLabel(record.authorized_tier)}</strong></div><div><span>Qualification</span><strong>${esc(record.qualification_status)}</strong></div><div><span>Disclosure</span><strong>${esc(record.disclosure_status)}</strong></div></div>
    <div class="two-col grid"><article class="card"><h3>Authorized scope</h3><p>${esc(scope.statement||'Awaiting Salus authorization.')}</p><p class="subtle">Checklist: ${esc(scope.checklist_version||'Not assigned')}</p><div class="salintel-lenses">${lenses.map(x=>`<span>${esc(x)}</span>`).join('')||'<span>Not assigned</span>'}</div></article>
    <article class="card"><h3>Completion and next depth</h3><p>${esc(record.completion_statement||'Authorized work has not been completed.')}</p><p><strong>Residual unknowns:</strong> ${esc(record.residual_unknowns||'None recorded')}</p>${record.deeper_tier_recommended?`<div class="notice"><strong>Deeper tier recommended</strong><br>${esc(record.deeper_tier_reason)}</div>`:''}</article></div>
    <div class="form-actions salintel-controls">${controls}</div>
    ${record.authorized_tier&&record.status!=='Tier Complete'?`<div class="card"><h3>Add governed analytic item</h3><form id="salintel-item-form"><div class="form-grid">
      <label>Kind<select name="item_kind">${['Finding','Indicator / Warning','Question','Collection Requirement','Reassessment Trigger','Contradiction'].map(x=>salintelOption(x,x,'')).join('')}</select></label>
      <label>Knowledge state<select name="epistemic_state">${salintelEpistemicStates.map(x=>salintelOption(x,x,'')).join('')}</select></label>
      <label>Title<input name="title" maxlength="240" required></label><label>Source material ID (optional)<input name="source_material_id" type="number" min="1"></label>
      <label>Source reliability<input name="source_reliability" maxlength="80" value="Not Assessed"></label><label>Information confidence<input name="information_confidence" maxlength="80" value="Not Assessed"></label></div>
      <label>Analysis, question, or collection requirement<textarea name="detail" maxlength="12000" required></textarea></label><div class="form-actions"><button class="btn">Add to investigation</button></div></form></div>`:''}
    <div class="section-title"><h3>Investigative record</h3><span class="subtle">${items.length} analytic items · ${links.length} governed materials</span></div>
    ${table(['State','Kind','Title','Reliability / confidence','Member release'],items.map(item=>[
      esc(item.epistemic_state),esc(item.item_kind),`<strong>${esc(item.title)}</strong><br><span class="subtle">${esc(item.detail)}</span>`,`${esc(item.source_reliability)} / ${esc(item.information_confidence)}`,`${item.member_visible?'Released':'Salus internal'} <button class="btn secondary" onclick="releaseSalintelItem(${record.id},${item.id},${item.member_visible?'false':'true'})">${item.member_visible?'Withdraw':'Release'}</button>`
    ]))}
    <div class="two-col grid"><article><div class="section-title"><h3>Known unknowns and contradictions</h3><span class="subtle">${gaps.length}</span></div>${table(['State','Question / gap'],gaps.map(item=>[esc(item.epistemic_state),`<strong>${esc(item.title)}</strong><br><span class="subtle">${esc(item.detail)}</span>`]))}</article>
    <article><div class="section-title"><h3>Version history</h3><span class="subtle">${events.length} governed events</span></div>${table(['Version','Event','Authority','Time'],events.map(event=>[event.version_no,esc(event.event_type),`${esc(event.changed_by)} · ${esc(event.changed_by_role)}`,esc(event.created_at)]))}</article></div>
  </div>`;
}
async function salintelDomains(){
  if(isProtectedMember()){
    $('#content').innerHTML='<div class="notice"><strong>Salus workspace</strong><br>Investigative-domain records are available to Protected Members only after explicit Salus qualification and release through their authorized experience.</div>';return;
  }
  const state=salintelDomainUiState,params=new URLSearchParams();
  if(state.domain)params.set('domain_key',state.domain);if(state.status)params.set('status',state.status);if(state.tier)params.set('authorized_tier',state.tier);if(state.epistemic)params.set('epistemic_state',state.epistemic);if(state.phase)params.set('phase',state.phase);
  const [catalog,records]=await Promise.all([api('/api/salintel/domains/catalog'),api('/api/salintel/investigations?'+params.toString())]);
  if(state.recordId&&!records.some(row=>row.id===state.recordId))state.recordId=null;
  const detail=state.recordId?await api('/api/salintel/investigations/'+state.recordId):null,enabled=catalog.filter(row=>row.lifecycle_status==='Enabled').length;
  $('#content').innerHTML=`<section class="salintel-domain-hero"><div><span class="component intel">SalINTEL</span><h2>Investigative Domains</h2><p>One governed workspace for source-grounded investigations, bounded research depth, explicit uncertainty, human qualification, and controlled disclosure.</p></div><div class="salintel-domain-metrics"><strong>${enabled}</strong><span>enabled domains</span><strong>${records.length}</strong><span>matching records</span></div></section>
  <div class="notice"><strong>Depth is not danger.</strong> Tier 1, Tier 2, and Tier 3 describe authorized investigative effort. They do not use the red–yellow–green condition scale and never expand scope or customer cost automatically.</div>
  <details class="card salintel-create"><summary>Start a governed investigation request</summary><form id="salintel-investigation-form"><div class="form-grid">
    <label>Investigative domain<select name="domain_key" required>${catalog.map(row=>salintelOption(row.domain_key,row.display_name,'')).join('')}</select></label>
    <label>Requested depth<select name="requested_tier">${[1,2,3].map(x=>salintelOption(x,'Tier '+x,'')).join('')}</select></label><label>Title<input name="title" maxlength="240" required></label><label>Subject reference<input name="subject_reference" maxlength="500" required></label>
    <label>Sensitivity<select name="sensitivity">${['Restricted','Standard','Sensitive','Highly Sensitive'].map(x=>salintelOption(x,x,'Restricted')).join('')}</select></label><label>Engagement context<input name="engagement_context" maxlength="1000"></label></div>
    <label>Purpose<textarea name="purpose" maxlength="4000" required></textarea></label><div class="form-actions"><button class="btn">Create request</button></div></form></details>
  <section class="card"><div class="section-title"><h3>Browse and filter</h3><span class="subtle">Filters are applied by the governed API</span></div><form id="salintel-filter-form" class="salintel-filters">
    <label>Domain<select name="domain"><option value="">All domains</option>${catalog.map(row=>salintelOption(row.domain_key,row.display_name,state.domain)).join('')}</select></label>
    <label>Status<select name="status"><option value="">All statuses</option>${['Requested','Authorized','In Progress','Tier Complete','Closed'].map(x=>salintelOption(x,x,state.status)).join('')}</select></label>
    <label>Tier<select name="tier"><option value="">All tiers</option>${[1,2,3].map(x=>salintelOption(x,'Tier '+x,state.tier)).join('')}</select></label>
    <label>Knowledge state<select name="epistemic"><option value="">All states</option>${salintelEpistemicStates.map(x=>salintelOption(x,x,state.epistemic)).join('')}</select></label>
    <label>Mission lens<select name="phase"><option value="">All lenses</option>${salintelPhases.map(x=>salintelOption(x,x,state.phase)).join('')}</select></label><button class="btn">Apply filters</button><button type="button" class="btn secondary" onclick="resetSalintelDomainFilters()">Reset</button>
  </form></section>
  <div class="section-title"><h3>Governed investigations</h3><span class="subtle">Originating engagement does not create uncontrolled ownership or disclosure.</span></div>
  ${table(['Record','Domain / subject','Status','Authorized work','Disclosure','Actions'],records.map(record=>[
    `<strong>${esc(record.title)}</strong><br><span class="subtle">${esc(record.record_key)}</span>`,`${esc(salintelDomainName(catalog,record.domain_key))}<br><span class="subtle">${esc(record.subject_reference)}</span>`,esc(record.status),`${salintelTierLabel(record.authorized_tier)} · completed ${record.completed_tier||0}<br><span class="subtle">${esc(record.qualification_status)}</span>`,esc(record.disclosure_status),salintelRecordActions(record)
  ]))}
  <details class="card salintel-registry"><summary>Investigative-domain registry</summary>${table(['Domain','Purpose','Lifecycle','Review','Available depth'],catalog.map(row=>[
    esc(row.display_name),esc(row.description),esc(row.lifecycle_status),esc(row.required_review_level),(row.tier_profiles||[]).map(t=>`<span class="salintel-tier">Tier ${esc(t.tier)} · ${esc(t.name)}</span>`).join('')
  ]))}</details>${salintelDetail(detail,catalog)}`;
  $('#salintel-filter-form').onsubmit=event=>{event.preventDefault();const data=new FormData(event.target);for(const key of ['domain','status','tier','epistemic','phase'])state[key]=String(data.get(key)||'');state.recordId=null;salintelDomains();};
  $('#salintel-investigation-form').onsubmit=async event=>{event.preventDefault();const data=new FormData(event.target);await api('/api/salintel/investigations',{method:'POST',body:JSON.stringify({domain_key:data.get('domain_key'),title:data.get('title'),subject_reference:data.get('subject_reference'),purpose:data.get('purpose'),requested_tier:Number(data.get('requested_tier')),sensitivity:data.get('sensitivity'),engagement_context:data.get('engagement_context')})});await salintelDomains();};
  const itemForm=$('#salintel-item-form');if(itemForm)itemForm.onsubmit=async event=>{event.preventDefault();const data=new FormData(event.target),body={item_kind:data.get('item_kind'),epistemic_state:data.get('epistemic_state'),title:data.get('title'),detail:data.get('detail'),source_reliability:data.get('source_reliability'),information_confidence:data.get('information_confidence')};if(data.get('source_material_id'))body.source_material_id=Number(data.get('source_material_id'));await api('/api/salintel/investigations/'+state.recordId+'/items',{method:'POST',body:JSON.stringify(body)});await salintelDomains();};
  if(detail&&detail.authorized_tier===0)await showSalintelTierAuthorization(detail.id);
}
async function selectSalintelInvestigation(id,authorize=false){salintelDomainUiState.recordId=id;await salintelDomains();if(authorize)await showSalintelTierAuthorization(id);}
function closeSalintelInvestigation(){salintelDomainUiState.recordId=null;salintelDomains();}
function resetSalintelDomainFilters(){salintelDomainUiState={domain:'',status:'',tier:'',epistemic:'',phase:'',recordId:null};salintelDomains();}
async function showSalintelTierAuthorization(id){
  const tier=Number(prompt('Authorize Tier 1, 2, or 3:','1'));if(![1,2,3].includes(tier))return;
  const scope=prompt('Bounded scope statement:');if(!scope)return;const checklist=prompt('Checklist/profile version:','shared-v1');if(!checklist)return;
  const selected=prompt('Investigative lenses (comma-separated):',salintelPhases.join(', '));if(!selected)return;
  const lenses=selected.split(',').map(x=>x.trim()).filter(x=>salintelPhases.includes(x)),maximumHours=Number(prompt('Maximum human effort hours (0 if separately governed):','0')||0);
  const commercial=prompt('Commercial treatment: Not Determined, Included, Bundled, Separate Proposal, or Waived','Not Determined')||'Not Determined',reference=prompt('Commercial authorization/reference (optional):','')||'',reason=prompt('Salus authorization basis:');if(!reason)return;
  await api('/api/salintel/investigations/'+id+'/authorize-tier',{method:'POST',body:JSON.stringify({authorized_tier:tier,scope_statement:scope,checklist_version:checklist,investigative_lenses:lenses,effort_bounds:maximumHours>0?{maximum_human_hours:maximumHours}:{},source_categories:[],exclusions:[],commercial_treatment:commercial,commercial_reference:reference,reason})});
  salintelDomainUiState.recordId=id;await salintelDomains();
}
async function qualifySalintelInvestigation(id){const status=prompt('Qualification: Analyst Reviewed, Qualified, Rejected, or Unqualified','Qualified');if(!status)return;const reason=prompt('Human qualification basis:');if(!reason)return;await api('/api/salintel/investigations/'+id+'/qualify',{method:'POST',body:JSON.stringify({status,reason})});await salintelDomains();}
async function completeSalintelTier(id,tier){const completion_statement=prompt('Completion statement for the bounded authorized scope:');if(!completion_statement)return;const residual_unknowns=prompt('Residual unknowns and collection needs (optional):','')||'';await api('/api/salintel/investigations/'+id+'/complete-tier',{method:'POST',body:JSON.stringify({tier,completion_statement,residual_unknowns})});await salintelDomains();}
async function recommendSalintelTier(id,recommended){const reason=prompt(recommended?'Why should Salus consider a separately authorized deeper tier?':'Why is the deeper-tier recommendation withdrawn?');if(!reason)return;await api('/api/salintel/investigations/'+id+'/recommend-tier',{method:'POST',body:JSON.stringify({recommended,reason})});await salintelDomains();}
async function decideSalintelDisclosure(id,approved_for_tenant){const reason=prompt(approved_for_tenant?'Protected Member disclosure basis:':'Reason for returning the investigation to Salus-internal handling:');if(!reason)return;await api('/api/salintel/investigations/'+id+'/disclosure',{method:'POST',body:JSON.stringify({approved_for_tenant,reason})});await salintelDomains();}
async function releaseSalintelItem(recordId,itemId,approved_for_tenant){const reason=prompt(approved_for_tenant?'Item release basis:':'Item release withdrawal basis:');if(!reason)return;await api('/api/salintel/investigations/'+recordId+'/items/'+itemId+'/release',{method:'POST',body:JSON.stringify({approved_for_tenant,reason})});await salintelDomains();}
