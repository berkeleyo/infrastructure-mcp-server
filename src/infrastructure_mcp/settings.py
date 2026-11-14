from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from infrastructure_mcp.errors import InfrastructureMcpError


class Destination(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    hostname: str = Field(pattern=r"^[A-Za-z0-9.-]+$")
    port: int = Field(default=443, ge=1, le=65535)
    schemes: list[str] = Field(default_factory=lambda: ["https"])

    @field_validator("schemes")
    @classmethod
    def safe_schemes(cls, value: list[str]) -> list[str]:
        if not value or any(item not in {"http", "https"} for item in value):
            raise ValueError("schemes must contain only http or https")
        return value


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    config: Path
    desired_states: dict[str, Path] = Field(default_factory=dict)
    allow_live: bool = False


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    version: int = Field(ge=1, le=1)
    profiles: dict[str, Profile]
    destinations: dict[str, Destination] = Field(default_factory=dict)
    diagnostic_timeout_seconds: float = Field(default=5.0, ge=0.2, le=15)
    max_diagnostic_records: int = Field(default=20, ge=1, le=100)
    max_concurrent_diagnostics: int = Field(default=4, ge=1, le=16)


def load_settings(path: Path | None = None) -> tuple[Settings, Path]:
    selected = path or Path(os.environ.get("INFRA_MCP_CONFIG", "examples/server.yaml"))
    try:
        data = yaml.safe_load(selected.read_text(encoding="utf-8"))
        settings = Settings.model_validate(data)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise InfrastructureMcpError(f"invalid server configuration: {type(exc).__name__}") from exc
    base = selected.resolve().parent
    profiles = {
        name: profile.model_copy(
            update={
                "config": base / profile.config
                if not profile.config.is_absolute()
                else profile.config,
                "desired_states": {
                    key: base / value if not value.is_absolute() else value
                    for key, value in profile.desired_states.items()
                },
            }
        )
        for name, profile in settings.profiles.items()
    }
    return settings.model_copy(update={"profiles": profiles}), selected.resolve()
