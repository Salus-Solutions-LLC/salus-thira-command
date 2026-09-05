# SalCAPA v3.15 release notes

## Governed PostgreSQL administrator lifecycle repair

- Replaces the unavailable hosted-runner PostgreSQL `ad-admin` extension command with the stable Azure Resource Manager administrator REST resource.
- Creates the transient managed-identity database administrator by exact object ID, tenant ID, principal name, and `ServicePrincipal` type.
- Verifies the exact administrator resource before the private Container Apps bootstrap job starts.
- Isolates cleanup in a subshell so fail-closed shell behavior remains active throughout provisioning and execution.
- Deletes and verifies removal of the transient administrator, bootstrap job, and managed identity on success or failure.
- Retains immutable image verification, passwordless authentication, server-controlled Entra user mapping, least-privilege runtime grants, and demonstration-data suppression.

The failed v3.14 bootstrap created no SalCAPA application deployment. This repair does not change DNS, create a client secret or database password, or perform public production cutover.
