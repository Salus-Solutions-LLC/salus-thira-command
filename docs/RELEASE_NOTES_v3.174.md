# SalCAPA 3.174 Release Notes

SalCAPA 3.174 keeps exact knowledge originals eligible for hash-verified promotion and archive even when derived extraction needs an automatic retry. After archive, a later scan retries extraction from the same hash-checked original while retaining the original citation identity. A failed or changed archived source remains a visible retry obligation.

The isolated PDF worker now accepts an empty page annotation array as inert structure. Declared actions, rich media, actual annotations, embedded files, encrypted PDFs, and unsafe content remain blocked from derived extraction. The real four-page pending PDF was inspected without executing PDF features and extracted locally through the corrected worker.

This release does not change Microsoft 365 permissions. Live ingestion remains incomplete until the SalCAPA application's site-scoped destination write receives the required authority and the two pending files pass end-to-end hash, archive, and citation verification.
