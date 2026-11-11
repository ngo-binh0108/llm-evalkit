"""Command-line entry point: `evalkit run cases.jsonl`."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from . import report
from .cases import load_cases
from .runner import run_all


def _run(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases)
    if args.tag:
        cases = [c for c in cases if args.tag in c.tags]
    if not cases:
        print("No cases to run.", file=sys.stderr)
        return 1
    from . import models

    # models.claude() imports anthropic when it is called, so that is where a missing SDK shows up
    uses_judge = any(ch.get("type") == "judge" for c in cases for ch in c.checks)
    try:
        model = models.claude(args.model, effort=args.effort)
        judge = models.claude(args.judge_model, effort="low") if uses_judge else None
    except ImportError:
        print("Running evals needs the Anthropic SDK: pip install 'llm-evalkit[claude]'", file=sys.stderr)
        return 1

    results = asyncio.run(run_all(cases, model, judge, args.concurrency))
    print(report.to_text(results))
    if args.markdown:
        Path(args.markdown).write_text(report.to_markdown(results), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(report.to_json(results), encoding="utf-8")
    rate = report.summary(results)["pass_rate"]
    return 0 if rate >= args.fail_under else 2


def _validate(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases)
    print(f"{len(cases)} valid case(s) in {args.cases}")
    return 0


def main(argv: list[str] | None = None) -> int:
    from .models import DEFAULT_MODEL

    parser = argparse.ArgumentParser(prog="evalkit", description="Lightweight evals for LLM prompts.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="run a JSONL suite against Claude")
    p.add_argument("cases")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--judge-model", default=DEFAULT_MODEL)
    p.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--tag", help="only run cases with this tag")
    p.add_argument("--markdown", help="write a Markdown report to this path")
    p.add_argument("--json", help="write a JSON report to this path")
    p.add_argument("--fail-under", type=float, default=1.0, help="exit 2 if pass rate is below this (0-1)")
    p.set_defaults(func=_run)

    p = sub.add_parser("validate", help="check a suite file without calling a model")
    p.add_argument("cases")
    p.set_defaults(func=_validate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
