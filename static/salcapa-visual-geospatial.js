/* Restricted location metadata and source-region visual review. */
let salcapaVisualReviewData={location_metadata:[],observations:[]};
let salcapaVisualObjectData={items:[],guidance:''};

function visualLocationRows(items){
  return table(['Source','Location metadata','Review state','Action'],items.map(item=>[
    `<strong>${esc(item.source_title)}</strong><br><span class="subtle">${esc(item.original_name)} · ${esc(item.sensitivity)}</span>`,
    `<strong>${esc(item.metadata_status)}</strong><br><span class="subtle">Exact values remain restricted and are not included in this queue.</span>`,
    `<strong>${esc(item.review_status)}</strong><br><span class="subtle">${esc(item.disclosure_status)}</span>`,
    `<button class="btn secondary" type="button" onclick="viewRestrictedLocation(${Number(item.id)})">Review location metadata</button>${item.review_status==='Awaiting Human Review'&&(accessState?.permissions||[]).includes('decide')?` <button class="btn secondary" type="button" onclick="reviewRestrictedLocation(${Number(item.id)})">Record review</button>`:''}`
  ]));
}

function visualObservationRows(items){
  return table(['Source region','Visible observation','State','Action'],items.map(item=>[
    `<strong>${esc(item.source_title)}</strong><br><span class="subtle">x ${Number(item.region_x)}, y ${Number(item.region_y)}, ${Number(item.region_width)} × ${Number(item.region_height)} pixels</span>`,
    `<strong>${esc(item.current_text)}</strong><details><summary>Purpose and limits</summary><p>${esc(item.purpose)}</p><p>${esc(item.uncertainty_note)}</p><p>${esc(item.authority_note)}</p></details>`,
    `<strong>${esc(item.review_status)}</strong><br><span class="subtle">${esc(item.record_type)} · ${esc(item.record_origin)}</span>`,
    item.review_status==='Awaiting Human Review'&&(accessState?.permissions||[]).includes('decide')
      ?`<button class="btn secondary" type="button" onclick="reviewVisualObservation(${Number(item.id)})">Review observation</button>`
      :item.review_status==='Human Reviewed'||item.review_status==='Corrected'
        ?`<button class="btn secondary" type="button" onclick="proposeVisualObservationLink(${Number(item.id)})">Prepare reference</button>`
        :esc(item.review_status)
  ]));
}

async function loadVisualGeospatialReview(){
  [salcapaVisualReviewData,salcapaVisualObjectData]=await Promise.all([api('/api/visual-geospatial/triage'),api('/api/visual-object-analysis/triage')]);
  const processorStatus=await api('/api/visual-object-analysis/status');
  const anchor=$('#material-review-detail');
  if(!anchor)return;
  const locationPending=salcapaVisualReviewData.location_metadata.filter(item=>item.review_status==='Awaiting Human Review').length;
  const observationPending=salcapaVisualReviewData.observations.filter(item=>item.review_status==='Awaiting Human Review').length;
  const objectPending=salcapaVisualObjectData.items.filter(item=>item.review_status==='Awaiting Human Review').length;
  anchor.insertAdjacentHTML('beforebegin',`<section class="card visual-review-aids"><div class="section-title"><div><span>Restricted source metadata</span><h2>Location Metadata Review</h2><p>Review source-stored location facts without treating them as proof of where a depicted person, incident, or event occurred.</p></div><strong>${locationPending} awaiting review</strong></div><div class="notice"><strong>Exact location remains restricted.</strong> Coordinates appear only after a purpose is recorded and authorization is checked. They are not placed in this queue, ordinary search, notifications, or logs.</div>${visualLocationRows(salcapaVisualReviewData.location_metadata)}</section><section class="card visual-review-aids"><div class="section-title"><div><span>Source-grounded review</span><h2>Visible Conditions</h2><p>${esc(salcapaVisualReviewData.guidance)}</p></div><strong>${observationPending} awaiting review</strong></div>${visualObservationRows(salcapaVisualReviewData.observations)}</section><section class="card visual-review-aids"><div class="section-title"><div><span>Technology-supported review aid</span><h2>Processing Suggestions</h2><p>${esc(salcapaVisualObjectData.guidance)}</p></div><strong>${objectPending} awaiting review</strong></div><div class="notice"><strong>${processorStatus.available?'Local processor available':'Manual review remains available'}.</strong> ${esc(processorStatus.guidance)}</div>${visualObjectRows(salcapaVisualObjectData.items)}</section><div id="visual-restricted-detail" aria-live="polite"></div>`);
}

