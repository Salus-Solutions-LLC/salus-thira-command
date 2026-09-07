/* SalCAPA display doctrine: day month year, 24-hour time, and no engineering metadata. */
(() => {
  const months = [
    'January','February','March','April','May','June',
    'July','August','September','October','November','December'
  ];
  const pad = value => String(value).padStart(2, '0');
  const render = (year, month, day, hour, minute, utc) => {
    const date = `${Number(day)} ${months[Number(month) - 1]} ${year}`;
    return hour === undefined ? date : `${date} ${pad(hour)}:${pad(minute)}${utc ? ' UTC' : ''}`;
  };
  window.salcapaFormatDateTime = value => {
    const raw = String(value || '').trim();
    let match = raw.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$/);
    if (match) return render(match[1], match[2], match[3], match[4], match[5], match[6] === 'Z');
    match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    return match ? render(match[1], match[2], match[3]) : raw;
  };
  const formatText = node => {
    if (!node || node.nodeType !== Node.TEXT_NODE || !node.nodeValue) return;
    const parent = node.parentElement;
    if (!parent || /^(SCRIPT|STYLE|TEXTAREA|INPUT|OPTION|CODE|PRE)$/.test(parent.tagName)) return;
    let value = node.nodeValue.replace(
      /\b(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?\b/g,
      (_all, year, month, day, hour, minute, zone) =>
        render(year, month, day, hour, minute, zone === 'Z')
    );
    value = value.replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g,
      (_all, year, month, day) => render(year, month, day));
    if (value !== node.nodeValue) node.nodeValue = value;
  };
  const formatTree = root => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(formatText);
  };
  const start = () => {
    formatTree(document.body);
    new MutationObserver(records => records.forEach(record =>
      record.addedNodes.forEach(node => {
        if (node.nodeType === Node.TEXT_NODE) formatText(node);
        else if (node.nodeType === Node.ELEMENT_NODE) formatTree(node);
      })
    )).observe(document.body, { childList: true, subtree: true });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
