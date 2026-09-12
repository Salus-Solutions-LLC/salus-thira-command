const facilityReviewProfileState={profiles:[],sourcesById:{}};

function facilityReviewProfileText(value,fallback='Not recorded'){
  const text=String(value??'').trim();
  return esc(text||fallback);
}

function facilityReviewProfileTitle(context){
  return context==='mission_map'?'Mission Map':'Facility Assessment';
}

function facilityReviewProfileCompatible(profile,source){
  return (profile.allowed_representation_classes||[]).includes(source.representation_class)
    &&(profile.allowed_coordinate_spaces||[]).includes(source.coordinate_space);
}

function facilityReviewProfileRows(items){
  if(!items.length)return '<p>No review-profile applications have been prepared for this Protected Member environment.</p>';
  return `<div class="facility-imagery-table-wrap"><table class="facility-imagery-table"><thead><tr><th>Review profile</th><th>Purpose and question</th><th>Source lineage</th><th>Authority boundary</th></tr></thead><tbody>${items.map(item=>{
    const profile=item.profile_snapshot||{};
    const sourceHash=String(item.source_sha256||'').slice(0,12);
    const geometryHash=String(item.geometry_sha256||'').slice(0,12);
    return `<tr><td><strong>${facilityReviewProfileText(profile.name||item.capability_class)}</strong><br><span class="facility-imagery-state">${facilityReviewProfileText(item.application_status)}</span><br><span class="subtle">${facilityReviewProfileText(item.profile_key)} · version ${facilityReviewProfileText(profile.profile_version)}</span></td><td><strong>Purpose:</strong> ${facilityReviewProfileText(item.purpose)}<br><strong>Review question:</strong> ${facilityReviewProfileText(item.review_question)}<br><strong>Destination considered:</strong> ${facilityReviewProfileText(item.destination_under_consideration)}</td><td>Material ${Number(item.source_material_id)} · page ${Number(item.page_number)}<br><span class="subtle">Source ${facilityReviewProfileText(sourceHash)}… · geometry ${facilityReviewProfileText(geometryHash)}…</span><br><span class="subtle">${facilityReviewProfileText(item.representation_class)} · ${facilityReviewProfileText(item.coordinate_space)}</span></td><td>${facilityReviewProfileText(profile.required_human_step)}<br><span class="subtle">${facilityReviewProfileText(profile.known_limitations)} ${facilityReviewProfileText(profile.negative_inference_rule)}</span></td></tr>`;
  }).join('')}</tbody></table></div>`;
}

function facilityReviewProfileSourceRows(items,profiles,context){
  if(!items.length)return '<p>No governed source region is available for profile preparation.</p>';
  const seen=new Set();
  const sources=items.filter(item=>{
    const key=Number(item.source_id);
    if(seen.has(key))return false;
    seen.add(key);
    return true;
  });
  return `<div class="facility-imagery-table-wrap"><table class="facility-imagery-table"><thead><tr><th>Source region</th><th>Available review profiles</th><th>Prepare</th></tr></thead><tbody>${sources.map(source=>{
    facilityReviewProfileState.sourcesById[Number(source.source_id)]=source;
    const compatible=profiles.filter(profile=>facilityReviewProfileCompatible(profile,source));
    const names=compatible.map(profile=>facilityReviewProfileText(profile.name)).join('<br>')||'No compatible server-approved profile';
    const action=compatible.length?`<button class="btn secondary" onclick="facilityReviewProfilePrepare(${Number(source.source_id)},'${context}')">Prepare review profile</button>`:'';
    return `<tr><td>Material ${Number(source.source_material_id)} · page ${Number(source.page_number)}<br><span class="subtle">${facilityReviewProfileText(source.representation_class)} · ${facilityReviewProfileText(source.coordinate_space)}</span></td><td>${names}</td><td>${action}</td></tr>`;
  }).join('')}</tbody></table></div>`;
}

