(() => {
  const VIEW = 'salops_preparedness';
  const escHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const headers = () => ({'Content-Type':'application/json', ...(typeof authHeaders === 'function' ? authHeaders() : {})});
  async function request(url, options={}) {
    const response = await fetch(url, {...options, headers:{...headers(), ...(options.headers||{})}});
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }
  const isMember = () => typeof workspaceState !== 'undefined' && workspaceState?.experience === 'Protected Member';
  const rows = (items, columns) => {
    if (!items?.length) return '<div class="prep-empty">No records yet.</div>';
    return `<div class="prep-table-wrap"><table class="prep-table"><thead><tr>${columns.map(c=>`<th>${escHtml(c[0])}</th>`).join('')}</tr></thead><tbody>${items.map(item=>`<tr>${columns.map(c=>`<td>${c[2] ? c[2](item[c[1]], item) : escHtml(item[c[1]])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  };
  const phaseTags = phases => (phases||[]).map(p=>`<span class="prep-tag">${escHtml(p)}</span>`).join(' ');
  const lifecycle = stages => `<div class="prep-lifecycle" aria-label="Preparedness lifecycle">${(stages||[]).map((s,i)=>`<div class="prep-stage"><span>${i+1}</span><strong>${escHtml(s)}</strong></div>`).join('')}</div>`;
  const button = (label, action, secondary=false) => `<button class="btn ${secondary?'secondary':''}" data-prep-action="${action}">${escHtml(label)}</button>`;

  async function createPlan() {
    const title = prompt('Plan title (for example, Crisis Communications Plan):'); if (!title) return;
    const plan_type = prompt('Plan type:', 'Emergency & Crisis Planning') || 'Emergency & Crisis Planning';
    const scope_statement = prompt('Exact approved scope (facilities, business units, personnel or portfolio subset):'); if (!scope_statement) return;
    const purpose = prompt('Plan purpose:') || '';
    const phases = (prompt('Mission lenses, comma separated:', 'Prevention, Protection, Mitigation, Response, Recovery')||'').split(',').map(x=>x.trim()).filter(Boolean);
    await request('/api/salops/preparedness/plans',{method:'POST',body:JSON.stringify({title,plan_type,purpose,scope_statement,mission_lenses:phases,portfolio_scope:{scope_basis:'Explicit approved scope'},commercial_treatment:'Not Determined'})});
    await renderPreparedness();
  }
  async function createTraining() {
    const title=prompt('Training title:'); if(!title)return;
    const objective=prompt('Training objective:'); if(!objective)return;
    const scheduled_at=prompt('Scheduled date/time (optional):')||'';
    await request('/api/salops/preparedness/training',{method:'POST',body:JSON.stringify({title,objective,scheduled_at,mission_lenses:['Response'],commercial_treatment:'Not Determined'})});
    await renderPreparedness();
  }
  async function createExercise() {
    const title=prompt('Exercise title:'); if(!title)return;
    const exercise_type=prompt('Exercise type: Orientation / Seminar, Workshop, Drill, Tabletop Exercise, Functional Exercise, Full-Scale Exercise, or Custom','Tabletop Exercise')||'Tabletop Exercise';
    const scope_statement=prompt('Exact exercise scope:'); if(!scope_statement)return;
    const purpose=prompt('Exercise purpose:')||'';
    const objective=prompt('Primary objective:')||'';
    const scheduled_at=prompt('Scheduled date/time (optional):')||'';
    await request('/api/salops/preparedness/exercises',{method:'POST',body:JSON.stringify({title,exercise_type,purpose,objectives:objective?[objective]:[],scope_statement,portfolio_scope:{scope_basis:'Explicit approved scope'},mission_lenses:['Response','Recovery'],scheduled_at,safety_real_world_controls:'Exercise control must yield to any real-world emergency.',commercial_treatment:'Not Determined'})});
    await renderPreparedness();
  }
  async function createCorrective() {
    const title=prompt('Corrective action title:'); if(!title)return;
    const description=prompt('Required corrective action:'); if(!description)return;
    const owner=prompt('Action owner:')||'';
    const validation_method=prompt('How will completion be validated or re-tested?')||'';
    await request('/api/salops/preparedness/corrective-actions',{method:'POST',body:JSON.stringify({title,description,owner,validation_method,reexercise_required:false})});
    await renderPreparedness();
  }

  async function renderPreparedness() {
    const content = document.getElementById('content');
    if (!content) return;
    document.getElementById('page-title').textContent='SalOPS™ — Preparedness, Planning & Exercises';
    document.getElementById('page-subtitle').textContent='Plan • Train • Exercise • Observe • Evaluate • Improve • Validate • Sustain';
    content.innerHTML='<div class="card"><p class="subtle">Loading governed preparedness records…</p></div>';
    try {
      const [overview, plans, training, exercises, actions, aars] = await Promise.all([
        request('/api/salops/preparedness/overview'), request('/api/salops/preparedness/plans'),
        request('/api/salops/preparedness/training'), request('/api/salops/preparedness/exercises'),
        request('/api/salops/preparedness/corrective-actions'), request('/api/salops/preparedness/aars')
      ]);
      const c=overview.counts||{};
      const controls = isMember() ? '' : `<div class="prep-actions">${button('New Plan','plan')}${button('Schedule Training','training',true)}${button('Design Exercise','exercise',true)}${button('New Corrective Action','corrective',true)}</div>`;
      content.innerHTML = `
        <section class="card prep-hero"><span class="component ops">SalOPS™</span><h2>Preparedness, Planning & Exercises</h2><p>Human + Chat-powered preparedness work converts qualified intelligence and assessed capability gaps into plans, training, exercises, corrective action, validation, and sustained readiness. Salus human authority remains controlling.</p>${controls}</section>
        ${lifecycle(overview.lifecycle)}
        <div class="grid stats prep-stats">
          <div class="card metric"><span>Current Plans</span><strong>${Number(c.plans||0)}</strong></div>
          <div class="card metric"><span>Training Activities</span><strong>${Number(c.training||0)}</strong></div>
          <div class="card metric"><span>Exercises</span><strong>${Number(c.exercises||0)}</strong></div>
          <div class="card metric"><span>Awaiting Validation</span><strong>${Number(c.awaiting_validation||0)}</strong></div>
        </div>
        <section class="card prep-section"><div class="section-title"><div><h2>Emergency & Crisis Planning</h2><p class="subtle">Living, versioned plans with exact portfolio scope and Prevention • Protection • Mitigation • Response • Recovery lenses.</p></div></div>${rows(plans,[['Plan','title'],['Type','plan_type'],['Mission lenses','mission_lenses',(v)=>phaseTags(v)],['Status','status'],['Review','review_date']])}</section>
        <section class="card prep-section"><div class="section-title"><div><h2>Training</h2><p class="subtle">Training completion is recorded separately from evidence that a capability performs under exercise or real-world conditions.</p></div></div>${rows(training,[['Training','title'],['Objective','objective'],['Scheduled','scheduled_at'],['Status','status']])}</section>
        <section class="card prep-section"><div class="section-title"><div><h2>Exercises</h2><p class="subtle">Seminars, workshops, drills, tabletops, functional and full-scale exercises use governed objectives, evaluation criteria and defensive scenario controls.</p></div></div>${rows(exercises,[['Exercise','title'],['Type','exercise_type'],['Mission lenses','mission_lenses',(v)=>phaseTags(v)],['Scheduled','scheduled_at'],['Status','status']])}</section>
        <section class="card prep-section"><div class="section-title"><div><h2>Improvement & Validation</h2><p class="subtle">Implementation is not validation. Corrective actions remain open until the required evidence or re-test supports closure.</p></div></div>${rows(actions,[['Corrective action','title'],['Owner','owner'],['Due','due_date'],['Status','status'],['Re-exercise','reexercise_required',(v)=>v?'Required':'Not specified']])}</section>
        <section class="card prep-section"><div class="section-title"><div><h2>After-Action Reports / Improvement Plans</h2><p class="subtle">Released products preserve exercise observations, strengths, gaps, corrective actions and unresolved questions without overwriting source records.</p></div></div>${rows(aars,[['AAR / IP','title'],['Status','status'],['Version','version']])}</section>
        <div class="notice prep-principle"><strong>Governance:</strong> planning or Chat-assisted work does not establish Protected Member policy, legal authority, emergency command authority, evacuation authority, use-of-force policy, commercial commitment, or readiness by itself.</div>`;
      content.querySelectorAll('[data-prep-action]').forEach(el=>el.onclick=()=>({plan:createPlan,training:createTraining,exercise:createExercise,corrective:createCorrective}[el.dataset.prepAction]||(()=>{}))());
    } catch (error) {
      content.innerHTML=`<div class="notice"><strong>Preparedness workspace unavailable</strong><br>${escHtml(error.message)}</div>`;
    }
  }

  function activate() {
    if (typeof currentView !== 'undefined') currentView=VIEW;
    document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===VIEW));
    renderPreparedness();
  }
  const nav=document.querySelector('#nav button[data-view="salops_preparedness"]');
  if(nav) nav.onclick=activate;
  if (typeof subtitles !== 'undefined') subtitles[VIEW]='Plan • Train • Exercise • Observe • Evaluate • Improve • Validate • Sustain';
  if (typeof render === 'function') {
    const baseRender=render;
    render=async function(){ return (typeof currentView!=='undefined' && currentView===VIEW) ? renderPreparedness() : baseRender(); };
  }
  window.SalusPreparedness={render:renderPreparedness,activate};
})();
