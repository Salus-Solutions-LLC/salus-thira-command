(() => {
  const MAX_FILE_BYTES = 25 * 1024 * 1024;
  const PURPOSES = ['Documentation','Evidence','Investigation','Intelligence','Assessment','Planning','Operations','Reporting','Analysis','Continuity','Other'];

  function el(tag, attrs={}, text='') {
    const node=document.createElement(tag);
    Object.entries(attrs).forEach(([k,v])=>{
      if(k==='class') node.className=v;
      else if(k==='html') node.innerHTML=v;
      else if(k.startsWith('aria-')) node.setAttribute(k,v);
      else node[k]=v;
    });
    if(text) node.textContent=text;
    return node;
  }

  function ensureSurface(){
    if(document.getElementById('salcapa-intake-launch')) return;
    const topbar=document.querySelector('.topbar');
    if(!topbar) return;
    let actions=topbar.querySelector('.intake-topbar-actions');
    if(!actions){
      actions=el('div',{class:'intake-topbar-actions'});
      const status=topbar.querySelector('.status-pill');
      if(status){ topbar.insertBefore(actions,status); actions.appendChild(status); }
      else topbar.appendChild(actions);
    }
    const launch=el('button',{id:'salcapa-intake-launch',class:'btn intake-launch',type:'button','aria-haspopup':'dialog'},'＋ Add Information');
    launch.title='Capture pasted information or attach source material using governed SalCAPA controls.';
    actions.insertBefore(launch,actions.firstChild);
    launch.addEventListener('click',openDialog);
  }

  function dialogMarkup(){
    return `
      <div class="intake-backdrop" data-close-intake></div>
      <section class="intake-dialog" role="dialog" aria-modal="true" aria-labelledby="intake-title">
        <header class="intake-dialog-header">
          <div><span class="intake-eyebrow">GOVERNED INTAKE</span><h2 id="intake-title">Add Information</h2><p>Capture useful source material now. SalCAPA preserves governance; submission alone does not make material verified evidence, qualified intelligence, an assessment finding, a decision, or operational authority.</p></div>
          <button type="button" class="intake-close" aria-label="Close Add Information" data-close-intake>×</button>
        </header>
        <div class="intake-tabs" role="tablist" aria-label="Information capture method">
          <button type="button" class="intake-tab active" role="tab" aria-selected="true" data-intake-tab="text">Paste / Enter Text</button>
          <button type="button" class="intake-tab" role="tab" aria-selected="false" data-intake-tab="file">Upload Material</button>
        </div>
        <div class="intake-panel" data-intake-panel="text">
          <form id="intake-text-form">
            <div class="form-grid">
              <label>Capture as<select name="recordType" required><option>Observation</option><option>Evidence Lead</option><option>Discovery</option><option>Decision Input</option></select></label>
              <label>Title<input name="title" maxlength="160" required placeholder="Short description of the information"></label>
            </div>
            <label>Source / context<input name="sourceContext" maxlength="500" required placeholder="Where this came from, when received, person/system/source, location, or other useful provenance"></label>
            <label>Information<textarea name="details" maxlength="4000" required rows="8" placeholder="Paste or enter the source text, notes, observations, call notes, extracted text, links, or other information to preserve."></textarea></label>
            <div class="intake-safeguard"><strong>Preserved as a Draft intake record.</strong> Human review and governed promotion are required before it becomes authoritative elsewhere in SalCAPA.</div>
            <div class="form-actions"><button class="btn" type="submit">Capture Information</button></div>
          </form>
        </div>
        <div class="intake-panel" data-intake-panel="file" hidden>
          <form id="intake-file-form">
            <div class="form-grid">
              <label>Attach to evidence record<select name="evidenceId" required><option value="">Loading authorized evidence…</option></select></label>
              <label>Purpose<select name="purpose" required>${PURPOSES.map(x=>`<option>${x}</option>`).join('')}</select></label>
            </div>
            <label>Source / context<input name="sourceContext" maxlength="500" required placeholder="Origin, acquisition date/time, location, sender/source, collection circumstances, or other provenance"></label>
            <label>Description / analyst note<textarea name="description" maxlength="1800" rows="3" placeholder="What the material contains and why it may be useful"></textarea></label>
            <label>Files<input name="files" type="file" multiple required></label>
            <p class="subtle">Current governed upload accepts multiple files one at a time, up to 25 MB each. Documents, images, maps, audio, video and other file types may be preserved as source material subject to the server's security controls. Extraction/transcription support is being expanded separately.</p>
            <label>Recording / possession authority or consent basis <span class="subtle">(when applicable)</span><input name="recordingBasis" maxlength="500" placeholder="For recorded calls/audio/video, document the lawful source/authority or consent basis when applicable"></label>
            <div class="intake-safeguard"><strong>Existing evidence controls remain authoritative.</strong> Uploaded bytes are hashed, scanned according to configured malware policy, retained/governed, sensitivity-scoped, audited, and stored through the existing SalCAPA storage layer.</div>
            <div class="form-actions"><button class="btn" type="submit">Upload Material</button></div>
          </form>
        </div>
        <div id="intake-status" class="intake-status" role="status" aria-live="polite"></div>
      </section>`;
  }

  async function loadEvidence(){
    const select=document.querySelector('#intake-file-form select[name="evidenceId"]');
    if(!select) return;
    try{
      const assessment=await getActiveAssessment();
      if(!assessment){ select.innerHTML='<option value="">No active assessment available</option>'; return; }
      const rows=await api('/api/evidence?assessment_id='+assessment.id);
      select.innerHTML=rows.length
        ? rows.map(r=>`<option value="${r.id}">#${r.id} ${esc(r.title)}</option>`).join('')
        : '<option value="">Create an evidence record first for governed file attachment</option>';
    }catch(err){ select.innerHTML='<option value="">Unable to load authorized evidence</option>'; setStatus(err.message,'error'); }
  }

  function setStatus(message,kind=''){
    const status=document.getElementById('intake-status');
    if(!status) return;
    status.className='intake-status '+kind;
    status.textContent=message||'';
  }

  function switchTab(which){
    document.querySelectorAll('.intake-tab').forEach(b=>{
      const active=b.dataset.intakeTab===which;
      b.classList.toggle('active',active); b.setAttribute('aria-selected',String(active));
    });
    document.querySelectorAll('[data-intake-panel]').forEach(p=>p.hidden=p.dataset.intakePanel!==which);
    setStatus('');
    if(which==='file') loadEvidence();
  }

  function closeDialog(){
    const root=document.getElementById('salcapa-intake-root');
    if(root) root.remove();
    document.removeEventListener('keydown',escapeHandler);
    const launch=document.getElementById('salcapa-intake-launch');
    if(launch) launch.focus();
  }

  function escapeHandler(e){ if(e.key==='Escape') closeDialog(); }

  function openDialog(){
    if(document.getElementById('salcapa-intake-root')) return;
    const root=el('div',{id:'salcapa-intake-root',class:'intake-root',html:dialogMarkup()});
    document.body.appendChild(root);
    root.querySelectorAll('[data-close-intake]').forEach(x=>x.addEventListener('click',closeDialog));
    root.querySelectorAll('.intake-tab').forEach(x=>x.addEventListener('click',()=>switchTab(x.dataset.intakeTab)));
    root.querySelector('#intake-text-form').addEventListener('submit',submitText);
    root.querySelector('#intake-file-form').addEventListener('submit',submitFiles);
    document.addEventListener('keydown',escapeHandler);
    root.querySelector('input[name="title"]').focus();
  }

  async function submitText(e){
    e.preventDefault(); setStatus('Capturing information…');
    const fd=new FormData(e.currentTarget);
    try{
      const payload={recordType:fd.get('recordType'),title:fd.get('title'),details:fd.get('details'),sourceContext:fd.get('sourceContext')};
      const result=await api('/api/intake',{method:'POST',body:JSON.stringify(payload)});
      setStatus(`Captured ${result.record?.id||'intake record'} as governed Draft.`,'success');
      e.currentTarget.reset();
    }catch(err){ setStatus(err.message,'error'); }
  }

  async function submitFiles(e){
    e.preventDefault();
    const fd=new FormData(e.currentTarget), evidenceId=fd.get('evidenceId');
    const files=[...e.currentTarget.elements.files.files];
    if(!evidenceId){setStatus('Select an authorized evidence record before uploading.','error');return;}
    if(!files.length){setStatus('Choose at least one file.','error');return;}
    const tooLarge=files.find(f=>f.size>MAX_FILE_BYTES);
    if(tooLarge){setStatus(`${tooLarge.name} exceeds the current 25 MB per-file limit.`,'error');return;}
    try{
      const uploaded=[];
      for(let i=0;i<files.length;i++){
        setStatus(`Uploading ${i+1} of ${files.length}: ${files[i].name}…`);
        const one=new FormData(); one.append('file',files[i],files[i].name);
        const row=await apiForm(`/api/evidence/${evidenceId}/attachments`,one);
        uploaded.push(row);
      }
      const purpose=fd.get('purpose'), sourceContext=fd.get('sourceContext'), description=String(fd.get('description')||'').trim(), recordingBasis=String(fd.get('recordingBasis')||'').trim();
      const details=[`Purpose: ${purpose}`,`Evidence record: #${evidenceId}`,`Uploaded material: ${files.map(f=>f.name).join(', ')}`,description?`Description: ${description}`:'',recordingBasis?`Recording/possession authority or consent basis (user supplied): ${recordingBasis}`:''].filter(Boolean).join('\n');
      await api('/api/intake',{method:'POST',body:JSON.stringify({recordType:'Evidence Lead',title:`Material upload: ${files[0].name}${files.length>1?` (+${files.length-1} more)`:''}`,details:details.slice(0,4000),sourceContext})});
      setStatus(`Uploaded ${uploaded.length} file${uploaded.length===1?'':'s'} through governed evidence storage and captured the source context for review.`,'success');
      e.currentTarget.reset(); await loadEvidence();
    }catch(err){setStatus(err.message,'error');}
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',ensureSurface);
  else ensureSurface();
})();
