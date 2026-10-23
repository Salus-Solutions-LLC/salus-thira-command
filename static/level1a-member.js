/* Signed-in Level 1A buyer path. The server remains the authority for every step. */
const level1aStorageKey='salus_level1a_current_order';
function level1aState(){try{return JSON.parse(sessionStorage.getItem(level1aStorageKey)||'{}')}catch{return {}}}
function saveLevel1aState(value){sessionStorage.setItem(level1aStorageKey,JSON.stringify(value))}
function level1aStatus(message){const node=document.querySelector('#level1a-status');if(node)node.textContent=message}
function level1aError(){level1aStatus('This step could not be completed. No new payment or file access was granted. Check the details or contact Salus.')}

async function level1aView(){
  const host=$('#content');
  $('#page-title').textContent='Level 1A Assessment';
  $('#page-subtitle').textContent=systemMode.level1a_checkout_available?'One defined site or function · fixed $1,500 assessment · secure online purchase':'Protected review of one defined site or function · no payment today';
  if(!isProtectedMember()||!(systemMode.level1a_draft_available||systemMode.level1a_purchase_available)){
    host.innerHTML='<div class="notice">Level 1A online purchase is not available yet.</div>';
    return;
  }
  const saved=level1aState();
  host.innerHTML='<div class="card"><h2>Level 1A Assessment</h2><p>For one defined site or function. The $1,500 assessment includes a baseline review, benchmark, priorities and decision support. Additional sites, investigations and SalOPS services have separate scope and prices.</p><p id="level1a-status" role="status" aria-live="polite"></p></div><div id="level1a-step"></div>';
  try{
    const recovered=await api('/api/level1a/orders/recoverable');
    const orders=recovered.orders||[];
    const current=orders.find(order=>Number(order.order_id)===Number(saved.order_id));
    if(orders.length===1||current){
      const order=current||orders[0];
      const state={order_id:order.order_id,scope_sha256:order.scope_sha256,accepted:true};
      saveLevel1aState(state);return level1aPayment(state);
    }
    if(orders.length>1){
      const step=document.querySelector('#level1a-step');
      step.innerHTML='<div class="card"><h2>Continue a paid assessment</h2><p>Choose the assessment you already paid for. No new payment is needed.</p><div id="level1a-recovered-orders"></div></div>';
      const choices=step.querySelector('#level1a-recovered-orders');
      orders.forEach(order=>{
        const button=document.createElement('button');button.type='button';button.className='btn secondary';
        button.textContent=`L1A-${Number(order.order_id)} · ${order.unit_name}`;
        button.onclick=()=>{const state={order_id:order.order_id,scope_sha256:order.scope_sha256,accepted:true};saveLevel1aState(state);level1aPayment(state)};
        choices.appendChild(button);
      });
      return;
    }
  }catch{
    document.querySelector('#level1a-step').innerHTML='<div class="notice"><h2>We could not check your existing orders</h2><p>Please try again before starting a new order or payment.</p><button class="btn secondary" id="level1a-recover-retry">Try again</button></div>';
    document.querySelector('#level1a-recover-retry').onclick=()=>level1aView();
    return;
  }
  if(saved.order_id){
    try{
      const order=await api(`/api/level1a/orders/${Number(saved.order_id)}`);
      if(order.scope_sha256!==saved.scope_sha256){saveLevel1aState({});return level1aView()}
      if(saved.accepted)return level1aPayment(saved);
      if(saved.agreement)return level1aAgreement(saved);
      if(saved.quote)return level1aQuote(saved);
      try{
        const quote=await api(`/api/level1a/orders/${Number(saved.order_id)}/quote`,{method:'POST'});
        saved.quote=quote;saveLevel1aState(saved);return level1aQuote(saved);
      }catch{
        document.querySelector('#level1a-step').innerHTML=`<div class="notice"><h2>Your order is saved</h2><p>Order L1A-${Number(saved.order_id)} could not be priced yet. No payment was taken. A verified tax decision for the service-use location is required. <button class="btn secondary" id="level1a-quote-retry">Check again</button></p></div>`;
        document.querySelector('#level1a-quote-retry').onclick=()=>level1aView();
        return;
      }
    }catch{saveLevel1aState({});return level1aView()}
  }
  level1aStart();
}

