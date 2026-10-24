"""A transfer agent under governance. Scripted, so it runs the same way every time.

The rules: up to 5,000 goes through, 5,000 to 10,000 is capped at 5,000, above 10,000 a person decides,
and one account is blocked outright.

Run:  PYTHONPATH=src python3 examples/transfer_demo.py
"""

from fourverdicts import (
    BasePolicy,
    ExecutionPhase,
    GovernanceContext,
    GovernanceEngine,
    PolicyResult,
)
from fourverdicts.adapters import GovernanceDenied, governed_tool
from fourverdicts.report import format_outcome

BLOCKED_ACCOUNTS = {"ACC-9999"}
SOFT_CAP = 5_000
APPROVAL_ABOVE = 10_000


class BlockedAccount(BasePolicy):
    def __init__(self):
        super().__init__("blocked-account", phases=frozenset({ExecutionPhase.TOOL_PRE}), priority=10)

    def evaluate(self, payload, context):
        if payload["arguments"]["to_account"] in BLOCKED_ACCOUNTS:
            return PolicyResult.deny(self.rule_id, "destination account is blocked")
        return PolicyResult.allow(self.rule_id, "destination account is fine")


class SoftCap(BasePolicy):
    def __init__(self):
        super().__init__("soft-cap", phases=frozenset({ExecutionPhase.TOOL_PRE}), priority=20)

    def evaluate(self, payload, context):
        amount = payload["arguments"]["amount"]
        if SOFT_CAP < amount <= APPROVAL_ABOVE:
            amended = {**payload, "arguments": {**payload["arguments"], "amount": SOFT_CAP}}
            return PolicyResult.modify(self.rule_id, amended, f"capped at {SOFT_CAP:,}")
        if amount > APPROVAL_ABOVE:
            return PolicyResult.allow(self.rule_id, f"above {APPROVAL_ABOVE:,}: left to approval")
        return PolicyResult.allow(self.rule_id, "no cap needed")


class LargeTransferApproval(BasePolicy):
    def __init__(self):
        super().__init__("large-transfer-approval", phases=frozenset({ExecutionPhase.TOOL_PRE}), priority=30)

    def evaluate(self, payload, context):
        if payload["arguments"]["amount"] > APPROVAL_ABOVE:
            return PolicyResult.require_approval(self.rule_id, f"above {APPROVAL_ABOVE:,}: a person must approve")
        return PolicyResult.allow(self.rule_id, "below the approval threshold")


def main() -> None:
    engine = GovernanceEngine()
    for policy in (BlockedAccount(), SoftCap(), LargeTransferApproval()):
        engine.register(policy)

    approvals = iter([True, False])  # the scripted human: approves the first request, refuses the second

    def human(outcome):
        decision = next(approvals)
        print(f"  a person is asked: {'approved' if decision else 'refused'}")
        return decision

    context = GovernanceContext(session_id="demo", agent_id="payments-agent")
    @governed_tool(engine, context, approver=human, observer=lambda outcome: print(format_outcome(outcome)))
    def transfer_funds(to_account: str, amount: float) -> str:
        return f"moved {amount:,.0f} to {to_account}"

    scenarios = [
        ("a small transfer", "ACC-1001", 400),
        ("a transfer above the soft cap", "ACC-1001", 7_500),
        ("a transfer to a blocked account", "ACC-9999", 300),
        ("a very large transfer (person approves)", "ACC-1001", 50_000),
        ("a very large transfer (person refuses)", "ACC-1001", 80_000),
    ]
    for title, account, amount in scenarios:
        print(f"\n{title}: transfer_funds({account!r}, {amount:,})")
        try:
            print("  result:", transfer_funds(account, amount))
        except GovernanceDenied as denied:
            print("  result: BLOCKED,", denied)


if __name__ == "__main__":
    main()
