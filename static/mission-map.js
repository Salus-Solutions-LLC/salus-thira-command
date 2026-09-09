/* SalCAPA Mission Map — visual way-finding over governed server state. */
viewTitles.mission_map='Mission Map';
subtitles.mission_map='See where governed work is, why it exists, what is expected next, and how evidence and results feed improvement.';

let salcapaMissionMapData=null;
let salcapaMissionMapCatalog=null;
let salcapaMissionMapFilters={functional_area:'',workflow_status:'',attention:'',owner:''};
let salcapaMissionMapSelectedId=null;

function missionMapReducedMotion(){
  return Boolean(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches);
}

function missionMapAnnounce(message){
  const status=$('#mission-map-status');
  if(!status||!message)return;
  status.textContent='';
  window.requestAnimationFrame(()=>{status.textContent=message;});
}

function missionMapRestoreFocus(id){
  if(!id)return;
  window.requestAnimationFrame(()=>{const target=document.getElementById(id);if(target)target.focus();});
}

function missionMapOpenFallback(event){
  event.preventDefault();
  const fallback=$('#mission-map-list');
  if(!fallback)return;
  fallback.open=true;
  const summary=fallback.querySelector('summary');
  if(summary)summary.focus();
  missionMapAnnounce('Conventional Mission Map list opened.');
}

function missionMapOptions(values,current,label){
  return `<option value="">${esc(label)}</option>`+values.map(value=>`<option value="${esc(value)}"${value===current?' selected':''}>${esc(value)}</option>`).join('');
}

function missionMapPortfolio(data){
  const portfolio=data.portfolio||{};
  const attention=portfolio.by_attention||{};
  const evidence=portfolio.by_evidence_state||{};
  return `<section class="card mission-portfolio" aria-labelledby="mission-portfolio-heading"><div class="section-title"><div><span>Authorized portfolio view</span><h3 id="mission-portfolio-heading">Where attention may be needed</h3></div></div><div class="mission-portfolio-grid"><div><strong>${Number(portfolio.total_items||0)}</strong><span>governed items in this view</span></div><div><strong>${Number(attention['Waiting / input needed']||0)}</strong><span>waiting or needing input</span></div><div><strong>${Number(attention['Review / validation needed']||0)}</strong><span>awaiting review or validation</span></div><div><strong>${Number(attention['Decision / coordination needed']||0)}</strong><span>awaiting an authorized decision or coordination step</span></div><div><strong>${Number(attention['Reassessment needed']||0)}</strong><span>needing reassessment</span></div><div><strong>${Number(evidence['Evidence Needed']||0)}</strong><span>with evidence still needed</span></div></div><p class="subtle">${esc(portfolio.interpretation||'')}</p></section>`;
}

function missionMapFilterPanel(catalog){
  return `<section class="card mission-filters" aria-labelledby="mission-filter-heading"><h3 id="mission-filter-heading" class="mission-visually-hidden">Filter this authorized Mission Map view</h3><form onsubmit="event.preventDefault();missionMapApplyFilters()"><div class="mission-filter-grid"><label for="mission-filter-area">Functional area<select id="mission-filter-area" name="functional_area">${missionMapOptions(catalog.functional_areas||[],salcapaMissionMapFilters.functional_area,'All functional areas')}</select></label><label for="mission-filter-status">Workflow state<select id="mission-filter-status" name="workflow_status">${missionMapOptions(catalog.workflow_states||[],salcapaMissionMapFilters.workflow_status,'All workflow states')}</select></label><label for="mission-filter-attention">Attention needed<select id="mission-filter-attention" name="attention">${missionMapOptions(catalog.attention_states||[],salcapaMissionMapFilters.attention,'All attention states')}</select></label><label for="mission-filter-owner">Owner or responsible role<input id="mission-filter-owner" name="owner" maxlength="120" value="${esc(salcapaMissionMapFilters.owner)}" placeholder="All authorized owners" autocomplete="off" /></label></div><div class="mission-filter-actions"><button class="btn secondary" type="submit">Apply filters</button><button class="btn secondary" type="button" onclick="missionMapClearFilters()">Clear</button><button class="btn secondary" type="button" aria-describedby="mission-print-guidance" onclick="missionMapPreparePrint()">Prepare printable view</button></div></form><p class="subtle">${esc(catalog.filter_guidance||'Filters narrow this authorized view without changing the underlying work.')}</p><p class="subtle" id="mission-print-guidance">${esc(catalog.report_guidance||'Printing preserves this authorized view without changing the underlying work.')}</p></section>`;
}

