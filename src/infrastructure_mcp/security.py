from __future__ import annotations

import ipaddress
import socket
from collections.abc import Awaitable, Callable

import anyio

from infrastructure_mcp.errors import AuthorizationError, DiagnosticError
from infrastructure_mcp.settings import Destination, Settings

Resolver = Callable[[str, int], Awaitable[list[str]]]

BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "instance-data.ec2.internal",
    "metadata.azure.internal",
}


async def system_resolve(hostname: str, port: int) -> list[str]:
    try:
        records = await anyio.to_thread.run_sync(
            lambda: socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        )
    except OSError as exc:
        raise DiagnosticError("destination resolution failed") from exc
    return sorted({str(item[4][0]) for item in records})


def validate_public_addresses(hostname: str, addresses: list[str]) -> None:
    canonical = hostname.rstrip(".").lower()
    if canonical in BLOCKED_HOSTS or canonical.endswith((".localhost", ".internal", ".local")):
        raise AuthorizationError("destination hostname is prohibited")
    if not addresses:
        raise DiagnosticError("destination did not resolve")
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise DiagnosticError("resolver returned an invalid address") from exc
        if not address.is_global:
            raise AuthorizationError("destination resolved to a prohibited address")


class TargetAuthorizer:
    def __init__(self, settings: Settings, resolver: Resolver = system_resolve) -> None:
        self.settings, self.resolver = settings, resolver

    def destination(self, name: str) -> Destination:
        try:
            return self.settings.destinations[name]
        except KeyError as exc:
            raise AuthorizationError("unknown or unauthorised diagnostic destination") from exc

    async def authorize(self, name: str) -> tuple[Destination, list[str]]:
        destination = self.destination(name)
        addresses = await self.resolver(destination.hostname, destination.port)
        validate_public_addresses(destination.hostname, addresses)
        return destination, addresses
