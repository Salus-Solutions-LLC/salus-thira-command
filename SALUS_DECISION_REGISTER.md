# Salus Solutions — Decision Register

| ID | Decision | Status |
|---|---|---|
| SAL-D001 | GitHub is the authoritative technical source of truth. | Approved |
| SAL-D002 | The program architecture is Protected Members, SalCAPA, SalINTEL, SalTHIRA, and SalOPS. | Approved |
| SAL-D003 | The client term is “Protected Members.” | Approved |
| SAL-D004 | Salus THIRA uses the approved six-step method in the Program Charter. | Approved |
| SAL-D005 | Protection Advisor uses a two-part structure: anonymous Part 1 and authenticated detailed Part 2. | Approved |
| SAL-D006 | Protection Advisor information is retained indefinitely under the approved policy. | Approved |
| SAL-D007 | Protection Advisor scoring reflects the five mission areas and 32 core capabilities. | Approved |
| SAL-D008 | Service recommendations vary by answers and use Levels 1, 2, and 3. | Approved |
| SAL-D009 | Assessments define bounded Initial Pass, Focused Assessment, and Deep Dive levels. | Approved |
| SAL-D010 | The polished Protection Advisor example report is the reporting design and content authority. | Approved 22 September 2026 |
| SAL-D011 | The public Print or Save action, governed DOCX, and governed PDF must carry substantively consistent professional report content. | Approved 22 September 2026 |
| SAL-D012 | Raw questionnaire dumps, browser printouts, JSON, and internal report-contract material are not client reports. | Approved 22 September 2026 |
| SAL-D013 | Governed Protection Advisor reports are stored in SharePoint under Protected Member Reports / SalCAPA Generated Reports. | Approved |
| SAL-D014 | Existing governed report filenames should be overwritten when regenerating the same report; do not create duplicates. | Approved |
| SAL-D015 | Protective Intelligence updates occur on the tenth day of each month. | Approved |
| SAL-D016 | Use “See, Decide, Coordinate, Act, Prove” in the SalCAPA top bar. | Approved |
| SAL-D017 | Use day-month-year dates and 24-hour time in SalCAPA. | Approved |
| SAL-D018 | Default operating model is Chat first; use Work/Codex for executable software and deployments by exception. | Approved |
| SAL-D019 | Approved artifacts must be inspected directly and must not be reconstructed from chat memory. | Approved 22 September 2026 |
| SAL-D020 | OneDrive `SalCAPA Intake / 10 Pending Classification` is the governed staging queue. SalCAPA may automatically capture and inventory candidates, but promotion into SharePoint `Salus Knowledge Sources` requires human classification approval, destination verification, provenance retention, and duplicate controls. Source removal occurs only after verified promotion and separate retained authorization. | Superseded by SAL-D021 on 22 September 2026 |
| SAL-D021 | SalCAPA automatically classifies and promotes low-risk, high-confidence knowledge after destination upload and SHA-256 verification. Sensitive, duplicate, conflicting, unsupported, superseded, restricted, or low-confidence material requires human exception review. Verified sources move to `90 Processed Intake` and are not deleted. | Superseded by SAL-D022 on 23 September 2026 |
| SAL-D022 | Every file beneath OneDrive `SalCAPA Intake / 10 Pending Classification` is automatically captured, hash-bound, fully processed through the available safe extraction chain, classified, indexed as knowledge, copied and SHA-256 verified in the mapped SharePoint knowledge folder, and then moved to `90 Processed Intake`. Format, sensitivity, duplication, external authorship, ownership uncertainty, conflict, restriction, or low confidence become metadata flags and never create an ingestion exception or require human ingestion approval. Processing limitations trigger automatic retries. Originals and citation metadata are retained indefinitely and files are never automatically deleted. Human authority remains required only for consequential use such as external publication, Protected Member disclosure, final findings, formal recommendations, risk acceptance, and methodology changes. | Approved 23 September 2026 |

| SAL-D023 | Large batches of nested files and folders are a required SalCAPA intake capability for Salus and Protected Member work. Each item must be durably discoverable, processable without starvation or silent skip, source-bound and auditable, and recoverable after partial failure. Protected Member sources remain segregated by member and engagement; intake does not approve cross-member reuse, findings, or disclosure. Implementation and acceptance are tracked in Issue #520. | Approved by Marc, 24 September 2026 |

| SAL-D024 | Marc clarified on 25 September 2026 that the existing OneDrive `SalCAPA Intake / 10 Pending Classification` Salus folder and its nested backlog contain Salus material for enterprise knowledge processing. Bulk customer material has a separate sibling staging folder, `40 Customer Batch Staging - Unassigned`, and must remain outside enterprise promotion until its member/engagement route and access are accepted. This supersedes the 25 September mixed-backlog routing assumption recorded in the handoff and issue #520; it does not waive source verification, hash/provenance, extraction limits, customer isolation, or governed release acceptance. | Approved 25 September 2026 |

| SAL-D025 | Salus shall operate as a governed, cumulative learning system across Protected Members, sectors, domains and derivatives. Every authorized engagement and service should capture and test transferable methods, strategies, objectives, tactics, resources, laws and regulations, competing-resource dependencies, outcomes and lessons; approved knowledge should inform later research, assessment and operations, and later evidence should revise or supersede it. Preserve source provenance, applicability, confidence, currency, restrictions, review and version history. Generalize member-neutral lessons for enterprise reuse; cross-engagement correlation does not authorize automatic cross-Protected-Member disclosure. Identifiable customer information or sensitive derivatives require a specific lawful purpose, access and human disclosure approval. Human authority remains required for methodology changes, final findings, recommendations, risk acceptance and publication. The collection boundary and unresolved blind spots must remain explicit; no work may claim exhaustive knowledge without evidence. | Approved by Marc, 27 September 2026 |

## Register maintenance rule

Add a dated entry whenever Marc approves a material change to terminology, architecture, methodology, governance, report design, data handling, release policy, or customer experience. Never silently replace an approved decision; mark it superseded and reference the new decision.
