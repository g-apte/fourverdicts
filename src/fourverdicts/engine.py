"""The engine: runs every policy for a phase and reaches one decision."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from fourverdicts.policy import BasePolicy
from fourverdicts.types import (
    STRICTNESS,
    ExecutionPhase,
    GovernanceAction,
    GovernanceContext,
    PolicyResult,
)


@dataclass(frozen=True)
class GovernanceOutcome:
    """The engine's decision.

    `action` is the strictest verdict any policy returned. `decisive` is the first policy (in
    evaluation order) that returned it. `payload` is the payload after any MODIFY verdicts, so a
    person asked to approve sees what would actually run. `results` lists every policy's answer.
    """

    action: GovernanceAction
    payload: Any
    decisive: PolicyResult | None
    results: Tuple[PolicyResult, ...]

    @property
    def reason(self) -> str:
        return self.decisive.reason if self.decisive else "no policy applied"


class GovernanceEngine:
    """Register policies, then call `evaluate` at each point where the agent should be governed."""

    def __init__(self) -> None:
        self._policies: Dict[str, BasePolicy] = {}

    def register(self, policy: BasePolicy) -> None:
        if not isinstance(policy, BasePolicy):
            raise TypeError(f"expected a BasePolicy, got {type(policy).__name__}")
        if policy.rule_id in self._policies:
            raise ValueError(f"duplicate rule_id: {policy.rule_id!r}")
        self._policies[policy.rule_id] = policy

    def evaluate(self, phase: ExecutionPhase, context: GovernanceContext, payload: Any) -> GovernanceOutcome:
        """Run all policies for the phase in (priority, rule_id) order and fold their verdicts.

        Rules:
        - the strictest verdict wins: DENY, then REQUIRE_APPROVAL, then MODIFY, then ALLOW;
        - a MODIFY verdict rewrites the payload for the policies that run after it;
        - every policy runs, even after a DENY, so the record shows everything that applied;
        - a policy that crashes is a DENY unless it was set to fail open.
        - each policy sees its own copy of the payload; only a MODIFY verdict changes it.
        """
        ordered = sorted(
            (p for p in self._policies.values() if phase in p.phases),
            key=lambda p: (p.priority, p.rule_id),
        )
        current = payload
        results = []
        for policy in ordered:
            try:
                # Each policy gets its own copy, so changing the payload in place cannot change what
                # later policies see or what the tool runs with. The only way to change it is MODIFY.
                seen = deepcopy(current)
            except Exception as exc:
                results.append(PolicyResult.deny(policy.rule_id, f"payload could not be copied: {exc}"))
                continue
            result = policy.safe_evaluate(seen, context)
            if result.action is GovernanceAction.MODIFY:
                current = result.modified_payload
            results.append(result)

        if not results:
            return GovernanceOutcome(GovernanceAction.ALLOW, current, None, ())
        strictest = max(STRICTNESS[r.action] for r in results)
        decisive = next(r for r in results if STRICTNESS[r.action] == strictest)
        return GovernanceOutcome(decisive.action, current, decisive, tuple(results))
