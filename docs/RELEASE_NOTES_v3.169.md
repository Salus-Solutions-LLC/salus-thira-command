# SalCAPA 3.169 Release Notes

## Automatic complete knowledge processing

SalCAPA 3.169 processes every file placed beneath `OneDrive / SalCAPA Intake / 10 Pending Classification` without an ingestion exception queue or human ingestion approval.

- Every source is captured with Microsoft identity, eTag/cTag, timestamps, owner, modifier, size, MIME type, trusted URL, and SHA-256.
- The full available safe-processing chain extracts text and accessible components from inert text, Office Open XML, PDF, images, and audio/video.
- Structured citation metadata preserves document title, authors, source dates, source location, version identifiers, SHA-256 citation key, and format-appropriate locators.
- Duplicates, sensitivity indicators, restrictions, external authorship, ambiguous classification, and other concerns become searchable metadata flags and never block ingestion.
- Ambiguous material defaults to `05 Research and Reference`.
- Processing limitations create automatic retry obligations rather than human exceptions.
- A scheduled processor scans every 60 seconds when governed Microsoft 365 configuration is complete.
- Promoted bytes are independently SHA-256 verified before the source moves to `90 Processed Intake`.
- Originals and citation metadata are retained indefinitely; files are never automatically deleted.

Human authority remains required for consequential use and disclosure, including external publication, Protected Member disclosure, final findings, formal recommendations, risk acceptance, and methodology changes.

Rollback target: SalCAPA 3.168.
