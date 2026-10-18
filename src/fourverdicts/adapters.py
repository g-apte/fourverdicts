"""The adapter: put the engine in front of an ordinary function with one decorator."""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Optional

from fourverdicts.engine import GovernanceEngine, GovernanceOutcome
from fourverdicts.types import ExecutionPhase, GovernanceAction, GovernanceContext

Approver = Callable[[GovernanceOutcome], bool]
Observer = Callable[[GovernanceOutcome], None]


class GovernanceDenied(Exception):
    """Raised instead of running the tool when the decision is DENY, or approval was not given."""

    def __init__(self, outcome: GovernanceOutcome, message: str) -> None:
        super().__init__(message)
        self.outcome = outcome


def governed_tool(
    engine: GovernanceEngine,
    context: GovernanceContext,
    approver: Optional[Approver] = None,
    observer: Optional[Observer] = None,
    name: Optional[str] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a tool so every call is judged first, at the TOOL_PRE phase.

    - ALLOW: the tool runs with the arguments as given.
    - MODIFY: the tool runs with the amended arguments.
    - REQUIRE_APPROVAL: `approver(outcome)` decides. With no approver, the call is refused.
    - DENY: `GovernanceDenied` is raised and the tool never runs.

    `observer`, if given, is called with every outcome before anything else happens (for logging
    or to show the decision).
    """

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or fn.__name__
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            payload = {"tool": tool_name, "arguments": dict(bound.arguments)}
            outcome = engine.evaluate(ExecutionPhase.TOOL_PRE, context, payload)
            if observer is not None:
                observer(outcome)

            if outcome.action is GovernanceAction.DENY:
                raise GovernanceDenied(outcome, f"{tool_name} denied: {outcome.reason}")
            if outcome.action is GovernanceAction.REQUIRE_APPROVAL:
                if approver is None or not approver(outcome):
                    raise GovernanceDenied(outcome, f"{tool_name} not approved: {outcome.reason}")
            return fn(**outcome.payload["arguments"])

        return wrapper

    return decorate
