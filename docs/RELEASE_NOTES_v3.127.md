# SalCAPA v3.127 release notes

## Canonical Wix Protection Advisor

- Makes `https://www.salus.solutions/protection-advisor` the canonical public Protection Advisor page.
- Redirects the legacy `/protection-advisor` application route to the Wix page, including requests made through the Azure-native hostname.
- Keeps `/protection-advisor/embed` as the internal Wix frame surface without a duplicate Salus header, menu, or footer.
- Preserves all public assessment APIs, administrator review routes, consent controls, retention controls, and the v3.126 Microsoft Entra callback.
- Adds no Entra, Graph, Azure, or Wix permission expansion.
