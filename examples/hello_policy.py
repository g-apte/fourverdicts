"""One policy, three verdicts. Run:  PYTHONPATH=src python3 examples/hello_policy.py"""

from fourverdicts import BasePolicy, ExecutionPhase, GovernanceContext, PolicyResult


class TransferLimit(BasePolicy):
    """Allow up to a limit, cap anything up to twice the limit, deny anything above that."""

    def __init__(self, limit: float) -> None:
        super().__init__("transfer-limit", "Cap or deny large transfers",
                         phases=frozenset({ExecutionPhase.TOOL_PRE}), priority=10)
        self.limit = limit

    def evaluate(self, payload, context):
        amount = payload["amount"]
        if amount <= self.limit:
            return PolicyResult.allow(self.rule_id, "within the limit")
        if amount <= 2 * self.limit:
            return PolicyResult.modify(self.rule_id, {**payload, "amount": self.limit}, f"capped at {self.limit}")
        return PolicyResult.deny(self.rule_id, f"{amount} is more than twice the limit of {self.limit}")


if __name__ == "__main__":
    policy = TransferLimit(limit=1_000)
    context = GovernanceContext(session_id="demo", agent_id="payments-agent")
    for amount in (250, 1_500, 5_000):
        result = policy.safe_evaluate({"amount": amount}, context)
        print(f"transfer {amount:>6}: {result.action.value:<6} ({result.reason})")
