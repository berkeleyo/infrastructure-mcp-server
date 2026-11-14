# Architecture

```mermaid
flowchart TB
  H[Host-controlled MCP client] -->|stdio| M[Official MCP SDK]
  M --> T[Typed tools]
  T --> AUTH[Alias authorization]
  AUTH --> INV[Inventory service]
  AUTH --> DIAG[Diagnostic service]
  INV --> MVIA[Commit-pinned Project 1]
  MVIA --> OFF[Fixtures]
  MVIA --> LIVE[Read-only live adapters]
  DIAG --> DNS[DNS]
  DIAG --> TLS[TLS]
  DIAG --> HTTP[Body-free HTTP]
  T --> AUDIT[Redacted stderr audit]
```

Dependency injection replaces inventory and diagnostic boundaries in tests. A real official SDK
client also launches the packaged stdio process and completes the legacy initialize handshake.

