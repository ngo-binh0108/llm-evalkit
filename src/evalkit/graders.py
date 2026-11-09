"""Graders: functions that decide whether a model response passes one check."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

# A model call: (system, prompt) -> response text. Injected so graders and the
# runner can be tested without network access.
ModelFn = Callable[[str | None, str], Awaitable[str]]


@dataclass
class CheckResult:
    type: str
    passed: bool
    detail: str = ""


def _contains(response: str, check: dict[str, Any]) -> CheckResult:
    needle = check["value"]
    ignore_case = check.get("ignore_case", True)
    hay, nd = (response.lower(), needle.lower()) if ignore_case else (response, needle)
    return CheckResult("contains", nd in hay, f"looked for {needle!r}")


def _not_contains(response: str, check: dict[str, Any]) -> CheckResult:
    r = _contains(response, check)
    return CheckResult("not_contains", not r.passed, f"must not contain {check['value']!r}")


def _regex(response: str, check: dict[str, Any]) -> CheckResult:
    flags = re.IGNORECASE if check.get("ignore_case") else 0
    ok = re.search(check["pattern"], response, flags) is not None
    return CheckResult("regex", ok, f"pattern {check['pattern']!r}")


def _exact(response: str, check: dict[str, Any]) -> CheckResult:
    ok = response.strip() == str(check["value"]).strip()
    return CheckResult("exact", ok, f"expected {check['value']!r}")


def _json_valid(response: str, check: dict[str, Any]) -> CheckResult:
    text = response.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return CheckResult("json", False, f"invalid JSON: {e.msg}")
    missing = [k for k in check.get("required_keys", []) if not isinstance(data, dict) or k not in data]
    if missing:
        return CheckResult("json", False, f"missing keys: {', '.join(missing)}")
    return CheckResult("json", True, "valid JSON")


def _max_words(response: str, check: dict[str, Any]) -> CheckResult:
    n = len(response.split())
    return CheckResult("max_words", n <= check["value"], f"{n} words (limit {check['value']})")


SYNC_GRADERS: dict[str, Callable[[str, dict[str, Any]], CheckResult]] = {
    "contains": _contains,
    "not_contains": _not_contains,
    "regex": _regex,
    "exact": _exact,
    "json": _json_valid,
    "max_words": _max_words,
}

JUDGE_SYSTEM = (
    "You are a strict evaluator. Given a task, a model's response, and a rubric, decide whether "
    "the response satisfies the rubric. Reply with PASS or FAIL on the first line, then one "
    "sentence explaining why."
)


async def _judge(response: str, check: dict[str, Any], prompt: str, judge: ModelFn) -> CheckResult:
    judge_prompt = (
        f"<task>\n{prompt}\n</task>\n\n<response>\n{response}\n</response>\n\n"
        f"<rubric>\n{check['rubric']}\n</rubric>"
    )
    verdict = (await judge(JUDGE_SYSTEM, judge_prompt)).strip()
    first, _, reason = verdict.partition("\n")
    return CheckResult("judge", first.strip().upper().startswith("PASS"), reason.strip() or first)


async def grade(response: str, check: dict[str, Any], prompt: str, judge: ModelFn | None) -> CheckResult:
    kind = check.get("type")
    if kind == "judge":
        if judge is None:
            return CheckResult("judge", False, "no judge model configured")
        return await _judge(response, check, prompt, judge)
    if kind not in SYNC_GRADERS:
        return CheckResult(str(kind), False, f"unknown check type {kind!r}")
    try:
        return SYNC_GRADERS[kind](response, check)
    except (KeyError, re.error) as e:
        return CheckResult(kind, False, f"bad check config: {e}")
