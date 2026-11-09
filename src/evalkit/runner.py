"""Run cases concurrently against a model and grade the responses."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from .cases import Case
from .graders import CheckResult, ModelFn, grade


@dataclass
class CaseResult:
    case: Case
    response: str = ""
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None
    seconds: float = 0.0

    @property
    def passed(self) -> bool:
        return self.error is None and all(c.passed for c in self.checks)


async def run_case(case: Case, model: ModelFn, judge: ModelFn | None) -> CaseResult:
    start = time.perf_counter()
    result = CaseResult(case)
    try:
        result.response = await model(case.system, case.prompt)
        for check in case.checks:
            result.checks.append(await grade(result.response, check, case.prompt, judge))
    except Exception as e:  # one failing case must not abort the whole run
        result.error = f"{type(e).__name__}: {e}"
    result.seconds = time.perf_counter() - start
    return result


async def run_all(
    cases: list[Case],
    model: ModelFn,
    judge: ModelFn | None = None,
    concurrency: int = 4,
) -> list[CaseResult]:
    """Run every case with at most `concurrency` in flight; results keep input order."""
    sem = asyncio.Semaphore(max(1, concurrency))

    async def bounded(case: Case) -> CaseResult:
        async with sem:
            return await run_case(case, model, judge)

    return list(await asyncio.gather(*(bounded(c) for c in cases)))
