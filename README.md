# llm-evalkit

[![tests](https://github.com/ngo-binh0108/llm-evalkit/actions/workflows/tests.yml/badge.svg)](https://github.com/ngo-binh0108/llm-evalkit/actions/workflows/tests.yml)

Lightweight, test-style **evaluations for LLM prompts**. You write cases in a JSONL file, run them against Claude, and get a pass rate, like a unit test suite for prompts.

- **Rule-based checks:** `contains`, `not_contains`, `regex`, `exact`, `json` (with required keys), `max_words`
- **LLM-as-judge:** `judge` grades a response against a plain-English rubric
- **Concurrent:** cases run in parallel, with a configurable limit
- **Reports:** console summary, Markdown table, or JSON. Results can be broken down by tag.
- **CI-friendly:** `--fail-under 0.9` exits non-zero when the pass rate drops below 90%

## Install

```bash
git clone https://github.com/ngo-binh0108/llm-evalkit.git
cd llm-evalkit
pip install -e ".[claude]"      # add ",dev" for pytest
export ANTHROPIC_API_KEY=sk-ant-...
```

## Quick start

```bash
evalkit validate examples/basic.jsonl          # check the file, no API calls
evalkit run examples/basic.jsonl --markdown report.md
```

```
[PASS] capital-france  (1.2s)
[PASS] arithmetic  (0.9s)
[PASS] json-extract  (1.4s)
[FAIL] no-jargon  (3.1s)
       x max_words: 64 words (limit 60)
[PASS] refuse-unknown  (2.0s)

4/5 passed (80%)
  extraction: 1/1
  facts: 1/1
  ...
```

## Writing cases

Each line of the JSONL file is one case:

```json
{"id": "json-extract",
 "system": "Reply with JSON only, no prose.",
 "prompt": "Extract the name and age from: 'Linh is 29 years old.'",
 "checks": [
   {"type": "json", "required_keys": ["name", "age"]},
   {"type": "contains", "value": "29"}
 ],
 "tags": ["extraction"]}
```

A case passes only when **every** check passes.

| Check | Options | Passes when |
|---|---|---|
| `contains` | `value`, `ignore_case` (default `true`) | the response contains `value` |
| `not_contains` | `value`, `ignore_case` | the response does not contain `value` |
| `regex` | `pattern`, `ignore_case` | `pattern` matches anywhere in the response |
| `exact` | `value` | the trimmed response equals `value` |
| `json` | `required_keys` | the response parses as JSON (code fences allowed) and has the keys |
| `max_words` | `value` | the word count is at most `value` |
| `judge` | `rubric` | a judge model answers PASS for the rubric |

## CLI options

| Flag | Default | Description |
|---|---|---|
| `--model` | `claude-opus-5-5` | Model under test (or set `EVALKIT_MODEL`) |
| `--judge-model` | `claude-opus-5-5` | Model used for `judge` checks |
| `--effort` | `medium` | `low` / `medium` / `high` / `xhigh` / `max` |
| `--concurrency` | `4` | Cases in flight at once |
| `--tag` | none | Only run cases with this tag |
| `--markdown PATH` / `--json PATH` | none | Write a report file |
| `--fail-under` | `1.0` | Exit code 2 if the pass rate is below this |

## Use as a library

Any async `(system, prompt) -> str` function works as the model, so you can evaluate other providers or a local stub:

```python
import asyncio
from evalkit import load_cases, run_all
from evalkit.report import to_text

async def my_model(system, prompt):
    return "Paris"

results = asyncio.run(run_all(load_cases("examples/basic.jsonl"), my_model))
print(to_text(results))
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

The tests stub the model and the Anthropic client, so they need no API key and make no network calls.

## License

MIT
