/* Staff-only entry to the paid Level 1A report workflow. Server permissions,
 * paid-source checks and exact-version scanner gates remain authoritative. */
const LEVEL1A_STAFF_PRODUCTS=[
  ['SalINTEL','SalINTEL™','SalINTEL Report Template v1.0'],
  ['SalTHIRA','SalTHIRA™','SalTHIRA Report Template v1.0'],
  ['SalOPS','SalOPS™','SalOPS Report Template v2'],
  ['SalCAPA','SalCAPA™','SalCAPA Integrated Report Template v2']
];
const LEVEL1A_CONFORMANCE_CHECKS=[
  ['level_status_and_handoffs','Assessment level and product handoffs'],
  ['evidence_and_provenance','Evidence and provenance'],
  ['uncertainty_and_contradictions','Uncertainty and contrary evidence'],
  ['protected_member_isolation','Protected Member isolation'],
  ['confidentiality_and_audience','Confidentiality and intended audience'],
  ['approved_title_and_brand','Approved title and Salus names'],
  ['arial_headings_times_body','Arial headings and Times body'],
  ['cover_blank_second_page_page_x_of_y','Cover, blank second page, and page count'],
  ['accessibility','Accessibility'],
  ['all_rendered_pages','Every rendered page'],
  ['docx_pdf_print_parity','Word, PDF, and print consistency'],
  ['method_and_template_version','Exact method and template versions'],
  ['qualified_review_and_release_authority','Qualified review and issue authority']
];
const LEVEL1A_PAGE_CHECKS=[
  ['all_pages','Every page inspected at full size'],
  ['native_word','Native Word file checked'],
  ['accessibility','Accessibility checked'],
  ['format_parity','Word, PDF, and print consistency checked'],
  ['member_isolation','Protected Member isolation checked']
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
    const canDecide=['System Administrator','Assessment Director'].includes(currentRole);
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
      const conformanceText=report?`<p><strong>Charter conformance:</strong> ${current.conformance?esc(current.conformance.status):'not recorded'}</p>`:'';
      const reviewText=report?`<p><strong>Human page review:</strong> ${current.review?`${esc(current.review.decision)} · ${esc(current.review.review_mode)}`:'not recorded'}</p>`:'';
      const matrixForm=canDecide&&report?.status==='Draft'&&current.qa_evidence
        ? `<details><summary>Record exact report Charter checks</summary>
          <form class="level1a-staff-matrix" data-report-id="${Number(report.id)}" data-report-sha="${esc(report.content_sha256)}">
          <p>Each item needs an observed result and a specific reason. Pending or not applicable items keep issue closed.</p>
          ${LEVEL1A_CONFORMANCE_CHECKS.map(([id,text])=>`<fieldset data-check="${id}"><legend>${esc(text)}</legend>
            <label>Result<select name="status" required><option value="Pending">Pending</option><option value="Met">Met</option><option value="Not applicable">Not applicable</option></select></label>
            <label>Specific reason<input name="reason" required minlength="8" maxlength="2000"></label></fieldset>`).join('')}
          <label>Overall review summary<textarea name="summary" required minlength="20" maxlength="4000"></textarea></label>
          <button class="btn" type="submit">Record Charter checks for this Word version</button></form></details>`:'';
      const humanReview=canDecide&&report?.status==='Draft'&&current.qa_evidence
        ? `<details><summary>Marc's exact page-review decision</summary>
          <form class="level1a-staff-review" data-report-id="${Number(report.id)}" data-evidence-id="${Number(current.qa_evidence.id)}">
          <p>Only the named human reviewer may complete this after inspecting the exact Word and PDF pages. ChatGPT assistance is not independent human review. Single-operator review requires the protected staff identity and order setting.</p>
          <label>Review mode<select name="review_mode" required><option value="">Choose mode</option><option value="Single-operator">Single-operator</option><option value="Independent">Independent human reviewer</option></select></label>
          <label>Decision<select name="decision" required><option value="">Choose decision</option><option value="Returned">Returned for changes</option><option value="Reviewed">Reviewed</option></select></label>
          ${LEVEL1A_PAGE_CHECKS.map(([id,text])=>`<label><input type="checkbox" name="${id}"> ${esc(text)}</label>`).join('')}
          <label>Qualification basis<textarea name="qualification_basis" required minlength="20" maxlength="2000"></textarea></label>
          <label>Review note<textarea name="review_note" required minlength="20" maxlength="4000" placeholder="For single-operator review, explicitly state single-operator and the source limits."></textarea></label>
          <button class="btn" type="submit">Record human review decision</button></form></details>`:'';
      return `<section class="card"><h3>${label}</h3><p class="subtle">Controlled template: ${esc(template)}</p>${reportText}${scanText}${held}${qaText}${qaHeld}${conformanceText}${reviewText}<div class="row-actions">${finalButton}${qaFinalize}<button class="btn secondary" type="button" data-refresh-staff>Check file status</button></div>${upload}${qaForm}${matrixForm}${humanReview}</section>`;
    }).join('');
    const blockers=(readiness.blockers||[]).map(item=>`<li>${esc(item)}</li>`).join('');
    const canReconcile=canDecide&&LEVEL1A_STAFF_PRODUCTS.every(([key])=>
      workspace.products[key]?.report?.status==='Draft');
    const reconcileForm=canReconcile?`<details><summary>Compare SalCAPA with the three exact source reports</summary>
      <form id="level1a-staff-reconcile">
        <p>For each product, compare the current Word version with SalCAPA. Unresolved differences keep issue closed.</p>
        ${LEVEL1A_STAFF_PRODUCTS.filter(([key])=>key!=='SalCAPA').map(([key,label])=>{
          const source=workspace.products[key].report;
          return `<fieldset data-source="${key}"><legend>${label} · version ${Number(source.version_no)} · SHA-256 <code>${esc(source.content_sha256)}</code></legend>
            <label>Alignment<select name="alignment" required><option value="Unresolved">Unresolved</option><option value="Aligned">Aligned</option><option value="Qualified difference">Qualified difference</option></select></label>
            <label>Evidence and explanation<textarea name="explanation" required minlength="20" maxlength="2000"></textarea></label></fieldset>`;
        }).join('')}
        <label>Comparison summary<textarea name="summary" required minlength="20" maxlength="4000"></textarea></label>
        <button class="btn" type="submit">Record source comparison</button>
      </form></details>`:'';
    const comparisonText=workspace.reconciliation
      ? `Latest four-report comparison: ${esc(workspace.reconciliation.status)} · record SHA-256 <code>${esc(workspace.reconciliation.record_sha256)}</code>`
      : 'No four-report source comparison has been recorded.';
    const issueForm=canDecide&&readiness.blockers?.length===0
      ? `<details><summary>Marc's separate report issue decision</summary>
        <form id="level1a-staff-issue">
          <p>The exact four Word versions below passed the automated checks. Marc must still confirm substantive qualification and personally authorize release to the named paid buyer. This action issues all four reports.</p>
          <ul>${LEVEL1A_STAFF_PRODUCTS.map(([key,label])=>{
            const report=workspace.products[key].report;
            return `<li>${label}: version ${Number(report.version_no)} · SHA-256 <code>${esc(report.content_sha256)}</code></li>`;
          }).join('')}</ul>
          <p>Recipient is the paid buyer account on order L1A-${Number(workspace.order_id)}.</p>
          <label>Human issue basis<textarea name="issue_basis" required minlength="40" maxlength="4000"></textarea></label>
          <label><input type="checkbox" name="confirm" required> I have reviewed these exact reports and authorize issue to the named buyer.</label>
          <button class="btn" type="submit">Issue these four exact reports</button>
        </form></details>`:'';
    const issuedText=workspace.issue
      ? `<p><strong>Latest issued packet:</strong> ${Number(workspace.issue.id)} · SHA-256 <code>${esc(workspace.issue.record_sha256)}</code>. A qualified successor requires four new exact draft versions and a separate issue decision. Named buyer delivery and acknowledgment still require verification.</p>`:'';
    $('#content').innerHTML=`
      <div class="card cop-hero"><span>Salus staff · Level 1A Assessment</span><h2>Prepare the four controlled reports</h2>
        <p>Use the existing paid order. Stage each exact Word file for private screening, then register only a cleared version. Drafts remain staff-only; a separate human issue decision is required.</p></div>
      ${selector}
      <div class="notice"><strong>Paid source verified:</strong> order L1A-${Number(workspace.order_id)} · assessment ${Number(workspace.assessment_id)} · source SHA-256 <code>${esc(workspace.source_record_sha256)}</code></div>
      <p id="level1a-staff-message" role="status" aria-live="polite"></p>
      <div class="grid two-col">${cards}</div>
      <section class="card"><h2>Release checks</h2>
        <p>${esc(readiness.status)}. A source, draft, scan result, or completed checklist alone does not issue a report.</p>
        ${blockers?`<ul>${blockers}</ul>`:'<p>No automated blockers are listed. Marc must still inspect exact rendered pages and make the separate human issue decision.</p>'}
        <p>${comparisonText}</p>${reconcileForm}${issuedText}${issueForm}
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
  document.querySelectorAll('.level1a-staff-matrix').forEach(form=>form.onsubmit=async event=>{
    event.preventDefault();
    const message=$('#level1a-staff-message'),button=form.querySelector('button[type="submit"]');
    const checks={};
    LEVEL1A_CONFORMANCE_CHECKS.forEach(([id])=>{
      const group=form.querySelector(`[data-check="${id}"]`);
      checks[id]={status:group.querySelector('[name="status"]').value,
        reason:group.querySelector('[name="reason"]').value.trim()};
    });
    button.disabled=true;
    try{
      const result=await api(`/api/level1a-reports/${Number(form.dataset.reportId)}/conformance`,
        {method:'POST',body:JSON.stringify({content_sha256:form.dataset.reportSha,
          checks,summary:form.querySelector('[name="summary"]').value.trim()})});
      await level1aStaffView();
      $('#level1a-staff-message').textContent=`Charter checks recorded as ${result.status}. This did not issue a report.`;
    }catch(exc){message.textContent=`Charter checks were not recorded: ${exc.message}`;button.disabled=false;}
  });
  document.querySelectorAll('.level1a-staff-review').forEach(form=>form.onsubmit=async event=>{
    event.preventDefault();
    const message=$('#level1a-staff-message'),button=form.querySelector('button[type="submit"]');
    const checks=Object.fromEntries(LEVEL1A_PAGE_CHECKS.map(([id])=>
      [id,form.querySelector(`[name="${id}"]`).checked]));
    const payload={evidence_id:Number(form.dataset.evidenceId),
      decision:form.querySelector('[name="decision"]').value,
      review_mode:form.querySelector('[name="review_mode"]').value,
      checks,qualification_basis:form.querySelector('[name="qualification_basis"]').value.trim(),
      review_note:form.querySelector('[name="review_note"]').value.trim()};
    button.disabled=true;
    try{
      const result=await api(`/api/level1a-reports/${Number(form.dataset.reportId)}/qa-reviews`,
        {method:'POST',body:JSON.stringify(payload)});
      await level1aStaffView();
      $('#level1a-staff-message').textContent=`Human review recorded as ${result.decision}. This did not issue a report.`;
    }catch(exc){message.textContent=`Human review was not recorded: ${exc.message}`;button.disabled=false;}
  });
  const reconcile=$('#level1a-staff-reconcile');
  if(reconcile) reconcile.onsubmit=async event=>{
    event.preventDefault();
    const message=$('#level1a-staff-message'),button=reconcile.querySelector('button[type="submit"]');
    const sources={};
    LEVEL1A_STAFF_PRODUCTS.filter(([key])=>key!=='SalCAPA').forEach(([key])=>{
      const report=workspace.products[key].report,group=reconcile.querySelector(`[data-source="${key}"]`);
      sources[key]={report_id:Number(report.id),content_sha256:report.content_sha256,
        alignment:group.querySelector('[name="alignment"]').value,
        explanation:group.querySelector('[name="explanation"]').value.trim()};
    });
    const payload={salcapa_sha256:workspace.products.SalCAPA.report.content_sha256,
      sources,summary:reconcile.querySelector('[name="summary"]').value.trim()};
    button.disabled=true;
    try{
      const result=await api(`/api/level1a-reports/${Number(workspace.products.SalCAPA.report.id)}/source-reconciliation`,
        {method:'POST',body:JSON.stringify(payload)});
      await level1aStaffView();
      $('#level1a-staff-message').textContent=`Source comparison recorded as ${result.status}. This did not issue a report.`;
    }catch(exc){message.textContent=`Source comparison was not recorded: ${exc.message}`;button.disabled=false;}
  };
  const issue=$('#level1a-staff-issue');
  if(issue) issue.onsubmit=async event=>{
    event.preventDefault();
    const message=$('#level1a-staff-message'),button=issue.querySelector('button[type="submit"]');
    if(!issue.querySelector('[name="confirm"]').checked) return;
    const reportIds=Object.fromEntries(LEVEL1A_STAFF_PRODUCTS.map(([key])=>
      [key,Number(workspace.products[key].report.id)]));
    button.disabled=true;
    try{
      const result=await api(`/api/assessments/${Number(workspace.assessment_id)}/level1a-report-issues`,
        {method:'POST',body:JSON.stringify({report_ids:reportIds,
          recipient_user_id:Number(workspace.buyer_user_id),
          issue_basis:issue.querySelector('[name="issue_basis"]').value.trim(),
          confirm_qualified_release:true})});
      await level1aStaffView();
      $('#level1a-staff-message').textContent=`Four-report packet ${result.id} issued to the named buyer. Delivery and acknowledgment remain to verify.`;
    }catch(exc){message.textContent=`Reports were not issued: ${exc.message}`;button.disabled=false;}
  };
}
