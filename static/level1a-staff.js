/* Staff-only entry to the paid Level 1A report workflow. Server permissions,
 * paid-source checks and exact-version scanner gates remain authoritative. */
const LEVEL1A_STAFF_PRODUCTS=[
  ['SalINTEL','SalINTEL™','SalINTEL Report Template v1.0'],
  ['SalTHIRA','SalTHIRA™','SalTHIRA Report Template v1.0'],
  ['SalOPS','SalOPS™','SalOPS Report Template v2'],
  ['SalCAPA','SalCAPA™','SalCAPA Integrated Report Template v2']
];

async function level1aStaffMultipart(url,body){
  const response=await fetch(url,{method:'POST',headers:authHeaders(),body});
  if(!response.ok) throw new Error(await response.text());
  return response.json();
}

async function level1aStaffView(){
  if(isProtectedMember()||!['System Administrator','Assessment Director','Lead Assessor'].includes(currentRole)){
    $('#content').innerHTML='<div class="notice">This report workspace is limited to assigned Salus staff.</div>';
    return;
  }
  const assessments=await api('/api/assessments');
  if(!assessments.length){
    $('#content').innerHTML='<div class="notice">No assessment is available to this staff account.</div>';
    return;
  }
  let selected=assessments.find(item=>item.id===activeAssessmentId);
  if(!selected){selected=assessments[0];activeAssessmentId=selected.id;}
  let workspace,readiness,error;
  try{
    [workspace,readiness]=await Promise.all([
      api(`/api/assessments/${selected.id}/level1a-report-workspace`),
      api(`/api/assessments/${selected.id}/level1a-report-readiness`)
    ]);
  }catch(exc){error=exc;}
  const choices=assessments.map(item=>
    `<option value="${Number(item.id)}" ${item.id===selected.id?'selected':''}>${esc(item.name||'Assessment')} · ${Number(item.id)}</option>`
  ).join('');
  const selector=`<div class="card"><label>Assessment
    <select id="level1a-staff-assessment">${choices}</select></label>
    <p class="subtle">Select the assessment linked to the already paid Level 1A order. A source check runs before any report file can be staged.</p>
  </div>`;
  if(error){
    $('#content').innerHTML=`${selector}<div class="notice" role="status">The selected assessment does not have a verified paid Level 1A report source available to this staff account. ${esc(error.message)}</div>`;
  }else{
    const cards=LEVEL1A_STAFF_PRODUCTS.map(([key,label,template])=>{
      const current=workspace.products[key]||{};
      const report=current.report,scan=current.draft_scan;
      const archiveScan=current.qa_archive_scan,pdfScan=current.qa_pdf_scan;
      const reportText=report
        ? `<p><strong>Current Word draft:</strong> version ${Number(report.version_no)} · ${esc(report.status)} · SHA-256 <code>${esc(report.content_sha256)}</code></p>`
        : '<p>No current Word draft has been registered.</p>';
      const scanText=scan
        ? `<p><strong>Latest file screening:</strong> ${esc(scan.status)} · SHA-256 <code>${esc(scan.content_sha256)}</code></p>`
        : '<p>No draft file is waiting for screening.</p>';
      const finalButton=scan?.status==='Cleared'
        ? `<button class="btn" type="button" data-finalize-scan="${Number(scan.id)}">Register cleared Word draft</button>`:'';
      const held=scan&&['Malicious','Held','Error','Mismatch'].includes(scan.status)
        ? '<p class="notice">This file remains held. Investigate its exact scan result before submitting a corrected version.</p>':'';
      const draftAwaiting=scan&&['Pending','Cleared'].includes(scan.status);
      const canStage=(!report||report.status==='Draft')&&!draftAwaiting;
      const upload=!canStage?'':`<form class="level1a-staff-draft" data-product="${key}">
        <label>Exact controlled method version<input name="method_version" required maxlength="120" autocomplete="off"></label>
        <label>Exact approved template version<input name="template_version" required maxlength="120" autocomplete="off" placeholder="${esc(template)}"></label>
        <label>Working Word draft (.docx)<input name="file" type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required></label>
        <div class="form-actions"><button class="btn" type="submit">${report?'Stage revised Word draft':'Stage Word draft'} for screening</button></div>
      </form>`;
      const qaText=report ? `<p><strong>Page-review evidence:</strong> ${current.qa_evidence
        ? `registered · archive SHA-256 <code>${esc(current.qa_evidence.archive_sha256)}</code>`
        : `not registered${archiveScan?` · archive ${esc(archiveScan.status)}`:''}${pdfScan?` · rendered PDF ${esc(pdfScan.status)}`:''}`}</p>`:'';
      const qaAwaiting=archiveScan&&['Pending','Cleared'].includes(archiveScan.status);
      const qaForm=report?.status==='Draft'&&!current.qa_evidence&&!qaAwaiting
        ? `<form class="level1a-staff-qa" data-report-id="${Number(report.id)}">
          <label>Exact page-review archive (.zip) with manifest and rendered PDF
          <input name="file" type="file" accept=".zip,application/zip" required></label>
          <button class="btn" type="submit">Stage page-review evidence for screening</button>
        </form>`:'';
      const qaFinalize=archiveScan?.status==='Cleared'&&pdfScan?.status==='Cleared'
        ? `<button class="btn" type="button" data-finalize-qa="${Number(archiveScan.id)}" data-report-id="${Number(report.id)}">Register cleared page evidence</button>`:'';
      const qaHeld=[archiveScan,pdfScan].some(item=>item&&['Malicious','Held','Error','Mismatch'].includes(item.status))
        ? '<p class="notice">Page evidence remains held. Investigate the exact scan result before submitting a corrected archive.</p>':'';
      return `<section class="card"><h3>${label}</h3><p class="subtle">Controlled template: ${esc(template)}</p>${reportText}${scanText}${held}${qaText}${qaHeld}<div class="row-actions">${finalButton}${qaFinalize}<button class="btn secondary" type="button" data-refresh-staff>Check file status</button></div>${upload}${qaForm}</section>`;
    }).join('');
    const blockers=(readiness.blockers||[]).map(item=>`<li>${esc(item)}</li>`).join('');
    $('#content').innerHTML=`
      <div class="card cop-hero"><span>Salus staff · Level 1A Assessment</span><h2>Prepare the four controlled reports</h2>
        <p>Use the existing paid order. Stage each exact Word file for private screening, then register only a cleared version. Drafts remain staff-only; a separate human issue decision is required.</p></div>
      ${selector}
      <div class="notice"><strong>Paid source verified:</strong> order L1A-${Number(workspace.order_id)} · assessment ${Number(workspace.assessment_id)} · source SHA-256 <code>${esc(workspace.source_record_sha256)}</code></div>
      <p id="level1a-staff-message" role="status" aria-live="polite"></p>
      <div class="grid two-col">${cards}</div>
      <section class="card"><h2>Release checks</h2>
        <p>${esc(readiness.status)}. This screen does not approve or issue a report.</p>
        ${blockers?`<ul>${blockers}</ul>`:'<p>No automated blockers are listed. Marc must still inspect exact rendered pages and make the separate human issue decision.</p>'}
      </section>`;
  }
  const picker=$('#level1a-staff-assessment');
  picker.onchange=()=>{
    activeAssessmentId=Number(picker.value);
    localStorage.setItem('salus_assessment_id',String(activeAssessmentId));
    level1aStaffView();
  };
  document.querySelectorAll('[data-refresh-staff]').forEach(button=>button.onclick=()=>level1aStaffView());
  document.querySelectorAll('[data-finalize-scan]').forEach(button=>button.onclick=async()=>{
    const message=$('#level1a-staff-message');
    button.disabled=true;
    try{
      await api(`/api/level1a-report-scans/${Number(button.dataset.finalizeScan)}/finalize-draft`,{method:'POST'});
      await level1aStaffView();
    }catch(exc){message.textContent=`The cleared draft was not registered: ${exc.message}`;button.disabled=false;}
  });
  document.querySelectorAll('[data-finalize-qa]').forEach(button=>button.onclick=async()=>{
    const message=$('#level1a-staff-message');
    button.disabled=true;
    try{
      await api(`/api/level1a-reports/${Number(button.dataset.reportId)}/qa-scans/${Number(button.dataset.finalizeQa)}/finalize`,{method:'POST'});
      await level1aStaffView();
    }catch(exc){message.textContent=`The cleared page evidence was not registered: ${exc.message}`;button.disabled=false;}
  });
  document.querySelectorAll('.level1a-staff-draft').forEach(form=>form.onsubmit=async event=>{
    event.preventDefault();
    const message=$('#level1a-staff-message');
    const button=form.querySelector('button[type="submit"]');
    const body=new FormData(form);
    const product=form.dataset.product;
    button.disabled=true;
    try{
      const result=await level1aStaffMultipart(
        `/api/assessments/${selected.id}/level1a-reports/${product}/draft-scans`,body);
      await level1aStaffView();
      $('#level1a-staff-message').textContent=`${product} Word file is ${result.scan_status}. Register it only after an exact Clean result.`;
    }catch(exc){message.textContent=`The Word file was not staged: ${exc.message}`;button.disabled=false;}
  });
  document.querySelectorAll('.level1a-staff-qa').forEach(form=>form.onsubmit=async event=>{
    event.preventDefault();
    const message=$('#level1a-staff-message');
    const button=form.querySelector('button[type="submit"]');
    const reportId=Number(form.dataset.reportId);
    button.disabled=true;
    try{
      await level1aStaffMultipart(`/api/level1a-reports/${reportId}/qa-scans`,new FormData(form));
      await level1aStaffView();
      $('#level1a-staff-message').textContent='Page-review evidence is held pending exact archive and PDF screening.';
    }catch(exc){message.textContent=`Page-review evidence was not staged: ${exc.message}`;button.disabled=false;}
  });
}
