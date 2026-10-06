/* Wix custom embed, BODY_START. Keep this source identical to the published embed. */
(function () {
  'use strict';

  var key = '__salusProtectionAdvisorLoading20261006';
  var existing = window[key];
  if (existing) {
    existing.activate();
    return;
  }

  var advisorOrigin = 'https://salcapa.salus.solutions';
  var advisorPath = '/protection-advisor/embed';
  var pagePath = '/protection-advisor';
  var frame = null;
  var readyFrame = null;
  var panel = null;
  var timer = null;
  var finder = null;
  var attempts = 0;

  function removePanel() {
    if (timer !== null) {
      window.clearTimeout(timer);
      timer = null;
    }
    if (panel && panel.parentNode) panel.parentNode.removeChild(panel);
    panel = null;
  }

  function clearFinder() {
    if (finder !== null) {
      window.clearInterval(finder);
      finder = null;
    }
    attempts = 0;
  }

  function findFrame() {
    return Array.from(document.querySelectorAll('iframe[src]')).find(function (item) {
      try {
        var url = new URL(item.src);
        return url.origin === advisorOrigin && url.pathname === advisorPath;
      } catch (_) {
        return false;
      }
    }) || null;
  }

  function showTimeout() {
    if (!panel) return;
    panel.setAttribute('aria-busy', 'false');
    var message = panel.querySelector('[data-salus-loading-message]');
    message.textContent = 'Protection Advisor is taking longer than expected. You can keep waiting or open it directly.';
    var link = document.createElement('a');
    link.href = advisorOrigin + advisorPath;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = 'Open Protection Advisor';
    link.style.cssText = 'display:inline-block;margin-top:8px;color:#285b7b;text-decoration:underline;font-weight:700;';
    panel.appendChild(link);
    var dismiss = document.createElement('button');
    dismiss.type = 'button';
    dismiss.textContent = 'Dismiss';
    dismiss.style.cssText = 'margin-left:16px;border:0;background:transparent;color:#285b7b;text-decoration:underline;cursor:pointer;font:inherit;';
    dismiss.addEventListener('click', function () {
      readyFrame = frame;
      removePanel();
    });
    panel.appendChild(dismiss);
  }

  function mount(found) {
    if (found === readyFrame) return;
    if (frame === found && panel) return;
    removePanel();
    frame = found;
    var host = found.closest('[id^="comp-"]');
    if (!host) return;

    panel = document.createElement('div');
    panel.id = 'salus-protection-advisor-loading';
    panel.setAttribute('role', 'status');
    panel.setAttribute('aria-live', 'polite');
    panel.setAttribute('aria-busy', 'true');
    panel.style.cssText = 'position:absolute;top:12px;left:50%;transform:translateX(-50%);box-sizing:border-box;width:calc(100% - 24px);max-width:650px;z-index:10;background:#fff;border:2px solid #427799;border-radius:7px;box-shadow:0 3px 12px rgba(0,0,0,.15);padding:14px 18px;color:#1b2934;font:16px/1.45 Arial,sans-serif;text-align:center;';
    var message = document.createElement('span');
    message.setAttribute('data-salus-loading-message', '');
    message.textContent = 'Loading Protection Advisor. Please wait.';
    panel.appendChild(message);
    host.appendChild(panel);
    timer = window.setTimeout(showTimeout, 60000);
  }

  function locate() {
    if (window.location.pathname !== pagePath) {
      frame = null;
      readyFrame = null;
      removePanel();
      clearFinder();
      return;
    }
    var found = findFrame();
    if (found) {
      clearFinder();
      mount(found);
    } else if (++attempts >= 120) {
      clearFinder();
    }
  }

  function activate() {
    if (window.location.pathname !== pagePath) {
      locate();
      return;
    }
    if (finder === null) finder = window.setInterval(locate, 250);
    locate();
  }

  window.addEventListener('message', function (event) {
    if (!frame) frame = findFrame();
    if (!frame || event.origin !== advisorOrigin || event.source !== frame.contentWindow) return;
    var data = event.data;
    if (!data || data.type !== 'salus-protection-advisor-height' || data.source !== 'protection-advisor') return;
    readyFrame = frame;
    removePanel();
  });

  window[key] = { activate: activate };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', activate, { once: true });
  else activate();
}());

