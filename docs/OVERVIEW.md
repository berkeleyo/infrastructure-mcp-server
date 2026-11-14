# Overview

The server converts eight typed Python functions into MCP tools through the official SDK. Inventory
profiles map aliases to host-controlled Project 1 YAML files. Desired states are separately aliased.
Diagnostics map aliases to exact hosts and ports. AI clients cannot provide filesystem paths, URLs,
shell commands, provider credentials, or arbitrary destinations.

Offline operation uses deterministic synthetic fixtures. Live inventory is possible only where both
Project 1 configuration selects live mode and this server's profile explicitly sets `allow_live`.

