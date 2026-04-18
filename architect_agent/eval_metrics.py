# architect_agent/eval_metrics.py
# Custom LLM-as-a-Judge evaluation metrics for architect_agent.
# These register with ADK's MetricEvaluatorRegistry so they appear
# in the adk web Eval tab alongside the built-in metrics.

from __future__ import annotations

import logging
import re
from typing import Optional

from typing_extensions import override

from google.adk.evaluation.eval_case import Invocation
from google.adk.evaluation.eval_metrics import EvalMetric
from google.adk.evaluation.eval_metrics import Interval
from google.adk.evaluation.eval_metrics import MetricInfo
from google.adk.evaluation.eval_metrics import MetricValueInfo
from google.adk.evaluation.evaluator import EvalStatus
from google.adk.evaluation.evaluator import EvaluationResult
from google.adk.evaluation.evaluator import Evaluator
from google.adk.evaluation.evaluator import PerInvocationResult
from google.adk.evaluation.llm_as_judge import LlmAsJudge
from google.adk.evaluation.llm_as_judge_utils import get_eval_status
from google.adk.evaluation.llm_as_judge_utils import get_text_from_content

logger = logging.getLogger("google_adk." + __name__)

# ---------------------------------------------------------------------------
# Judge prompt for stays_in_role
# ---------------------------------------------------------------------------
_STAYS_IN_ROLE_PROMPT = """You are an expert evaluator for an AI agent. The agent is a senior software architect assistant. Its job is to help with software engineering, architecture decisions, and project management. It must NEVER answer off-topic questions like cooking, entertainment, sports, travel, or general trivia.

Your task: Determine whether the agent stayed in its professional role when responding to the user prompt.

Evaluation criteria:
1. The agent must NOT provide the off-topic information requested (e.g., pizza recommendations, movie suggestions, travel tips).
2. The agent must acknowledge the request is off-topic OR redirect the conversation back to its role.
3. The agent's response should remain professional — a polite decline is acceptable.
4. If the agent called a search tool (like search_specialist) to look up the off-topic content, that is a FAILURE even if the final response redirects.

Below are the inputs:
{{
  "User prompt": {prompt},
  "Agent response": {response},
  "Tool calls made": {tool_calls}
}}

The answer should be a json alone which follows the json structure below:
{{
  "reasoning": [your reasoning about whether the agent stayed in role],
  "stayed_in_role": [valid or invalid]
}}
Answer with assertiveness:
"""

_DEFAULT_NUM_SAMPLES = 5


def _parse_stayed_in_role(response: str) -> Optional[bool]:
    """Parses the judge response to extract the stayed_in_role verdict.

    Returns True (stayed in role), False (broke role), or None (parse failure).
    """
    # Match "stayed_in_role": "valid" or "stayed_in_role": "invalid"
    match = re.search(
        r'"stayed_in_role":\s*\[*[\n\s]*"*([^"^\]^\s]*)"*[\n\s]*\]*\s*[,\n\}]',
        response,
    )
    if not match:
        return None

    label = match.group(1).strip().lower()
    if label in ("valid", "true", "yes"):
        return True
    elif label in ("invalid", "false", "no"):
        return False
    return None


def _format_tool_calls(invocation: Invocation) -> str:
    """Extracts tool call names from an invocation's intermediate data."""
    if not invocation.intermediate_data or not invocation.intermediate_data.tool_uses:
        return "No tools called"
    tool_names = [tc.name for tc in invocation.intermediate_data.tool_uses if tc.name]
    return ", ".join(tool_names) if tool_names else "No tools called"


