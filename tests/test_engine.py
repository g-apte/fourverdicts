import unittest

from fourverdicts import (
    BasePolicy,
    ExecutionPhase,
    FailMode,
    GovernanceAction,
    GovernanceContext,
    PolicyResult,
)
from fourverdicts.engine import GovernanceEngine

CONTEXT = GovernanceContext(session_id="s", agent_id="a")
PHASE = ExecutionPhase.TOOL_PRE


class Returns(BasePolicy):
    def __init__(self, rule_id, result_fn, **kwargs):
        super().__init__(rule_id, **kwargs)
        self._fn = result_fn
        self.seen = []

    def evaluate(self, payload, context):
        self.seen.append(payload)
        return self._fn(self.rule_id, payload)


def allow(r, p): return PolicyResult.allow(r, "fine")
def deny(r, p): return PolicyResult.deny(r, "no")
def approve(r, p): return PolicyResult.require_approval(r, "ask")
def cap(r, p): return PolicyResult.modify(r, {**p, "amount": 5}, "capped")


class EngineTests(unittest.TestCase):
    def engine(self, *policies):
        e = GovernanceEngine()
        for p in policies:
            e.register(p)
        return e

    def test_no_policies_allows(self):
        out = self.engine().evaluate(PHASE, CONTEXT, {"amount": 1})
        self.assertIs(out.action, GovernanceAction.ALLOW)
        self.assertEqual(out.reason, "no policy applied")

    def test_strictest_verdict_wins_whatever_the_order(self):
        cases = [
            ([allow, cap], GovernanceAction.MODIFY),
            ([cap, approve], GovernanceAction.REQUIRE_APPROVAL),
            ([approve, deny, allow], GovernanceAction.DENY),
            ([allow, allow], GovernanceAction.ALLOW),
        ]
        for fns, expected in cases:
            for order in (fns, list(reversed(fns))):
                with self.subTest(expected=expected, order=[f.__name__ for f in order]):
                    pols = [Returns(f"r{i}", f, priority=i) for i, f in enumerate(order)]
                    out = self.engine(*pols).evaluate(PHASE, CONTEXT, {"amount": 100})
                    self.assertIs(out.action, expected)

    def test_policies_run_in_priority_then_rule_id_order(self):
        order = []
        def record(r, p):
            order.append(r)
            return PolicyResult.allow(r)
        e = self.engine(Returns("b", record, priority=1), Returns("a", record, priority=1), Returns("c", record, priority=0))
        e.evaluate(PHASE, CONTEXT, {})
        self.assertEqual(order, ["c", "a", "b"])

    def test_modify_rewrites_the_payload_for_later_policies(self):
        first = Returns("first", cap, priority=1)
        second = Returns("second", allow, priority=2)
        out = self.engine(first, second).evaluate(PHASE, CONTEXT, {"amount": 100})
        self.assertEqual(second.seen, [{"amount": 5}])
        self.assertEqual(out.payload, {"amount": 5})

    def test_every_policy_runs_even_after_a_deny(self):
        later = Returns("later", allow, priority=2)
        out = self.engine(Returns("stop", deny, priority=1), later).evaluate(PHASE, CONTEXT, {})
        self.assertIs(out.action, GovernanceAction.DENY)
        self.assertEqual(len(later.seen), 1)
        self.assertEqual(len(out.results), 2)

    def test_decisive_is_the_first_policy_with_the_strictest_verdict(self):
        e = self.engine(Returns("a", deny, priority=1), Returns("b", deny, priority=2))
        self.assertEqual(e.evaluate(PHASE, CONTEXT, {}).decisive.rule_id, "a")

    def test_only_policies_for_the_phase_run(self):
        other = Returns("other", deny, phases=frozenset({ExecutionPhase.OUTPUT}))
        out = self.engine(other).evaluate(PHASE, CONTEXT, {})
        self.assertIs(out.action, GovernanceAction.ALLOW)

    def test_crashing_policy_denies_unless_set_to_fail_open(self):
        def boom(r, p): raise RuntimeError("x")
        closed = self.engine(Returns("c", boom)).evaluate(PHASE, CONTEXT, {})
        opened = self.engine(Returns("o", boom, fail_mode=FailMode.FAIL_OPEN)).evaluate(PHASE, CONTEXT, {})
        self.assertIs(closed.action, GovernanceAction.DENY)
        self.assertIs(opened.action, GovernanceAction.ALLOW)

    def test_modify_without_a_payload_is_a_deny(self):
        out = self.engine(Returns("m", lambda r, p: PolicyResult(GovernanceAction.MODIFY, r))).evaluate(PHASE, CONTEXT, {})
        self.assertIs(out.action, GovernanceAction.DENY)

    def test_duplicate_and_wrong_type_registration(self):
        e = self.engine(Returns("a", allow))
        with self.assertRaises(ValueError):
            e.register(Returns("a", allow))
        with self.assertRaises(TypeError):
            e.register("not a policy")


if __name__ == "__main__":
    unittest.main()
