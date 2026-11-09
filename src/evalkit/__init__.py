"""llm-evalkit: lightweight, test-style evaluations for LLM prompts."""

from .cases import Case, load_cases
from .graders import CheckResult, grade
from .runner import CaseResult, run_all

__all__ = ["Case", "CaseResult", "CheckResult", "grade", "load_cases", "run_all"]
__version__ = "0.1.0"
