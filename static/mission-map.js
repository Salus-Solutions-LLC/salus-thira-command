/* SalCAPA Mission Map — visual way-finding over governed server state. */
viewTitles.mission_map='Mission Map';
subtitles.mission_map='See where governed work is, why it exists, what is expected next, and how evidence and results feed improvement.';

let salcapaMissionMapData=null;
let salcapaMissionMapCatalog=null;
let salcapaMissionMapFilters={functional_area:'',workflow_status:'',attention:'',owner:''};

function missionMapOptions(values,current,label){
  return `<option value="">${esc(label)}</option>`+values.map(value=>`<option value="${esc(value)}"${value===current?' selected':''}>${esc(value)}</option>`).join('');
}

function missionMapPortfolio(data){
  const portfolio=data.portfolio||{};
  const attention=portfolio.by_attention||{};
  const evidence=portfolio.by_evidence_state||{};
  return `<section class="card mission-portfolio" aria-live="polite"><div class="section-title"><div><span>Authorized portfolio view</span><h3>Where attention may be needed</h3></div></div><div class="mission-portfolio-grid"><div><strong>${Number(portfolio.total_items||0)}</strong><span>governed items in this view</span></div><div><strong>${Number(attention['Waiting / input needed']||0)}</strong><span>waiting or needing input</span></div><div><strong>${Number(attention['Review / validation needed']||0)}</strong><span>awaiting review or validation</span></div><div><strong>${Number(attention['Reassessment needed']||0)}</strong><span>needing reassessment</span></div><div><strong>${Number(evidence['Evidence Needed']||0)}</strong><span>with evidence still needed</span></div></div><p class="subtle">${esc(portfolio.interpretation||'')}</p></section>`;
}

function missionMapFilterPanel(catalog){
  return `<section class="card mission-filters" aria-label="Mission Map filters"><div class="mission-filter-grid"><label>Functional area<select id="mission-filter-area">${missionMapOptions(catalog.functional_areas||[],salcapaMissionMapFilters.functional_area,'All functional areas')}</select></label><label>Workflow state<select id="mission-filter-status">${missionMapOptions(catalog.workflow_states||[],salcapaMissionMapFilters.workflow_status,'All workflow states')}</select></label><label>Attention needed<select id="mission-filter-attention">${missionMapOptions(catalog.attention_states||[],salcapaMissionMapFilters.attention,'All attention states')}</select></label><label>Owner or responsible role<input id="mission-filter-owner" maxlength="120" value="${esc(salcapaMissionMapFilters.owner)}" placeholder="All authorized owners" /></label></div><div class="mission-filter-actions"><button class="btn secondary" type="button" onclick="missionMapApplyFilters()">Apply filters</button><button class="btn secondary" type="button" onclick="missionMapClearFilters()">Clear</button></div><p class="subtle">${esc(catalog.filter_guidance||'Filters narrow this authorized view without changing the underlying work.')}</p></section>`;
}

async function missionMapApplyFilters(){
  salcapaMissionMapFilters={
    functional_area:$('#mission-filter-area').value,
    workflow_status:$('#mission-filter-status').value,
    attention:$('#mission-filter-attention').value,
    owner:$('#mission-filter-owner').value.trim(),
  };
  await salcapaMissionMap();
}

async function missionMapClearFilters(){
  salcapaMissionMapFilters={functional_area:'',workflow_status:'',attention:'',owner:''};
  await salcapaMissionMap();
}

function missionMapRoute(route,items){
  const routeItems=items.filter(item=>item.route_key===route.key);
  const cells=route.stations.map(station=>{
    const stationItems=routeItems.filter(item=>item.station===station);
    const markers=stationItems.map(item=>`<button class="mission-marker shape-${esc(item.marker_shape)}" type="button" title="${esc(item.title)} — ${esc(item.status)}" aria-label="${esc(item.title)}. ${esc(item.status)}. Current station ${esc(item.station)}." onclick="missionMapDetail('${esc(item.id)}')"><span class="mission-marker-icon" aria-hidden="true"></span><span class="mission-marker-label">${esc(item.title)}</span></button>`).join('');
    return `<div class="mission-station"><div class="mission-station-node" aria-hidden="true"></div><strong>${esc(station)}</strong><div class="mission-station-items">${markers||'<span class="mission-empty">No work here</span>'}</div></div>`;
  }).join('');
  return `<section class="mission-route route-${esc(route.key)}"><div class="mission-route-heading"><div><h3>${esc(route.label)}</h3><p>${esc(route.description)}</p></div><span>${routeItems.length} item${routeItems.length===1?'':'s'}</span></div><div class="mission-track" style="--station-count:${route.stations.length}">${cells}</div></section>`;
}

