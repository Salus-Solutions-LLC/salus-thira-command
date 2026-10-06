/* Wix custom embed: BODY_START, ESSENTIAL, loadOnce=false. */
(function () {
  'use strict';

  if (window.__salusAdvisorLoader) window.__salusAdvisorLoader.cancel();
  if (window.location.pathname !== '/protection-advisor') return;

  var origin = 'https://salcapa.salus.solutions';
  var path = '/protection-advisor/embed';
  var frame = null;
  var note = null;
  var ready = false;
  var poll = null;
  var delay = null;
  var limit = null;

  function findFrame() {
    return Array.from(document.querySelectorAll('iframe[src]')).find(function (item) {
      try {
        var url = new URL(item.src);
        return url.origin === origin && url.pathname === path;
      } catch (_) { return false; }
    }) || null;
  }

  function clear() {
    if (poll) window.clearInterval(poll);
    if (delay) window.clearTimeout(delay);
    if (limit) window.clearTimeout(limit);
    if (note) note.remove();
    window.removeEventListener('message', onMessage);
    poll = delay = limit = note = null;
  }

  function onMessage(event) {
    frame = frame || findFrame();
    if (!frame || event.origin !== origin || event.source !== frame.contentWindow) return;
    if (event.data && event.data.type === 'salus-protection-advisor-height' && event.data.source === 'protection-advisor') {
      ready = true;
      clear();
    }
  }

  window.__salusAdvisorLoader = { cancel: clear };
  window.addEventListener('message', onMessage);

  function show() {
    if (ready || !frame) return;
    var host = frame.closest('[id^="comp-"]');
    if (!host) return;
    note = document.createElement('div');
    note.textContent = 'Protection Advisor is loading...';
    note.setAttribute('role', 'status');
    note.setAttribute('aria-live', 'polite');
    var visibleWidth = Math.min(host.clientWidth, Math.max(0, window.innerWidth - Math.max(0, host.getBoundingClientRect().left)));
    var noteWidth = Math.max(160, Math.min(650, visibleWidth - 24));
    var noteLeft = Math.max(12, (visibleWidth - noteWidth) / 2);
    note.style.cssText = 'position:absolute;top:12px;left:' + noteLeft + 'px;box-sizing:border-box;width:' + noteWidth + 'px;z-index:10;background:#fff;border:2px solid #427799;border-radius:7px;padding:14px 18px;color:#1b2934;font:16px/1.45 Arial,sans-serif;text-align:center;';
    host.appendChild(note);
  }

  poll = window.setInterval(function () {
    frame = findFrame();
    if (!frame || ready) return;
    window.clearInterval(poll);
    poll = null;
    delay = window.setTimeout(show, 10000);
    limit = window.setTimeout(clear, 60000);
  }, 100);
  window.setTimeout(function () { if (poll) window.clearInterval(poll); }, 10000);
}());