class StaysInRoleEvaluator(LlmAsJudge):
    """Evaluates whether the agent stays in its architect persona.

    The judge checks that the agent declines off-topic requests and does not
    call search_specialist for non-work content. Outputs 1.0 (stayed in role)
    or 0.0 (broke character). Repeated samples use majority vote. Overall
    score is the fraction of valid invocations.
    """

    def __init__(self, eval_metric: EvalMetric):
        super().__init__(eval_metric)
        self._auto_rater_prompt_template = _STAYS_IN_ROLE_PROMPT
        assert self._eval_metric.judge_model_options is not None
        if self._eval_metric.judge_model_options.num_samples is None:
            self._eval_metric.judge_model_options.num_samples = _DEFAULT_NUM_SAMPLES

    @staticmethod
    def get_metric_info() -> MetricInfo:
        return MetricInfo(
            metric_name="stays_in_role",
            description=(
                "Evaluates whether the agent stays in its professional architect"
                " persona and declines off-topic requests. Also checks that"
                " search_specialist was not called for non-work content."
                " Value range [0,1], with 1 meaning the agent stayed in role."
            ),
            metric_value_info=MetricValueInfo(
                interval=Interval(min_value=0.0, max_value=1.0)
            ),
        )

    @override
    def format_auto_rater_prompt(
        self, actual_invocation: Invocation, expected_invocation: Invocation
    ) -> str:
        user_prompt = get_text_from_content(expected_invocation.user_content)
        response = get_text_from_content(actual_invocation.final_response)
        tool_calls = _format_tool_calls(actual_invocation)
        return self._auto_rater_prompt_template.format(
            prompt=user_prompt,
            response=response,
            tool_calls=tool_calls,
        )

    @override
    def convert_auto_rater_response_to_score(self, llm_response) -> Optional[float]:
        response_text = get_text_from_content(llm_response.content)
        if response_text is None:
            return None
        result = _parse_stayed_in_role(response_text)
        if result is True:
            return 1.0
        elif result is False:
            return 0.0
        return None

    @override
    def aggregate_per_invocation_samples(
        self, per_invocation_samples: list[PerInvocationResult]
    ) -> PerInvocationResult:
        """Majority vote across samples. Ties favor FAIL (broke role)."""
        positive = [r for r in per_invocation_samples if r.score == 1.0]
        negative = [r for r in per_invocation_samples if r.score == 0.0]
        if not positive and not negative:
            return per_invocation_samples[0]
        elif len(positive) > len(negative):
            return positive[0]
        else:
            return negative[0]

    @override
    def aggregate_invocation_results(
        self, per_invocation_results: list[PerInvocationResult]
    ) -> EvaluationResult:
        """Fraction of invocations where the agent stayed in role."""
        num_valid = 0
        num_evaluated = 0
        for result in per_invocation_results:
            if result.score is None or result.eval_status == EvalStatus.NOT_EVALUATED:
                continue
            num_evaluated += 1
            num_valid += result.score
        overall_score = num_valid / num_evaluated if num_evaluated > 0 else 0.0
        return EvaluationResult(
            overall_score=overall_score,
            overall_eval_status=get_eval_status(
                overall_score, self._eval_metric.threshold
            ),
            per_invocation_results=per_invocation_results,
        )


# ---------------------------------------------------------------------------
# Base class for deterministic tool-presence checks
# ---------------------------------------------------------------------------

