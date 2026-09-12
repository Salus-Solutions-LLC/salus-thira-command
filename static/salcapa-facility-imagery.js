const facilityImageryReviewStatuses=['Accept Representation','Corrected','Rejected','Needs More Information','Superseded'];

function facilityImageryText(value,fallback='Not recorded'){
  const text=String(value??'').trim();
  return esc(text||fallback);
}

function facilityImageryContextTitle(context){
  return context==='mission_map'?'Mission Map':'Facility Assessment';
}

function facilityImageryProposalRows(items,context){
  if(!items.length)return '<p>No source-region relationship proposals are awaiting or available for review in this Protected Member environment.</p>';
  return `<div class="facility-imagery-table-wrap"><table class="facility-imagery-table"><thead><tr><th>Proposed relationship</th><th>Source and region</th><th>Authority and limits</th><th>Review</th></tr></thead><tbody>${items.map(item=>{
    const state=facilityImageryText(item.review_status);
    const canReview=item.review_status==='Awaiting Human Review';
    const canProposeDestination=['Accept Representation','Corrected'].includes(item.review_status);
    const actions=[canReview?`<button class="btn secondary" onclick="facilityImageryReviewProposal(${Number(item.id)},'${context}')">Review representation</button>`:'',canProposeDestination?`<button class="btn secondary" onclick="facilityImageryDestinationProposal(${Number(item.id)},'${context}')">Propose ${facilityImageryContextTitle(context)} reference</button>`:''].filter(Boolean).join(' ');
    return `<tr><td><strong>${facilityImageryText(item.relationship_type)}</strong><br>${facilityImageryText(item.current_description||item.description)}<br><span class="facility-imagery-state">${facilityImageryText(item.epistemic_state)}</span></td><td>Material ${Number(item.source_material_id)} · page ${Number(item.page_number)}<br><span class="subtle">${facilityImageryText(item.representation_class)} · ${facilityImageryText(item.coordinate_space)}</span><br><span class="subtle">Region x ${Number(item.region_x)}, y ${Number(item.region_y)}, width ${Number(item.region_width)}, height ${Number(item.region_height)}</span></td><td><strong>Authority:</strong> ${facilityImageryText(item.authority_basis)}<br><strong>Scale:</strong> ${facilityImageryText(item.scale_status)}<br><strong>Uncertainty:</strong> ${facilityImageryText(item.uncertainty_note)}<br><strong>Contradictions:</strong> ${facilityImageryText(item.contradictions,'None recorded')}</td><td><span class="facility-imagery-state">${state}</span>${actions?`<div class="facility-imagery-actions">${actions}</div>`:''}</td></tr>`;
  }).join('')}</tbody></table></div>`;
}

function facilityImageryReviewPanel(data,context){
  const title=facilityImageryContextTitle(context);
  return `<section id="facility-imagery-review-${context}" class="card facility-imagery-review" aria-labelledby="facility-imagery-heading-${context}"><div class="section-title"><div><span>Source-grounded review</span><h3 id="facility-imagery-heading-${context}">Maps, plans, diagrams, and facility imagery</h3></div><span class="facility-imagery-state">Salus review only</span></div><p>${facilityImageryText(data.guidance)}</p><div class="notice"><strong>Derived — Unverified.</strong><br>A proposed relationship is a review aid, not a Facility Assessment finding, Mission Map decision, engineering conclusion, safe-route determination, disclosure, or authorization. Compare the exact source region, authority, revision, coordinate space, scale limits, contradictions, and uncertainty before accepting its representation.</div><p class="subtle">This ${title} view does not silently attach a proposal. An accepted representation still requires a separately proposed destination reference and the destination's own authority and review.</p>${facilityImageryProposalRows(data.items||[],context)}</section>`;
}

async function facilityImageryAttach(context){
  if(typeof isProtectedMember==='function'&&isProtectedMember())return;
  const host=$('#content');
  if(!host||host.querySelector(`#facility-imagery-review-${context}`))return;
  const data=await api('/api/facility-imagery/triage');
  host.insertAdjacentHTML('beforeend',facilityImageryReviewPanel(data,context));
}

async function facilityImageryReviewProposal(id,context){
  const status=prompt(`Review outcome: ${facilityImageryReviewStatuses.join(' | ')}`,facilityImageryReviewStatuses[0]);
  if(!facilityImageryReviewStatuses.includes(status))return;
  const reason=prompt('Record the source comparison, limitations, and reason for this review outcome:');
  if(!reason||!reason.trim())return;
  const body={status,reason:reason.trim(),corrected_description:'',corrected_target_type:'',corrected_target_id:0,corrected_geometry_json:'{}'};
  if(status==='Corrected'){
    body.corrected_description=(prompt('Corrected relationship wording:')||'').trim();
    if(!body.corrected_description)return;
  }
  await api(`/api/facility-imagery/relationship-proposals/${Number(id)}/review`,{method:'POST',body:JSON.stringify(body)});
  if(context==='mission_map')await salcapaMissionMap({announcement:'Source-region representation review recorded.'});
  else await facilityAssessments();
}

async function facilityImageryDestinationProposal(id,context){
  const title=facilityImageryContextTitle(context);
  const defaultId=context==='facility_assessment'&&facilityAssessmentState.recordId?String(facilityAssessmentState.recordId):'';
  const target=prompt(`${title} record or item ID for the proposed reference:`,defaultId);
  if(target===null||!/^\d+$/.test(target.trim()))return;
  const purpose=prompt(`Why should this reviewed representation be considered in ${title}?`);
  if(!purpose||!purpose.trim())return;
  await api(`/api/facility-imagery/relationship-proposals/${Number(id)}/destination-proposals`,{method:'POST',body:JSON.stringify({destination_product:title,destination_type:context==='mission_map'?'Mission Map Item':'Facility Assessment Record',destination_id:Number(target),purpose:purpose.trim()})});
  alert(`A ${title} reference was proposed. The destination must apply its own authority, review, and disclosure rules before use.`);
  if(context==='mission_map')await salcapaMissionMap({announcement:'Mission Map reference proposed for separate review.'});
  else await facilityAssessments();
}

if(typeof facilityAssessments==='function'){
  const facilityImageryBaseFacilityAssessments=facilityAssessments;
  facilityAssessments=async function(){
    const result=await facilityImageryBaseFacilityAssessments();
    if(currentView==='facility_assessments'&&facilityAssessmentState.recordId){
      try{await facilityImageryAttach('facility_assessment');}catch(error){console.warn('Facility imagery guidance unavailable',error);}
    }
    return result;
  };
}

if(typeof salcapaMissionMap==='function'){
  const facilityImageryBaseMissionMap=salcapaMissionMap;
  salcapaMissionMap=async function(options={}){
    const result=await facilityImageryBaseMissionMap(options);
    if(currentView==='mission_map'){
      try{await facilityImageryAttach('mission_map');}catch(error){console.warn('Facility imagery guidance unavailable',error);}
    }
    return result;
  };
}