function missionMapPath(item){
  const parts=[...(item.mission_path||[]),{node_type:item.node_type,title:item.title}];
  return parts.map(part=>`<span><strong>${esc(part.node_type)}</strong> ${esc(part.title)}</span>`).join('<span class="mission-path-arrow" aria-hidden="true">→</span>');
}

function missionMapDetail(id){
  if(!salcapaMissionMapData)return;
  const item=salcapaMissionMapData.items.find(entry=>entry.id===id);
  if(!item)return;
  const salus=!isProtectedMember();
  const controls=salus&&!item.read_only?`<div class="mission-actions"><button class="btn secondary" onclick="missionMapTransition('${esc(item.id)}')">Record next state</button>${item.visibility!=='Released'?`<button class="btn secondary" onclick="missionMapRelease('${esc(item.id)}')">Release to Protected Member view</button>`:''}</div>`:'';
  const source=item.read_only?`<div><small>Authoritative source</small><p>${esc(item.source_type)} · ${esc(item.source_status)}</p></div>`:'';
  $('#mission-map-detail').innerHTML=`<article class="card mission-detail-card"><div class="section-title"><div><span class="mission-kicker">${esc(item.functional_area)} · ${esc(item.node_type)}</span><h2>${esc(item.title)}</h2></div><span class="mission-neutral-state">${esc(item.status)}</span></div><div class="mission-path" aria-label="Mission Structure path">${missionMapPath(item)}</div><div class="mission-detail-grid"><div><small>Why this work exists</small><p>${esc(item.purpose||'Purpose has not been released or recorded for this view.')}</p></div><div><small>Current location</small><p><strong>${esc(item.station)}</strong> on ${esc(item.functional_area)}</p></div><div><small>Who owns the next step</small><p>${esc(item.owner||'Owner not yet identified')}</p></div><div><small>What is needed now</small><p>${esc(item.waiting_on||'No waiting requirement is currently recorded.')}</p></div><div><small>Expected next step</small><p>${esc(item.next_step||item.next_station||'Review the governed record.')}</p></div><div><small>Evidence / result state</small><p>${esc(item.evidence_state)}${item.result_summary?` — ${esc(item.result_summary)}`:''}</p></div>${source}</div><p class="subtle">${esc(item.projection_basis||item.guidance||'')}</p>${item.projection_basis?`<p class="subtle">${esc(item.guidance||'')}</p>`:''}${salus&&item.authority?`<p class="mission-authority"><strong>Authority:</strong> ${esc(item.authority)}</p>`:''}${controls}</article>`;
  $('#mission-map-detail').scrollIntoView({behavior:'smooth',block:'nearest'});
}

function missionMapFallback(data){
  const rows=data.items.map(item=>[
    `<strong>${esc(item.title)}</strong><br><span class="subtle">${esc(item.node_type)}</span>`,
    esc(item.functional_area),esc(item.station),esc(item.status),esc(item.owner||'Not identified'),
    esc(item.next_step||item.next_station||'Review governed record'),esc(item.evidence_state)
  ]);
  return `<details class="card mission-fallback"><summary>Conventional list view</summary><p class="subtle">${esc(data.fallback.description)}</p>${table(['Work item','Area','Current location','State','Next owner','Expected next step','Evidence state'],rows)}</details>`;
}