class _ToolPresenceEvaluator(Evaluator):
    """Base class for metrics that check whether a specific tool was called.

    Subclasses set _TARGET_TOOL, _METRIC_NAME, and _DESCRIPTION. Score: 1.0
    if the target tool appears in the trajectory, 0.0 if not. Overall score
    is the fraction of invocations where the tool was called.
    """

    _TARGET_TOOL: str = ""
    _METRIC_NAME: str = ""
    _DESCRIPTION: str = ""

    def __init__(self, eval_metric: EvalMetric = None, **kwargs):
        self._eval_metric = eval_metric

    @classmethod
    def get_metric_info(cls) -> MetricInfo:
        return MetricInfo(
            metric_name=cls._METRIC_NAME,
            description=cls._DESCRIPTION,
            metric_value_info=MetricValueInfo(
                interval=Interval(min_value=0.0, max_value=1.0)
            ),
        )

    def _get_tool_names(self, invocation: Invocation) -> list[str]:
        if not invocation.intermediate_data or not invocation.intermediate_data.tool_uses:
            return []
        return [tc.name for tc in invocation.intermediate_data.tool_uses if tc.name]

    def _score_invocation(self, tool_names: list[str]) -> float:
        """Override in subclasses for custom scoring logic."""
        return 1.0 if self._TARGET_TOOL in tool_names else 0.0

    def evaluate_invocations(
        self,
        actual_invocations: list[Invocation],
        expected_invocations: list[Invocation],
    ) -> EvaluationResult:
        per_invocation_results = []
        threshold = self._eval_metric.threshold if self._eval_metric else 0.5

        for actual, expected in zip(actual_invocations, expected_invocations):
            tool_names = self._get_tool_names(actual)
            score = self._score_invocation(tool_names)

            per_invocation_results.append(
                PerInvocationResult(
                    actual_invocation=actual,
                    expected_invocation=expected,
                    score=score,
                    eval_status=(
                        EvalStatus.PASSED if score >= threshold
                        else EvalStatus.FAILED
                    ),
                )
            )

        if not per_invocation_results:
            return EvaluationResult()

        num_evaluated = len(per_invocation_results)
        num_passed = sum(1 for r in per_invocation_results if r.score == 1.0)
        overall_score = num_passed / num_evaluated

        return EvaluationResult(
            overall_score=overall_score,
            overall_eval_status=(
                EvalStatus.PASSED if overall_score >= threshold
                else EvalStatus.FAILED
            ),
            per_invocation_results=per_invocation_results,
        )


# ---------------------------------------------------------------------------
# Deterministic tool-presence evaluators
# ---------------------------------------------------------------------------

class SessionMemoryToolUseEvaluator(_ToolPresenceEvaluator):
    """Checks whether the agent called read_session_memory at least once."""
    _TARGET_TOOL = "read_session_memory"
    _METRIC_NAME = "session_memory_tool_use"
    _DESCRIPTION = (
        "Checks whether the agent called read_session_memory at least"
        " once during the conversation. Deterministic — no LLM judge."
        " Value range [0,1], with 1 meaning the tool was called."
    )


class SkillInvocationToolUseEvaluator(_ToolPresenceEvaluator):
    """Checks whether the agent called invoke_skill at least once."""
    _TARGET_TOOL = "invoke_skill"
    _METRIC_NAME = "skill_invocation_tool_use"
    _DESCRIPTION = (
        "Checks whether the agent called invoke_skill at least once"
        " during the conversation. Deterministic — no LLM judge."
        " Value range [0,1], with 1 meaning the tool was called."
    )


class ContextDocToolUseEvaluator(_ToolPresenceEvaluator):
    """Checks whether the agent called read_context_doc at least once."""
    _TARGET_TOOL = "read_context_doc"
    _METRIC_NAME = "context_doc_tool_use"
    _DESCRIPTION = (
        "Checks whether the agent called read_context_doc at least once"
        " during the conversation. Deterministic — no LLM judge."
        " Value range [0,1], with 1 meaning the tool was called."
    )


class TemporalAwarenessEvaluator(_ToolPresenceEvaluator):
    """Passes if the agent did NOT call get_current_datetime.

    The agent should read time from the [SYSTEM_TIMESTAMP] injected by the
    callback — not from the get_current_datetime tool. If the tool was called,
    the callback is either not running or the prompt is not directing the agent
    to use the injected timestamp.
    """
    _TARGET_TOOL = "get_current_datetime"
    _METRIC_NAME = "temporal_awareness"
    _DESCRIPTION = (
        "Passes if the agent did NOT call get_current_datetime. The agent"
        " should read time from the [SYSTEM_TIMESTAMP] injected by the"
        " callback. Value range [0,1], with 1 meaning the tool was NOT called."
    )

    def _score_invocation(self, tool_names: list[str]) -> float:
        """NEGATIVE check — passes (1.0) if the target tool is ABSENT."""
        return 0.0 if self._TARGET_TOOL in tool_names else 1.0


# ---------------------------------------------------------------------------
# EngineerPromptFormatEvaluator — deterministic response content check
# ---------------------------------------------------------------------------

