(function(){
  viewTitles.demo_environments='Demonstration Environments';
  subtitles.demo_environments='Inspect the three governed fictional Protected Member environments without changing identity or tenant authority.';

  function environmentOptions(rows){
    return rows.map((row,index)=>`<option value="${index}">${esc(row.name)}</option>`).join('');
  }

  function list(items, renderItem){
    return items.length?`<ul>${items.map(renderItem).join('')}</ul>`:'<p class="subtle">No records prepared.</p>';
  }

  function detail(environment){
    const assessment=environment.assessments[0]||{};
    const counts=environment.counts||{};
    return `<div class="card cop-hero"><span>${esc(environment.label)}</span><h2>${esc(environment.name)}</h2><p>${esc(environment.purpose)}</p></div>
      <div class="grid stats cop-stats">
        ${metric('Intelligence records',environment.intelligence.length)}
        ${metric('Threats and hazards',counts.threats_and_hazards||0)}
        ${metric('Capability records',counts.capabilities||0)}
        ${metric('Improvement actions',counts.improvement_actions||0)}
      </div>
      <div class="grid two-col">
        <div class="card"><h3>Protected Member context</h3><p><strong>Sector:</strong> ${esc(environment.sector)}<br><strong>Environment:</strong> ${esc(environment.status)}<br><strong>Assessment:</strong> ${esc(assessment.name||'Awaiting preparation')}<br><strong>Assessment state:</strong> ${esc(assessment.status||'Evidence Needed')}</p><p>${esc(assessment.mission||'')}</p></div>
        <div class="card"><h3>Evidence and authority</h3><p>This is a read-only evaluation view. It does not sign you in as a fictional person, change your authenticated tenant, or grant decision authority.</p><p class="subtle">Fixture ${esc(environment.fixture_version)}</p></div>
      </div>
      <div class="grid two-col">
        <div class="card"><h3>SalINTEL — information for review</h3>${list(environment.intelligence,item=>`<li><strong>${esc(item.title)}</strong><br><span class="subtle">${esc(item.status)} · ${esc(item.credibility)} · ${esc(item.validation_status)}</span></li>`)}</div>
        <div class="card"><h3>SalTHIRA — assessment basis</h3><p>${counts.threats_and_hazards||0} threat or hazard record(s), ${counts.capabilities||0} capability record(s), ${counts.evidence_records||0} evidence record(s), and ${counts.improvement_actions||0} improvement action(s).</p><p class="subtle">Authorized people establish priorities and decisions; this display does not.</p></div>
        <div class="card"><h3>SalCAPA — coordination and decisions</h3>${list(environment.coordination,item=>`<li><strong>${esc(item.subject)}</strong><br><span class="subtle">${esc(item.status)} · ${esc(item.assigned_contact_summary||'Awaiting assignment')}</span></li>`)}${list(environment.decisions,item=>`<li><strong>${esc(item.title)}</strong><br><span class="subtle">${esc(item.status)}${item.decision?' · '+esc(item.decision):' · Awaiting authorized review'}</span></li>`)}</div>
        <div class="card"><h3>SalOPS and PROVE</h3>${list(environment.operations,item=>`<li><strong>${esc(item.title)}</strong><br><span class="subtle">${esc(item.priority)} · ${esc(item.status)}</span></li>`)}<p class="subtle">${environment.reports.length} governed report version(s). Evidence, traceability, results, learning, and improvement remain cross-cutting.</p></div>
      </div>`;
  }

  async function render(){
    const data=await api('/api/demonstration-environments');
    if(!data.environments.length){
      $('#content').innerHTML='<div class="notice">The governed fictional demonstration environments are not prepared in this deployment.</div>';
      return;
    }
    $('#content').innerHTML=`<div class="card"><div class="section-title"><div><h2>Demonstration Environments</h2><p class="subtle">${esc(data.label)} · ${esc(data.access_mode)}</p></div><label>Environment<select id="demo-environment-select">${environmentOptions(data.environments)}</select></label></div><div class="notice">${data.boundaries.map(esc).join('<br>')}</div></div><div id="demo-environment-detail"></div>`;
    const select=$('#demo-environment-select');
    const show=()=>{$('#demo-environment-detail').innerHTML=detail(data.environments[Number(select.value)||0]);};
    select.onchange=show;
    show();
  }

  window.SalusDemoEnvironments={render};
})();

