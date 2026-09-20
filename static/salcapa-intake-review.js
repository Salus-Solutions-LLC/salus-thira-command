(() => {
  const REVIEW_LIMIT = 50;
  const EXECUTE_LIMIT = 25;
  const state = {items: [], selected: new Set(), decisions: new Map(), filter: 'Action required'};

  function esc(value){
    return String(value ?? '').replace(/[&<>\"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[ch]));
  }
  function isAdmin(){ return currentRole === 'System Administrator'; }
  function actionable(item){ return ['New','Changed','Missing'].includes(item.status); }
  function announce(message, kind=''){
    const node=document.getElementById('m365-review-status');
    if(node){ node.className='m365-review-status '+kind; node.textContent=message; }
  }
  function request(path, options={}){
    return api(path, {headers:{'Content-Type':'application/json'}, ...options});
  }
  function ensureLaunch(){
    const existing=document.getElementById('m365-intake-review-launch');
    if(!isAdmin()){ if(existing) existing.remove(); return; }
    if(existing) return;
    const actions=document.querySelector('.intake-topbar-actions') || document.querySelector('.topbar');
    if(!actions) return;
    const button=document.createElement('button');
    button.id='m365-intake-review-launch'; button.type='button'; button.className='btn secondary';
    button.textContent='Review Intake'; button.addEventListener('click', open);
    actions.insertBefore(button, actions.firstChild);
  }
  function markup(){
    return `<div class="m365-review-backdrop" data-review-close></div>
      <section class="m365-review-dialog" role="dialog" aria-modal="true" aria-labelledby="m365-review-title">
        <header><div><span class="m365-review-eyebrow">MICROSOFT 365 · GOVERNED INTAKE</span><h2 id="m365-review-title">Intake Review</h2><p>Review the authorized folder and every nested folder. Nothing is captured, reprocessed, indexed, or routed without an explicit authorized action.</p></div><button class="m365-review-close" type="button" aria-label="Close Intake Review" data-review-close>×</button></header>
        <div class="m365-review-toolbar">
          <button class="btn" id="m365-reconcile" type="button">Refresh source inventory</button>
          <label>Status <select id="m365-review-filter"><option>Action required</option><option>All</option><option>New</option><option>Changed</option><option>Missing</option><option>Unchanged</option><option>Approved</option><option>Deferred</option><option>Dismissed</option></select></label>
          <span id="m365-review-counts" class="m365-review-counts"></span>
        </div>
        <div class="m365-review-notice"><strong>Human authorization remains required.</strong> Missing sources fail closed. Changed sources receive a new immutable version. Successful capture still requires separate human review before SalINTEL indexing or SalTHIRA evidence routing.</div>
        <div class="m365-review-table-wrap"><table><thead><tr><th><input id="m365-select-visible" type="checkbox" aria-label="Select visible items"></th><th>Source</th><th>Status</th><th>Review</th><th>Version / modified</th></tr></thead><tbody id="m365-review-rows"><tr><td colspan="5">Refresh the source inventory to begin.</td></tr></tbody></table></div>
        <section class="m365-review-actions" aria-label="Selected-item actions">
          <strong><span id="m365-selected-count">0</span> selected</strong>
          <label>Reason <input id="m365-review-reason" maxlength="4000" placeholder="Document the review or capture authority basis"></label>
          <div><button type="button" class="btn secondary" data-decision="Defer">Defer</button><button type="button" class="btn secondary" data-decision="Dismiss">Dismiss</button><button type="button" class="btn" data-decision="Approve">Approve</button><button type="button" class="btn" id="m365-execute">Capture approved</button></div>
        </section>
        <div id="m365-review-status" class="m365-review-status" role="status" aria-live="polite"></div>
      </section>`;
  }
  function visibleItems(){
    const f=state.filter;
    const reviewFilter={Approved:'Approve',Deferred:'Defer',Dismissed:'Dismiss'}[f];
    return state.items.filter(item => f==='All' || (f==='Action required' && actionable(item)) || item.status===f || item.review_decision===reviewFilter);
  }
  function render(){
    const body=document.getElementById('m365-review-rows'); if(!body) return;
    const rows=visibleItems();
    body.innerHTML=rows.length ? rows.map(item=>`<tr class="status-${esc(item.status).toLowerCase()}"><td><input type="checkbox" data-item-id="${esc(item.item_id)}" ${state.selected.has(item.item_id)?'checked':''} ${item.status==='Unchanged'?'disabled':''}></td><td><strong>${esc(item.name || item.item_id)}</strong><small>${esc(item.relative_path || 'Authorized intake root')}</small><small>${item.size ? esc(Math.ceil(item.size/1024).toLocaleString())+' KB' : ''}</small></td><td><span class="m365-badge">${esc(item.status)}</span></td><td>${esc(item.review_decision || 'Pending')}<small>${esc(item.review_reason || '')}</small></td><td><code>${esc((item.version_etag || '').slice(0,24))}</code><small>${esc(item.last_modified || '')}</small></td></tr>`).join('') : '<tr><td colspan="5">No sources match this filter.</td></tr>';
    body.querySelectorAll('[data-item-id]').forEach(box=>box.addEventListener('change',()=>{box.checked?state.selected.add(box.dataset.itemId):state.selected.delete(box.dataset.itemId); updateSelected();}));
    updateSelected();
  }
  function updateSelected(){ const n=document.getElementById('m365-selected-count'); if(n)n.textContent=String(state.selected.size); }
  async function reconcile(){
    announce('Reconciling the authorized intake folder and nested folders…');
    try{
      const result=await request('/api/integrations/m365/intake/reconcile-source-versions',{method:'POST'});
      state.items=result.items || []; state.selected.clear();
      state.items.forEach(item=>{ if(item.review_decision==='Approve' && item.review_decision_id) state.decisions.set(item.item_id,item.review_decision_id); });
      const c=result.counts || {}; document.getElementById('m365-review-counts').textContent=`${c.New||0} new · ${c.Changed||0} changed · ${c.Missing||0} missing · ${c.Unchanged||0} unchanged`;
      render(); announce(`Reconciliation completed at ${result.reconciled_at || 'the current time'}.`,'success');
    }catch(err){ announce(err.message,'error'); }
  }
  async function decide(decision){
    const ids=[...state.selected], reason=document.getElementById('m365-review-reason').value.trim();
    if(!ids.length) return announce('Select at least one actionable source.','error');
    if(ids.length>REVIEW_LIMIT) return announce(`Review decisions are limited to ${REVIEW_LIMIT} sources per batch.`,'error');
    if(!reason) return announce('Document a review reason before continuing.','error');
    announce(`Recording ${decision.toLowerCase()} decision for ${ids.length} source${ids.length===1?'':'s'}…`);
    try{
      const result=await request('/api/integrations/m365/intake/review-queue/batch-decision',{method:'POST',body:JSON.stringify({item_ids:ids,decision,reason})});
      (result.items||[]).forEach(row=>state.decisions.set(row.item_id,row.decision_id));
      await reconcile(); announce(`${result.count} source${result.count===1?'':'s'} marked ${decision}.`,'success');
    }catch(err){ announce(err.message,'error'); }
  }
  async function execute(){
    const selected=[...state.selected], reason=document.getElementById('m365-review-reason').value.trim();
    const decisionIds=selected.map(id=>state.decisions.get(id)).filter(Boolean);
    if(!decisionIds.length) return announce('Approve selected sources in this session before capture.','error');
    if(decisionIds.length>EXECUTE_LIMIT) return announce(`Capture is limited to ${EXECUTE_LIMIT} approved sources per batch.`,'error');
    if(!reason) return announce('Document the recording authority basis before capture.','error');
    announce(`Capturing ${decisionIds.length} approved source${decisionIds.length===1?'':'s'}…`);
    try{
      const result=await request('/api/integrations/m365/intake/review-queue/execute-approved',{method:'POST',body:JSON.stringify({decision_ids:decisionIds,recording_authority_basis:reason,sensitivity:'Restricted',purpose_tags:['SalINTEL research']})});
      const failures=(result.items||[]).filter(x=>x.status!=='Succeeded');
      announce(`${result.succeeded} captured; ${result.failed} failed safely.${failures.length?' Review the failed item details and reconcile before retrying.':''}`,result.failed?'error':'success');
      state.selected.clear(); await reconcile();
    }catch(err){ announce(err.message,'error'); }
  }
  function close(){ document.getElementById('m365-intake-review-root')?.remove(); }
  function open(){
    if(!isAdmin() || document.getElementById('m365-intake-review-root')) return;
    const root=document.createElement('div'); root.id='m365-intake-review-root'; root.className='m365-review-root'; root.innerHTML=markup(); document.body.appendChild(root);
    root.querySelectorAll('[data-review-close]').forEach(x=>x.addEventListener('click',close));
    root.querySelector('#m365-reconcile').addEventListener('click',reconcile);
    root.querySelector('#m365-review-filter').addEventListener('change',e=>{state.filter=e.target.value;render();});
    root.querySelector('#m365-select-visible').addEventListener('change',e=>{visibleItems().filter(actionable).forEach(x=>e.target.checked?state.selected.add(x.item_id):state.selected.delete(x.item_id));render();});
    root.querySelectorAll('[data-decision]').forEach(x=>x.addEventListener('click',()=>decide(x.dataset.decision)));
    root.querySelector('#m365-execute').addEventListener('click',execute); reconcile();
  }
  window.SalusM365IntakeReview=Object.freeze({sync:ensureLaunch,open,close});
  document.addEventListener('change',e=>{if(e.target?.id==='role-select') queueMicrotask(ensureLaunch);},true);
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',ensureLaunch); else ensureLaunch();
})();
