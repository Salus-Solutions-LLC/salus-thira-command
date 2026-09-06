(() => {
  const pageGuides = {
    'command center': {
      summary: 'Your role-aware operating picture. Start here to see what requires attention, coordinate with Salus, and move approved work forward.',
      why: 'The Command Center brings together persisted intelligence, assessment priorities, operations, decisions, evidence-linked results, and member coordination without changing the authority of the source records.'
    },
    'common operating picture': {
      summary: 'A shared, tenant-isolated picture of what is known, what matters now, and what authorized action is underway.',
      why: 'Use this workspace to connect information across SalINTEL, SalTHIRA, and SalOPS while keeping decisions and approvals traceable.'
    },
    'intelligence': {
      summary: 'Qualified information that may affect the Protected Member’s people, mission, operations, assets, facilities, or continuity.',
      why: 'SalINTEL develops information through research, qualification, validation, provenance, confidence, and lifecycle controls before it is relied upon for decisions.'
    },
    'assessments': {
      summary: 'Controlled SalTHIRA workspaces for identifying threats and hazards, understanding context, establishing capability targets, assessing capability, identifying gaps, and describing impact.',
      why: 'Assessment records convert evidence into defensible priorities while preserving source traceability and accountable professional judgment.'
    },
    'requests & operations': {
      summary: 'Governed SalOPS requests, assignments, approvals, handoffs, status, completion evidence, and operational outcomes.',
      why: 'Use this workspace to turn approved priorities into accountable action without bypassing authority, tenant isolation, or evidence requirements.'
    },
    'reports': {
      summary: 'Executive and operational reporting generated from authoritative SalCAPA records.',
      why: 'Reports are the Prove stage: they show what was known, decided, done, evidenced, closed, and carried forward for reassessment.'
    },
    'risk': {
      summary: 'Calculated risk remains intact while accountable professional judgment is documented separately.',
      why: 'Use this view to understand exposure, consequences, and recorded judgment without silently overwriting calculated results.'
    },
    'priorities': {
      summary: 'Transparent ranking of improvements and actions across consequence reduction, mission benefit, feasibility, sustainability, compliance, staffing, cost, and time.',
      why: 'Prioritization helps decision-makers compare competing actions using a repeatable, reviewable basis.'
    },
    'evidence': {
      summary: 'Controlled evidence with provenance, verification, validity, lifecycle review, and stale-evidence reassessment.',
      why: 'Evidence supports findings and decisions. Lifecycle state is server controlled so ordinary edits cannot manufacture currency or verification.'
    },
    'governance': {
      summary: 'Workflow transitions, scope approvals, assessment versions, and revision history.',
      why: 'Governance preserves who had authority to change what, when the change occurred, and how the record evolved.'
    },
    'audit': {
      summary: 'Governed activity and version history for accountable review.',
      why: 'Audit records help reconstruct significant actions without depending on memory or editable narrative.'
    },
    'backups': {
      summary: 'Integrity-verified backup packages, recovery controls, and restore safeguards.',
      why: 'Recovery controls are designed to preserve governed state and prevent a restore from silently changing tenancy, authority, provenance, or lifecycle.'
    }
  };

  const fieldHelp = {
    'credibility': 'How believable and dependable the information is based on the available source and validation record.',
    'confidence': 'How strongly the current evidence supports the analytic conclusion. Confidence is not the same as consequence or priority.',
    'classification': 'The handling level assigned to the record. Access remains role-aware and tenant-scoped.',
    'status': 'The governed lifecycle position of this record. A normal edit must not manufacture a protected status transition.',
    'evidence': 'Information or material linked to a finding, decision, action, or validation record with controlled provenance and lifecycle.',
    'valid until': 'The date through which evidence may be treated as current before lifecycle review or staleness rules apply.',
    'reassessment': 'A governed trigger to reconsider an assessment because conditions, intelligence, incidents, exercises, evidence, or implemented improvements changed.',
    'priority': 'The urgency or relative importance of attention based on the applicable governed method and source records.',
    'residual exposure': 'The exposure that remains after existing controls, decisions, or improvements are considered.',
    'authorized amount': 'The amount an authorized decision-maker approved. It is server-controlled decision state, not a client-calculated total.',
    'assessment': 'The controlled SalTHIRA engagement or assessment context to which this record is linked.'
  };

  const navHelp = {
    'command center': 'Open the SalCAPA™ role-aware operating picture.',
    'common operating picture': 'Use SalCAPA™ to see cross-component priorities, coordination, decisions, and current action.',
    'reports': 'Review SalCAPA™ released executive and operational reporting.',
    'intelligence overview': 'Review qualified SalINTEL™ information and alerts.',
    'investigative domains': 'Develop and govern SalINTEL™ investigations across authorized domains.',
    'risk assessments': 'Work with SalTHIRA™ assessments, risks, gaps, capabilities, and recommendations.',
    'operations & requests': 'Track governed SalOPS™ requests, tasks, handoffs, action, and results.'
  };

  const stages = [
    ['see', 'See', 'Understand what is known', 'dashboard'],
    ['decide', 'Decide', 'Assess and prioritize', 'assessments'],
    ['coordinate', 'Coordinate', 'Align people and authority', 'common_operating_picture'],
    ['act', 'Act', 'Execute approved work', 'salops'],
    ['prove', 'Prove', 'Evidence, report, reassess', 'reports']
  ];

  let lastFocus = null;
  let observerPending = false;

  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }

  function currentTitle() {
    const node = document.getElementById('page-title');
    return node ? node.textContent.trim() : 'Command Center';
  }

  function normalize(value) {
    return String(value || '').trim().toLowerCase();
  }

  function guideForTitle(title) {
    const key = normalize(title).replace(/[™®]/g, '').replace(/^(salcapa|salintel|salthira|salops)\s+/, '');
    if (pageGuides[key]) return pageGuides[key];
    if (key.includes('assessment')) return pageGuides.assessments;
    if (key.includes('intelligence') || key.includes('salintel')) return pageGuides.intelligence;
    if (key.includes('operation') || key.includes('salops') || key.includes('implementation')) return pageGuides['requests & operations'];
    if (key.includes('report')) return pageGuides.reports;
    if (key.includes('evidence') || key.includes('attachment')) return pageGuides.evidence;
    if (key.includes('audit')) return pageGuides.audit;
    if (key.includes('govern')) return pageGuides.governance;
    if (key.includes('backup') || key.includes('recovery')) return pageGuides.backups;
    return {
      summary: 'This workspace is part of the governed SalCAPA operating environment.',
      why: 'Use the page-level description, contextual help, and lifecycle strip to understand what belongs here and the next authorized step.'
    };
  }

  function currentStage() {
    const title = normalize(currentTitle());
    if (title.includes('intelligence') || title.includes('salintel') || title.includes('threat')) return 'see';
    if (title.includes('assessment') || title.includes('risk') || title.includes('priorit') || title.includes('gap') || title.includes('capabil') || title.includes('scenario')) return 'decide';
    if (title.includes('operation') || title.includes('request') || title.includes('salops') || title.includes('implementation')) return 'act';
    if (title.includes('report') || title.includes('audit') || title.includes('govern') || title.includes('backup') || title.includes('reassess')) return 'prove';
    return 'coordinate';
  }

  function isSalusWorkspaceVisible() {
    return Boolean(document.querySelector('#nav [data-salus-only="true"]:not([hidden])'));
  }

  function go(view) {
    if (typeof window.setView === 'function') {
      window.setView(view);
      return;
    }
    const button = document.querySelector(`#nav button[data-view="${view}"]`);
    if (button && !button.hidden) button.click();
  }

  function ensureShell() {
    if (document.getElementById('salcapa-guidance-root')) return;
    const root = document.createElement('div');
    root.id = 'salcapa-guidance-root';
    root.innerHTML = `
      <div class="guidance-overlay" id="guidance-overlay" aria-hidden="true"></div>
      <aside class="guidance-drawer" id="guidance-drawer" aria-hidden="true" aria-labelledby="guidance-title" role="dialog" aria-modal="true">
        <div class="guidance-drawer-header">
          <div><h2 id="guidance-title">How SalCAPA Works</h2><p id="guidance-subtitle">Contextual guidance for this workspace</p></div>
          <button type="button" class="guidance-close" id="guidance-close" aria-label="Close help">×</button>
        </div>
        <div class="guidance-drawer-body" id="guidance-body"></div>
      </aside>`;
    document.body.appendChild(root);

    const topbar = document.querySelector('.topbar');
    if (topbar) {
      const existingStatus = topbar.querySelector('.status-pill');
      const actions = document.createElement('div');
      actions.className = 'topbar-actions';
      if (existingStatus) actions.appendChild(existingStatus);
      const help = document.createElement('button');
      help.type = 'button';
      help.className = 'guidance-trigger';
      help.id = 'guidance-trigger';
      help.textContent = 'Help / How SalCAPA Works';
      help.setAttribute('aria-haspopup', 'dialog');
      help.addEventListener('click', () => openHelp('page'));
      actions.appendChild(help);
      topbar.appendChild(actions);
    }

    const main = document.querySelector('.main');
    const content = document.getElementById('content');
    if (main && content) {
      const orientation = document.createElement('section');
      orientation.className = 'guidance-orientation';
      orientation.id = 'guidance-orientation';
      orientation.setAttribute('aria-label', 'SalCAPA orientation');
      orientation.innerHTML = '<nav class="guidance-breadcrumbs" id="guidance-breadcrumbs" aria-label="Breadcrumb"></nav><div class="lifecycle-strip" id="lifecycle-strip" aria-label="SalCAPA lifecycle"></div>';
      main.insertBefore(orientation, content);
    }

    const nav = document.getElementById('nav');
    if (nav) {
      const help = document.createElement('button');
      help.type = 'button';
      help.className = 'guidance-nav-help';
      help.textContent = 'How SalCAPA Works';
      help.addEventListener('click', () => openHelp('overview'));
      nav.appendChild(help);
    }

    document.getElementById('guidance-close').addEventListener('click', closeHelp);
    document.getElementById('guidance-overlay').addEventListener('click', closeHelp);
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && document.getElementById('guidance-drawer').classList.contains('open')) closeHelp();
    });
  }

  function renderOrientation() {
    const title = currentTitle();
    const breadcrumbs = document.getElementById('guidance-breadcrumbs');
    if (breadcrumbs) {
      const rootLabel = isSalusWorkspaceVisible() ? 'Salus workspace' : 'Protected Member';
      const assessmentId = Number(localStorage.getItem('salus_assessment_id') || 0);
      const assessmentPart = assessmentId && normalize(title).includes('assessment') ? `<span class="crumb-sep">›</span><span>Assessment ${assessmentId}</span>` : '';
      breadcrumbs.innerHTML = `<button type="button" data-guidance-home>${esc(rootLabel)}</button><span class="crumb-sep">›</span><span class="crumb-current">${esc(title)}</span>${assessmentPart}`;
      const home = breadcrumbs.querySelector('[data-guidance-home]');
      if (home) home.addEventListener('click', () => go('dashboard'));
    }

    const strip = document.getElementById('lifecycle-strip');
    if (strip) {
      const active = currentStage();
      strip.innerHTML = stages.map(([key,label,description,view]) => `
        <button type="button" class="lifecycle-step ${key === active ? 'active' : ''}" data-stage="${key}" data-view="${view}" title="${esc(description)}">
          <strong>${label}</strong><span>${description}</span>
        </button>`).join('');
      strip.querySelectorAll('button').forEach(button => button.addEventListener('click', () => go(button.dataset.view)));
    }
  }

  function enhanceNavigation() {
    document.querySelectorAll('#nav button[data-view]').forEach(button => {
      const key = normalize(button.textContent);
      const text = navHelp[key];
      if (!text) return;
      button.title = text;
      button.setAttribute('aria-label', `${button.textContent.trim()}. ${text}`);
    });
  }

  function directLabelText(label) {
    return Array.from(label.childNodes)
      .filter(node => node.nodeType === Node.TEXT_NODE)
      .map(node => node.textContent.trim())
      .filter(Boolean)
      .join(' ');
  }

  function helpTextForLabel(labelText) {
    const key = normalize(labelText);
    if (fieldHelp[key]) return fieldHelp[key];
    const match = Object.keys(fieldHelp).find(item => key.includes(item));
    return match ? fieldHelp[match] : '';
  }

  function enhanceFields() {
    document.querySelectorAll('#content label:not([data-guidance-enhanced])').forEach(label => {
      const labelText = directLabelText(label);
      const text = helpTextForLabel(labelText);
      label.dataset.guidanceEnhanced = 'true';
      if (!text || !labelText) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'help-dot';
      button.textContent = '?';
      button.title = text;
      button.setAttribute('aria-label', `Help for ${labelText}`);
      button.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        openHelp('field', {label: labelText, text});
      });
      label.insertBefore(button, label.firstElementChild || null);
    });
  }

  function contextForEmptyCell(cell) {
    const section = cell.closest('.card, .cop-stage, section, div');
    if (!section) return 'This area';
    const heading = section.querySelector('h2, h3');
    return heading ? heading.textContent.trim() : 'This area';
  }

  function enhanceEmptyStates() {
    document.querySelectorAll('#content td.subtle:not([data-guidance-empty])').forEach(cell => {
      if (normalize(cell.textContent) !== 'no records yet.') return;
      cell.dataset.guidanceEmpty = 'true';
      cell.classList.add('guidance-empty');
      const context = contextForEmptyCell(cell);
      cell.innerHTML = `<strong>No records yet</strong><span>${esc(context)} will appear here when an authorized record reaches this workspace. Use the available governed action on this page to begin; SalCAPA will preserve required authority, tenant, provenance, lifecycle, and audit controls.</span>`;
    });

    document.querySelectorAll('#content .card.subtle:not([data-guidance-empty])').forEach(card => {
      if (!normalize(card.textContent).startsWith('no ')) return;
      card.dataset.guidanceEmpty = 'true';
      card.classList.add('guidance-empty');
      const original = card.textContent.trim();
      card.innerHTML = `<strong>${esc(original.replace(/\.$/, ''))}</strong><span>When authorized activity begins, its persisted status and next governed action will appear here.</span>`;
    });
  }

  function overviewMarkup() {
    return `
      <div class="guidance-panel">
        <span class="guidance-kicker">Operating model</span>
        <h3>Protected Member centered by design</h3>
        <p>Protected Members share priorities, requests, observations, concerns, and operational context. SalCAPA™ coordinates the work; SalINTEL™ develops qualified intelligence; SalTHIRA™ assesses risk and establishes defensible priorities; SalOPS™ implements, sustains, and improves approved capability.</p>
        <div class="guidance-brand-grid" aria-label="Salus product terminology">
          <div><strong>SalCAPA™</strong><span>Secure coordination and Common Operating Picture</span></div>
          <div><strong>SalINTEL™</strong><span>Intelligence and investigations</span></div>
          <div><strong>SalTHIRA™</strong><span>Risk assessment and prioritization</span></div>
          <div><strong>SalOPS™</strong><span>Operations, readiness, and protective services</span></div>
        </div>
      </div>
      <img class="guidance-graphic" src="/static/assets/how-salcapa-works.svg" alt="Diagram showing Protected Members connected through SalCAPA to SalINTEL, SalTHIRA and SalOPS" />
      <div class="guidance-panel" style="margin-top:14px">
        <span class="guidance-kicker">Lifecycle</span>
        <h3>See → Decide → Coordinate → Act → Prove</h3>
        <div class="guidance-steps">
          <div class="guidance-step-card"><span>1</span><div><strong>See</strong><p>Collect observations and develop qualified intelligence with source, confidence, validation, and lifecycle context.</p></div></div>
          <div class="guidance-step-card"><span>2</span><div><strong>Decide</strong><p>Use SalTHIRA to understand threats, hazards, vulnerabilities, dependencies, consequences, capabilities, gaps, and priorities.</p></div></div>
          <div class="guidance-step-card"><span>3</span><div><strong>Coordinate</strong><p>Bring the right Protected Member and Salus roles together around persisted priorities, messages, requests, decisions, and authority.</p></div></div>
          <div class="guidance-step-card"><span>4</span><div><strong>Act</strong><p>Move authorized work into SalOPS assignments, handoffs, operational support, completion evidence, and exceptions.</p></div></div>
          <div class="guidance-step-card"><span>5</span><div><strong>Prove</strong><p>Preserve evidence, audit/version history, reports, closure, lessons learned, and reassessment triggers.</p></div></div>
        </div>
      </div>`;
  }

  function pageMarkup() {
    const title = currentTitle();
    const guide = guideForTitle(title);
    return `
      <div class="guidance-panel">
        <span class="guidance-kicker">You are here</span>
        <h3>${esc(title)}</h3>
        <p><strong>What is this?</strong> ${esc(guide.summary)}</p>
        <p><strong>Why it matters.</strong> ${esc(guide.why)}</p>
        <p><strong>What happens next?</strong> Use the lifecycle strip above the workspace or the authorized actions visible on this page. SalCAPA will not use a help or navigation shortcut to bypass required approvals, role checks, tenant isolation, lifecycle, provenance, evidence, or audit controls.</p>
      </div>
      ${overviewMarkup()}`;
  }

  function fieldMarkup(data) {
    return `
      <div class="guidance-panel guidance-field-focus">
        <span class="guidance-kicker">Field help</span>
        <h3>${esc(data.label)}</h3>
        <p><strong>What is this?</strong> ${esc(data.text)}</p>
        <p><strong>Why it matters.</strong> This value contributes context to governed records and should be interpreted with the surrounding source, role, lifecycle, evidence, and authority controls.</p>
      </div>
      ${pageMarkup()}`;
  }

  function openHelp(mode, data) {
    ensureShell();
    lastFocus = document.activeElement;
    const drawer = document.getElementById('guidance-drawer');
    const overlay = document.getElementById('guidance-overlay');
    const body = document.getElementById('guidance-body');
    const title = document.getElementById('guidance-title');
    const subtitle = document.getElementById('guidance-subtitle');
    title.textContent = mode === 'field' ? `${data.label} help` : 'How SalCAPA Works';
    subtitle.textContent = mode === 'overview' ? 'The Salus operating model and user journey' : `Guidance for ${currentTitle()}`;
    body.innerHTML = mode === 'overview' ? overviewMarkup() : mode === 'field' ? fieldMarkup(data) : pageMarkup();
    drawer.classList.add('open');
    overlay.classList.add('open');
    drawer.setAttribute('aria-hidden', 'false');
    overlay.setAttribute('aria-hidden', 'false');
    document.getElementById('guidance-close').focus();
    localStorage.setItem('salcapa_guidance_seen', '1');
  }

  function closeHelp() {
    const drawer = document.getElementById('guidance-drawer');
    const overlay = document.getElementById('guidance-overlay');
    if (!drawer || !overlay) return;
    drawer.classList.remove('open');
    overlay.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
    overlay.setAttribute('aria-hidden', 'true');
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
  }

  function enhance() {
    renderOrientation();
    enhanceNavigation();
    enhanceFields();
    enhanceEmptyStates();
  }

  function scheduleEnhance() {
    if (observerPending) return;
    observerPending = true;
    requestAnimationFrame(() => {
      observerPending = false;
      enhance();
    });
  }

  function init() {
    ensureShell();
    enhance();
    const target = document.querySelector('.main');
    if (target) new MutationObserver(scheduleEnhance).observe(target, {childList: true, subtree: true, characterData: true});
    if (!localStorage.getItem('salcapa_guidance_seen')) {
      window.setTimeout(() => openHelp('page'), 700);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
