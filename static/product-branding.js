(() => {
  const term = (name, description) => Object.freeze({ name, description });
  window.SalusProductTerms = Object.freeze({
    salcapa: term('SalCAPA™', 'Secure coordination and Common Operating Picture'),
    salintel: term('SalINTEL™', 'Intelligence and investigations'),
    salthira: term('SalTHIRA™', 'Risk assessment and prioritization'),
    salops: term('SalOPS™', 'Operations, readiness, and protective services')
  });
})();
