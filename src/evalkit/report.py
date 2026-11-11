"""Render run results as console text, Markdown, or JSON."""

from __future__ import annotations

import json
from collections import defaultdict

from .runner import CaseResult


def summary(results: list[CaseResult]) -> dict:
    passed = sum(r.passed for r in results)
    by_tag: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in results:
        for tag in r.case.tags:
            by_tag[tag][0] += r.passed
            by_tag[tag][1] += 1
    return {
        "total": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 4) if results else 0.0,
        "by_tag": {t: {"passed": p, "total": n} for t, (p, n) in sorted(by_tag.items())},
    }


def to_text(results: list[CaseResult]) -> str:
    lines = []
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        lines.append(f"[{mark}] {r.case.id}  ({r.seconds:.1f}s)")
        if r.error:
            lines.append(f"       error: {r.error}")
        for c in r.checks:
            if not c.passed:
                lines.append(f"       x {c.type}: {c.detail}")
    s = summary(results)
    lines.append(f"\n{s['passed']}/{s['total']} passed ({s['pass_rate']:.0%})")
    for tag, t in s["by_tag"].items():
        lines.append(f"  {tag}: {t['passed']}/{t['total']}")
    return "\n".join(lines)


def to_markdown(results: list[CaseResult]) -> str:
    s = summary(results)
    out = [
        "# Eval report",
        "",
        f"**{s['passed']}/{s['total']} passed ({s['pass_rate']:.0%})**",
        "",
        "| Case | Result | Failed checks |",
        "|---|---|---|",
    ]
    for r in results:
        failed = "; ".join(f"{c.type}: {c.detail}" for c in r.checks if not c.passed)
        if r.error:
            failed = f"error: {r.error}"
        # a table row has to stay on one line, and a "|" would start a new cell
        failed = " ".join(failed.splitlines()).replace("|", "\\|")
        out.append(f"| {r.case.id} | {'✅' if r.passed else '❌'} | {failed} |")
    return "\n".join(out) + "\n"


def to_json(results: list[CaseResult]) -> str:
    return json.dumps(
        {
            "summary": summary(results),
            "cases": [
                {
                    "id": r.case.id,
                    "passed": r.passed,
                    "seconds": round(r.seconds, 3),
                    "error": r.error,
                    "response": r.response,
                    "checks": [{"type": c.type, "passed": c.passed, "detail": c.detail} for c in r.checks],
                }
                for r in results
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
