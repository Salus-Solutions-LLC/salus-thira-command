# SalCAPA v3.28 release notes

## Governed Azure replica-query correction

SalCAPA v3.28 corrects the revision-selection query used only after a failed
development deployment. The numeric JMESPath literal is now passed exactly as
Azure CLI requires, allowing the workflow to identify an existing replica and
capture bounded, redacted application console evidence for the startup failure.

The runtime remains fail-closed. This diagnostic repair does not create
credentials, broaden access, alter DNS, perform a production cutover, or change
the approved development cost boundary.
