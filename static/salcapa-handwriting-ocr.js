/* Source-grounded handwriting and difficult-text review. */
let salcapaHandwritingOcrData={items:[],guidance:''};

function handwritingOcrRows(items){
  return table(['Source region','Prepared text','Review state','Action'],items.map(item=>[
    `<strong>${esc(item.source_title)}</strong><br><span class="subtle">x ${Number(item.region_x)}, y ${Number(item.region_y)}, ${Number(item.region_width)} × ${Number(item.region_height)} pixels · ${esc(item.segment_type)}</span>`,
    `<strong>${esc(item.original_text||'[Illegible segment]')}</strong><details><summary>Alternatives, uncertainty, and limits</summary><p>Alternatives: ${esc((item.alternatives||[]).join(' · ')||'None returned')}</p><p>${esc((item.uncertain_spans||[]).map(span=>`${span.start}–${span.end}: ${span.reason||'Uncertain reading'}`).join(' · ')||'No character-level uncertainty was returned; source comparison is still required.')}</p><p>${esc(item.limitations||'No processor-specific limitation was returned; source and context review remain necessary.')}</p><p>${esc(item.authority_note)}</p></details>`,
    `<strong>${esc(item.review_status)}</strong><br><span class="subtle">${esc(item.recognition_mode)} · ${esc(item.route)}</span>`,
    item.review_status==='Awaiting Human Review'&&(accessState?.permissions||[]).includes('decide')?`<button class="btn secondary" type="button" onclick="reviewHandwritingOcrSegment(${Number(item.id)})">Compare with original</button>`:esc(item.review_status)
  ]));
}

async function loadHandwritingOcrReview(){
  salcapaHandwritingOcrData=await api('/api/handwriting-ocr/triage');
  const processorStatus=await api('/api/handwriting-ocr/status');
  const anchor=$('#material-review-detail'); if(!anchor)return;
  const pending=salcapaHandwritingOcrData.items.filter(item=>item.review_status==='Awaiting Human Review').length;
  anchor.insertAdjacentHTML('beforebegin',`<section class="card visual-review-aids"><div class="section-title"><div><span>Source-grounded text review</span><h2>Handwriting and Difficult Text</h2><p>${esc(salcapaHandwritingOcrData.guidance)}</p></div><strong>${pending} awaiting review</strong></div><div class="notice"><strong>${processorStatus.available?'Local profile available':'Manual transcription remains available'}.</strong> ${esc(processorStatus.guidance)}</div>${handwritingOcrRows(salcapaHandwritingOcrData.items)}</section>`);
}

async function prepareHandwritingOcr(materialId,mode){
  const purpose=prompt(`Purpose for ${mode==='Printed text'?'extracting printed text':'reviewing handwriting or difficult text'}:`); if(!purpose)return;
  const region=prompt('Optional source region as x,y,width,height in original pixels. Targeted region review requires it. Leave blank for the full image:','');
  const body={purpose,mode};
  if(region&&region.trim()){
    const values=region.split(',').map(value=>Number(value.trim()));
    if(values.length!==4||values.some(value=>!Number.isInteger(value)||value<0)||values[2]<1||values[3]<1){alert('Enter x,y,width,height as four whole numbers.');return;}
    [body.region_x,body.region_y,body.region_width,body.region_height]=values;
  }
  await api(`/api/materials/${Number(materialId)}/handwriting-ocr-jobs`,{method:'POST',body:JSON.stringify(body)}); await salcapaMaterialReview();
}

async function reviewHandwritingOcrSegment(id){
  const status=prompt('Review outcome: Confirm Representation, Correct, Reject, or Needs More Information','Confirm Representation'); if(!status)return;
  const reason=prompt('Review basis. Record what you compared with the original and what remains uncertain:'); if(!reason)return;
  const body={status,reason};
  if(status==='Correct'){
    body.corrected_text=prompt('Corrected transcription. Enter [Illegible] rather than guessing when the marks do not support a reading:')||'';
    body.corrected_segment_type=prompt('Optional corrected type: printed, handwritten, mixed, mark, checkbox, field, table, unknown, or illegible:','')||'';
    if(!body.corrected_text&&!body.corrected_segment_type){alert('A correction needs corrected text or segment type.');return;}
  }
  body.limitations=prompt('Additional uncertainty, source condition, or context that should remain with this review:','')||'';
  await api(`/api/handwriting-ocr/segments/${Number(id)}/review`,{method:'POST',body:JSON.stringify(body)}); await salcapaMaterialReview();
}

async function recordManualTranscription(materialId){
  const purpose=prompt('Purpose for recording a manual transcription:'); if(!purpose)return;
  const transcription=prompt('Transcribe only the visible marks. Use [Illegible] rather than guessing:'); if(!transcription)return;
  const segment_type=prompt('Type: printed, handwritten, mixed, mark, checkbox, field, table, unknown, or illegible:','handwritten'); if(!segment_type)return;
  const limitations=prompt('Record uncertainty, source condition, or context that must remain with this transcription:'); if(!limitations)return;
  const region=prompt('Optional source region as x,y,width,height in original pixels. Leave blank for the full image:',''); const body={purpose,transcription,segment_type,limitations};
  if(region&&region.trim()){
    const values=region.split(',').map(value=>Number(value.trim()));
    if(values.length!==4||values.some(value=>!Number.isInteger(value)||value<0)||values[2]<1||values[3]<1){alert('Enter x,y,width,height as four whole numbers.');return;}
    [body.region_x,body.region_y,body.region_width,body.region_height]=values;
  }
  await api(`/api/materials/${Number(materialId)}/manual-transcriptions`,{method:'POST',body:JSON.stringify(body)}); await salcapaMaterialReview();
}

const salcapaMaterialReviewWithoutHandwritingOcr=salcapaMaterialReview;
salcapaMaterialReview=async function(){await salcapaMaterialReviewWithoutHandwritingOcr();if(!isProtectedMember())await loadHandwritingOcrReview();};

const openMaterialDerivativeWithoutHandwritingOcr=openMaterialDerivative;
openMaterialDerivative=async function(id){
  await openMaterialDerivativeWithoutHandwritingOcr(id); if(isProtectedMember())return;
  const item=await api(`/api/material-processing/derivatives/${Number(id)}`); if(!/\.(?:jpe?g|png)$/i.test(item.original_name||''))return;
  $('.material-review-detail').insertAdjacentHTML('beforeend',`<div class="form-actions"><button class="btn secondary" type="button" onclick="prepareHandwritingOcr(${Number(item.source_material_id)},'Printed text')">Extract printed text</button><button class="btn secondary" type="button" onclick="prepareHandwritingOcr(${Number(item.source_material_id)},'Handwritten text')">Review handwriting</button><button class="btn secondary" type="button" onclick="prepareHandwritingOcr(${Number(item.source_material_id)},'Mixed text')">Review mixed text</button><button class="btn secondary" type="button" onclick="prepareHandwritingOcr(${Number(item.source_material_id)},'Targeted region review')">Review selected region</button><button class="btn secondary" type="button" onclick="recordManualTranscription(${Number(item.source_material_id)})">Record manual transcription</button></div><p class="subtle">Prepared text remains derived and unverified. Compare it with the exact original marks before use. Recognition does not establish authorship, authenticity, identity, source truth, a finding, or disclosure authority.</p>`);
};
