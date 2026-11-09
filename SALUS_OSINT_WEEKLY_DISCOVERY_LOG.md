# Salus OSINT Weekly Discovery Log

**Authority:** SAL-D123–SAL-D124. **Handling:** Salus Internal Confidential. **Purpose:** durable evidence for the required weekly worldwide OSINT source-discovery, work-triggered topic expansion and endpoint-register maintenance. **Schedule:** active Codex heartbeat `weekly-salus-osint-source-expansion`, Mondays at 09:00 America/Chicago.

## Completion and counting rule

A scheduled invocation is not a completed run. Completion requires a dated log entry with the exact authoritative source commit, scheduled and actual start/end times, countries/areas and source families screened, queries or directory routes, new/changed/superseded/unavailable dispositions, access barriers, unresolved queue, validations, candidate pull request when applicable and the report delivered to Marc.

The authoritative list total is the number of unique absolute HTTP or HTTPS destinations in `SALUS_OSINT_GLOBAL_ENDPOINT_REGISTER.md` endpoint-table entries after canonicalization. Count a destination once even if it has multiple labels, functions or appearances. Do not count duplicate aliases. Retain superseded and unavailable addresses with their status and replacement lineage unless a separately governed decision removes them from the historical register.

Every completed run tells Marc:

- total unique addresses on the authoritative register;
- addresses added to the authoritative register since the prior completed run;
- addresses changed, relocated or redirected;
- addresses superseded;
- addresses unavailable after permitted recheck;
- candidate addresses pending governed review and merge; and
- material access, cost, rights, security or unresolved-search limits.

## Initial inventory and schedule activation

| Record | Authoritative commit | Address total | Added | Changed | Superseded | Unavailable | Pending review | Evidence and status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Initial inventory baseline; 2 November 2026 Central | `62bf383dc158aed76f45382ddd691917d470ab1b` | 93 | 0 | 0 | 0 | 0 | 0 | 81 endpoint entries and 93 unique table addresses recomputed from the authoritative register; schedule created active. This is a baseline, not a completed weekly discovery run. |

## Weekly run entries

For each run, add one row and supporting notes. Use `YYYY-MM-DD-WNN` as the run ID, where `NN` distinguishes reruns in the same week.

