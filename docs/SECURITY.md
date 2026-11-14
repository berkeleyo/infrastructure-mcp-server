# Security

Security is deny-by-default. Inventory profiles, desired states, and destinations are host-defined
aliases. Live profiles require `allow_live: true`. Diagnostics resolve the configured hostname and
reject every non-global IPv4/IPv6 address, loopback, private, link-local, reserved, multicast,
metadata, `.internal`, `.local`, and localhost target. HTTP redirects are rejected, response bodies
are omitted, headers and DNS records are bounded, timeouts are enforced, and TLS uses hostname
verification and the system trust store. A host-configured semaphore bounds concurrent diagnostics.

HTTP and TLS connect directly to an address from the validated resolution set while retaining the
configured hostname for HTTP Host and TLS SNI/certificate verification. Environment proxy settings
are disabled. Use OS or container egress controls as an additional enforcement layer. MCP tool
approval is not a security boundary. Stdio inherits the host user's authority, so run with a
dedicated low-privilege identity.

Credentials are supplied only through Project 1's standard provider mechanisms. Errors, audit events,
and results redact common credential forms and never report credential values.

