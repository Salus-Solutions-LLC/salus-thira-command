(() => {
  'use strict';

  const HUMAN_FIRST_COMMUNICATIONS = Object.freeze({
    principle: 'People lead. Methods guide. Technology supports. Evidence proves.',
    publicDescription: 'Salus people use disciplined methods and purpose-built technology to help Protected Members understand risk, make informed decisions, coordinate action, and improve protective capability.',
    authority: 'Authorized people remain responsible for judgment, decisions, approval, release, and action.',
    disclosure: 'Technology is described plainly when it materially affects privacy, data handling, provenance, cost, contractual obligations, limitations, or decision authority. Prepared work is never presented as human-reviewed, approved, released, or validated until that governed step occurs.',
    preferredLabels: Object.freeze({
      prepare: 'Prepare Draft',
      recommend: 'Recommended Next Step',
      monitor: 'Ongoing Monitoring',
      analyze: 'Review and Analyze'
    })
  });
  window.salcapaHumanFirstCommunications = HUMAN_FIRST_COMMUNICATIONS;

  const PRODUCT_GUIDANCE = [
    {
      key: 'see',
      name: 'SalINTEL™',
      verb: 'See',
      summary: 'Develops qualified intelligence.',
      detail: 'SalINTEL collects, investigates, reconciles, and qualifies information while preserving sources, confidence, contradictions, gaps, and human review.'
    },
    {
      key: 'decide',
      name: 'SalTHIRA™',
      verb: 'Decide',
      summary: 'Identifies risk and establishes priorities; authorized people decide.',
      detail: 'SalTHIRA turns qualified inputs into a defensible risk picture, capability gaps, and priorities. It supports decisions but never replaces the authorized decision-maker.'
    },
    {
      key: 'coordinate',
      name: 'SalCAPA™',
      verb: 'Coordinate',
      summary: 'Coordinates Protected Members, information, decisions, and action.',
      detail: 'SalCAPA keeps the operating picture, decisions, handoffs, requests, status, and authorized releases connected without assuming human authority.'
    },
    {
      key: 'act',
      name: 'SalOPS™',
      verb: 'Act',
      summary: 'Implements, sustains, and improves protective capability.',
      detail: 'SalOPS carries approved work into planning, assignments, operations, preparedness, exercises, evidence of completion, sustainment, and improvement.'
    }
  ];

  const PAGE_GUIDANCE = {
    prove: {
      cue: 'Trace evidence, accountability, results, validation, learning, and improvement across the whole SalCAPA operating model.',
      detail: 'PROVE is a cross-cutting SalCAPA assurance capability, not a separate fifth product. It traces only explicit governed relationships from qualified intelligence through risk, priority, decision, authorized action, execution, evidence, result, validation, and reassessment.'
    },
    monitoring: {
      cue: 'Compare approved sources with a governed baseline without silently expanding the investigation.',
      detail: 'Monitoring is separate from investigation depth. It defaults to No and begins only after an affirmative request or Salus initiation and authorized approval of scope, cadence, sources, recipients, release policy, and commercial treatment.'
    },
    investigation: {
      cue: 'Develop source-grounded intelligence within the exact authorized tier and scope.',
      detail: 'Tier 1, Tier 2, and Tier 3 describe bounded depth and effort—not danger or readiness. A completed tier stops at its authorized scope; unresolved questions remain known unknowns, collection requirements, reassessment triggers, or a recommendation for a deeper tier.'
    },
    assessment: {
      cue: 'Identify risk, capability gaps, consequences, and priorities so authorized people can decide.',
      detail: 'SalTHIRA provides a governed risk picture and defensible priorities. It does not coordinate work and it does not make the decision for the authorized person.'
    },
    operations: {
      cue: 'Implement approved protective work and preserve accountable status and completion evidence.',
      detail: 'SalOPS receives governed operational work. A request or handoff does not itself prove authorization, execution, completion, validation, or release.'
    },
    default: {
      cue: 'Use this workspace within the governed SalCAPA operating model.',
      detail: 'Guidance explains purpose and next steps, but it cannot grant authority, change lifecycle state, disclose information, expand scope, activate monitoring, incur cost, or complete work.'
    }
  };

  const ACTION_GUIDANCE = [
    {
      pattern: /(?:start|request|resume) monitoring/,
      label: 'Before monitoring begins',
      summary: 'Monitoring does not activate automatically.',
      salus: 'Confirm the approved purpose, scope, cadence, dates, sources and exclusions, thresholds, review and release policy, recipients, partner eligibility, and commercial treatment. This action does not change investigation tier or create a charge.',
      member: 'Your request is sent for Salus review. It does not activate monitoring, change an investigation tier, authorize an external partner, or create a charge.'
    },
    {
      pattern: /(?:change|upgrade|authorize|recommend).*(?:tier|investigation)|(?:tier|investigation).*(?:change|upgrade|authorize|recommend)/,
      label: 'Before changing investigation depth',
      summary: 'A tier change expands depth only after Salus authorization.',
      salus: 'Confirm the bounded scope, checklist, deliverable, authority, audit reason, and commercial treatment. Tier is depth and effort—not a risk, danger, or readiness rating.',
      member: 'A recommendation or request does not expand the investigation. Salus must approve the bounded scope, authority, and any commercial treatment first.'
    },
    {
      pattern: /(?:qualify|qualification)/,
      label: 'Before qualification',
      summary: 'Qualification is accountable human judgment, not automatic fact creation.',
      salus: 'Review provenance, source access, reliability, confidence, contradictions, epistemic state, known unknowns, and scope. Technology-assisted content, allegations, and inferred associations do not become verified facts merely through this action.',
      member: 'Only authorized, qualified, and released results enter the Protected Member experience. Internal investigative records and cross-member information remain controlled.'
    },
    {
      pattern: /(?:disclos|release|publish|share with member)/,
      label: 'Before release or disclosure',
      summary: 'Correlation and internal analytical value do not authorize disclosure.',
      salus: 'Confirm tenant, sensitivity, clearance, source restrictions, recognizable identities, disclosure authority, recipient, purpose, and the exact approved version. Cross-Protected-Member identifiable disclosure requires explicit Salus approval.',
      member: 'You will receive only the exact version and content authorized for your role and clearance. A record existing in SalCAPA does not by itself make it releasable.'
    },
    {
      pattern: /(?:approve|reviewed|mark reviewed)/,
      label: 'Before governance approval',
      summary: 'Approval changes accountable lifecycle state.',
      salus: 'Verify the current version, supporting evidence, authority, scope, unresolved gaps, downstream effects, and required separation of duties. Approval does not automatically release, disclose, execute, or charge.',
      member: 'This action is governed by your role and the record lifecycle. Approval does not automatically disclose information or prove that operational work occurred.'
    },
    {
      pattern: /(?:create|generate).*(?:assurance|package|report)/,
      label: 'Before creating an assurance package',
      summary: 'The package is a server-derived, immutable snapshot of authorized records.',
      salus: 'Confirm tenant, purpose, package type, scope, and intended audience. Creation starts a governed Draft; it does not review, approve, release, or fill missing traceability links.',
      member: 'Protected Members receive only packages explicitly approved and released for their role and clearance; package creation remains Salus-controlled.'
    },
    {
      pattern: /(?:handoff|send to salops|create.*request|assign|dispatch)/,
      label: 'Before an operational handoff',
      summary: 'A handoff creates governed work; it does not authorize or complete it.',
      salus: 'Confirm the qualified source, authorized purpose, tenant, sensitivity, requested action, responsible role, and required approval. The receiving SalOPS workflow retains its own authority and completion controls.',
      member: 'Your request enters a governed coordination and review process. It does not itself authorize execution, guarantee acceptance, or mark work complete.'
    },
    {
      pattern: /(?:complete|close|validate)/,
      label: 'Before completion or validation',
      summary: 'Completion and validation are distinct claims and require supporting evidence.',
      salus: 'Confirm required scope, checklist, evidence, exceptions, human qualification, known unknowns, downstream handoffs, and reassessment needs. Do not treat workflow progress alone as proof of improved safety or readiness.',
      member: 'Completion records what was done; validation establishes what the evidence supports. Remaining gaps and reassessment needs stay visible.'
    },
    {
      pattern: /(?:price|charge|commercial|authorize amount|approve estimate)/,
      label: 'Before a commercial decision',
      summary: 'SalCAPA never creates a charge automatically.',
      salus: 'Confirm authorization, engagement terms, scope, tier or monitoring treatment, amount, rationale, and audit record before proceeding.',
      member: 'Requests and recommendations do not automatically create charges. Any commercial treatment must be explicitly authorized under the engagement.'
    }
  ];

  let scheduled = false;

  function normalize(value) {
    return String(value || '').replace(/[™®]/g, '').trim().toLowerCase();
  }

  function isSalus() {
    return Boolean(document.querySelector('#nav [data-salus-only="true"]:not([hidden])'));
  }

  function pageKey() {
    const title = normalize(document.getElementById('page-title')?.textContent);
    const active = normalize(document.querySelector('#nav button.active')?.dataset.view);
    const value = `${title} ${active}`;
    if (value.includes('prove') || value.includes('assurance')) return 'prove';
    if (value.includes('monitor')) return 'monitoring';
    if (value.includes('investig') || value.includes('personnel') || value.includes('facility')) return 'investigation';
    if (value.includes('assessment') || value.includes('risk') || value.includes('salthira')) return 'assessment';
    if (value.includes('operation') || value.includes('request') || value.includes('salops') || value.includes('preparedness')) return 'operations';
    return 'default';
  }

  function detailMarkup(title, summary, detail) {
    return `<details class="salcapa-context-detail"><summary>${title}</summary><p><strong>Purpose.</strong> ${summary}</p><p><strong>Authority and next step.</strong> ${detail}</p></details>`;
  }

  function operatingModelMarkup() {
    const cards = PRODUCT_GUIDANCE.map(product => `
      <article class="salcapa-doctrine-card salcapa-doctrine-${product.key}">
        <span>${product.verb}</span><h4>${product.name}</h4><p>${product.summary}</p>
        <details><summary>How this function fits</summary><p>${product.detail}</p></details>
      </article>`).join('');
    return `
      <section class="salcapa-doctrine" aria-label="SalCAPA operating model">
        <p class="salcapa-doctrine-intro"><strong>${HUMAN_FIRST_COMMUNICATIONS.principle}</strong> Four connected functions support one governed operating model. Authorized people retain decision authority.</p>
        <div class="salcapa-doctrine-grid">${cards}</div>
        <article class="salcapa-prove-band">
          <strong>PROVE — Assurance &amp; Results</strong>
          <p>Cross-cutting evidence, accountability, results, validation, traceability, learning, and improvement across See, Decide, Coordinate, and Act.</p>
          <details><summary>What PROVE traces</summary><p>Qualified intelligence → risk and priority → authorized decision → authorized action → execution → evidence → result and validation → reassessment. Missing governed links remain visible gaps; SalCAPA never invents causality or completion.</p></details>
        </article>
      </section>`;
  }

  function enhanceLifecycle() {
    const prove = document.querySelector('#lifecycle-strip [data-stage="prove"]');
    if (prove) {
      prove.dataset.view = 'prove';
      prove.title = 'Cross-cutting evidence, accountability, results, validation, learning, and improvement';
      const description = prove.querySelector('span');
      if (description && description.textContent !== 'Assure every function') description.textContent = 'Assure every function';
      prove.setAttribute('aria-label', 'Prove. Cross-cutting assurance across See, Decide, Coordinate, and Act.');
    }
    const decide = document.querySelector('#lifecycle-strip [data-stage="decide"] span');
    if (decide && decide.textContent !== 'Risk and priorities; people decide') decide.textContent = 'Risk and priorities; people decide';
    const coordinate = document.querySelector('#lifecycle-strip [data-stage="coordinate"] span');
    if (coordinate && coordinate.textContent !== 'SalCAPA aligns people and action') coordinate.textContent = 'SalCAPA aligns people and action';
  }

  function enhancePageCue() {
    const subtitle = document.getElementById('page-subtitle');
    if (!subtitle) return;
    const key = pageKey();
    const guide = PAGE_GUIDANCE[key];
    let cue = document.getElementById('salcapa-page-guidance');
    if (!cue) {
      cue = document.createElement('div');
      cue.id = 'salcapa-page-guidance';
      cue.className = 'salcapa-page-guidance';
      subtitle.insertAdjacentElement('afterend', cue);
    }
    if (cue.dataset.key === `${key}:${isSalus()}`) return;
    cue.dataset.key = `${key}:${isSalus()}`;
    cue.innerHTML = `<span>${guide.cue}</span>${detailMarkup('Purpose, authority, and next step', guide.cue, guide.detail)}`;
  }

  function actionFor(button) {
    const text = normalize(`${button.textContent} ${button.getAttribute('aria-label') || ''}`);
    return ACTION_GUIDANCE.find(item => item.pattern.test(text));
  }

  function enhanceActions() {
    document.querySelectorAll('#content button:not([data-context-guidance]), #content input[type="submit"]:not([data-context-guidance])').forEach(button => {
      button.dataset.contextGuidance = 'checked';
      const guide = actionFor(button);
      if (!guide) return;
      const container = button.closest('form, .card, .assurance-actions, .monitoring-actions, section') || button.parentElement;
      if (!container) return;
      const key = guide.label.replace(/[^a-z0-9]+/gi, '-').toLowerCase();
      if (container.querySelector(`[data-action-guidance="${key}"]`)) return;
      const note = document.createElement('aside');
      note.className = 'salcapa-action-guidance';
      note.dataset.actionGuidance = key;
      note.setAttribute('aria-label', guide.label);
      note.innerHTML = detailMarkup(guide.label, guide.summary, isSalus() ? guide.salus : guide.member);
      button.insertAdjacentElement('beforebegin', note);
    });
  }

  function rewriteDrawer() {
    const drawer = document.getElementById('guidance-drawer');
    const body = document.getElementById('guidance-body');
    if (!drawer || !body || !drawer.classList.contains('open')) return;
    const key = pageKey();
    const guide = PAGE_GUIDANCE[key];
    const role = isSalus() ? 'Salus personnel' : 'Protected Member';
    document.getElementById('guidance-title').textContent = 'How SalCAPA Works';
    document.getElementById('guidance-subtitle').textContent = `${role} guidance for ${document.getElementById('page-title')?.textContent || 'this workspace'}`;
    body.innerHTML = `
      <div class="guidance-panel salcapa-role-guidance">
        <span class="guidance-kicker">You are here</span>
        <h3>${document.getElementById('page-title')?.textContent || 'SalCAPA'}</h3>
        <p><strong>What is this?</strong> ${guide.cue}</p>
        <p><strong>Why it matters.</strong> ${guide.detail}</p>
        <p><strong>What happens next?</strong> Use only the actions available to your role. Guidance cannot grant authority, change lifecycle state, disclose information, expand scope, activate monitoring, incur cost, or establish completion.</p>
      </div>
      <div class="guidance-panel salcapa-role-guidance">
        <span class="guidance-kicker">How the work is performed</span>
        <h3>${HUMAN_FIRST_COMMUNICATIONS.principle}</h3>
        <p>${HUMAN_FIRST_COMMUNICATIONS.publicDescription}</p>
        <p><strong>Human authority.</strong> ${HUMAN_FIRST_COMMUNICATIONS.authority}</p>
        <details><summary>When technology use is explained</summary><p>${HUMAN_FIRST_COMMUNICATIONS.disclosure}</p></details>
      </div>
      ${operatingModelMarkup()}`;
  }

  function hookHelp() {
    document.querySelectorAll('#guidance-trigger, .guidance-nav-help, .help-dot').forEach(button => {
      if (button.dataset.canonicalGuidance) return;
      button.dataset.canonicalGuidance = 'true';
      button.addEventListener('click', () => window.setTimeout(rewriteDrawer, 0));
    });
  }

  function enhance() {
    enhanceLifecycle();
    enhancePageCue();
    enhanceActions();
    hookHelp();
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      enhance();
    });
  }

  function init() {
    enhance();
    const main = document.querySelector('.main');
    if (main) new MutationObserver(schedule).observe(main, {childList: true, subtree: true, characterData: true});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
