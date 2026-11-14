import json
import logging
from typing import Any

from mvia.redaction import redact  # type: ignore[import-untyped]

logger = logging.getLogger("infrastructure_mcp.audit")


def event(action: str, outcome: str, **fields: Any) -> None:
    logger.info(
        json.dumps(redact({"action": action, "outcome": outcome, **fields}), sort_keys=True)
    )
