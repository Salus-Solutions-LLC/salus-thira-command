# SalCAPA v3.27 release notes

## Revision-targeted Azure startup evidence

SalCAPA v3.27 corrects the governed Azure system-log query to use the JSON
format required by Azure Container Apps. When the current revision cannot scale
from zero, the workflow now identifies revisions that actually have replicas and
captures bounded, redacted console evidence from the specific revision and
replica instead of asking Azure for logs from a nonexistent latest replica.

The diagnostic path remains read-only after deployment failure. It does not
create credentials, broaden access, alter DNS, perform a production cutover, or
change the approved development cost boundary.
