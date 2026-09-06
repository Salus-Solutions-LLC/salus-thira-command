# SalCAPA v3.36 Release Notes

## Governed Add Information capture

SalCAPA now provides a persistent, role-aware **Add Information** entry point for
authorized write roles. Users can preserve pasted or entered text through the
existing tenant-scoped intake workflow and upload multiple source files through
the existing governed evidence attachment path.

The capture surface records source/context, purpose, descriptive notes, and an
optional user-supplied recording or possession authority/consent basis. Existing
server controls remain authoritative for authorization, tenant and sensitivity
scope, file size, filename/storage safety, malware policy, hashing, retention,
legal hold, audit, and Azure/local storage.

Submission preserves source material as a draft or governed attachment. It does
not create verified evidence, qualified intelligence, a SalTHIRA finding, an
executive decision, or operational authority. Client input cannot set lifecycle,
verification, tenant, authority, calculated, audit, or release state.

The entry point is removed when the active identity lacks write permission and
an open intake dialog closes if access is lost. Keyboard focus, Escape-to-close,
touch/click operation, responsive layout, and print suppression are retained.

This release is the first UI slice of the broader universal-ingestion program.
Generic material records, derived extraction/transcription, cross-component
links, corpus search, processing status, and synthetic multi-format exercises
remain separately governed follow-on capabilities.
