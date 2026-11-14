from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mvia.redaction import redact  # type: ignore[import-untyped]

from infrastructure_mcp import __version__
from infrastructure_mcp.audit import event
from infrastructure_mcp.contracts import DnsRequest, DriftRequest, HttpRequest, ProfileRequest
from infrastructure_mcp.diagnostics import DiagnosticService
from infrastructure_mcp.errors import InfrastructureMcpError
from infrastructure_mcp.inventory import InventoryService
from infrastructure_mcp.security import TargetAuthorizer
from infrastructure_mcp.settings import Settings, load_settings

RESOURCE_TYPES = {
    "aws": ["vpc", "subnet"],
    "azure": ["virtual_network", "subnet"],
    "cloudflare": ["zone", "dns_record"],
    "palo_alto": ["address_object"],
}
TOOLS = [
    "infrastructure_health",
    "discover_infrastructure",
    "detect_infrastructure_drift",
    "validate_infrastructure_config",
    "diagnose_dns",
    "diagnose_tls",
    "diagnose_http",
    "list_available_capabilities",
]


def _success(data: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def _failure(action: str, exc: Exception) -> dict[str, Any]:
    event(action, "failure", error_type=type(exc).__name__)
    message = redact(str(exc))
    return {
        "ok": False,
        "data": {},
        "error": {"type": type(exc).__name__, "message": str(message)},
    }


def build_server(
    settings: Settings,
    *,
    inventory: InventoryService | None = None,
    diagnostics: DiagnosticService | None = None,
) -> MCPServer:
    inventory_service = inventory or InventoryService(settings)
    diagnostic_service = diagnostics or DiagnosticService(
        TargetAuthorizer(settings),
        timeout=settings.diagnostic_timeout_seconds,
        max_records=settings.max_diagnostic_records,
    )
    diagnostic_limit = asyncio.Semaphore(settings.max_concurrent_diagnostics)
    server = MCPServer(
        "infrastructure-mcp-server",
        instructions="Read-only infrastructure discovery, drift, validation and bounded diagnostics.",
    )

    @server.tool()
    async def infrastructure_health() -> dict[str, Any]:
        """Return configuration readiness; this does not assert live connectivity."""
        profiles = []
        for name in sorted(settings.profiles):
            try:
                config = inventory_service.validated_config(name)
                providers = [
                    str(item)
                    for item, provider in sorted(config.providers.items())
                    if provider.enabled
                ]
                profiles.append(
                    {
                        "name": name,
                        "ready": True,
                        "mode": config.mode,
                        "providers": providers,
                        "connectivity_verified": False,
                    }
                )
            except InfrastructureMcpError as exc:
                profiles.append(
                    {
                        "name": name,
                        "ready": False,
                        "error": type(exc).__name__,
                        "connectivity_verified": False,
                    }
                )
        return _success({"status": "ok", "version": __version__, "profiles": profiles})

    @server.tool()
    async def discover_infrastructure(profile: str) -> dict[str, Any]:
        """Discover normalized resources from an allowlisted inventory profile."""
        try:
            request = ProfileRequest(profile=profile)
            result = inventory_service.discover(request.profile)
            event(
                "discover_infrastructure",
                "success",
                profile=request.profile,
                resources=len(result.resources),
            )
            return _success(result.model_dump(mode="json"))
        except Exception as exc:
            return _failure("discover_infrastructure", exc)

    @server.tool()
    async def detect_infrastructure_drift(profile: str, desired_state: str) -> dict[str, Any]:
        """Compare discovered resources with an allowlisted desired state."""
        try:
            request = DriftRequest(profile=profile, desired_state=desired_state)
            return _success(inventory_service.drift(request.profile, request.desired_state))
        except Exception as exc:
            return _failure("detect_infrastructure_drift", exc)

    @server.tool()
    async def validate_infrastructure_config(profile: str) -> dict[str, Any]:
        """Validate a configured profile without contacting live providers."""
        try:
            request = ProfileRequest(profile=profile)
            config = inventory_service.validated_config(request.profile)
            return _success(
                {
                    "valid": True,
                    "mode": config.mode,
                    "providers": [
                        str(item)
                        for item, provider in sorted(config.providers.items())
                        if provider.enabled
                    ],
                    "live_connectivity_verified": False,
                }
            )
        except Exception as exc:
            return _failure("validate_infrastructure_config", exc)

    @server.tool()
    async def diagnose_dns(
        destination: str, record_types: list[str] | None = None
    ) -> dict[str, Any]:
        """Resolve bounded DNS record types for an allowlisted public destination."""
        try:
            request = DnsRequest.model_validate(
                {"destination": destination, "record_types": record_types or ["A", "AAAA"]}
            )
            async with diagnostic_limit:
                result = await diagnostic_service.dns(request.destination, request.record_types)
            return _success(result)
        except Exception as exc:
            return _failure("diagnose_dns", exc)

    @server.tool()
    async def diagnose_tls(destination: str) -> dict[str, Any]:
        """Inspect TLS metadata for an allowlisted public HTTPS destination."""
        try:
            request = ProfileRequest(profile=destination)
            async with diagnostic_limit:
                result = await diagnostic_service.tls(request.profile)
            return _success(result)
        except Exception as exc:
            return _failure("diagnose_tls", exc)

    @server.tool()
    async def diagnose_http(destination: str, method: str = "HEAD") -> dict[str, Any]:
        """Make a bounded body-free HTTP diagnostic to an allowlisted destination."""
        try:
            request = HttpRequest.model_validate({"destination": destination, "method": method})
            async with diagnostic_limit:
                result = await diagnostic_service.http(request.destination, request.method)
            return _success(result)
        except Exception as exc:
            return _failure("diagnose_http", exc)

    @server.tool()
    async def list_available_capabilities() -> dict[str, Any]:
        """List tools, configured providers and resource types without claiming connectivity."""
        providers: set[str] = set()
        for name in settings.profiles:
            try:
                config = inventory_service.validated_config(name)
                providers.update(
                    str(item) for item, provider in config.providers.items() if provider.enabled
                )
            except InfrastructureMcpError:
                continue
        credentials_present = {
            "cloudflare": bool(os.getenv("CLOUDFLARE_API_TOKEN")),
            "palo_alto": bool(os.getenv("PANOS_API_KEY")),
            "aws": bool(os.getenv("AWS_PROFILE") or os.getenv("AWS_ACCESS_KEY_ID")),
            "azure": bool(os.getenv("AZURE_CLIENT_ID")),
        }
        return _success(
            {
                "tools": TOOLS,
                "providers": [
                    {
                        "name": name,
                        "resource_types": RESOURCE_TYPES.get(name, []),
                        "configured": True,
                        "credential_hint_present": credentials_present.get(name, False),
                        "connectivity_verified": False,
                    }
                    for name in sorted(providers)
                ],
                "diagnostic_destinations": sorted(settings.destinations),
            }
        )

    return server


def create_default_server(config_path: Path | None = None) -> MCPServer:
    settings, _ = load_settings(config_path)
    return build_server(settings)


def main() -> None:
    create_default_server().run(transport="stdio")


if __name__ == "__main__":
    main()
