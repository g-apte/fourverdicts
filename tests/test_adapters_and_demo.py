import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from fourverdicts import (
    BasePolicy,
    ExecutionPhase,
    GovernanceAction,
    GovernanceContext,
    GovernanceEngine,
    PolicyResult,
)
from fourverdicts.adapters import GovernanceDenied, governed_tool
from fourverdicts.report import format_outcome

CONTEXT = GovernanceContext(session_id="s", agent_id="a")


class Rule(BasePolicy):
    def __init__(self, fn):
        super().__init__("rule", phases=frozenset({ExecutionPhase.TOOL_PRE}))
        self._fn = fn

    def evaluate(self, payload, context):
        return self._fn(self.rule_id, payload)


def tool_with(fn, approver=None, observer=None):
    engine = GovernanceEngine()
    engine.register(Rule(fn))
    calls = []

    @governed_tool(engine, CONTEXT, approver=approver, observer=observer)
    def move(to: str, amount: int = 1) -> str:
        calls.append((to, amount))
        return f"moved {amount} to {to}"

    return move, calls


class AdapterTests(unittest.TestCase):
    def test_allow_runs_the_tool_with_the_arguments_as_given(self):
        move, calls = tool_with(lambda r, p: PolicyResult.allow(r))
        self.assertEqual(move("x", amount=5), "moved 5 to x")
        self.assertEqual(calls, [("x", 5)])

    def test_defaults_are_part_of_the_judged_payload(self):
        seen = []
        move, _ = tool_with(lambda r, p: (seen.append(p), PolicyResult.allow(r))[1])
        move("x")
        self.assertEqual(seen[0], {"tool": "move", "arguments": {"to": "x", "amount": 1}})

    def test_modify_runs_the_tool_with_the_amended_arguments(self):
        amend = lambda r, p: PolicyResult.modify(r, {**p, "arguments": {**p["arguments"], "amount": 2}})
        move, calls = tool_with(amend)
        move("x", amount=100)
        self.assertEqual(calls, [("x", 2)])

    def test_deny_never_runs_the_tool(self):
        move, calls = tool_with(lambda r, p: PolicyResult.deny(r, "no"))
        with self.assertRaises(GovernanceDenied) as ctx:
            move("x")
        self.assertEqual(calls, [])
        self.assertIs(ctx.exception.outcome.action, GovernanceAction.DENY)

    def test_approval_needed_and_no_approver_means_refused(self):
        move, calls = tool_with(lambda r, p: PolicyResult.require_approval(r, "ask"))
        with self.assertRaises(GovernanceDenied):
            move("x")
        self.assertEqual(calls, [])

    def test_approver_decides(self):
        move, calls = tool_with(lambda r, p: PolicyResult.require_approval(r, "ask"), approver=lambda o: True)
        move("x")
        self.assertEqual(calls, [("x", 1)])
        move2, calls2 = tool_with(lambda r, p: PolicyResult.require_approval(r, "ask"), approver=lambda o: False)
        with self.assertRaises(GovernanceDenied):
            move2("x")
        self.assertEqual(calls2, [])

    def test_observer_sees_every_outcome_before_the_tool_runs(self):
        order = []
        move, calls = tool_with(lambda r, p: PolicyResult.allow(r), observer=lambda o: order.append(("seen", len(calls))))
        move("x")
        self.assertEqual(order, [("seen", 0)])


class SignatureTests(unittest.TestCase):
    """The decorator must call the tool the way the tool was written, including after a MODIFY."""

    def governed(self, fn, rule=lambda r, p: PolicyResult.allow(r), name=None):
        engine = GovernanceEngine()
        engine.register(Rule(rule))
        return governed_tool(engine, CONTEXT, name=name)(fn)

    def test_positional_only_arguments(self):
        def fn(a, /, b=2):
            return (a, b)
        self.assertEqual(self.governed(fn)(1), (1, 2))
        self.assertEqual(self.governed(fn)(1, b=3), (1, 3))

    def test_star_args_and_star_kwargs(self):
        def fn(first, *rest, **extra):
            return (first, rest, extra)
        self.assertEqual(self.governed(fn)(1, 2, 3, k=4), (1, (2, 3), {"k": 4}))

    def test_modify_works_with_unusual_signatures(self):
        def bump(r, p):
            args = dict(p["arguments"])
            args["first"] = 99
            return PolicyResult.modify(r, {**p, "arguments": args})
        def fn(first, /, *rest, **extra):
            return (first, rest, extra)
        self.assertEqual(self.governed(fn, bump)(1, 2, k=3), (99, (2,), {"k": 3}))

    def test_malformed_modified_payloads_fail_closed(self):
        bad_payloads = {
            "no arguments key": {"amount": 2},
            "arguments not a mapping": {"tool": "t", "arguments": [1]},
            "a missing argument": {"tool": "t", "arguments": {}},
            "an extra argument": {"tool": "t", "arguments": {"amount": 1, "extra": 2}},
            "not a mapping at all": "x",
        }
        calls = []
        def fn(amount):
            calls.append(amount)
        for label, payload in bad_payloads.items():
            with self.subTest(label):
                tool = self.governed(fn, lambda r, p, pl=payload: PolicyResult.modify(r, pl))
                with self.assertRaises(GovernanceDenied):
                    tool(1)
        self.assertEqual(calls, [])

    def test_the_name_option_sets_the_tool_name_the_policies_see(self):
        seen = []
        def fn(x):
            return x
        tool = self.governed(fn, lambda r, p: (seen.append(p["tool"]), PolicyResult.allow(r))[1], name="custom")
        tool(1)
        self.assertEqual(seen, ["custom"])


class ReportAndDemoTests(unittest.TestCase):
    def test_report_lists_every_policy_and_the_decision(self):
        engine = GovernanceEngine()
        engine.register(Rule(lambda r, p: PolicyResult.deny(r, "because")))
        out = engine.evaluate(ExecutionPhase.TOOL_PRE, CONTEXT, {})
        text = format_outcome(out)
        self.assertIn("rule", text)
        self.assertIn("decision: DENY  (because)", text)

    def test_demo_runs_and_shows_all_four_verdicts(self):
        root = Path(__file__).resolve().parent.parent
        env = {"PYTHONPATH": str(root / "src")}
        proc = subprocess.run([sys.executable, str(root / "examples" / "transfer_demo.py")],
                              capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for expected in ("decision: ALLOW", "decision: MODIFY", "decision: DENY",
                         "decision: REQUIRE_APPROVAL", "moved 5,000 to ACC-1001",
                         "moved 50,000 to ACC-1001", "not approved"):
            self.assertIn(expected, proc.stdout)


if __name__ == "__main__":
    unittest.main()
