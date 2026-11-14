from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, cast

import dns.asyncresolver
import dns.exception
import httpx

from infrastructure_mcp.errors import DiagnosticError
from infrastructure_mcp.security import TargetAuthorizer, validate_public_addresses

SAFE_HEADERS = {"content-type", "content-length", "cache-control", "server", "date"}


class DiagnosticService:
    def __init__(
        self,
        authorizer: TargetAuthorizer,
        *,
        timeout: float,
        max_records: int,
        http_client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ) -> None:
        self.authorizer = authorizer
        self.timeout = timeout
        self.max_records = max_records
        self.http_client_factory = http_client_factory

    async def dns(self, destination_name: str, record_types: Sequence[str]) -> dict[str, Any]:
        destination, _ = await self.authorizer.authorize(destination_name)
        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = self.timeout
        results: dict[str, list[str]] = {}
        for record_type in record_types:
            try:
                answer = await resolver.resolve(
                    destination.hostname, record_type, lifetime=self.timeout
                )
                values = [item.to_text()[:1024] for item in answer][: self.max_records]
                if record_type in {"A", "AAAA"}:
                    validate_public_addresses(destination.hostname, values)
                results[record_type] = values
            except (dns.exception.DNSException, OSError) as exc:
                results[record_type] = [f"error:{type(exc).__name__}"]
        return {"hostname": destination.hostname, "records": results}

    async def http(self, destination_name: str, method: str) -> dict[str, Any]:
        destination, addresses = await self.authorizer.authorize(destination_name)
        scheme = destination.schemes[0]
        url = f"{scheme}://{destination.hostname}:{destination.port}/"
        address = ipaddress.ip_address(addresses[0])
        address_literal = f"[{address}]" if address.version == 6 else str(address)
        connect_url = f"{scheme}://{address_literal}:{destination.port}/"
        default_port = 443 if scheme == "https" else 80
        host_header = (
            destination.hostname
            if destination.port == default_port
            else f"{destination.hostname}:{destination.port}"
        )
        started = time.monotonic()
        try:
            async with self.http_client_factory(
                timeout=httpx.Timeout(self.timeout), follow_redirects=False, trust_env=False
            ) as client:
                async with client.stream(
                    method,
                    connect_url,
                    headers={"Host": host_header},
                    extensions={"sni_hostname": destination.hostname},
                ) as response:
                    status = response.status_code
                    headers = {
                        key.lower(): value[:1024]
                        for key, value in response.headers.items()
                        if key.lower() in SAFE_HEADERS
                    }
        except httpx.HTTPError as exc:
            raise DiagnosticError(f"HTTP diagnostic failed: {type(exc).__name__}") from exc
        elapsed = round((time.monotonic() - started) * 1000, 2)
        if 300 <= status < 400:
            raise DiagnosticError("HTTP redirects are prohibited")
        return {
            "url": url,
            "method": method,
            "status": status,
            "elapsed_ms": elapsed,
            "headers": headers,
            "body_returned": False,
        }

    async def tls(self, destination_name: str) -> dict[str, Any]:
        destination, addresses = await self.authorizer.authorize(destination_name)
        if "https" not in destination.schemes:
            raise DiagnosticError("TLS diagnostic requires an HTTPS destination")

        def inspect() -> dict[str, Any]:
            context = ssl.create_default_context()
            with socket.create_connection(
                (addresses[0], destination.port), timeout=self.timeout
            ) as raw:
                with context.wrap_socket(raw, server_hostname=destination.hostname) as tls_socket:
                    certificate = cast(dict[str, Any], tls_socket.getpeercert() or {})
                    expiry_text = certificate.get("notAfter")
                    expiry = ssl.cert_time_to_seconds(expiry_text) if expiry_text else None
                    return {
                        "hostname": destination.hostname,
                        "port": destination.port,
                        "subject": _flatten_name(certificate.get("subject", ())),
                        "issuer": _flatten_name(certificate.get("issuer", ())),
                        "sans": [
                            value
                            for kind, value in certificate.get("subjectAltName", ())
                            if kind == "DNS"
                        ][: self.max_records],
                        "not_before": certificate.get("notBefore"),
                        "not_after": expiry_text,
                        "valid_now": bool(expiry and expiry > datetime.now(UTC).timestamp()),
                        "protocol": tls_socket.version(),
                        "cipher": cipher[0] if (cipher := tls_socket.cipher()) else None,
                    }

        try:
            return await asyncio.wait_for(asyncio.to_thread(inspect), timeout=self.timeout + 1)
        except (TimeoutError, OSError, ssl.SSLError) as exc:
            raise DiagnosticError(f"TLS diagnostic failed: {type(exc).__name__}") from exc


def _flatten_name(value: Any) -> dict[str, str]:
    return {str(key): str(item) for group in value for key, item in group}
