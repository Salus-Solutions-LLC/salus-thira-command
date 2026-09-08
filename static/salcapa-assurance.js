/* SalCAPA PROVE — server-derived assurance, results, and accountability. */
viewTitles.prove='SalCAPA™ PROVE — Assurance & Results';
subtitles.prove='Trace what was known, prioritized, decided, authorized, performed, evidenced, validated, and reassessed.';

function salcapaAssuranceStage(stage,index){
  const has=stage.record_count>0;
  return `<article class="assurance-stage ${has?'has-evidence':'has-gap'}"><span class="assurance-stage-number">${index+1}</span><div><strong>${esc(stage.label)}</strong><small>${esc(stage.function)} · ${esc(stage.owner)}</small><span>${has?'Evidence present':'Assurance gap'} · ${Number(stage.record_count)} qualifying record${Number(stage.record_count)===1?'':'s'}</span></div></article>`;
}
function salcapaAssuranceLinks(items){return `<div class="assurance-links">${items.map(item=>`<button class="btn secondary" onclick="setView('${esc(item.view)}')">${esc(item.label)}</button>`).join('')}</div>`;}
let salcapaAssurancePackageTypes=[];
function salcapaAssurancePackageRows(item){
  return table(['Package / version','Governed lifecycle','Classification','Snapshot'],(item.assurance_packages||[]).map(pkg=>{
    const next={Draft:'Reviewed',Reviewed:'Approved',Approved:'Released'}[pkg.status];
    const action=next&&!isProtectedMember()?`<button class="btn secondary" onclick="transitionSalcapaAssurancePackage(${Number(pkg.id)},'${next}')">Record ${next}</button>`:'';
    return [`<strong>${esc(pkg.package_type)}</strong><br><span class="subtle">Package v${Number(pkg.package_version)} · assessment v${esc(pkg.assessment_version)}</span>`,`<strong>${esc(pkg.status)}</strong><br><span class="subtle">Created ${salcapaFormatDateTime(pkg.created_at||pkg.released_at)}</span>${action?`<br>${action}`:''}`,esc(pkg.classification),`<a class="btn secondary" href="/api/reports/versions/${Number(pkg.id)}/snapshot" target="_blank" rel="noopener">Open verified snapshot</a><br><span class="subtle">SHA-256 ${esc(pkg.snapshot_sha256)}</span>`];
  }));
}
function salcapaAssuranceAssessment(item){
  const gaps=item.assurance_gaps||[],edges=item.explicit_edges||[];
  const prep=item.preparedness_trace||{};
  const gapRows=gaps.map(gap=>[esc(gap.stage),esc(gap.reason),gap.record_key?esc(gap.record_key):'Stage-level gap']);
  const edgeRows=edges.map(edge=>[esc(edge.source),esc(edge.relationship),esc(edge.target),esc(edge.basis)]);
  const prepRows=[['Plans',prep.plans],['Training',prep.training],['Exercises',prep.exercises],['Observations',prep.observations],['Corrective actions',prep.corrective_actions],['AAR / improvement plans',prep.after_action_reports]].map(row=>[esc(row[0]),Number(row[1]||0)]);
  const create=!isProtectedMember()?'<button class="btn" onclick="createSalcapaAssurancePackage('+Number(item.assessment.id)+')">Create immutable package</button>':'';
  return `<section class="assurance-assessment"><div class="section-title"><div><h2>${esc(item.assessment.name)}</h2><p class="subtle">${esc(item.assessment.organization)} · assessment version ${esc(item.assessment.version)} · ${esc(item.assessment.status)}</p></div><span class="assurance-neutral-status">${gaps.length} explicit gap${gaps.length===1?'':'s'}</span></div><div class="assurance-stages">${item.stages.map(salcapaAssuranceStage).join('')}</div><div class="two-col grid"><article class="card"><h3>Assurance gaps</h3><p class="subtle">Missing links remain visible. SalCAPA does not invent causality or completion.</p>${table(['Stage or handoff','What is missing','Record'],gapRows)}</article><article class="card"><h3>Direct traceability</h3><p class="subtle">Only persisted explicit links are shown.</p>${table(['Source','Relationship','Target','Basis'],edgeRows)}</article></div><article class="card"><h3>Preparedness assurance trace</h3><p class="subtle">PROVE reads governed plan, training, exercise, observation, corrective-action, and AAR records. Their SalOPS lifecycles remain authoritative; presence here does not schedule work, prove readiness, authorize disclosure, or close a gap.</p>${table(['Governed record','Visible in this assurance scope'],prepRows)}</article><article class="card"><div class="section-title"><div><h3>Governed assurance packages</h3><p class="subtle">Server-generated immutable snapshots follow Draft → Reviewed → Approved → Released. Protected Members see only released packages within their clearance.</p></div>${create}</div>${salcapaAssurancePackageRows(item)}</article><article class="card"><h3>Released assurance outputs</h3>${table(['Output','Status','Released'],[...(item.released_outputs.reports||[]).map(x=>[esc(x.report_type),esc(x.status),salcapaFormatDateTime(x.released_at)]),...(item.released_outputs.field_reports||[]).map(x=>[esc(x.report_type),esc(x.status),salcapaFormatDateTime(x.released_at)])])}</article></section>`;
}
async function salcapaAssurance(){
  const suffix=activeAssessmentId?`?assessment_id=${Number(activeAssessmentId)}`:'';
  const data=await api('/api/salcapa/assurance'+suffix);
  salcapaAssurancePackageTypes=data.package_types||[];
  $('#content').innerHTML=`<div class="card assurance-hero"><span>PROVE · cross-cutting SalCAPA assurance</span><h2>Evidence, accountability, results, validation, and improvement</h2><p>${esc(data.purpose)}</p><p class="subtle">PROVE spans See, Decide, Coordinate, and Act. It is not a separate product or an automatic claim that work is complete.</p>${salcapaAssuranceLinks(data.links)}</div>${data.assessments.length?data.assessments.map(salcapaAssuranceAssessment).join(''):'<div class="notice">No accessible assessment is available for assurance review.</div>'}`;
}

async function createSalcapaAssurancePackage(assessmentId){const packageType=prompt(`Package type: ${salcapaAssurancePackageTypes.join(' | ')}`,salcapaAssurancePackageTypes[0]||'Executive Assurance');if(!salcapaAssurancePackageTypes.includes(packageType))return;await api(`/api/salcapa/assurance/assessments/${Number(assessmentId)}/packages`,{method:'POST',body:JSON.stringify({package_type:packageType})});await salcapaAssurance();}
async function transitionSalcapaAssurancePackage(packageId,status){const reason=prompt(`Authority basis to record ${status}:`);if(!reason)return;await api(`/api/reports/versions/${Number(packageId)}/transition`,{method:'POST',body:JSON.stringify({status,reason})});await salcapaAssurance();}

const salcapaRenderWithoutAssurance=render;
render=async function(){if(currentView==='prove')return salcapaAssurance();return salcapaRenderWithoutAssurance();};
