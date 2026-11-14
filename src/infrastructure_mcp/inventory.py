from mvia.drift import compare  # type: ignore[import-untyped]
from mvia.errors import MviaError  # type: ignore[import-untyped]
from mvia.models import AppConfig, Inventory, load_config, load_inventory  # type: ignore[import-untyped]
from mvia.service import discover  # type: ignore[import-untyped]

from infrastructure_mcp.errors import AuthorizationError, InfrastructureMcpError
from infrastructure_mcp.settings import Profile, Settings


class InventoryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def profile(self, name: str) -> Profile:
        try:
            return self.settings.profiles[name]
        except KeyError as exc:
            raise AuthorizationError("unknown or unauthorised inventory profile") from exc

    def validated_config(self, name: str) -> AppConfig:
        profile = self.profile(name)
        try:
            config = load_config(profile.config)
        except MviaError as exc:
            raise InfrastructureMcpError(str(exc)) from exc
        if config.mode == "live" and not profile.allow_live:
            raise AuthorizationError("live access is disabled for this profile")
        return config

    def discover(self, name: str) -> Inventory:
        profile = self.profile(name)
        config = self.validated_config(name)
        try:
            return discover(config, config_dir=profile.config.parent)
        except MviaError as exc:
            raise InfrastructureMcpError(str(exc)) from exc

    def drift(self, name: str, desired_name: str) -> dict[str, object]:
        profile = self.profile(name)
        try:
            desired_path = profile.desired_states[desired_name]
        except KeyError as exc:
            raise AuthorizationError("unknown or unauthorised desired state") from exc
        try:
            report = compare(load_inventory(desired_path), self.discover(name))
        except MviaError as exc:
            raise InfrastructureMcpError(str(exc)) from exc
        result: dict[str, object] = report.model_dump(mode="json")
        return result