function facilityReviewProfilePanel(triage,profilesData,applicationsData,context){
  const title=facilityReviewProfileTitle(context);
  const profiles=profilesData.items||[];
  facilityReviewProfileState.profiles=profiles;
  return `<section id="facility-review-profiles-${context}" class="card facility-imagery-review" aria-labelledby="facility-review-profiles-heading-${context}"><div class="section-title"><div><span>Purpose-bounded preparation</span><h3 id="facility-review-profiles-heading-${context}">Facility review profiles</h3></div><span class="facility-imagery-state">Human Review Required</span></div><p>${facilityReviewProfileText(profilesData.guidance)}</p><div class="notice"><strong>Review aid — not a conclusion.</strong><br>Choose a profile only for an authorized purpose and exact source region. A prepared profile does not process source bytes or establish a finding, priority, engineering conclusion, safe route, decision, disclosure, or authorization.</div><p class="subtle">${title} receives no silent attachment. Prepared work remains Salus internal, Derived — Unverified, and subject to independent source comparison and the destination's own authority.</p><h4>Prepare from a governed source region</h4>${facilityReviewProfileSourceRows(triage.items||[],profiles,context)}<h4>Prepared applications</h4>${facilityReviewProfileRows(applicationsData.items||[])}</section>`;
}

async function facilityReviewProfilesAttach(context){
  if(typeof isProtectedMember==='function'&&isProtectedMember())return;
  const host=$('#content');
  if(!host||host.querySelector(`#facility-review-profiles-${context}`))return;
  const [triage,profiles,applications]=await Promise.all([
    api('/api/facility-imagery/triage'),
    api('/api/facility-imagery/review-profiles'),
    api('/api/facility-imagery/profile-applications'),
  ]);
  host.insertAdjacentHTML('beforeend',facilityReviewProfilePanel(triage,profiles,applications,context));
}

async function facilityReviewProfilePrepare(sourceId,context){
  const source=facilityReviewProfileState.sourcesById[Number(sourceId)];
  if(!source)return;
  const compatible=facilityReviewProfileState.profiles.filter(profile=>facilityReviewProfileCompatible(profile,source));
  if(!compatible.length)return;
  const keys=compatible.map(profile=>`${profile.profile_key} — ${profile.name}`).join('\n');
  const selected=(prompt(`Choose one server-approved profile key:\n${keys}`,compatible[0].profile_key)||'').trim();
  const profile=compatible.find(item=>item.profile_key===selected);
  if(!profile)return;
  const title=facilityReviewProfileTitle(context);
  const purposeDefault=`${profile.approved_purpose_terms[0]} review for ${title}`;
  const purpose=(prompt('State the authorized review purpose:',purposeDefault)||'').trim();
  if(!purpose)return;
  const question=(prompt('What must the reviewer compare with the exact source region?')||'').trim();
  if(!question)return;
  const countText=(prompt('Expected source regions for this bounded review:','1')||'').trim();
  if(!/^\d+$/.test(countText))return;
  const expectedRegionCount=Number(countText);
  if(expectedRegionCount<1||expectedRegionCount>20)return;
  await api(`/api/facility-imagery/sources/${Number(sourceId)}/profile-applications`,{
    method:'POST',
    body:JSON.stringify({
      profile_key:profile.profile_key,
      purpose,
      review_question:question,
      destination_under_consideration:title,
      expected_region_count:expectedRegionCount,
    }),
  });
  alert('The review profile was prepared. It remains Salus internal and requires independent comparison with the exact source region.');
  if(context==='mission_map')await salcapaMissionMap({announcement:'Facility review profile prepared for human review.'});
  else await facilityAssessments();
}

if(typeof facilityAssessments==='function'){
  const facilityReviewProfilesBaseFacilityAssessments=facilityAssessments;
  facilityAssessments=async function(){
    const result=await facilityReviewProfilesBaseFacilityAssessments();
    if(currentView==='facility_assessments'&&facilityAssessmentState.recordId){
      try{await facilityReviewProfilesAttach('facility_assessment');}catch(error){console.warn('Facility review profiles unavailable',error);}
    }
    return result;
  };
}

if(typeof salcapaMissionMap==='function'){
  const facilityReviewProfilesBaseMissionMap=salcapaMissionMap;
  salcapaMissionMap=async function(options={}){
    const result=await facilityReviewProfilesBaseMissionMap(options);
    if(currentView==='mission_map'){
      try{await facilityReviewProfilesAttach('mission_map');}catch(error){console.warn('Facility review profiles unavailable',error);}
    }
    return result;
  };
}
