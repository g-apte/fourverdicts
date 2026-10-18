"""The policy interface: a small piece of code that looks at an action and returns a verdict."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, FrozenSet

from fourverdicts.types import (
    ExecutionPhase,
    GovernanceAction,
    GovernanceContext,
    PolicyResult,
)


class EnforcementMode(str, Enum):
    """How hard a policy pushes when it finds a violation."""

    BLOCK = "BLOCK"          # a violation is a DENY
    ESCALATE = "ESCALATE"    # a violation asks a person instead (DENY becomes REQUIRE_APPROVAL)
    WARN_ONLY = "WARN_ONLY"  # shadow mode: record what would have happened, allow


class FailMode(str, Enum):
    """What happens when the policy itself crashes."""

    FAIL_CLOSED = "FAIL_CLOSED"  # a crash is a DENY (the safe default)
    FAIL_OPEN = "FAIL_OPEN"      # a crash is allowed through, to protect availability


class BasePolicy(ABC):
    """Subclass this and implement `evaluate`. Everything else is handled for you."""

    def __init__(
        self,
        rule_id: str,
        description: str = "",
        phases: FrozenSet[ExecutionPhase] = frozenset({ExecutionPhase.TOOL_PRE}),
        priority: int = 100,
        enforcement_mode: EnforcementMode = EnforcementMode.BLOCK,
        fail_mode: FailMode = FailMode.FAIL_CLOSED,
    ) -> None:
        if not rule_id or not rule_id.strip():
            raise ValueError("rule_id must not be empty")
        self.rule_id = rule_id
        self.description = description
        self.phases = frozenset(phases)
        self.priority = priority
        self.enforcement_mode = enforcement_mode
        self.fail_mode = fail_mode

    @abstractmethod
    def evaluate(self, payload: Any, context: GovernanceContext) -> PolicyResult:
        """Look at the payload and return a verdict."""

    def safe_evaluate(self, payload: Any, context: GovernanceContext) -> PolicyResult:
        """Run `evaluate`, then apply the failure mode and the enforcement mode."""
        try:
            result = self.evaluate(payload, context)
            if not isinstance(result, PolicyResult):
                raise TypeError(f"evaluate must return a PolicyResult, got {type(result).__name__}")
        except Exception as exc:  # a crashing policy must never silently allow
            if self.fail_mode is FailMode.FAIL_OPEN:
                return PolicyResult.allow(self.rule_id, f"policy error ignored (fail open): {exc}")
            return PolicyResult.deny(self.rule_id, f"policy error (fail closed): {exc}")
        return self._apply_mode(result)

    def _apply_mode(self, result: PolicyResult) -> PolicyResult:
        if result.action is GovernanceAction.ALLOW:
            return result
        if self.enforcement_mode is EnforcementMode.WARN_ONLY:
            return PolicyResult.allow(
                self.rule_id, f"warn only: would have been {result.action.value}: {result.reason}"
            )
        if self.enforcement_mode is EnforcementMode.ESCALATE and result.action is GovernanceAction.DENY:
            return PolicyResult.require_approval(self.rule_id, result.reason)
        return result
