class InfrastructureMcpError(Exception):
    """Safe, expected operation failure."""


class AuthorizationError(InfrastructureMcpError):
    """Requested profile or target is not authorised."""


class DiagnosticError(InfrastructureMcpError):
    """A bounded diagnostic failed."""