async function salcapaMissionMap(){
  const params=new URLSearchParams();
  if(activeAssessmentId)params.set('assessment_id',Number(activeAssessmentId));
  Object.entries(salcapaMissionMapFilters).forEach(([key,value])=>{if(value)params.set(key,value);});
  const query=params.toString()?`?${params.toString()}`:'';
  const [data,catalog]=await Promise.all([api('/api/salcapa/mission-map'+query),api('/api/salcapa/mission-map/catalog')]);
  salcapaMissionMapData=data;salcapaMissionMapCatalog=catalog;
  const add=!isProtectedMember()?'<button class="btn" onclick="missionMapCreate()">Add Mission Structure item</button>':'';
  $('#content').innerHTML=`<div class="card mission-hero"><div class="section-title"><div><span>SalCAPA™ way-finding</span><h2>Mission Map</h2><p>${esc(data.interpretation)}</p></div>${add}</div><div class="mission-structure-summary"><strong>Mission Structure</strong><span>${esc(catalog.mission_structure)}</span></div><p class="subtle">${esc(catalog.principle)} Select any marker to see why it is here, its current location, what is needed, who owns the next step, and what happens next.</p><p class="subtle">${esc(catalog.overlay_guidance||'')}</p></div>${missionMapFilterPanel(catalog)}${missionMapPortfolio(data)}${data.items.length?data.routes.map(route=>missionMapRoute(route,data.items)).join(''):'<div class="notice">No Mission Map items match the current authorized view and filters.</div>'}<div id="mission-map-detail"></div>${missionMapFallback(data)}`;
}

async function missionMapCreate(){
  if(!salcapaMissionMapCatalog)return;
  const types=salcapaMissionMapCatalog.node_types;
  const nodeType=prompt(`Type: ${types.join(' | ')}`,types[0]);
  if(!types.includes(nodeType))return;
  let area='Mission Structure';
  if(!['Mission','Priority','Objective','Strategy','Tactic'].includes(nodeType)){
    const areas=salcapaMissionMapCatalog.functional_areas;
    area=prompt(`Functional area: ${areas.join(' | ')}`,nodeType==='Evidence & Result'?'PROVE':'SalCAPA');
    if(!areas.includes(area))return;
  }
  const title=prompt('Short title for this governed work item:');if(!title)return;
  const purpose=prompt('Why does this work exist / what outcome does it support?');if(!purpose)return;
  const parentId=prompt('Parent Mission Structure item ID, if applicable:','')||null;
  const owner=prompt('Current owner or responsible role, if known:','')||'';
  const authority=prompt('Authority / approval basis, if applicable:','')||'';
  const internalNext=prompt('Expected next step:','')||'';
  const memberSummary=prompt('Protected Member summary for later release (may remain blank):','')||'';
  const memberNext=memberSummary?(prompt('Protected Member next-step explanation:','')||''):'';
  await api('/api/salcapa/mission-map/nodes',{method:'POST',body:JSON.stringify({assessment_id:activeAssessmentId?Number(activeAssessmentId):null,node_type:nodeType,title,purpose,parent_id:parentId,functional_area:area,owner,authority,internal_next_step:internalNext,internal_waiting_on:'',member_summary:memberSummary,member_next_step:memberNext,member_waiting_on:'',member_owner:owner,evidence_state:nodeType==='Evidence & Result'?'Evidence Needed':'Not Applicable',sensitivity:'Standard'})});
  await salcapaMissionMap();
}

async function missionMapTransition(id){
  if(!salcapaMissionMapCatalog)return;
  const item=salcapaMissionMapData.items.find(entry=>entry.id===id);if(!item)return;
  const status=prompt(`Current state: ${item.status}\nRecord the governed next state: ${salcapaMissionMapCatalog.workflow_states.join(' | ')}`,item.status);
  if(!status||status===item.status||!salcapaMissionMapCatalog.workflow_states.includes(status))return;
  const reason=prompt('Reason / authority basis for this state change:');if(!reason)return;
  const next=prompt('Expected next step after this change:',item.next_step||'')||'';
  const waiting=['Waiting','Awaiting Input'].includes(status)?(prompt('What is this item waiting on?','')||''):'';
  await api(`/api/salcapa/mission-map/nodes/${encodeURIComponent(id)}/transition`,{method:'POST',body:JSON.stringify({status,reason,internal_next_step:next,internal_waiting_on:waiting,member_next_step:null,member_waiting_on:null})});
  await salcapaMissionMap();
}

async function missionMapRelease(id){
  const reason=prompt('Release basis. This makes the prepared member summary and next-step wording visible to the Protected Member:');if(!reason)return;
  await api(`/api/salcapa/mission-map/nodes/${encodeURIComponent(id)}/release`,{method:'POST',body:JSON.stringify({reason})});
  await salcapaMissionMap();
}

const salcapaRenderWithoutMissionMap=render;
render=async function(){if(currentView==='mission_map')return salcapaMissionMap();return salcapaRenderWithoutMissionMap();};
