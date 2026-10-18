"""The vocabulary: four verdicts, seven lifecycle phases, and what a policy returns."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class GovernanceAction(str, Enum):
    """The verdict a policy returns about an agent action."""

    ALLOW = "ALLOW"                      # proceed unchanged
    MODIFY = "MODIFY"                    # proceed with an amended payload
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"  # pause until a person approves
    DENY = "DENY"                        # block the action


# When several policies disagree, the strictest verdict wins. Higher number = stricter.
STRICTNESS: Mapping[GovernanceAction, int] = {
    GovernanceAction.ALLOW: 0,
    GovernanceAction.MODIFY: 1,
    GovernanceAction.REQUIRE_APPROVAL: 2,
    GovernanceAction.DENY: 3,
}


class ExecutionPhase(str, Enum):
    """The seven points in an agent's life where governance can look and decide."""

    INPUT = "INPUT"                        # a prompt arrives
    STATE_PLAN = "STATE_PLAN"              # the agent plans or updates its state
    TOOL_PRE = "TOOL_PRE"                  # just before a tool runs
    TOOL_POST = "TOOL_POST"                # just after a tool returns
    OUTPUT = "OUTPUT"                      # before the answer leaves
    INTER_AGENT_OUT = "INTER_AGENT_OUT"    # before work is handed to another agent
    INTER_AGENT_IN = "INTER_AGENT_IN"      # when another agent's result comes back


@dataclass(frozen=True)
class GovernanceContext:
    """Who is acting, and in which session."""

    session_id: str
    agent_id: str
    role: str = "agent"
    trace_id: str = ""


@dataclass(frozen=True)
class PolicyResult:
    """What one policy decided, and why."""

    action: GovernanceAction
    rule_id: str
    reason: str = ""
    modified_payload: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls, rule_id: str, reason: str = "") -> "PolicyResult":
        return cls(GovernanceAction.ALLOW, rule_id, reason)

    @classmethod
    def modify(cls, rule_id: str, modified_payload: Any, reason: str = "") -> "PolicyResult":
        return cls(GovernanceAction.MODIFY, rule_id, reason, modified_payload)

    @classmethod
    def require_approval(cls, rule_id: str, reason: str = "") -> "PolicyResult":
        return cls(GovernanceAction.REQUIRE_APPROVAL, rule_id, reason)

    @classmethod
    def deny(cls, rule_id: str, reason: str = "") -> "PolicyResult":
        return cls(GovernanceAction.DENY, rule_id, reason)
