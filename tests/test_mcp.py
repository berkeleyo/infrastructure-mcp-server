import asyncio
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from infrastructure_mcp.server import TOOLS, _failure, build_server
from infrastructure_mcp.settings import Settings

ROOT = Path(__file__).parents[1]


def structured(result: object) -> dict[str, object]:
    value = getattr(result, "structured_content", None)
    assert isinstance(value, dict)
    return value


@pytest.mark.asyncio
async def test_in_process_protocol_tool_discovery_and_offline_calls(settings: Settings) -> None:
    server = build_server(settings)
    async with Client(server) as client:
        tools = await client.list_tools()
        assert sorted(tool.name for tool in tools.tools) == sorted(TOOLS)
        health = structured(await client.call_tool("infrastructure_health"))
        assert health["ok"] is True
        discovery = structured(
            await client.call_tool("discover_infrastructure", {"profile": "portfolio_offline"})
        )
        assert len(discovery["data"]["resources"]) == 4  # type: ignore[index]
        drift = structured(
            await client.call_tool(
                "detect_infrastructure_drift",
                {"profile": "portfolio_offline", "desired_state": "baseline"},
            )
        )
        assert drift["data"]["in_sync"] is True  # type: ignore[index]


@pytest.mark.asyncio
async def test_tool_invalid_schema_and_unknown_profile(settings: Settings) -> None:
    async with Client(build_server(settings)) as client:
        invalid = structured(
            await client.call_tool("discover_infrastructure", {"profile": "../escape"})
        )
        assert invalid["ok"] is False
        unknown = structured(
            await client.call_tool("discover_infrastructure", {"profile": "unknown"})
        )
        assert unknown["ok"] is False


class FakeDiagnostics:
    async def dns(self, destination: str, record_types: list[str]) -> dict[str, object]:
        return {"destination": destination, "types": record_types}

    async def tls(self, destination: str) -> dict[str, object]:
        return {"destination": destination, "valid_now": True}

    async def http(self, destination: str, method: str) -> dict[str, object]:
        return {"destination": destination, "method": method, "status": 200}


class ConcurrencyDiagnostics(FakeDiagnostics):
    def __init__(self) -> None:
        self.active = 0
        self.maximum = 0

    async def dns(self, destination: str, record_types: list[str]) -> dict[str, object]:
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        await asyncio.sleep(0.02)
        self.active -= 1
        return await super().dns(destination, record_types)


@pytest.mark.asyncio
async def test_all_metadata_and_diagnostic_tools(settings: Settings) -> None:
    server = build_server(settings, diagnostics=FakeDiagnostics())  # type: ignore[arg-type]
    async with Client(server) as client:
        validation = structured(
            await client.call_tool(
                "validate_infrastructure_config", {"profile": "portfolio_offline"}
            )
        )
        assert validation["data"]["valid"] is True  # type: ignore[index]
        capabilities = structured(await client.call_tool("list_available_capabilities"))
        assert len(capabilities["data"]["providers"]) == 4  # type: ignore[index]
        dns = structured(
            await client.call_tool(
                "diagnose_dns", {"destination": "example_public", "record_types": ["A"]}
            )
        )
        assert dns["ok"] is True
        tls = structured(await client.call_tool("diagnose_tls", {"destination": "example_public"}))
        assert tls["ok"] is True
        http = structured(
            await client.call_tool(
                "diagnose_http", {"destination": "example_public", "method": "GET"}
            )
        )
        assert http["data"]["status"] == 200  # type: ignore[index]


@pytest.mark.asyncio
async def test_diagnostic_concurrency_is_bounded(settings: Settings) -> None:
    limited = settings.model_copy(update={"max_concurrent_diagnostics": 1})
    diagnostics = ConcurrencyDiagnostics()
    async with Client(
        build_server(limited, diagnostics=diagnostics),  # type: ignore[arg-type]
        raise_exceptions=True,
    ) as client:
        await asyncio.gather(
            client.call_tool("diagnose_dns", {"destination": "example_public"}),
            client.call_tool("diagnose_dns", {"destination": "example_public"}),
        )
    assert diagnostics.maximum == 1


@pytest.mark.asyncio
async def test_real_stdio_client_server_handshake_and_tool_list() -> None:
    env = {"INFRA_MCP_CONFIG": str(ROOT / "examples/server.yaml")}
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "infrastructure_mcp.server"],
        env=env,
        cwd=str(ROOT),
    )
    async with Client(params, mode="legacy", read_timeout_seconds=10) as client:
        assert client.protocol_version is not None
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == set(TOOLS)
        discovery = structured(
            await client.call_tool("discover_infrastructure", {"profile": "portfolio_offline"})
        )
        assert len(discovery["data"]["resources"]) == 4  # type: ignore[index]


def test_failure_redacts_secret_values() -> None:
    result = _failure("test", ValueError("api_key=do-not-return"))
    assert "do-not-return" not in str(result)