function visualObjectRows(items){
  return table(['Source region','Processing suggestion','Review state','Action'],items.map(item=>[
    `<strong>${esc(item.source_title)}</strong><br><span class="subtle">x ${Number(item.region_x)}, y ${Number(item.region_y)}, ${Number(item.region_width)} × ${Number(item.region_height)} pixels</span>`,
    `<strong>${esc(item.display_label)}</strong><details><summary>Purpose, alternatives, and limits</summary><p>${esc(item.purpose)}</p><p>Alternatives: ${esc((item.alternatives||[]).join(', ')||'None returned')}</p><p>${esc(item.limitations||'No processor-specific limitation was returned; source and context review remain necessary.')}</p><p>${esc(item.authority_note)}</p></details>`,
    `<strong>${esc(item.review_status)}</strong><br><span class="subtle">${esc(item.record_type)}</span>`,
    item.review_status==='Awaiting Human Review'&&(accessState?.permissions||[]).includes('decide')?`<button class="btn secondary" type="button" onclick="reviewVisualObjectSuggestion(${Number(item.id)})">Compare with original</button>`:esc(item.review_status)
  ]));
}

async function prepareVisibleConditionSuggestions(materialId){
  const purpose=prompt('Operational or investigative purpose for identifying visible conditions:');
  if(!purpose)return;
  const region=prompt('Optional source region as x,y,width,height in original pixels. Leave blank for the full image:','');
  const body={purpose};
  if(region&&region.trim()){
    const values=region.split(',').map(value=>Number(value.trim()));
    if(values.length!==4||values.some(value=>!Number.isInteger(value)||value<0)||values[2]<1||values[3]<1){alert('Enter x,y,width,height as four whole numbers.');return;}
    [body.region_x,body.region_y,body.region_width,body.region_height]=values;
  }
  await api(`/api/materials/${Number(materialId)}/visual-object-analysis-jobs`,{method:'POST',body:JSON.stringify(body)});
  await salcapaMaterialReview();
}

async function reviewVisualObjectSuggestion(id){
  const status=prompt('Review outcome: Confirm Representation, Correct, Reject, or Needs More Information','Confirm Representation');
  if(!status)return;
  const reason=prompt('Review basis. Record what you compared with the original and what remains uncertain:');
  if(!reason)return;
  const body={status,reason};
  if(status==='Correct'){
    body.corrected_label=prompt('Corrected visible label, or leave blank if only the region changes:','')||'';
    const region=prompt('Corrected source region as x,y,width,height, or leave blank if only the label changes:','');
    if(region&&region.trim()){
      const values=region.split(',').map(value=>Number(value.trim()));
      if(values.length!==4||values.some(value=>!Number.isInteger(value)||value<0)||values[2]<1||values[3]<1){alert('Enter x,y,width,height as four whole numbers.');return;}
      [body.corrected_region_x,body.corrected_region_y,body.corrected_region_width,body.corrected_region_height]=values;
    }
    if(!body.corrected_label&&body.corrected_region_x===undefined){alert('A correction needs a corrected label or source region.');return;}
  }
  body.limitations=prompt('Additional limitations or context that should remain with this review:','')||'';
  await api(`/api/visual-object-analysis/suggestions/${Number(id)}/review`,{method:'POST',body:JSON.stringify(body)});
  await salcapaMaterialReview();
}

async function viewRestrictedLocation(id){
  const purpose=prompt('Purpose for viewing exact source-stored location metadata:');
  if(!purpose)return;
  const item=await api(`/api/visual-geospatial/location-metadata/${Number(id)}/view`,{method:'POST',body:JSON.stringify({purpose})});
  const coordinates=item.exact_location_available===false||!item.latitude_decimal
    ?'<p>Exact coordinates are not present in this source record.</p>'
    :`<dl><div><dt>Latitude</dt><dd>${esc(item.latitude_decimal)}</dd></div><div><dt>Longitude</dt><dd>${esc(item.longitude_decimal)}</dd></div><div><dt>Altitude</dt><dd>${esc(item.altitude_meters||'Not recorded')}</dd></div><div><dt>Image direction</dt><dd>${esc(item.image_direction_degrees||'Not recorded')}</dd></div><div><dt>GPS date and time</dt><dd>${esc([item.gps_date,item.gps_time_utc].filter(Boolean).join(' · ')||'Not recorded')}</dd></div><div><dt>Map datum</dt><dd>${esc(item.map_datum||'Not recorded')}</dd></div></dl>`;
  $('#visual-restricted-detail').innerHTML=`<article class="card restricted-location-detail" tabindex="-1"><div class="section-title"><div><span>${esc(item.metadata_key)}</span><h2>Restricted Location Metadata</h2></div><strong>${esc(item.review_status)}</strong></div>${coordinates}<div class="notice"><strong>Interpret with care.</strong> ${esc(item.authority_note)}</div></article>`;
  $('.restricted-location-detail').focus();
}