function level1aStart(){
  const host=document.querySelector('#level1a-step');
  host.innerHTML=`<div class="card"><h2>Define the covered unit</h2><p>Choose one site or one function. Name its boundary and exclusions so the fixed price stays clear. Enter the U.S. state where you will use the assessment. Salus conducts Level 1A assessments remotely for clients in every U.S. state, and the approved buyer total is $1,500.</p><form id="level1a-order-form">
    <label>Organization legal name<input name="buyer_legal_name" required maxlength="500"></label>
    <label>Covered unit type<select name="unit_kind" required><option value="">Select one</option><option value="Site">One site</option><option value="Function">One function</option></select></label>
    <label>Site or function name<input name="unit_name" required maxlength="500"></label>
    <label>Covered boundary<input name="covered_boundary" required maxlength="500"></label>
    <label>Operating activity<input name="operating_activity" required maxlength="500"></label>
    <label>Work excluded from this assessment<input name="exclusions" aria-label="Work excluded from this assessment" required maxlength="500"></label>
    <label>Decision owner role<input name="decision_owner_role" required maxlength="500"></label>
    <label>Notice email<input name="notice_email" type="email" required maxlength="254"></label>
    <label>Where will the service be used?<input name="service_use_address" required maxlength="500" autocomplete="street-address"></label>
    <label>Postal code<input name="service_use_postal_code" required maxlength="30" autocomplete="postal-code"></label>
    <label>State where the service will be used<input name="use_region" required minlength="2" maxlength="2" pattern="[A-Za-z]{2}" autocomplete="address-level1"></label>
    <input name="use_country" type="hidden" value="US">
    <div class="form-actions"><button class="btn" type="submit">Review exact scope and price</button></div>
  </form></div>`;
  host.querySelector('form').onsubmit=async event=>{
    event.preventDefault();const form=event.currentTarget,button=form.querySelector('button');
    if(!form.reportValidity())return;
    button.disabled=true;level1aStatus('Checking your scope and price…');
    try{
      const values=Object.fromEntries(new FormData(form).entries());
      values.use_country=values.use_country.toUpperCase();
      values.idempotency_key=crypto.randomUUID().replace(/-/g,'');
      const order=await api('/api/level1a/orders',{method:'POST',body:JSON.stringify(values)});
      const state={order_id:order.order_id,scope_sha256:order.scope_sha256};
      saveLevel1aState(state);
      const quote=await api(`/api/level1a/orders/${order.order_id}/quote`,{method:'POST'});
      state.quote=quote;saveLevel1aState(state);level1aQuote(state);
    }catch{level1aError();button.disabled=false}
  };
}

function level1aQuote(state){
  level1aStatus('');
  const quote=state.quote,host=document.querySelector('#level1a-step');
  if(!quote){level1aStart();return}
  if(quote.tax_rule_id!=='REMOTE-LEVEL1A-US-V1'||quote.tax_decision_reference!=='SAL-D107'){
    host.innerHTML='<div class="notice"><h2>Start a current remote assessment offer</h2><p>This earlier quote predates the corrected remote-assessment terms. It will remain on record, but cannot be used for a new agreement. Start a new scope and price review; no payment has been taken.</p><button class="btn" id="level1a-start-current-offer">Start a new offer</button></div>';
    host.querySelector('#level1a-start-current-offer').onclick=()=>{saveLevel1aState({});level1aView()};
    return;
  }
  const total=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(quote.total_cents)/100);
  const tax=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(quote.tax_cents)/100);
  host.innerHTML=`<div class="card"><h2>Review the exact offer</h2><p><strong>Level 1A Assessment:</strong> $1,500.00<br><strong>Tax:</strong> ${esc(tax)}<br><strong>Total before checkout:</strong> ${esc(total)}</p><p>The agreement will state your named unit, boundary, exclusions and what Salus delivers. Read the exact Word agreement before approving it.</p><form id="level1a-issue-form"><label>Your full name for the agreement<input name="signer_name" required minlength="2" maxlength="200"></label><div class="form-actions"><button class="btn">Prepare my agreement</button></div></form></div>`;
  host.querySelector('form').onsubmit=async event=>{
    event.preventDefault();const form=event.currentTarget,button=form.querySelector('button');
    if(!form.reportValidity())return;
    button.disabled=true;level1aStatus('Preparing your agreement…');
    try{
      const signer_name=new FormData(form).get('signer_name');
      const agreement=await api(`/api/level1a/orders/${Number(state.order_id)}/agreements/issue`,{method:'POST',body:JSON.stringify({quote_id:quote.quote_id,signer_name})});
      state.agreement=agreement;saveLevel1aState(state);level1aAgreement(state);
    }catch{level1aError();button.disabled=false}
  };
}

