# SalCAPA v3.136

## Trusted SharePoint intake download redirects

- Accepts Microsoft Graph content redirects only when they use HTTPS and terminate on a SharePoint Online `.sharepoint.com` host.
- Rejects userinfo-bearing, non-HTTPS, missing-host, and non-SharePoint redirect locations.
- Prevents the Microsoft Graph bearer token from being forwarded to the redirected download host.
- Preserves exact governed-folder membership checks and metadata/content size verification.
- Adds deterministic regression coverage for trusted redirect success and untrusted redirect denial.