async function reviewRestrictedLocation(id){
  const choice=prompt('Review outcome: Human Reviewed, Corrected, or Rejected','Human Reviewed');
  if(!choice)return;
  const reason=prompt('Review basis. Record what you compared and any remaining uncertainty:');
  if(!reason)return;
  const body={status:choice,reason};
  if(choice==='Corrected'){
    const latitude=prompt('Corrected latitude. This records a human interpretation and does not alter source metadata:');
    const longitude=prompt('Corrected longitude. This records a human interpretation and does not alter source metadata:');
    if(latitude===null||longitude===null)return;
    body.corrected_latitude_decimal=latitude;
    body.corrected_longitude_decimal=longitude;
  }
  await api(`/api/visual-geospatial/location-metadata/${Number(id)}/review`,{method:'POST',body:JSON.stringify(body)});
  await salcapaMaterialReview();
}

async function prepareLocationMetadata(materialId){
  const purpose=prompt('Purpose for preparing a restricted location-metadata review aid:');
  if(!purpose)return;
  await api(`/api/materials/${Number(materialId)}/location-metadata-review-aids`,{method:'POST',body:JSON.stringify({purpose})});
  await salcapaMaterialReview();
}

async function recordVisibleObservation(materialId){
  const purpose=prompt('Purpose for recording this visible condition:');
  if(!purpose)return;
  const observation_text=prompt('Describe only what is visibly supported by the image. Do not infer identity, intent, hidden cause, code compliance, or structural integrity:');
  if(!observation_text)return;
  const uncertainty_note=prompt('What remains uncertain or requires field, source, or professional confirmation:');
  if(!uncertainty_note)return;
  const region=prompt('Optional source region as x,y,width,height in original pixels. Leave blank for the full image:','');
  const body={purpose,observation_text,uncertainty_note};
  if(region&&region.trim()){
    const values=region.split(',').map(value=>Number(value.trim()));
    if(values.length!==4||values.some(value=>!Number.isInteger(value)||value<0)||values[2]<1||values[3]<1){alert('Enter x,y,width,height as four whole numbers.');return;}
    [body.region_x,body.region_y,body.region_width,body.region_height]=values;
  }
  await api(`/api/materials/${Number(materialId)}/visual-observations`,{method:'POST',body:JSON.stringify(body)});
  await salcapaMaterialReview();
}

async function reviewVisualObservation(id){
  const status=prompt('Review outcome: Human Reviewed, Corrected, Rejected, or Needs More Information','Human Reviewed');
  if(!status)return;
  const reason=prompt('Review basis. Record what you compared and any remaining uncertainty:');
  if(!reason)return;
  let corrected_text='';
  if(status==='Corrected'){
    corrected_text=prompt('Corrected visible observation. The initial wording will remain preserved:')||'';
    if(!corrected_text)return;
  }
  await api(`/api/visual-geospatial/observations/${Number(id)}/review`,{method:'POST',body:JSON.stringify({status,reason,corrected_text})});
  await salcapaMaterialReview();
}

async function proposeVisualObservationLink(id){
  const destination_product=prompt('Destination: SalINTEL, SalTHIRA, SalCAPA, SalOPS, PROVE, Personnel Assessment, Facility Assessment, or Mission Map');
  if(!destination_product)return;
  const destination_type=prompt('Destination record type. This does not create the relationship:');
  if(!destination_type)return;
  const destination_id_text=prompt('Destination record number, or 0 for selection by the destination authority:','0');
  if(destination_id_text===null)return;
  const destination_id=Number(destination_id_text);
  if(!Number.isInteger(destination_id)||destination_id<0){alert('Enter a whole record number or 0.');return;}
  const purpose=prompt('Purpose for preparing this governed reference:');
  if(!purpose)return;
  const result=await api(`/api/visual-geospatial/observations/${Number(id)}/governed-link-proposals`,{method:'POST',body:JSON.stringify({destination_product,destination_type,destination_id,purpose})});
  alert(`${result.status}. The destination authority must review this proposal before any authoritative relationship exists.`);
}

const salcapaMaterialReviewWithoutVisual=salcapaMaterialReview;
salcapaMaterialReview=async function(){
  await salcapaMaterialReviewWithoutVisual();
  if(!isProtectedMember())await loadVisualGeospatialReview();
};

const openMaterialDerivativeWithoutVisual=openMaterialDerivative;
openMaterialDerivative=async function(id){
  await openMaterialDerivativeWithoutVisual(id);
  if(isProtectedMember())return;
  const item=await api(`/api/material-processing/derivatives/${Number(id)}`);
  if(!/\.(?:jpe?g|png)$/i.test(item.original_name||''))return;
  $('.material-review-detail').insertAdjacentHTML('beforeend',`<div class="form-actions"><button class="btn secondary" type="button" onclick="prepareLocationMetadata(${Number(item.source_material_id)})">Review location metadata</button><button class="btn secondary" type="button" onclick="recordVisibleObservation(${Number(item.source_material_id)})">Record visible condition</button><button class="btn secondary" type="button" onclick="prepareVisibleConditionSuggestions(${Number(item.source_material_id)})">Identify visible conditions</button></div><p class="subtle">These actions prepare governed review aids. Processing suggestions remain derived and unverified until a different authorized person compares them with the original. No action establishes a location, finding, assessment, decision, disclosure, or operational authority.</p>`);
};