function level1aAgreement(state){
  level1aStatus('');
  const host=document.querySelector('#level1a-step'),id=Number(state.order_id),agreement=state.agreement;
  host.innerHTML=`<div class="card"><h2>Read and approve your agreement</h2><p>Download the exact Word agreement. It identifies the covered unit, included work, exclusions and total. Your approval is recorded electronically.</p><p><a class="btn secondary" href="/api/level1a/orders/${id}/agreements/${Number(agreement.agreement_id)}/download" target="_blank" rel="noopener">Download the Level 1A agreement</a></p><form id="level1a-accept-form"><label>Your full name<input name="typed_name" required minlength="2" maxlength="200"></label><label>How are you authorized to agree for this organization?<textarea name="authority_basis" required minlength="12" maxlength="1000"></textarea></label><label class="advisor-confirm"><input name="accept_quote_and_agreement" type="checkbox" required> I read the exact agreement and quote, approve them for the organization, and agree to use this electronic record.</label><div class="form-actions"><button class="btn">Approve agreement</button></div></form></div>`;
  const key=crypto.randomUUID().replace(/-/g,'');
  host.querySelector('form').onsubmit=async event=>{
    event.preventDefault();const form=event.currentTarget,button=form.querySelector('button');
    if(!form.reportValidity())return;
    button.disabled=true;level1aStatus('Recording your approval…');
    try{
      const values=Object.fromEntries(new FormData(form).entries());
      await api(`/api/level1a/orders/${id}/accept`,{method:'POST',body:JSON.stringify({quote_id:state.quote.quote_id,agreement_id:agreement.agreement_id,agreement_sha256:agreement.agreement_sha256,typed_name:values.typed_name,authority_basis:values.authority_basis,idempotency_key:key,accept_quote_and_agreement:true})});
      state.accepted=true;saveLevel1aState(state);level1aPayment(state);
    }catch{level1aError();button.disabled=false}
  };
}

