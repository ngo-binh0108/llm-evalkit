import asyncio
import json
from pathlib import Path

import pytest

from evalkit import Case, load_cases, run_all
from evalkit.report import summary, to_json, to_markdown, to_text

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "basic.jsonl"


async def echo_model(system, prompt):
    if "boom" in prompt:
        raise RuntimeError("model exploded")
    return prompt.upper()


def test_example_suite_loads():
    cases = load_cases(EXAMPLES)
    assert len(cases) == 5
    assert cases[2].system == "Reply with JSON only, no prose."


def test_load_rejects_bad_lines(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"prompt": "hi"}\n')
    with pytest.raises(ValueError, match="checks"):
        load_cases(bad)
    dup = tmp_path / "dup.jsonl"
    line = json.dumps({"id": "a", "prompt": "p", "checks": [{"type": "contains", "value": "p"}]})
    dup.write_text(line + "\n" + line + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(dup)


def test_run_all_keeps_order_and_isolates_errors():
    cases = [
        Case("ok", "hello", [{"type": "contains", "value": "HELLO"}], tags=["t"]),
        Case("bad", "boom", [{"type": "contains", "value": "x"}], tags=["t"]),
        Case("miss", "hi", [{"type": "exact", "value": "nope"}]),
    ]
    results = asyncio.run(run_all(cases, echo_model, concurrency=2))
    assert [r.case.id for r in results] == ["ok", "bad", "miss"]
    assert [r.passed for r in results] == [True, False, False]
    assert "exploded" in results[1].error

    s = summary(results)
    assert s["passed"] == 1 and s["by_tag"]["t"] == {"passed": 1, "total": 2}
    assert "1/3 passed" in to_text(results)
    assert "| bad | ❌ | error: RuntimeError: model exploded |" in to_markdown(results)
    assert json.loads(to_json(results))["summary"]["total"] == 3
