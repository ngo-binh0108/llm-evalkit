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
    # utf-8-sig: Windows PowerShell's Out-File and Set-Content put a byte order mark at the start
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{lineno}: invalid JSON ({e.msg})") from e
        where = f"{path}:{lineno}"
        if not isinstance(raw, dict):
            raise ValueError(f"{where}: each line must be a JSON object, not {type(raw).__name__}")
        if not isinstance(raw.get("prompt"), str) or not raw.get("checks"):
            raise ValueError(f"{where}: each case needs a 'prompt' string and a non-empty 'checks' list")
        checks = raw["checks"]
        if not isinstance(checks, list) or not all(isinstance(c, dict) for c in checks):
            raise ValueError(f"{where}: 'checks' must be a list of objects")
        system = raw.get("system")
        if system is not None and not isinstance(system, str):
            raise ValueError(f"{where}: 'system' must be a string")
        tags = raw.get("tags", [])
        if isinstance(tags, str):  # "tags": "geo" means one tag, not ['g', 'e', 'o']
            tags = [tags]
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise ValueError(f"{where}: 'tags' must be a list of strings")
        case = Case(
            id=str(raw.get("id", f"case-{lineno}")),
            prompt=raw["prompt"],
            checks=checks,
            system=system,
            tags=tags,
        )
        if case.id in seen:
            raise ValueError(f"{path}:{lineno}: duplicate case id {case.id!r}")
        seen.add(case.id)
        cases.append(case)
    return cases