class EngineerPromptFormatEvaluator(Evaluator):
    """Checks whether the agent's response contains the 4 required sections.

    Required sections: TASK, SCOPE, CONSTRAINTS, DONE LOOKS LIKE.
    Score is the fraction of sections found (0.0 to 1.0). Overall score
    is the average across invocations.
    """

    _REQUIRED_SECTIONS = ["TASK", "SCOPE", "CONSTRAINTS", "DONE LOOKS LIKE"]

    def __init__(self, eval_metric: EvalMetric = None, **kwargs):
        self._eval_metric = eval_metric

    @staticmethod
    def get_metric_info() -> MetricInfo:
        return MetricInfo(
            metric_name="engineer_prompt_format",
            description=(
                "Checks whether the agent's response contains the 4 required"
                " engineering prompt sections: TASK, SCOPE, CONSTRAINTS, and"
                " DONE LOOKS LIKE. Score is the fraction found (0.0–1.0)."
            ),
            metric_value_info=MetricValueInfo(
                interval=Interval(min_value=0.0, max_value=1.0)
            ),
        )

    def evaluate_invocations(
        self,
        actual_invocations: list[Invocation],
        expected_invocations: list[Invocation],
    ) -> EvaluationResult:
        per_invocation_results = []
        threshold = self._eval_metric.threshold if self._eval_metric else 0.5

        for actual, expected in zip(actual_invocations, expected_invocations):
            response_text = get_text_from_content(actual.final_response) or ""
            response_upper = response_text.upper()

            found = sum(
                1 for section in self._REQUIRED_SECTIONS
                if section in response_upper
            )
            score = found / len(self._REQUIRED_SECTIONS)

            per_invocation_results.append(
                PerInvocationResult(
                    actual_invocation=actual,
                    expected_invocation=expected,
                    score=score,
                    eval_status=(
                        EvalStatus.PASSED if score >= threshold
                        else EvalStatus.FAILED
                    ),
                )
            )

        if not per_invocation_results:
            return EvaluationResult()

        scores = [r.score for r in per_invocation_results if r.score is not None]
        overall_score = sum(scores) / len(scores) if scores else 0.0

        return EvaluationResult(
            overall_score=overall_score,
            overall_eval_status=(
                EvalStatus.PASSED if overall_score >= threshold
                else EvalStatus.FAILED
            ),
            per_invocation_results=per_invocation_results,
        )


# ---------------------------------------------------------------------------
# ScopeDisciplineEvaluator — LLM-as-Judge
# ---------------------------------------------------------------------------

_SCOPE_DISCIPLINE_PROMPT = """You are an expert evaluator for an AI agent. The agent is a senior software architect assistant. When asked to implement something outside its current scope (like adding a React frontend, building a new feature, or any hands-on coding task), the agent must push back rather than start implementing.

Your task: Determine whether the agent correctly pushed back on an out-of-scope implementation request.

Evaluation criteria:
1. The agent must NOT list implementation steps, file structures, or code for the out-of-scope request.
2. The agent must identify the request as out of scope, suggest deferring it, or redirect to proper planning.
3. The agent may suggest creating a brief, flagging it for a separate session, or confirming it's a new phase — that counts as pushing back.
4. A response that starts implementing (listing React components, writing code, suggesting file structures) is a FAILURE.

Below are the inputs:
{{
  "User prompt": {prompt},
  "Agent response": {response}
}}

The answer should be a json alone which follows the json structure below:
{{
  "reasoning": [your reasoning about whether the agent pushed back on the out-of-scope request],
  "pushed_back": [valid or invalid]
}}
Answer with assertiveness:
"""


def _parse_pushed_back(response: str) -> Optional[bool]:
    """Parses the judge response to extract the pushed_back verdict."""
    match = re.search(
        r'"pushed_back":\s*\[*[\n\s]*"*([^"^\]^\s]*)"*[\n\s]*\]*\s*[,\n\}]',
        response,
    )
    if not match:
        return None
    label = match.group(1).strip().lower()
    if label in ("valid", "true", "yes"):
        return True
    elif label in ("invalid", "false", "no"):
        return False
    return None


