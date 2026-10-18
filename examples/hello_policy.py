"""One policy, one verdict. Run:  PYTHONPATH=src python3 examples/hello_policy.py"""

from fourverdicts import BasePolicy, ExecutionPhase, GovernanceContext, PolicyResult


class NoLargeTransfers(BasePolicy):
    """Deny any transfer above a limit."""

    def __init__(self, limit: float) -> None:
        super().__init__("no-large-transfers", "Deny transfers above a limit",
                         phases=frozenset({ExecutionPhase.TOOL_PRE}), priority=10)
        self.limit = limit

    def evaluate(self, payload, context):
        if payload["amount"] > self.limit:
            return PolicyResult.deny(self.rule_id, f"{payload['amount']} is above {self.limit}")
        return PolicyResult.allow(self.rule_id, "within the limit")


if __name__ == "__main__":
    policy = NoLargeTransfers(limit=1_000)
    context = GovernanceContext(session_id="demo", agent_id="payments-agent")
    for amount in (250, 5_000):
        result = policy.safe_evaluate({"amount": amount}, context)
        print(f"transfer {amount:>6}: {result.action.value:<5} ({result.reason})")
