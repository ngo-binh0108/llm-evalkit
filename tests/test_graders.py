import asyncio

from evalkit.graders import grade


def g(response, check, judge=None):
    return asyncio.run(grade(response, check, "prompt", judge))


def test_contains_is_case_insensitive_by_default():
    assert g("The capital is PARIS.", {"type": "contains", "value": "paris"}).passed
    assert not g("Paris", {"type": "contains", "value": "paris", "ignore_case": False}).passed


def test_not_contains():
    assert g("simple words", {"type": "not_contains", "value": "transformer"}).passed
    assert not g("a Transformer", {"type": "not_contains", "value": "transformer"}).passed


def test_regex_and_exact():
    assert g(" 391\n", {"type": "regex", "pattern": r"^\s*391\s*$"}).passed
    assert g("  yes ", {"type": "exact", "value": "yes"}).passed
    assert not g("yes!", {"type": "exact", "value": "yes"}).passed


def test_json_accepts_code_fences_and_checks_keys():
    assert g('```json\n{"name": "Linh", "age": 29}\n```', {"type": "json", "required_keys": ["name", "age"]}).passed
    r = g('{"name": "Linh"}', {"type": "json", "required_keys": ["name", "age"]})
    assert not r.passed and "age" in r.detail
    assert not g("not json", {"type": "json"}).passed


def test_max_words():
    assert g("one two three", {"type": "max_words", "value": 3}).passed
    assert not g("one two three four", {"type": "max_words", "value": 3}).passed


def test_unknown_type_and_bad_config_fail_cleanly():
    assert "unknown" in g("x", {"type": "nope"}).detail
    assert not g("x", {"type": "regex", "pattern": "("}).passed
    assert not g("x", {"type": "contains"}).passed


def test_judge_uses_first_line_verdict():
    async def passing(system, prompt):
        assert "<rubric>" in prompt
        return "PASS\nLooks right."

    async def failing(system, prompt):
        return "FAIL\nInvented an answer."

    assert g("resp", {"type": "judge", "rubric": "r"}, passing).passed
    r = g("resp", {"type": "judge", "rubric": "r"}, failing)
    assert not r.passed and r.detail == "Invented an answer."
    assert not g("resp", {"type": "judge", "rubric": "r"}).passed
