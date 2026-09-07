/* SalCAPA PROVE — server-derived assurance, results, and accountability. */
viewTitles.prove='SalCAPA™ PROVE — Assurance & Results';
subtitles.prove='Trace what was known, prioritized, decided, authorized, performed, evidenced, validated, and reassessed.';

function salcapaAssuranceStage(stage,index){
  const has=stage.record_count>0;
  return `<article class="assurance-stage ${has?'has-evidence':'has-gap'}"><span class="assurance-stage-number">${index+1}</span><div><strong>${esc(stage.label)}</strong><small>${esc(stage.function)} · ${esc(stage.owner)}</small><span>${has?'Evidence present':'Assurance gap'} · ${Number(stage.record_count)} qualifying record${Number(stage.record_count)===1?'':'s'}</span></div></article>`;
}
function salcapaAssuranceLinks(items){return `<div class="assurance-links">${items.map(item=>`<button class="btn secondary" onclick="setView('${esc(item.view)}')">${esc(item.label)}</button>`).join('')}</div>`;}
function salcapaAssuranceAssessment(item){
  const gaps=item.assurance_gaps||[],edges=item.explicit_edges||[];
  const gapRows=gaps.map(gap=>[esc(gap.stage),esc(gap.reason),gap.record_key?esc(gap.record_key):'Stage-level gap']);
  const edgeRows=edges.map(edge=>[esc(edge.source),esc(edge.relationship),esc(edge.target),esc(edge.basis)]);
  return `<section class="assurance-assessment"><div class="section-title"><div><h2>${esc(item.assessment.name)}</h2><p class="subtle">${esc(item.assessment.organization)} · assessment version ${esc(item.assessment.version)} · ${esc(item.assessment.status)}</p></div><span class="assurance-neutral-status">${gaps.length} explicit gap${gaps.length===1?'':'s'}</span></div><div class="assurance-stages">${item.stages.map(salcapaAssuranceStage).join('')}</div><div class="two-col grid"><article class="card"><h3>Assurance gaps</h3><p class="subtle">Missing links remain visible. SalCAPA does not invent causality or completion.</p>${table(['Stage or handoff','What is missing','Record'],gapRows)}</article><article class="card"><h3>Direct traceability</h3><p class="subtle">Only persisted explicit links are shown.</p>${table(['Source','Relationship','Target','Basis'],edgeRows)}</article></div><article class="card"><h3>Released assurance outputs</h3>${table(['Output','Status','Released'],[...(item.released_outputs.reports||[]).map(x=>[esc(x.report_type),esc(x.status),salcapaFormatDateTime(x.released_at)]),...(item.released_outputs.field_reports||[]).map(x=>[esc(x.report_type),esc(x.status),salcapaFormatDateTime(x.released_at)])])}</article></section>`;
}
async function salcapaAssurance(){
  const suffix=activeAssessmentId?`?assessment_id=${Number(activeAssessmentId)}`:'';
  const data=await api('/api/salcapa/assurance'+suffix);
  $('#content').innerHTML=`<div class="card assurance-hero"><span>PROVE · cross-cutting SalCAPA assurance</span><h2>Evidence, accountability, results, validation, and improvement</h2><p>${esc(data.purpose)}</p><p class="subtle">PROVE spans See, Decide, Coordinate, and Act. It is not a separate product or an automatic claim that work is complete.</p>${salcapaAssuranceLinks(data.links)}</div>${data.assessments.length?data.assessments.map(salcapaAssuranceAssessment).join(''):'<div class="notice">No accessible assessment is available for assurance review.</div>'}`;
}

const salcapaRenderWithoutAssurance=render;
render=async function(){if(currentView==='prove')return salcapaAssurance();return salcapaRenderWithoutAssurance();};
