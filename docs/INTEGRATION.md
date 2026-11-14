# Project 1 Integration

This repository directly imports `mvia.models.load_config`, `load_inventory`, `mvia.service.discover`,
and `mvia.drift.compare`. It does not copy provider adapters or launch the CLI. The release dependency
is pinned to Project 1 commit `711fd51e11624f1a892b6ff5cb6e6bee8832a1e4`; local editable development
may install the adjacent checkout instead.

Project 1 does not currently publish a `py.typed` marker, so this project narrowly marks its `mvia`
imports as untyped while preserving strict mypy checking everywhere else. Runtime Pydantic contracts
remain authoritative. A future Project 1 release can add `py.typed` and remove these suppressions.

