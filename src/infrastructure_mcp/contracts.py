from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class ToolResult(StrictModel):
    ok: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, str] | None = None


class ProfileRequest(StrictModel):
    profile: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")


class DriftRequest(ProfileRequest):
    desired_state: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")


class DiagnosticRequest(StrictModel):
    destination: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")


class DnsRequest(DiagnosticRequest):
    record_types: list[Literal["A", "AAAA", "CNAME", "MX", "TXT"]] = Field(
        default_factory=lambda: ["A", "AAAA"],  # type: ignore[arg-type]
        min_length=1,
        max_length=5,
    )


class HttpRequest(DiagnosticRequest):
    method: Literal["HEAD", "GET"] = "HEAD"
