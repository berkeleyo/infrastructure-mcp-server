import httpx
import pytest

from infrastructure_mcp.diagnostics import DiagnosticService
from infrastructure_mcp.errors import DiagnosticError
from infrastructure_mcp.security import TargetAuthorizer
from infrastructure_mcp.settings import Destination, Settings


async def public_resolver(_: str, __: int) -> list[str]:
    return ["8.8.8.8"]


def service(handler: httpx.MockTransport) -> DiagnosticService:
    settings = Settings(
        version=1,
        profiles={},
        destinations={"target": Destination(hostname="example.com")},
    )
    return DiagnosticService(
        TargetAuthorizer(settings, public_resolver),
        timeout=0.2,
        max_records=2,
        http_client_factory=lambda **kwargs: httpx.AsyncClient(transport=handler, **kwargs),
    )


@pytest.mark.asyncio
async def test_http_returns_only_safe_metadata() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["host"] = request.url.host
        observed["host_header"] = request.headers["host"]
        observed["sni"] = request.extensions["sni_hostname"]
        return httpx.Response(
            200,
            headers={"Content-Type": "text/plain", "Set-Cookie": "secret=yes"},
            text="never return me",
        )

    transport = httpx.MockTransport(handler)
    result = await service(transport).http("target", "GET")
    assert result["body_returned"] is False
    assert result["headers"] == {"content-type": "text/plain", "content-length": "15"}
    assert observed == {"host": "8.8.8.8", "host_header": "example.com", "sni": "example.com"}


@pytest.mark.asyncio
async def test_redirect_is_denied() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(302, headers={"Location": "http://127.0.0.1/"})
    )
    with pytest.raises(DiagnosticError, match="redirects"):
        await service(transport).http("target", "HEAD")


@pytest.mark.asyncio
async def test_http_timeout_is_safe() -> None:
    async def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret=should-not-escape")

    with pytest.raises(DiagnosticError, match="ReadTimeout") as caught:
        await service(httpx.MockTransport(timeout)).http("target", "HEAD")
    assert "should-not-escape" not in str(caught.value)


@pytest.mark.asyncio
async def test_tls_rejects_non_https() -> None:
    settings = Settings(
        version=1,
        profiles={},
        destinations={"target": Destination(hostname="example.com", schemes=["http"])},
    )
    diagnostic = DiagnosticService(
        TargetAuthorizer(settings, public_resolver), timeout=1, max_records=2
    )
    with pytest.raises(DiagnosticError, match="requires"):
        await diagnostic.tls("target")


@pytest.mark.asyncio
async def test_dns_failure_is_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*args: object, **kwargs: object) -> object:
        import dns.resolver

        raise dns.resolver.NXDOMAIN

    monkeypatch.setattr("dns.asyncresolver.Resolver.resolve", fail)
    result = await service(httpx.MockTransport(lambda _: httpx.Response(200))).dns("target", ["A"])
    assert result["records"]["A"] == ["error:NXDOMAIN"]


@pytest.mark.asyncio
async def test_dns_success_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    class Answer:
        def to_text(self) -> str:
            return "8.8.8.8"

    async def resolve(*args: object, **kwargs: object) -> list[Answer]:
        return [Answer(), Answer(), Answer()]

    monkeypatch.setattr("dns.asyncresolver.Resolver.resolve", resolve)
    result = await service(httpx.MockTransport(lambda _: httpx.Response(200))).dns("target", ["A"])
    assert result["records"]["A"] == ["8.8.8.8", "8.8.8.8"]


@pytest.mark.asyncio
async def test_tls_success_path_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_thread(function: object) -> dict[str, object]:
        return {"hostname": "example.com", "valid_now": True}

    monkeypatch.setattr("infrastructure_mcp.diagnostics.asyncio.to_thread", fake_thread)
    result = await service(httpx.MockTransport(lambda _: httpx.Response(200))).tls("target")
    assert result["valid_now"] is True