async function level1aPayment(state){
  const id=Number(state.order_id),host=document.querySelector('#level1a-step');
  let payment;
  try{payment=await api(`/api/level1a/orders/${id}/checkout`)}catch{level1aError();return}
  if(payment.status==='Paid'){
    const intakeReady=Boolean(systemMode.level1a_purchase_available);
    const testMode=payment.test_mode===true;
    host.innerHTML=`<div class="card"><h2>${testMode?'Sandbox test payment verified':'Payment verified'}</h2><p>${testMode?'This was a Stripe sandbox transaction; no live funds were collected.':'Your Level 1A Assessment payment is recorded for this exact order.'} Your receipt is available below.</p><p><a href="/api/level1a/orders/${id}/receipt" target="_blank" rel="noopener">View or print your confidential receipt</a></p>${intakeReady?'<button class="btn" type="button" id="level1a-open-intake">Open my records request</button>':'<p class="notice">The records request is not open yet. Your receipt remains available while Salus completes acceptance.</p>'}</div>`;
    if(intakeReady)host.querySelector('#level1a-open-intake').onclick=async event=>{event.currentTarget.disabled=true;try{await api(`/api/level1a/orders/${id}/intake/open`,{method:'POST'});level1aIntake(state)}catch{level1aError();event.currentTarget.disabled=false}};
    try{
      const issued=await api(`/api/level1a/orders/${id}/reports`);
      const latest=(issued.issues||[]).at(-1);
      if(latest){
        const section=document.createElement('section');section.className='card';
        const products=['SalINTEL','SalTHIRA','SalOPS','SalCAPA'];
        section.innerHTML=`<h2>Your reviewed Level 1A reports</h2><p>Salus has issued four reviewed reports for this paid assessment. Download each report and review its scope and limitations.</p><ul>${products.map(product=>`<li>${product}: <a href="/api/level1a-report-issues/${Number(latest.id)}/reports/${product}.pdf" target="_blank" rel="noopener">Read PDF</a> · <a href="/api/level1a-report-issues/${Number(latest.id)}/reports/${product}.docx" target="_blank" rel="noopener">Download Word</a></li>`).join('')}</ul>${latest.acknowledged_at?'<p>Receipt acknowledged.</p>':'<form id="level1a-report-ack"><label><input type="checkbox" required> I received all four reports.</label><label><input type="checkbox" required> I reviewed the reports’ scope and limitations.</label><label>Receipt note<textarea name="acknowledgment_note" required minlength="20" maxlength="1000"></textarea></label><button class="btn" type="submit">Acknowledge report receipt</button></form>'}`;
        host.appendChild(section);
        const form=section.querySelector('#level1a-report-ack');
        if(form)form.onsubmit=async event=>{event.preventDefault();if(!form.reportValidity())return;const button=form.querySelector('button');button.disabled=true;try{await api(`/api/level1a-report-issues/${Number(latest.id)}/acknowledgment`,{method:'POST',body:JSON.stringify({issue_sha256:latest.record_sha256,confirm_received:true,confirm_reviewed_limitations:true,acknowledgment_note:new FormData(form).get('acknowledgment_note'),idempotency_key:crypto.randomUUID().replace(/-/g,'')})});await level1aPayment(state)}catch{level1aStatus('Download all four exact reports before acknowledging receipt.');button.disabled=false}};
      }
    }catch{level1aStatus('Your payment is verified. Report status is temporarily unavailable; please try again later.');}
    return;
  }
  if(!['Not started','Pending','Expired'].includes(payment.status)){
    host.innerHTML='<div class="notice"><h2>Payment needs review</h2><p>No records request is open. Contact Salus with your order reference; do not start another payment.</p></div>';
    return;
  }
  if(!systemMode.level1a_checkout_available){
    host.innerHTML='<div class="notice"><h2>Agreement recorded</h2><p>This protected review has stopped before payment. Salus will contact you when checkout is ready. No payment or records request has been opened.</p></div>';
    return;
  }
  host.innerHTML='<div class="card"><h2>Secure payment</h2><p>Stripe handles the $1,500 Level 1A Assessment payment for your accepted agreement. The records request opens only after Salus verifies the exact payment.</p><button class="btn" id="level1a-checkout">Continue to secure checkout</button> <button class="btn secondary" id="level1a-refresh">Check payment status</button></div>';
  host.querySelector('#level1a-refresh').onclick=()=>level1aPayment(state);
  host.querySelector('#level1a-checkout').onclick=async event=>{
    event.currentTarget.disabled=true;level1aStatus('Preparing secure checkout…');
    try{
      const result=await api(`/api/level1a/orders/${id}/checkout`,{method:'POST'});
      if(result.status==='Paid'){level1aPayment(state);return}
      const destination=new URL(result.checkout_url);
      if(destination.protocol!=='https:'||destination.hostname!=='checkout.stripe.com')throw Error('Unexpected destination');
      window.location.assign(destination.href);
    }catch{level1aError();event.currentTarget.disabled=false}
  };
}