async function missionMapApplyFilters(){
  salcapaMissionMapFilters={
    functional_area:$('#mission-filter-area').value,
    workflow_status:$('#mission-filter-status').value,
    attention:$('#mission-filter-attention').value,
    owner:$('#mission-filter-owner').value.trim(),
  };
  await salcapaMissionMap({announcement:'Filters applied to the authorized Mission Map view.',focusId:'mission-filter-area'});
}

async function missionMapClearFilters(){
  salcapaMissionMapFilters={functional_area:'',workflow_status:'',attention:'',owner:''};
  await salcapaMissionMap({announcement:'Mission Map filters cleared.',focusId:'mission-filter-area'});
}

function missionMapMarkerKey(event){
  const keys=['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'];
  if(!keys.includes(event.key))return;
  const marker=event.currentTarget;
  const route=marker.closest('.mission-route');
  const markers=route?Array.from(route.querySelectorAll('.mission-marker')):[];
  const current=markers.indexOf(marker);
  if(current<0||!markers.length)return;
  event.preventDefault();
  let next=current;
  if(event.key==='Home')next=0;
  else if(event.key==='End')next=markers.length-1;
  else if(event.key==='ArrowRight'||event.key==='ArrowDown')next=Math.min(current+1,markers.length-1);
  else next=Math.max(current-1,0);
  markers[next].focus();
}

function missionMapRoute(route,items){
  const routeItems=items.filter(item=>item.route_key===route.key);
  const cells=route.stations.map(station=>{
    const stationItems=routeItems.filter(item=>item.station===station);
    const markers=stationItems.map(item=>`<button class="mission-marker shape-${esc(item.marker_shape)}" id="mission-marker-${esc(item.id)}" data-mission-id="${esc(item.id)}" type="button" title="${esc(item.title)} — ${esc(item.status)}" aria-label="${esc(item.title)}. ${esc(item.status)}. Current station ${esc(item.station)}." aria-controls="mission-map-detail" aria-expanded="${item.id===salcapaMissionMapSelectedId?'true':'false'}" onkeydown="missionMapMarkerKey(event)" onclick="missionMapDetail('${esc(item.id)}')"><span class="mission-marker-icon" aria-hidden="true"></span><span class="mission-marker-label">${esc(item.title)}</span></button>`).join('');
    return `<div class="mission-station" role="group" aria-label="${esc(station)} station"><div class="mission-station-node" aria-hidden="true"></div><strong>${esc(station)}</strong><div class="mission-station-items">${markers||'<span class="mission-empty">No work here</span>'}</div></div>`;
  }).join('');
  return `<section class="mission-route route-${esc(route.key)}" aria-labelledby="mission-route-${esc(route.key)}"><div class="mission-route-heading"><div><h3 id="mission-route-${esc(route.key)}">${esc(route.label)}</h3><p>${esc(route.description)}</p></div><span>${routeItems.length} item${routeItems.length===1?'':'s'}</span></div><div class="mission-track" role="group" aria-label="${esc(route.label)} workflow route" style="--station-count:${route.stations.length}">${cells}</div></section>`;
}

function missionMapPath(item){
  const parts=[...(item.mission_path||[]),{node_type:item.node_type,title:item.title}];
  return parts.map(part=>`<span><strong>${esc(part.node_type)}</strong> ${esc(part.title)}</span>`).join('<span class="mission-path-arrow" aria-hidden="true">→</span>');
}

