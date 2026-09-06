(() => {
  const target = document.getElementById('salcapa-version');
  if (!target) return;

  const normalizeVersion = value => {
    const raw = String(value || '').trim();
    if (!raw) return '';
    return raw.replace(/^v/i, '');
  };

  async function renderProductVersion() {
    try {
      const response = await fetch('/api/system/mode', { cache: 'no-store' });
      if (!response.ok) throw new Error('version unavailable');
      const mode = await response.json();
      const version = normalizeVersion(mode.version || mode.app_version || mode.release_version);
      if (!version) {
        target.hidden = true;
        return;
      }
      target.textContent = `SalCAPA™ v${version}`;
      target.setAttribute('aria-label', `SalCAPA version ${version}`);
      target.setAttribute('title', `SalCAPA™ version ${version}`);
      target.hidden = false;
    } catch (_error) {
      target.hidden = true;
    }
  }

  renderProductVersion();
})();
