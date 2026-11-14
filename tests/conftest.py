from pathlib import Path

import pytest

from infrastructure_mcp.settings import Settings, load_settings

ROOT = Path(__file__).parents[1]


@pytest.fixture
def settings() -> Settings:
    return load_settings(ROOT / "examples/server.yaml")[0]
