from pathlib import Path

import pytest

from infrastructure_mcp.errors import AuthorizationError, InfrastructureMcpError
from infrastructure_mcp.inventory import InventoryService
from infrastructure_mcp.settings import Profile, Settings


def test_project_one_offline_discovery(settings: Settings) -> None:
    result = InventoryService(settings).discover("portfolio_offline")
    assert len(result.resources) == 4
    assert [str(item.provider) for item in result.resources] == [
        "aws",
        "azure",
        "cloudflare",
        "palo_alto",
    ]


def test_drift_is_deterministic(settings: Settings) -> None:
    service = InventoryService(settings)
    assert service.drift("portfolio_offline", "baseline") == service.drift(
        "portfolio_offline", "baseline"
    )
    assert service.drift("portfolio_offline", "baseline")["in_sync"] is True


def test_unknown_profile_and_desired_state(settings: Settings) -> None:
    service = InventoryService(settings)
    with pytest.raises(AuthorizationError, match="unknown"):
        service.discover("nope")
    with pytest.raises(AuthorizationError, match="desired"):
        service.drift("portfolio_offline", "nope")


def test_live_profile_is_denied_by_default(tmp_path: Path) -> None:
    config = tmp_path / "live.yaml"
    config.write_text("version: 1\nmode: live\nproviders:\n  aws:\n    region: eu-west-2\n")
    settings = Settings(
        version=1,
        profiles={"live": Profile(config=config, allow_live=False)},
    )
    with pytest.raises(AuthorizationError, match="disabled"):
        InventoryService(settings).validated_config("live")


def test_live_missing_credentials_is_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    config = tmp_path / "live.yaml"
    config.write_text("version: 1\nmode: live\nproviders:\n  cloudflare: {}\n")
    settings = Settings(
        version=1,
        profiles={"live": Profile(config=config, allow_live=True)},
    )
    with pytest.raises(InfrastructureMcpError, match="CLOUDFLARE_API_TOKEN"):
        InventoryService(settings).discover("live")


def test_disabled_provider_is_not_discovered(tmp_path: Path) -> None:
    config = tmp_path / "disabled.yaml"
    config.write_text("version: 1\nmode: offline\nproviders:\n  aws:\n    enabled: false\n")
    settings = Settings(version=1, profiles={"disabled": Profile(config=config)})
    assert InventoryService(settings).discover("disabled").resources == []
