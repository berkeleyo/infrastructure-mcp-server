import pytest

from infrastructure_mcp.errors import AuthorizationError, DiagnosticError
from infrastructure_mcp.security import TargetAuthorizer, validate_public_addresses
from infrastructure_mcp.settings import Destination, Settings


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1", "fe80::1"],
)
def test_private_ipv4_and_ipv6_are_denied(address: str) -> None:
    with pytest.raises(AuthorizationError):
        validate_public_addresses("example.com", [address])


def test_metadata_hostname_is_denied() -> None:
    with pytest.raises(AuthorizationError):
        validate_public_addresses("metadata.google.internal", ["8.8.8.8"])


def test_invalid_and_empty_resolver_results() -> None:
    with pytest.raises(DiagnosticError):
        validate_public_addresses("example.com", [])
    with pytest.raises(DiagnosticError):
        validate_public_addresses("example.com", ["not-an-ip"])


@pytest.mark.asyncio
async def test_unknown_destination_is_denied(settings: Settings) -> None:
    with pytest.raises(AuthorizationError, match="unknown"):
        await TargetAuthorizer(settings).authorize("not_configured")


@pytest.mark.asyncio
async def test_authorizer_checks_every_resolved_address() -> None:
    async def rebinding(_: str, __: int) -> list[str]:
        return ["8.8.8.8", "127.0.0.1"]

    settings = Settings(
        version=1,
        profiles={},
        destinations={"target": Destination(hostname="example.com")},
    )
    with pytest.raises(AuthorizationError):
        await TargetAuthorizer(settings, rebinding).authorize("target")
