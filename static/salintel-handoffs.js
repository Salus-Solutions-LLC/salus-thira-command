/* Governed internal SalINTEL™ handoffs to SalTHIRA™ and SalOPS™. */
const salintelHandoffState={recordId:null,data:null,assessments:[]};

function salintelHandoffPanel(record){
  if(!record||!record.id)return '';
  return `<section class="salintel-handoff-workspace" id="salintel-handoff-workspace"><div class="section-title"><div><h3>Qualified internal handoffs</h3><p class="subtle">Move only completed, human-qualified outputs into SalTHIRA™ assessment or a SalOPS™ request.</p></div><span class="personnel-state" id="salintel-handoff-status">Loading…</span></div><div id="salintel-handoff-content"><p class="subtle">Loading governed handoff state…</p></div></section>`;
}

function salintelHandoffRows(rows){
  return table(['Target','Assessment','Governed link','Status','Authority'],rows.map(row=>[
    `<span class="handoff-target">${esc(row.target_component)}</span>`,
    `<strong>${esc(row.assessment_name_snapshot)}</strong><br><span class="subtle">Assessment ${esc(row.assessment_id)}</span>`,
    `${esc(row.target_record_type)} #${esc(row.target_record_id)}<br><span class="subtle">${esc(row.summary)}</span>`,
    `<span class="handoff-state">${esc(row.target_status)}</span>`,
    `${esc(row.authorized_by)}<br><span class="subtle">${esc(row.authorized_at)}</span>`
  ]));
}

function salintelHandoffForm(data,assessments){
  const readiness=data.readiness||{ready:false,blockers:[],eligible_items:[],allowed_targets:[]};
  if(!readiness.ready){
    const blockers=(readiness.blockers||[]).map(item=>`<li>${esc(item)}</li>`).join('');
    return `<div class="notice"><strong>Handoff remains server-blocked.</strong><br>Complete and qualify the bounded investigation product first.<ul>${blockers}</ul></div>`;
  }
  if(!assessments.length)return '<div class="notice"><strong>No target assessment is available.</strong><br>Create or gain authorized access to a SalTHIRA™ assessment before handoff.</div>';
  return `<article class="card"><h4>Create governed handoff</h4><div class="notice"><strong>Internal routing is not member disclosure or operational authorization.</strong><br>This action creates an open SalTHIRA™ reassessment trigger or a requested SalOPS™ work item. It cannot change tier, price, disclosure, or execution authority.</div><form id="salintel-handoff-form"><div class="form-grid"><label>Target component<select name="target_component" required>${readiness.allowed_targets.map(target=>`<option>${esc(target)}</option>`).join('')}</select></label><label>Target assessment<select name="assessment_id" required>${assessments.map(item=>`<option value="${item.id}">${esc(item.name)}</option>`).join('')}</select></label></div><fieldset><legend>Qualified outputs to reference</legend>${readiness.eligible_items.map(item=>`<label class="handoff-check"><input type="checkbox" name="item_ids" value="${item.id}"> <strong>${esc(item.title)}</strong> <span class="subtle">${esc(item.epistemic_state)}</span></label>`).join('')}</fieldset><label>Qualified summary<textarea name="summary" maxlength="8000" required></textarea></label><label>Authorization rationale<textarea name="rationale" maxlength="4000" required></textarea></label><button class="btn">Authorize internal handoff</button></form></article>`;
}

async function loadSalintelHandoffs(record){
  if(!record||!record.id)return;
  salintelHandoffState.recordId=record.id;
  const [data,assessments]=await Promise.all([
    api(`/api/salintel/investigations/${record.id}/handoffs`),
    api('/api/assessments')
  ]);
  salintelHandoffState.data=data;
  salintelHandoffState.assessments=assessments;
  const root=$('#salintel-handoff-workspace');if(!root)return;
  $('#salintel-handoff-status').textContent=data.readiness.ready?'Ready for governed routing':'Governance gates remain';
  $('#salintel-handoff-content').innerHTML=`${salintelHandoffForm(data,assessments)}<div class="section-title"><h4>Handoff history</h4><span class="subtle">Immutable source references; live target status</span></div>${salintelHandoffRows(data.handoffs||[])}`;
  const form=$('#salintel-handoff-form');if(form)form.onsubmit=submitSalintelHandoff;
}

async function submitSalintelHandoff(event){
  event.preventDefault();
  const data=new FormData(event.target);
  const item_ids=data.getAll('item_ids').map(Number).filter(Boolean);
  if(!item_ids.length){alert('Select at least one qualified analytic output.');return;}
  const body={target_component:data.get('target_component'),assessment_id:Number(data.get('assessment_id')),item_ids,summary:data.get('summary'),rationale:data.get('rationale')};
  await api(`/api/salintel/investigations/${salintelHandoffState.recordId}/handoffs`,{method:'POST',body:JSON.stringify(body)});
  await personnelAssessments();
}
