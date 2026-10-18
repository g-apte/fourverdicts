"""A readable account of a decision, for people who do not read code."""

from __future__ import annotations

from fourverdicts.engine import GovernanceOutcome


def format_outcome(outcome: GovernanceOutcome) -> str:
    """One line per policy, then the decision and the reason."""
    lines = []
    for r in outcome.results:
        lines.append(f"    {r.rule_id:<24} {r.action.value:<17} {r.reason}")
    if outcome.action.value == "ALLOW":
        why = "no policy objected"
    else:
        why = outcome.reason
    lines.append(f"  decision: {outcome.action.value}  ({why})")
    return "\n".join(lines)
