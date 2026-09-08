/* SalCAPA Mission Map — visual way-finding over governed server state. */
viewTitles.mission_map='Mission Map';
subtitles.mission_map='See where governed work is, why it exists, what is expected next, and how evidence and results feed improvement.';

let salcapaMissionMapData=null;
let salcapaMissionMapCatalog=null;

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
  const controls=salus?`<div class="mission-actions"><button class="btn secondary" onclick="missionMapTransition('${esc(item.id)}')">Record next state</button>${item.visibility!=='Released'?`<button class="btn secondary" onclick="missionMapRelease('${esc(item.id)}')">Release to Protected Member view</button>`:''}</div>`:'';
  $('#mission-map-detail').innerHTML=`<article class="card mission-detail-card"><div class="section-title"><div><span class="mission-kicker">${esc(item.functional_area)} · ${esc(item.node_type)}</span><h2>${esc(item.title)}</h2></div><span class="mission-neutral-state">${esc(item.status)}</span></div><div class="mission-path" aria-label="Mission Structure path">${missionMapPath(item)}</div><div class="mission-detail-grid"><div><small>Why this work exists</small><p>${esc(item.purpose||'Purpose has not been released or recorded for this view.')}</p></div><div><small>Current location</small><p><strong>${esc(item.station)}</strong> on ${esc(item.functional_area)}</p></div><div><small>Who owns the next step</small><p>${esc(item.owner||'Owner not yet identified')}</p></div><div><small>What is needed now</small><p>${esc(item.waiting_on||'No waiting requirement is currently recorded.')}</p></div><div><small>Expected next step</small><p>${esc(item.next_step||item.next_station||'Review the governed record.')}</p></div><div><small>Evidence / result state</small><p>${esc(item.evidence_state)}${item.result_summary?` — ${esc(item.result_summary)}`:''}</p></div></div><p class="subtle">${esc(item.guidance||'')}</p>${salus&&item.authority?`<p class="mission-authority"><strong>Authority:</strong> ${esc(item.authority)}</p>`:''}${controls}</article>`;
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
  const query=activeAssessmentId?`?assessment_id=${Number(activeAssessmentId)}`:'';
  const [data,catalog]=await Promise.all([api('/api/salcapa/mission-map'+query),api('/api/salcapa/mission-map/catalog')]);
  salcapaMissionMapData=data;salcapaMissionMapCatalog=catalog;
  const add=!isProtectedMember()?'<button class="btn" onclick="missionMapCreate()">Add Mission Structure item</button>':'';
  $('#content').innerHTML=`<div class="card mission-hero"><div class="section-title"><div><span>SalCAPA™ way-finding</span><h2>Mission Map</h2><p>${esc(data.interpretation)}</p></div>${add}</div><div class="mission-structure-summary"><strong>Mission Structure</strong><span>${esc(catalog.mission_structure)}</span></div><p class="subtle">${esc(catalog.principle)} Select any marker to see why it is here, its current location, what is needed, who owns the next step, and what happens next.</p></div>${data.items.length?data.routes.map(route=>missionMapRoute(route,data.items)).join(''):'<div class="notice">No Mission Map items are available in this authorized scope yet.</div>'}<div id="mission-map-detail"></div>${missionMapFallback(data)}`;
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