function missionMapDetail(id){
  if(!salcapaMissionMapData)return;
  const item=salcapaMissionMapData.items.find(entry=>entry.id===id);
  if(!item)return;
  salcapaMissionMapSelectedId=id;
  document.querySelectorAll('.mission-marker').forEach(marker=>marker.setAttribute('aria-expanded',marker.dataset.missionId===id?'true':'false'));
  const salus=!isProtectedMember();
  const controls=salus&&!item.read_only?`<div class="mission-actions"><button class="btn secondary" onclick="missionMapTransition('${esc(item.id)}')">Record next state</button>${item.visibility!=='Released'?`<button class="btn secondary" onclick="missionMapRelease('${esc(item.id)}')">Release to Protected Member view</button>`:''}</div>`:'';
  const source=item.read_only?`<div><small>Authoritative source</small><p>${esc(item.source_type)} · ${esc(item.source_status)}</p></div>`:'';
  $('#mission-map-detail').innerHTML=`<article class="card mission-detail-card" tabindex="-1" aria-labelledby="mission-detail-heading"><div class="section-title"><div><span class="mission-kicker">${esc(item.functional_area)} · ${esc(item.node_type)}</span><h2 id="mission-detail-heading">${esc(item.title)}</h2></div><span class="mission-neutral-state">${esc(item.status)}</span></div><div class="mission-path" aria-label="Mission Structure path">${missionMapPath(item)}</div><div class="mission-detail-grid"><div><small>Why this work exists</small><p>${esc(item.purpose||'Purpose has not been released or recorded for this view.')}</p></div><div><small>Current location</small><p><strong>${esc(item.station)}</strong> on ${esc(item.functional_area)}</p></div><div><small>Who owns the next step</small><p>${esc(item.owner||'Owner not yet identified')}</p></div><div><small>What is needed now</small><p>${esc(item.waiting_on||'No waiting requirement is currently recorded.')}</p></div><div><small>Expected next step</small><p>${esc(item.next_step||item.next_station||'Review the governed record.')}</p></div><div><small>Evidence / result state</small><p>${esc(item.evidence_state)}${item.result_summary?` — ${esc(item.result_summary)}`:''}</p></div>${source}</div><p class="subtle">${esc(item.projection_basis||item.guidance||'')}</p>${item.projection_basis?`<p class="subtle">${esc(item.guidance||'')}</p>`:''}${salus&&item.authority?`<p class="mission-authority"><strong>Authority:</strong> ${esc(item.authority)}</p>`:''}${controls}</article>`;
  const detail=$('.mission-detail-card');
  detail.scrollIntoView({behavior:missionMapReducedMotion()?'auto':'smooth',block:'nearest'});
  detail.focus({preventScroll:true});
  missionMapAnnounce(`${item.title} details opened.`);
}

function missionMapFallback(data){
  const rows=data.items.map(item=>[
    `<strong>${esc(item.title)}</strong><br><span class="subtle">${esc(item.node_type)}</span>`,
    esc(item.functional_area),esc(item.station),esc(item.status),esc(item.owner||'Not identified'),
    esc(item.next_step||item.next_station||'Review governed record'),esc(item.evidence_state)
  ]);
  return `<details class="card mission-fallback" id="mission-map-list"><summary>Conventional list view</summary><p class="subtle">${esc(data.fallback.description)}</p>${table(['Work item','Area','Current location','State','Next owner','Expected next step','Evidence state'],rows)}</details>`;
}

function missionMapReportFilterSummary(report){
  const labels={functional_area:'Functional area',workflow_status:'Workflow state',attention:'Attention',owner:'Owner or responsible role'};
  const filters=Object.entries(report.active_filters||{}).filter(([,value])=>value);
  return filters.length?filters.map(([key,value])=>`<span><strong>${esc(labels[key]||key)}:</strong> ${esc(value)}</span>`).join(''):'<span>No additional filters applied</span>';
}

