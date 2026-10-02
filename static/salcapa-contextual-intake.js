(() => {
  const WORKSPACE_VIEWS = new Set([
    'dashboard','common_operating_picture','salintel','salintel_domains',
    'personnel_assessments','facility_assessments','salthira','assessments',
    'risk','priorities','reassessment','evidence','attachments','salops',
    'salops_preparedness','salops_plan_assembly','analytical_actions','prove','reports','trace'
  ]);
  let activeContext = null;
  let syncing = false;

  function safeContext(input){
    if(!input || !/^[a-z_]+$/.test(String(input.targetType||''))) return null;
    const targetId=Number(input.targetId);
    if(!Number.isInteger(targetId) || targetId < 1) return null;
    return {
      targetType:String(input.targetType), targetId,
      label:String(input.label||'Current authorized record').slice(0,500),
      purpose:String(input.purpose||'Contextual source material for governed review').slice(0,1000)
    };
  }

  function selectedInvestigationContext(){
    const workspace=document.querySelector('#salintel-research-workspace[data-record-id],#salintel-monitoring-workspace[data-record-id]');
    if(workspace){
      return safeContext({targetType:'salintel_investigation',targetId:workspace.dataset.recordId,label:'Current SalINTEL investigation',purpose:'Information submitted from the current SalINTEL investigation workspace'});
    }
    return null;
  }

  function workspaceContext(){
    const investigation=selectedInvestigationContext();
    if(investigation) return investigation;
    if(!WORKSPACE_VIEWS.has(String(currentView||'')) || !Number(activeAssessmentId||0)) return null;
    const title=document.getElementById('page-title')?.textContent?.trim()||'Current SalCAPA workspace';
    return safeContext({targetType:'assessment',targetId:activeAssessmentId,label:title,purpose:`Information submitted from ${title}`});
  }

  function contextBanner(context){
    const banner=document.createElement('div');
    banner.className='contextual-intake-banner';
    banner.innerHTML=`<strong>Proposed context</strong><span>${esc(context.label)}</span><small>This preserves where you were working. It does not create an authoritative link; human review and governed linking still apply.</small>`;
    return banner;
  }

  function prepareDialog(context){
    const root=document.getElementById('salcapa-intake-root');
    if(!root) return;
    root.querySelector('.contextual-intake-banner')?.remove();
    root.querySelector('.intake-dialog-header')?.after(contextBanner(context));
    const fileTab=root.querySelector('[data-intake-tab="file"]');
    fileTab?.click();
    const form=root.querySelector('#intake-file-form');
    if(!form) return;
    const evidenceLabel=form.querySelector('select[name="evidenceId"]')?.closest('label');
    if(evidenceLabel) evidenceLabel.hidden=true;
    const source=form.querySelector('[name="sourceContext"]');
    if(source && !source.value) source.value=`Submitted from ${context.label}`;
    const safeguard=form.querySelector('.intake-safeguard');
    if(safeguard) safeguard.innerHTML='<strong>Preserved as governed source material.</strong> Original bytes, integrity evidence, processing state, sensitivity, retention, and the proposed context remain distinct. A qualified person must review and link the material before authoritative use.';
  }

  function open(context){
    const checked=safeContext(context);
    if(!checked || !window.SalusIntakeCapture?.canCapture()) return;
    activeContext=checked;
    document.getElementById('salcapa-intake-launch')?.click();
    queueMicrotask(()=>prepareDialog(checked));
  }

  function addWorkspaceAction(){
    if(!window.SalusIntakeCapture?.canCapture()) return;
    const context=workspaceContext(), content=document.getElementById('content');
    if(!context || !content || content.querySelector('.contextual-intake-action')) return;
    const action=document.createElement('div');
    action.className='contextual-intake-action';
    const button=document.createElement('button');
    button.type='button'; button.className='btn secondary';
    button.textContent='＋ Attach information here';
    button.title='Preserve source material with this record as proposed context. Human review is still required before governed linking.';
    button.addEventListener('click',()=>open(context));
    action.appendChild(button); content.prepend(action);
  }

  function inferMaterialKind(file){
    const type=String(file.type||'').toLowerCase(), name=String(file.name||'').toLowerCase();
    if(type.startsWith('image/')) return /\.(geojson|kml|kmz)$/.test(name)?'Map / Geospatial':'Image';
    if(type.startsWith('audio/')) return 'Audio';
    if(type.startsWith('video/')) return 'Video';
    if(/\.(csv|tsv|json|xml|log)$/.test(name)) return 'Structured Data';
    if(/\.(eml|msg)$/.test(name)) return 'Email / Message';
    return 'Document';
  }

  async function submitContextualFiles(event){
    if(event.target?.id!=='intake-file-form' || !activeContext) return;
    event.preventDefault(); event.stopImmediatePropagation();
    const form=event.target, source=new FormData(form), files=[...form.elements.files.files];
    const status=document.getElementById('intake-status');
    const show=(message,kind='')=>{if(status){status.className='intake-status '+kind;status.textContent=message;}};
    if(!files.length){show('Choose at least one file.','error');return;}
    const tooLarge=files.find(file=>file.size>25*1024*1024);
    if(tooLarge){show(`${tooLarge.name} exceeds the current 25 MB per-file limit.`,'error');return;}
    let preserved=0;
    try{
      for(let index=0;index<files.length;index++){
        const file=files[index]; show(`Preserving ${index+1} of ${files.length}: ${file.name}…`);
        const body=new FormData();
        body.append('file',file,file.name);
        body.append('title',file.name);
        body.append('material_kind',inferMaterialKind(file));
        body.append('source_origin',String(source.get('sourceContext')||'Authorized user submission'));
        body.append('source_locator',`salcapa-proposed://${activeContext.targetType}/${activeContext.targetId}`);
        body.append('sensitivity','Standard');
        body.append('purpose_tags',JSON.stringify([String(source.get('purpose')||'Documentation')]));
        body.append('description',String(source.get('description')||''));
        body.append('recording_authority_basis',String(source.get('recordingBasis')||''));
        const material=await apiForm('/api/materials/upload',body); preserved++;
        try{
          await api(`/api/materials/${material.id}/context-proposals`,{method:'POST',body:JSON.stringify({
            target_type:activeContext.targetType,target_id:activeContext.targetId,
            context_label:activeContext.label,purpose:activeContext.purpose
          })});
        }catch(error){
          show(`${file.name} was preserved, but its proposed context could not be recorded. Do not upload it again; a reviewer can find material #${material.id} in the material register. ${error.message}`,'error');
          return;
        }
      }
      show(`Preserved ${preserved} source material item${preserved===1?'':'s'} with proposed context. Human review and governed linking are next.`,'success');
      form.reset();
    }catch(error){show(`${preserved?`${preserved} item${preserved===1?' was':'s were'} preserved before this error. `:''}${error.message}`,'error');}
  }

  function sync(){
    if(syncing) return; syncing=true;
    queueMicrotask(()=>{syncing=false;addWorkspaceAction();});
  }

  document.addEventListener('submit',submitContextualFiles,true);
  document.addEventListener('click',event=>{
    if(event.target?.matches('[data-close-intake]')) activeContext=null;
  },true);
  new MutationObserver(sync).observe(document.documentElement,{childList:true,subtree:true});
  window.SalusContextualIntake=Object.freeze({open,sync});
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',sync);
  else sync();
})();
