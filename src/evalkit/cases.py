"""Test-case model and JSONL loading."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Case:
    """One prompt plus the checks its response must pass.

    `checks` is a list of {"type": <grader name>, ...grader options}.
    """

    id: str
    prompt: str
    checks: list[dict[str, Any]]
    system: str | None = None
    tags: list[str] = field(default_factory=list)


def load_cases(path: str | Path) -> list[Case]:
    """Load cases from a JSONL file (one JSON object per line, `#` comments allowed)."""
    cases: list[Case] = []
    seen: set[str] = set()
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{lineno}: invalid JSON ({e.msg})") from e
        if "prompt" not in raw or not raw.get("checks"):
            raise ValueError(f"{path}:{lineno}: each case needs 'prompt' and a non-empty 'checks' list")
        case = Case(
            id=str(raw.get("id", f"case-{lineno}")),
            prompt=raw["prompt"],
            checks=raw["checks"],
            system=raw.get("system"),
            tags=list(raw.get("tags", [])),
        )
        if case.id in seen:
            raise ValueError(f"{path}:{lineno}: duplicate case id {case.id!r}")
        seen.add(case.id)
        cases.append(case)
    return cases