async function level1aIntake(state){
  const id=Number(state.order_id),host=document.querySelector('#level1a-step');
  let intake;try{intake=await api(`/api/level1a/orders/${id}/intake`)}catch{level1aError();return}
  host.innerHTML=`<div class="card"><h2>Your Level 1 records request</h2><p>${esc(intake.notice)}</p><p>For each requested item, choose whether you can provide it, do not hold it, do not know, or prefer to discuss it. An existing equivalent is welcome. Each requested item accepts up to five files, 25 MB each. Files stay held until the security scan clears the exact version.</p>${intake.pending_files.some(file=>file.status==='Pending')?'<button class="btn secondary" type="button" id="level1a-check-scan-status">Check file scan status</button>':''}${intake.disclosure_authority_recorded?'':`<form id="level1a-disclosure"><label>How are you authorized to share these records?<textarea name="authority_basis" required minlength="12" maxlength="1000"></textarea></label><label class="advisor-confirm"><input type="checkbox" required> I am authorized to disclose records for this named unit.</label><button class="btn">Confirm records authority</button></form>`}</div><div id="level1a-items"></div>`;
  const scanRefresh=host.querySelector('#level1a-check-scan-status');
  if(scanRefresh)scanRefresh.onclick=async event=>{const button=event.currentTarget;button.disabled=true;try{await level1aIntake(state)}finally{if(button.isConnected)button.disabled=false}};
  const authorityForm=host.querySelector('#level1a-disclosure');
  if(authorityForm)authorityForm.onsubmit=async event=>{event.preventDefault();const button=authorityForm.querySelector('button');if(!authorityForm.reportValidity())return;button.disabled=true;try{await api(`/api/level1a/orders/${id}/intake/disclosure-authority`,{method:'POST',body:JSON.stringify({authority_basis:new FormData(authorityForm).get('authority_basis'),confirm_authorized_disclosure:true})});level1aIntake(state)}catch{level1aError();button.disabled=false}};
  const itemHost=host.querySelector('#level1a-items');
  for(const item of intake.items){
    const section=document.createElement('section');section.className='card';
    const files=intake.files.filter(file=>Number(file.intake_request_id)===Number(item.id));
    const pending=intake.pending_files.filter(file=>Number(file.intake_request_id)===Number(item.id));
    section.innerHTML=`<h3>${esc(item.title)}</h3><p><strong>Why requested:</strong> ${esc(item.decision_use)}<br><strong>Accepted form:</strong> ${esc(item.requested_form)}<br><strong>Equivalent:</strong> ${esc(item.acceptable_equivalent)}</p><p>${files.map(file=>`<a href="/api/level1a/orders/${id}/intake/files/${Number(file.id)}/download">${esc(file.original_name)}</a> — cleared`).join('<br>')}${pending.map(file=>`${esc(file.original_name)} — ${esc(file.status)}`).join('<br>')}</p>${intake.upload_available&&item.status==='Requested'&&!files.length&&!pending.length?`<form data-item-id="${Number(item.id)}"><label>Send a requested file<input name="file" type="file" required accept=".pdf,.docx,.xlsx,.pptx,.csv,.txt,.png,.jpg,.jpeg,.webp,.tif,.tiff,.mp3,.m4a,.wav,.mp4,.mov"></label><button class="btn secondary">Send for security scan</button></form>`:''}`;
    itemHost.appendChild(section);
    if(!files.length&&!pending.length){
      const responseForm=document.createElement('form');
      responseForm.className='level1a-response-form';
      const label=document.createElement('label');label.textContent='Record availability';
      const select=document.createElement('select');select.name='status';
      for(const status of ['Requested','Not held','Not known','Prefer to discuss']){
        const option=document.createElement('option');option.value=status;option.textContent=status;
        option.selected=item.status===status;select.appendChild(option);
      }
      const save=document.createElement('button');save.className='btn secondary';save.textContent='Save response';
      label.appendChild(select);responseForm.append(label,save);section.appendChild(responseForm);
      responseForm.onsubmit=async event=>{
        event.preventDefault();save.disabled=true;
        try{await api('/api/level1a/orders/'+id+'/intake/'+Number(item.id)+'/response',
          {method:'PATCH',body:JSON.stringify({status:select.value})});await level1aIntake(state)}
        catch{level1aError();save.disabled=false}
      };
    }
    const form=section.querySelector('form[data-item-id]');
    if(form)form.onsubmit=async event=>{event.preventDefault();if(!form.reportValidity())return;const button=form.querySelector('button');button.disabled=true;const data=new FormData(form);try{const response=await fetch(`/api/level1a/orders/${id}/intake/${Number(item.id)}/files`,{method:'POST',headers:authHeaders(),body:data});if(!response.ok)throw Error('Upload failed');await level1aIntake(state)}catch{level1aError();button.disabled=false}};
  }
}