| Run ID | Scheduled / actual Central time | Exact source commit | Search boundary and routes | Total addresses | Added | Changed | Superseded | Unavailable | Pending review | Candidate PR / validation | Limitations and next proof |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| `2026-11-09-W01` | Scheduled 9 November 2026 09:00; actual discovery 10:21–10:55 CST | `3f089616b8c7736cbf4d0add2964d33afb9f05b9` | UN Member State and UN M49 baseline screened through worldwide authority/data directories; hazard/alert/feed, health, cyber/digital, law/governance, finance/economy, research/method and work-triggered payment/OIDC routes; details below. | 93 | 0 | 0 | 0 | 0 | 20 | [PR #1183](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/1183); 98 endpoint rows/IDs, 113 candidate-state unique addresses, table checks and `git diff --check` passed; repository checks pending. | Candidate merge would raise the total to 113. WMO XML feeds were confirmed from the register but not parsed by the browser extractor; UN Data Commons and some IAEA content require JavaScript or may require sign-in. Country-level linked artifacts remain a bounded follow-up queue. |

### 2026-11-09-W01 supporting evidence

- **Authoritative startup:** read the current Charter, Decision Register, Current Handoff, Approved Artifacts, startup protocol, OSINT Sources Library, Global Endpoint Register and this log from `development/salcapa-platform`. The exact source head was `3f089616b8c7736cbf4d0add2964d33afb9f05b9`. The deployed Level 1A state and other release state remain as recorded in the authoritative handoff; this run changed no production, connector, credential, Member record or deployment.
- **Jurisdiction boundary:** the 193 UN Member States, the two observer States where represented, and UN M49 countries/areas were screened at the global-directory level. The run did not assert that every country page, subpage or file was individually reviewed. Routes included WMO alerting-authority country records; UNDRR global loss/data systems; WHO global/regional outbreak routes; ITU Member State strategies; UNODC country data; FATF global-network jurisdiction reports; IMF country financial-system assessments; World Bank economy/governance profiles; UN System Data Commons; and IAEA country-information directories.
- **Exact query and directory routes:** `site:un.org OR site:worldbank.org official global country profiles open data portal directory API 2026 disaster risk governance`; `site:wmo.int official alerting authorities register CAP feeds global countries`; `site:usgs.gov global earthquake feeds API official OR site:noaa.gov global hazard datasets feeds`; `site:undrr.org official disaster loss database country profiles API 2026`; `site:data.un.org official UN System Data Commons 2026 statistics countries`; `site:who.int official disease outbreak news RSS API global 2026`; `site:itu.int official national cybersecurity strategies repository countries 2026`; `site:unodc.org official global data portal crime trafficking corruption countries API`; `site:pcisecuritystandards.org official PCI DSS document library standards 2026`; `site:openid.net official OpenID Connect specifications discovery certification security best current practice`; `site:nist.gov digital identity guidelines SP 800-63 revision 4 official 2025`; `site:stripe.com/docs live test mode API keys webhooks security official documentation`; `site:fatf-gafi.org official mutual evaluations country reports jurisdictions 2026`; `site:imf.org official financial sector assessment country reports data 2026`; `site:worldbank.org official Worldwide Governance Indicators 2026 data`; and `site:iaea.org official country nuclear safety profiles emergency preparedness database`.
- **Work-triggered topics:** reviewed new governed work since the 2 November baseline at the member-neutral level: research-capture/print-legibility standards, aligned Federal report footers, Knowledge Library consideration and receipts, Level 1A buyer/staff pilot evidence, live/test payment separation, payment-security controls and customer OIDC. The payment and OIDC topics produced Stripe, PCI SSC, NIST and OpenID candidates. No Protected Member name, answer, file, private location, vulnerability, relationship, credential or Salus-confidential value was submitted to a public service.
- **Candidate disposition:** 20 unique public HTTPS addresses in 17 stable endpoint records were added only to the candidate branch: WMO Register/RSS/Atom (3), USGS feeds (1), UNDRR APIs/DELTA (2), WHO outbreak page/API documentation (2), ITU strategies (1), NIST digital identity (1), OpenID specifications (1), Stripe keys (1), PCI SSC library (1), UNODC data (1), FATF evaluations (1), IMF FSAP (1), World Bank WGI/ESG (2), UN Data Commons (1), and IAEA country information (1). All remain `Unvetted Candidate` pending checks, Marc's exact-head approval and merge.
- **Access and link evidence:** 18 HTML/Markdown entry points opened at the HTTP/content layer. The WMO page directly exposed the RSS and Atom addresses; the browser extractor declined their XML content type, so feed contents were not reviewed. No paywall, credential or paid query was used; no binary was downloaded; no active reconnaissance, person query, automated crawl or prohibited bypass occurred.
- **Unresolved queue and next proof:** qualify terms, license, rate and automation conditions before collection; follow country-specific WMO CAP feeds and authority records only when relevant; verify national originals and effective dates for ITU, FATF and IAEA links; assess WHO API stability and write-method exposure before any integration; inspect exact PCI/NIST/OpenID versions for applicable Level 1A controls; run repository validations, open the governed PR, obtain exact-head approval and merge before changing the authoritative address count.

## Work-triggered topic-expansion queue

For every new white paper, customer inquiry, Protection Advisor Part 1, consented Part 2, assessment and other material explicit or inferred topic, record candidate addresses here until they are reconciled into a governed register update. Use member-neutral topic labels and never place Protected Member or Salus-confidential detail in this shared ledger.

| Work trigger and date | Member-neutral topic labels | Source families and routes screened | Candidate addresses | Duplicates | Access barriers / unresolved proof | Register candidate or disposition |
|---|---|---|---:|---:|---|---|

No SAL-D124 work-triggered candidate address is pending at this baseline.
