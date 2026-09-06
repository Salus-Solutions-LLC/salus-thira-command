/* SalCAPA Protected Member capability posture dashboard component. */
(function(global){
  function esc(value){
    return String(value == null ? '' : value).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});
  }
  function gauge(area){
    const unknown=area.score == null || area.band === 'Unknown';
    const score=unknown ? 0 : Math.max(0,Math.min(100,Number(area.score)));
    const label=unknown ? 'Unknown' : score.toFixed(1);
    return `<section class="salcapa-posture-gauge band-${esc(area.band).toLowerCase().replace(/[^a-z]+/g,'-')}" aria-label="${esc(area.mission_area)} capability posture">
      <div class="salcapa-posture-gauge-head"><strong>${esc(area.mission_area)}</strong><span>${esc(area.band)}</span></div>
      <div class="salcapa-posture-meter" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${unknown?'':score}" aria-valuetext="${esc(area.band)} ${esc(label)}">
        <div class="salcapa-posture-fill" style="width:${score}%"></div>
      </div>
      <div class="salcapa-posture-gauge-foot"><span class="score">${esc(label)}</span><span>Confidence: ${esc(area.confidence)}</span></div>
      <div class="salcapa-posture-gauge-foot"><span>${Number(area.capability_count||0)} capabilities</span><span>${Number(area.material_gap_count||0)} material gaps</span></div>
    </section>`;
  }
  function actionRows(actions){
    if(!actions.length) return '<div class="salcapa-posture-empty">No readiness action is currently prioritized.</div>';
    return `<div class="salcapa-posture-actions" role="list">${actions.map(function(a){
      const score=a.score==null?'Unknown':Number(a.score).toFixed(1);
      return `<div class="salcapa-posture-action" role="listitem">
        <div><strong>${esc(a.capability_name)}</strong><span>${esc(a.mission_area)} · Score ${esc(score)} · Confidence ${esc(a.confidence)}</span></div>
        <div><span>Next action</span><strong>${esc(a.recommended_action)}</strong></div>
      </div>`;
    }).join('')}</div>`;
  }
  function render(container,payload){
    if(!container) throw new Error('Capability posture container is required');
    const overall=payload && payload.overall ? payload.overall : {score:null,band:'Unknown',confidence:'Low'};
    const unknown=overall.score == null || overall.band === 'Unknown';
    const overallLabel=unknown ? 'Unknown' : Number(overall.score).toFixed(1);
    const areas=(payload && payload.mission_areas)||[];
    const actions=(payload && payload.prioritized_actions)||[];
    container.innerHTML=`<div class="salcapa-posture" data-status="${esc(payload&&payload.status||'Unknown')}">
      <header class="salcapa-posture-summary">
        <div><div class="eyebrow">Protected Member Capability Posture</div><h2>${esc(payload&&payload.protected_member_name||'Protected Member')}</h2></div>
        <div class="salcapa-posture-overall" aria-label="Overall capability posture">
          <span class="overall-score">${esc(overallLabel)}</span><strong>${esc(overall.band)}</strong><span>Confidence: ${esc(overall.confidence)}</span>
        </div>
      </header>
      <div class="salcapa-posture-grid">${areas.map(gauge).join('')}</div>
      <div class="salcapa-posture-context">
        <div><span>Strongest area</span><strong>${esc(payload&&payload.strongest_area||'Unknown')}</strong></div>
        <div><span>Weakest area</span><strong>${esc(payload&&payload.weakest_area||'Unknown')}</strong></div>
        <div><span>Material gaps</span><strong>${Number(payload&&payload.material_gap_count||0)}</strong></div>
        <div><span>Scoring version</span><strong>${esc(payload&&payload.scoring_version||'—')}</strong></div>
      </div>
      <section class="salcapa-posture-next"><div class="section-title"><h3>Prioritized Readiness Actions</h3><span>Decision support — authorization required</span></div>${actionRows(actions)}</section>
      <div class="salcapa-posture-note">Capability posture reflects current demonstrated capability and evidence confidence. Documentation or training alone does not establish demonstrated capability. Recommended actions do not authorize work or spending.</div>
    </div>`;
  }
  async function load(container,assessmentId,api){
    const request=api || (async function(url){const r=await fetch(url,{credentials:'same-origin'});if(!r.ok) throw new Error('Unable to load capability posture');return r.json();});
    const payload=await request(`/api/capability-posture/${encodeURIComponent(assessmentId)}`);
    render(container,payload); return payload;
  }
  global.SalCAPACapabilityPosture={render:render,load:load};
})(window);
