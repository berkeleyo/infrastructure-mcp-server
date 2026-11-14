# Cutover Checklist

- Review the pinned Project 1 commit and dependency audit.
- Run Python 3.11/3.12 CI, protocol integration, unit, lint, typing, build, and secret scans.
- Review every profile, desired-state alias, destination, port, and scheme.
- Keep live profiles disabled until least-privilege credentials and egress controls are approved.
- Configure the MCP host with absolute paths and only required environment variables.
- Capture a successful offline health, discovery, and drift baseline.
- Document ownership, log retention, credential rotation, and rollback authority.

