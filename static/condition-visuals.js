(() => {
  const CONDITION_STATES = [
    {key:'critical', cls:'condition-critical', symbol:'!', terms:['critical','extreme','severe','unsafe','dangerous','failed','not ready','deficient']},
    {key:'high', cls:'condition-high', symbol:'!', terms:['high risk','high','major degradation']},
    {key:'elevated', cls:'condition-elevated', symbol:'▲', terms:['elevated','serious','poor']},
    {key:'guarded', cls:'condition-guarded', symbol:'▲', terms:['guarded','moderate','caution','limited','partially ready']},
    {key:'improving', cls:'condition-improving', symbol:'●', terms:['improving','adequate','recovering']},
    {key:'ready', cls:'condition-ready', symbol:'✓', terms:['ready','safe','normal','resilient','low risk','low']}
  ];

  const EXCLUDED_WORKFLOW_TERMS = new Set([
    'approved','approve','rejected','deferred','awaiting decision','awaiting approval',
    'draft','analysis','client validation','implementation','validation','active monitoring',
    'evidence collection','sme review','salus qa','findings finalized','executive decisions',
    'scope approved','open','closed','current','verified','stale'
  ]);

  function normalize(value){
    return String(value || '').trim().toLowerCase().replace(/\s+/g,' ');
  }

  function stateFor(label){
    const text = normalize(label);
    if(!text || EXCLUDED_WORKFLOW_TERMS.has(text)) return null;
    for(const state of CONDITION_STATES){
      if(state.terms.includes(text)) return state;
    }
    return null;
  }

  function enhanceBadge(badge){
    if(!(badge instanceof HTMLElement) || badge.dataset.conditionEnhanced === 'true') return;
    const label = badge.textContent.trim();
    const state = stateFor(label);
    badge.dataset.conditionEnhanced = 'true';
    if(!state) return;
    badge.classList.add(state.cls);
    badge.setAttribute('data-condition-state', state.key);
    badge.setAttribute('title', `${label}: Salus condition/readiness indicator. Color supplements the text and symbol; it does not represent workflow completion.`);
    const symbol = document.createElement('span');
    symbol.className = 'condition-symbol';
    symbol.setAttribute('aria-hidden', 'true');
    symbol.textContent = state.symbol;
    badge.prepend(symbol);
    badge.setAttribute('aria-label', `${label} condition`);
  }

  function enhanceConditionBadges(root=document){
    root.querySelectorAll?.('.badge').forEach(enhanceBadge);
  }

  enhanceConditionBadges();
  const observer = new MutationObserver(records => {
    for(const record of records){
      for(const node of record.addedNodes){
        if(!(node instanceof HTMLElement)) continue;
        if(node.matches?.('.badge')) enhanceBadge(node);
        enhanceConditionBadges(node);
      }
    }
  });
  observer.observe(document.documentElement, {childList:true, subtree:true});

  window.SalusConditionVisuals = Object.freeze({
    stateFor,
    states: CONDITION_STATES.map(({key, cls, symbol}) => ({key, cls, symbol}))
  });
})();
