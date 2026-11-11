"""The CLI, the report files, the concurrency limit and the Claude adapter, without network access."""

import asyncio
import json
import sys
import types

import pytest

from evalkit import Case, models, run_all
from evalkit.cli import main
from evalkit.report import summary, to_markdown


def write_cases(tmp_path, *cases):
    path = tmp_path / "cases.jsonl"
    path.write_text("# a comment\n\n" + "\n".join(json.dumps(c) for c in cases) + "\n", encoding="utf-8")
    return str(path)


CAPITAL = {"id": "capital", "prompt": "capital of France?", "checks": [{"type": "contains", "value": "paris"}], "tags": ["geo"]}
JSON_CASE = {"id": "json", "prompt": "give json", "checks": [{"type": "json", "required_keys": ["a"]}], "tags": ["format"]}
JUDGED = {"id": "judged", "prompt": "be polite", "checks": [{"type": "judge", "rubric": "polite"}]}


@pytest.fixture
def fake_claude(monkeypatch):
    """Replace models.claude with stubs; records which models were built."""
    built = []

    def claude(model, effort="medium", max_tokens=16000):
        built.append((model, effort))

        async def call(system, prompt):
            if system is not None and "evaluator" in system:
                return "PASS\nIt is polite."
            return '{"a": 1}' if "json" in prompt else "It is Paris."

        return call

    monkeypatch.setattr(models, "claude", claude)
    return built


def test_validate_counts_cases(tmp_path, capsys):
    assert main(["validate", write_cases(tmp_path, CAPITAL, JSON_CASE)]) == 0
    assert "2 valid case(s)" in capsys.readouterr().out


def test_validate_reports_errors_without_a_traceback(tmp_path, capsys):
    assert main(["validate", str(tmp_path / "missing.jsonl")]) == 1
    assert capsys.readouterr().err.startswith("error:")


def test_run_writes_reports_and_skips_the_judge_when_unused(tmp_path, capsys, fake_claude):
    md, js = tmp_path / "r.md", tmp_path / "r.json"
    code = main(["run", write_cases(tmp_path, CAPITAL, JSON_CASE), "--model", "m", "--markdown", str(md), "--json", str(js)])
    assert code == 0
    assert "2/2 passed (100%)" in capsys.readouterr().out
    assert fake_claude == [("m", "medium")]
    assert "**2/2 passed (100%)**" in md.read_text(encoding="utf-8")
    assert json.loads(js.read_text(encoding="utf-8"))["summary"]["by_tag"] == {
        "format": {"passed": 1, "total": 1},
        "geo": {"passed": 1, "total": 1},
    }


def test_run_builds_a_low_effort_judge_when_a_case_needs_one(tmp_path, capsys, fake_claude):
    assert main(["run", write_cases(tmp_path, JUDGED), "--model", "m", "--judge-model", "j"]) == 0
    assert fake_claude == [("m", "medium"), ("j", "low")]


def test_tag_filter_and_fail_under(tmp_path, capsys, fake_claude):
    failing = {"id": "fails", "prompt": "anything", "checks": [{"type": "exact", "value": "nope"}], "tags": ["geo"]}
    path = write_cases(tmp_path, CAPITAL, failing, JSON_CASE)
    assert main(["run", path, "--tag", "geo"]) == 2  # 1 of 2 passes, below the default 1.0
    out = capsys.readouterr().out
    assert "1/2 passed" in out and "json" not in out
    assert main(["run", path, "--tag", "geo", "--fail-under", "0.5"]) == 0
    assert main(["run", path, "--tag", "none"]) == 1


def test_concurrency_limit_is_respected():
    in_flight = peak = 0

    async def slow(system, prompt):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return prompt

    cases = [Case(str(i), "p", [{"type": "contains", "value": "p"}]) for i in range(8)]
    results = asyncio.run(run_all(cases, slow, concurrency=3))
    assert peak == 3 and all(r.passed for r in results)
    assert asyncio.run(run_all(cases[:2], slow, concurrency=0))[1].passed  # 0 still runs one at a time


def test_summary_of_nothing_and_markdown_escaping():
    assert summary([]) == {"total": 0, "passed": 0, "pass_rate": 0.0, "by_tag": {}}
    results = asyncio.run(run_all([Case("pipe", "a|b", [{"type": "exact", "value": "x|y"}])], _echo))
    assert "expected 'x\\|y'" in to_markdown(results)


async def _echo(system, prompt):
    return prompt


def fake_anthropic(monkeypatch, stop_reason="end_turn", content=None):
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        blocks = content if content is not None else [types.SimpleNamespace(type="text", text="hi")]
        return types.SimpleNamespace(stop_reason=stop_reason, content=blocks)

    class AsyncAnthropic:
        def __init__(self):
            self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=create))

    module = types.ModuleType("anthropic")
    module.AsyncAnthropic = AsyncAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", module)
    return calls


def test_claude_adapter_sends_system_only_when_given(monkeypatch):
    calls = fake_anthropic(monkeypatch)
    call = models.claude("some-model", effort="low")
    assert asyncio.run(call(None, "hello")) == "hi"
    assert asyncio.run(call("be brief", "hello")) == "hi"
    assert "system" not in calls[0] and calls[1]["system"] == "be brief"
    assert calls[0]["model"] == "some-model" and calls[0]["messages"] == [{"role": "user", "content": "hello"}]


def test_claude_adapter_joins_text_and_raises_on_refusal(monkeypatch):
    text = [types.SimpleNamespace(type="thinking", text=""), types.SimpleNamespace(type="text", text="a"),
            types.SimpleNamespace(type="text", text="b")]
    fake_anthropic(monkeypatch, content=text)
    assert asyncio.run(models.claude("m")(None, "q")) == "ab"
    fake_anthropic(monkeypatch, stop_reason="refusal", content=[])
    with pytest.raises(RuntimeError, match="declined"):
        asyncio.run(models.claude("m")(None, "q"))


def test_run_without_the_sdk_explains_how_to_install_it(tmp_path, capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)  # makes `import anthropic` raise ImportError
    assert main(["run", write_cases(tmp_path, CAPITAL)]) == 1
    assert "pip install 'llm-evalkit[claude]'" in capsys.readouterr().err


def test_markdown_rows_stay_on_one_line():
    async def broken(system, prompt):
        raise RuntimeError("line one\nline two")

    report = to_markdown(asyncio.run(run_all([Case("multi", "p", [{"type": "contains", "value": "x"}])], broken)))
    assert "| multi | ❌ | error: RuntimeError: line one line two |" in report.splitlines()