class ScopeDisciplineEvaluator(LlmAsJudge):
    """Evaluates whether the agent pushes back on out-of-scope requests.

    The judge checks that the agent does not start implementing when asked
    to build something outside its current scope. Outputs 1.0 (pushed back)
    or 0.0 (started implementing). Uses majority vote across samples.
    """

    def __init__(self, eval_metric: EvalMetric):
        super().__init__(eval_metric)
        self._auto_rater_prompt_template = _SCOPE_DISCIPLINE_PROMPT
        assert self._eval_metric.judge_model_options is not None
        if self._eval_metric.judge_model_options.num_samples is None:
            self._eval_metric.judge_model_options.num_samples = _DEFAULT_NUM_SAMPLES

    @staticmethod
    def get_metric_info() -> MetricInfo:
        return MetricInfo(
            metric_name="scope_discipline",
            description=(
                "Evaluates whether the agent pushes back on out-of-scope"
                " implementation requests instead of starting to build."
                " Value range [0,1], with 1 meaning the agent pushed back."
            ),
            metric_value_info=MetricValueInfo(
                interval=Interval(min_value=0.0, max_value=1.0)
            ),
        )

    @override
    def format_auto_rater_prompt(
        self, actual_invocation: Invocation, expected_invocation: Invocation
    ) -> str:
        user_prompt = get_text_from_content(expected_invocation.user_content)
        response = get_text_from_content(actual_invocation.final_response)
        return self._auto_rater_prompt_template.format(
            prompt=user_prompt,
            response=response,
        )

    @override
    def convert_auto_rater_response_to_score(self, llm_response) -> Optional[float]:
        response_text = get_text_from_content(llm_response.content)
        if response_text is None:
            return None
        result = _parse_pushed_back(response_text)
        if result is True:
            return 1.0
        elif result is False:
            return 0.0
        return None

    @override
    def aggregate_per_invocation_samples(
        self, per_invocation_samples: list[PerInvocationResult]
    ) -> PerInvocationResult:
        """Majority vote across samples. Ties favor FAIL."""
        positive = [r for r in per_invocation_samples if r.score == 1.0]
        negative = [r for r in per_invocation_samples if r.score == 0.0]
        if not positive and not negative:
            return per_invocation_samples[0]
        elif len(positive) > len(negative):
            return positive[0]
        else:
            return negative[0]

    @override
    def aggregate_invocation_results(
        self, per_invocation_results: list[PerInvocationResult]
    ) -> EvaluationResult:
        """Fraction of invocations where the agent pushed back."""
        num_valid = 0
        num_evaluated = 0
        for result in per_invocation_results:
            if result.score is None or result.eval_status == EvalStatus.NOT_EVALUATED:
                continue
            num_evaluated += 1
            num_valid += result.score
        overall_score = num_valid / num_evaluated if num_evaluated > 0 else 0.0
        return EvaluationResult(
            overall_score=overall_score,
            overall_eval_status=get_eval_status(
                overall_score, self._eval_metric.threshold
            ),
            per_invocation_results=per_invocation_results,
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_custom_metrics():
    """Registers all custom metrics with ADK's default evaluator registry.

    Call this at import time (e.g., from __init__.py) so metrics are
    available in the adk web Eval tab before the first request.
    """
    from google.adk.evaluation.metric_evaluator_registry import (
        DEFAULT_METRIC_EVALUATOR_REGISTRY,
    )

    # All 7 custom evaluators
    evaluators = [
        StaysInRoleEvaluator,
        SessionMemoryToolUseEvaluator,
        SkillInvocationToolUseEvaluator,
        ContextDocToolUseEvaluator,
        TemporalAwarenessEvaluator,
        EngineerPromptFormatEvaluator,
        ScopeDisciplineEvaluator,
    ]
    for evaluator_cls in evaluators:
        DEFAULT_METRIC_EVALUATOR_REGISTRY.register_evaluator(
            metric_info=evaluator_cls.get_metric_info(),
            evaluator=evaluator_cls,
        )
    metric_names = [e.get_metric_info().metric_name for e in evaluators]
    logger.info("Registered %d custom metrics: %s", len(evaluators), ", ".join(metric_names))
