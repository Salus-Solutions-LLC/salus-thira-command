# SalCAPA v3.26 release notes

## Evidence-driven Azure runtime diagnostics

SalCAPA v3.26 makes failed Azure Container Apps startup verification
evidence-driven. If the immutable development runtime does not become ready,
the governed deployment records a non-secret revision-state summary and bounded,
redacted system and container logs. System logs remain available even when Azure
has not created a replica, closing the diagnostic gap that previously returned
only `Could not find a replica for this app`.

The deployment remains immutable-digest based, passwordless, restricted to the
approved development resource group, bounded by the existing cost controls, and
unchanged with respect to DNS and public production cutover.