function missionMapPrintableReport(data){
  const report=data.report||{};
  const rows=(data.items||[]).map(item=>{
    const path=[...(item.mission_path||[]),{node_type:item.node_type,title:item.title}]
      .map(part=>`${part.node_type}: ${part.title}`).join(' → ');
    const evidence=item.result_summary?`${item.evidence_state} — ${item.result_summary}`:item.evidence_state;
    const source=item.read_only?`${item.source_type||'Governed source'} — ${item.source_status||'Current recorded state'}`:'Mission Structure record';
    return `<tr><td><strong>${esc(item.title)}</strong><br><small>${esc(path)}</small></td><td>${esc(item.purpose||'Purpose is not recorded or released for this view.')}</td><td>${esc(item.functional_area)} · ${esc(item.station)}<br><small>${esc(item.status)}</small></td><td>${esc(item.owner||'Not yet identified')}<br><small>${esc(item.waiting_on||'No waiting requirement is recorded.')}</small></td><td>${esc(item.next_step||item.next_station||'Review the governed record.')}</td><td>${esc(evidence||'Not Applicable')}<br><small>${esc(source)}</small></td></tr>`;
  }).join('');
  return `<section class="mission-print-report" aria-label="Printable Mission Map authorized work summary"><div class="mission-print-version">SalCAPA™ v${esc(report.release_version||'')}</div><header><span>Salus Solutions · SalCAPA™</span><h1>${esc(report.title||'Mission Map — Authorized Work Summary')}</h1><p>${esc(report.status||'Prepared view of governed records')}</p></header><dl class="mission-print-meta"><div><dt>Prepared</dt><dd>${esc(report.prepared_at_display||report.prepared_at||'')}</dd></div><div><dt>Audience</dt><dd>${esc(report.audience||'Authorized view')}</dd></div><div><dt>Scope</dt><dd>${esc(report.scope||'Current authorized view')}</dd></div><div><dt>Items included</dt><dd>${Number(report.included_item_count||0)}</dd></div></dl><div class="mission-print-filters">${missionMapReportFilterSummary(report)}</div><section class="mission-print-governance"><h2>Purpose, authority, and lifecycle</h2><p>${esc(report.authorization_basis||'')}</p><p>${esc(report.governance||'')}</p><p>${esc(report.correction_and_lifecycle||'')}</p></section><section><h2>Current authorized work</h2>${rows?`<table><thead><tr><th>Work and mission path</th><th>Why it exists</th><th>Location and state</th><th>Next owner / requirement</th><th>Expected next step</th><th>Evidence, result, and source</th></tr></thead><tbody>${rows}</tbody></table>`:'<p>No Mission Map items match the current authorized view and filters.</p>'}</section></section>`;
}

function missionMapPreparePrint(){
  if(!salcapaMissionMapData)return;
  document.body.classList.add('mission-map-printing');
  window.addEventListener('afterprint',()=>document.body.classList.remove('mission-map-printing'),{once:true});
  missionMapAnnounce('Printable Mission Map view prepared.');
  window.print();
}

async function salcapaMissionMap(options={}){
  const params=new URLSearchParams();
  if(activeAssessmentId)params.set('assessment_id',Number(activeAssessmentId));
  Object.entries(salcapaMissionMapFilters).forEach(([key,value])=>{if(value)params.set(key,value);});
  const query=params.toString()?`?${params.toString()}`:'';
  const [data,catalog]=await Promise.all([api('/api/salcapa/mission-map'+query),api('/api/salcapa/mission-map/catalog')]);
  salcapaMissionMapData=data;salcapaMissionMapCatalog=catalog;
  const add=!isProtectedMember()?'<button class="btn" onclick="missionMapCreate()">Add Mission Structure item</button>':'';
  $('#content').innerHTML=`<section class="card mission-hero" aria-labelledby="mission-map-heading"><a class="mission-skip-link" href="#mission-map-list" onclick="missionMapOpenFallback(event)">Skip to conventional list view</a><div class="section-title"><div><span>SalCAPA™ way-finding</span><h2 id="mission-map-heading">Mission Map</h2><p>${esc(data.interpretation)}</p></div>${add}</div><div class="mission-structure-summary"><strong>Mission Structure</strong><span>${esc(catalog.mission_structure)}</span></div><p class="subtle">${esc(catalog.principle)} Select any marker to see why it is here, its current location, what is needed, who owns the next step, and what happens next.</p><p class="subtle">${esc(catalog.keyboard_guidance||'')}</p><p class="subtle">${esc(catalog.accessibility_guidance||'')}</p><p class="subtle">${esc(catalog.overlay_guidance||'')}</p></section><div id="mission-map-status" class="mission-visually-hidden" role="status" aria-live="polite" aria-atomic="true"></div>${missionMapFilterPanel(catalog)}${missionMapPortfolio(data)}<div id="mission-map-routes">${data.items.length?data.routes.map(route=>missionMapRoute(route,data.items)).join(''):'<div class="notice">No Mission Map items match the current authorized view and filters.</div>'}</div><div id="mission-map-detail" role="region" aria-live="polite" aria-label="Selected Mission Map item details"></div>${missionMapFallback(data)}${missionMapPrintableReport(data)}`;
  missionMapRestoreFocus(options.focusId);
  missionMapAnnounce(options.announcement);
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
