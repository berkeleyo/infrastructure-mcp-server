# Runbook

## Start and verify

Create the venv, install the reviewed dependencies, and run `scripts/verify.sh`. Start with
`INFRA_MCP_CONFIG=/absolute/path/server.yaml infrastructure-mcp-server`. Stdio must remain reserved
for MCP JSON-RPC; audit logs go to stderr. The host controls the executable, environment, credentials,
configuration, filesystem permissions, and network egress.

## Operate

Begin with `infrastructure_health`, then `validate_infrastructure_config`. Neither proves provider
connectivity. Run offline discovery before enabling a profile with `allow_live: true`. Treat all live
credentials as read-only and short-lived. Retain redacted audit events according to local policy.

For failures, check profile authorisation, schema errors, credential presence, DNS/egress, provider
status, and Project 1 compatibility. Do not weaken address controls or TLS validation to restore
service. Stop the process and revert package/config revisions for rollback; this server makes no
infrastructure changes.

