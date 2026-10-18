import unittest

from fourverdicts import (
    BasePolicy,
    EnforcementMode,
    ExecutionPhase,
    FailMode,
    GovernanceAction,
    GovernanceContext,
    PolicyResult,
    STRICTNESS,
)

CONTEXT = GovernanceContext(session_id="s", agent_id="a")


class Fixed(BasePolicy):
    """A policy that always returns the result it was given."""

    def __init__(self, result, **kwargs):
        super().__init__("fixed", **kwargs)
        self._result = result

    def evaluate(self, payload, context):
        return self._result


class Crashing(BasePolicy):
    def evaluate(self, payload, context):
        raise RuntimeError("boom")


class WrongReturn(BasePolicy):
    def evaluate(self, payload, context):
        return "ALLOW"


class VocabularyTests(unittest.TestCase):
    def test_four_verdicts_and_seven_phases(self):
        self.assertEqual(len(GovernanceAction), 4)
        self.assertEqual(len(ExecutionPhase), 7)

    def test_strictness_order(self):
        order = sorted(GovernanceAction, key=lambda a: STRICTNESS[a])
        self.assertEqual(
            order,
            [GovernanceAction.ALLOW, GovernanceAction.MODIFY,
             GovernanceAction.REQUIRE_APPROVAL, GovernanceAction.DENY],
        )

    def test_result_helpers(self):
        self.assertIs(PolicyResult.allow("r").action, GovernanceAction.ALLOW)
        self.assertIs(PolicyResult.deny("r", "why").action, GovernanceAction.DENY)
        self.assertIs(PolicyResult.require_approval("r").action, GovernanceAction.REQUIRE_APPROVAL)
        modified = PolicyResult.modify("r", {"x": 1}, "capped")
        self.assertEqual((modified.action, modified.modified_payload), (GovernanceAction.MODIFY, {"x": 1}))


class PolicyTests(unittest.TestCase):
    def test_rule_id_required(self):
        with self.assertRaises(ValueError):
            Crashing("  ")

    def test_verdict_passes_through_in_block_mode(self):
        for result in (PolicyResult.allow("f"), PolicyResult.deny("f", "no"),
                       PolicyResult.require_approval("f"), PolicyResult.modify("f", 1)):
            with self.subTest(result.action):
                self.assertIs(Fixed(result).safe_evaluate({}, CONTEXT).action, result.action)

    def test_escalate_turns_deny_into_approval_only(self):
        policy = lambda r: Fixed(r, enforcement_mode=EnforcementMode.ESCALATE)
        self.assertIs(policy(PolicyResult.deny("f")).safe_evaluate({}, CONTEXT).action,
                      GovernanceAction.REQUIRE_APPROVAL)
        self.assertIs(policy(PolicyResult.modify("f", 1)).safe_evaluate({}, CONTEXT).action,
                      GovernanceAction.MODIFY)

    def test_warn_only_allows_but_says_what_would_have_happened(self):
        result = Fixed(PolicyResult.deny("f", "bad"), enforcement_mode=EnforcementMode.WARN_ONLY).safe_evaluate({}, CONTEXT)
        self.assertIs(result.action, GovernanceAction.ALLOW)
        self.assertIn("DENY", result.reason)

    def test_crash_fails_closed_by_default(self):
        self.assertIs(Crashing("c").safe_evaluate({}, CONTEXT).action, GovernanceAction.DENY)

    def test_crash_can_fail_open_when_asked(self):
        result = Crashing("c", fail_mode=FailMode.FAIL_OPEN).safe_evaluate({}, CONTEXT)
        self.assertIs(result.action, GovernanceAction.ALLOW)

    def test_wrong_return_type_is_a_failure_not_an_allow(self):
        self.assertIs(WrongReturn("w").safe_evaluate({}, CONTEXT).action, GovernanceAction.DENY)


if __name__ == "__main__":
    unittest.main()
