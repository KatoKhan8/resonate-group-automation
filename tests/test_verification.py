"""The verification waterfall and its policy. Parts 5 to 10.

Every case here is decided offline from normalised evidence. The matrix at the
bottom is the one that matters: it is the list of ways a verifier can be wrong,
and what this system does about each of them.
"""
import os
import shutil
import tempfile
import unittest

from src import lint, store, verification as v
from tests.base import ProviderTest


def ev(provider, status, **fields):
    return v.result(provider, status, "someone@example.test", **fields)


# The agreement logic and the confirmation count are two separate layers, and
# these tests are about the first one: given this evidence, what does the
# resolver conclude about the address itself? `SINGLE` isolates that question
# by asking for one confirmation, exactly as the module behaved before double
# verification was required. The rule that two independent providers must agree
# before anything is sendable is a layer on top, and it has its own tests in
# `TestRequiredConfirmations` below - written against the default policy, which
# is the one production runs.
SINGLE = dict(v.DEFAULT_POLICY, required_confirmations=1)


def contact(**kw):
    c = {"name": "Test Person", "key": "test-person",
         "email": "someone@example.test"}
    c.update(kw)
    return c


class TestTheDecisionIsPure(unittest.TestCase):
    def test_no_evidence_is_unknown_and_never_sendable(self):
        decision = v.decide([])
        self.assertEqual(decision["state"], v.UNKNOWN)
        self.assertFalse(decision["sendable"])

    def test_a_valid_primary_is_verified(self):
        decision = v.decide([ev("contactout", v.S_VALID)], SINGLE)
        self.assertEqual(decision["state"], v.VERIFIED)
        self.assertTrue(decision["sendable"])

    def test_an_invalid_primary_is_invalid(self):
        decision = v.decide([ev("contactout", v.S_INVALID)])
        self.assertEqual(decision["state"], v.INVALID)
        self.assertFalse(decision["sendable"])

    def test_disposable_is_never_sendable(self):
        for evidence in ([ev("contactout", v.S_DISPOSABLE)],
                         [ev("deliverable", v.S_VALID, disposable=True)]):
            decision = v.decide(evidence)
            self.assertEqual(decision["state"], v.INVALID)
            self.assertFalse(decision["sendable"])

    def test_a_catch_all_alone_is_uncleared(self):
        decision = v.decide([ev("contactout", v.S_ACCEPT_ALL, catch_all=True)])
        self.assertEqual(decision["state"], v.ACCEPT_ALL_UNCLEARED)
        self.assertFalse(decision["sendable"])

    def test_only_reoon_clears_a_catch_all_by_default(self):
        evidence = [ev("contactout", v.S_ACCEPT_ALL, catch_all=True),
                    ev("deliverable", v.S_VALID, deliverable=True)]
        self.assertEqual(v.decide(evidence)["state"], v.ACCEPT_ALL_UNCLEARED)

        evidence.append(ev("reoon", v.S_VALID, safe_to_send=True))
        decision = v.decide(evidence)
        self.assertEqual(decision["state"], v.VERIFIED)
        self.assertTrue(decision["sendable"])

    def test_a_client_may_let_the_secondary_clear_a_catch_all(self):
        policy = v.policy_for({"verification": {
            "accept_all_clears_on": ["deliverable", "reoon"]}})
        policy["required_confirmations"] = 1
        evidence = [ev("contactout", v.S_ACCEPT_ALL, catch_all=True),
                    ev("deliverable", v.S_VALID, deliverable=True, safe_to_send=True)]
        self.assertEqual(v.decide(evidence, policy)["state"], v.VERIFIED)

    def test_reoon_saying_unsafe_settles_it_as_uncleared(self):
        evidence = [ev("contactout", v.S_ACCEPT_ALL, catch_all=True),
                    ev("reoon", v.S_ACCEPT_ALL, catch_all=True, safe_to_send=False)]
        decision = v.decide(evidence)
        self.assertEqual(decision["state"], v.ACCEPT_ALL_UNCLEARED)
        self.assertFalse(decision["sendable"])


class TestTheDisagreementMatrix(unittest.TestCase):
    """Part 9. Each row is a way two verifiers can contradict each other."""

    def assertHeld(self, evidence, policy=None):
        decision = v.decide(evidence, policy)
        self.assertFalse(decision["sendable"], decision)
        self.assertIn(decision["state"], (v.HELD, v.UNKNOWN,
                                          v.ACCEPT_ALL_UNCLEARED), decision)
        return decision

    def test_valid_against_invalid_is_a_disagreement_and_holds(self):
        decision = self.assertHeld([ev("contactout", v.S_VALID),
                                    ev("deliverable", v.S_INVALID)])
        self.assertEqual(decision["state"], v.HELD)
        self.assertIn("disagree", decision["reason"])

    def test_a_lone_invalid_is_invalid_not_a_disagreement(self):
        decision = v.decide([ev("contactout", v.S_INVALID)])
        self.assertEqual(decision["state"], v.INVALID)
        self.assertNotIn("disagree", decision["reason"])

    def test_invalid_against_valid_holds_whichever_way_round(self):
        decision = v.decide([ev("deliverable", v.S_VALID),
                             ev("contactout", v.S_INVALID)])
        self.assertFalse(decision["sendable"])

    def test_a_configured_policy_may_trust_the_primary_explicitly(self):
        policy = v.policy_for({"verification": {"disagreement": "trust_primary",
                                               "required_confirmations": 1}})
        evidence = [ev("contactout", v.S_VALID), ev("deliverable", v.S_UNKNOWN)]
        self.assertTrue(v.decide(evidence, policy)["sendable"])

    def test_an_unknown_primary_is_not_rescued_by_a_valid_secondary(self):
        decision = self.assertHeld([ev("contactout", v.S_UNKNOWN),
                                    ev("deliverable", v.S_VALID)])
        self.assertIn("policy does not clear", decision["reason"])

    def test_unless_the_client_turns_that_on(self):
        policy = v.policy_for({"verification": {
            "trust_secondary_when_primary_unknown": True,
            "required_confirmations": 1}})
        evidence = [ev("contactout", v.S_UNKNOWN), ev("deliverable", v.S_VALID)]
        self.assertTrue(v.decide(evidence, policy)["sendable"])

    def test_a_deliverable_timeout_holds(self):
        self.assertHeld([ev("contactout", v.S_ACCEPT_ALL, catch_all=True),
                         ev("deliverable", v.S_TIMEOUT)])

    def test_a_reoon_timeout_holds(self):
        self.assertHeld([ev("contactout", v.S_ACCEPT_ALL, catch_all=True),
                         ev("reoon", v.S_TIMEOUT)])

    def test_every_provider_failing_holds(self):
        decision = self.assertHeld([ev("contactout", v.S_ERROR),
                                    ev("deliverable", v.S_ERROR),
                                    ev("reoon", v.S_ERROR)])
        self.assertEqual(decision["state"], v.HELD)
        self.assertIn("every verifier failed", decision["reason"])

    def test_a_provider_error_alongside_a_valid_still_clears(self):
        """An error is evidence of nothing, so it neither blocks nor counts."""
        decision = v.decide([ev("contactout", v.S_VALID),
                             ev("deliverable", v.S_ERROR)], SINGLE)
        self.assertTrue(decision["sendable"])

    def test_a_provider_error_never_counts_as_a_confirmation(self):
        """Under the real policy the same evidence is one confirmation short,
        which is the conservative hold section 6 asks for on a provider error."""
        decision = v.decide([ev("contactout", v.S_VALID),
                             ev("deliverable", v.S_ERROR)])
        self.assertFalse(decision["sendable"])
        self.assertEqual(decision["confirmation_count"], 1)

    def test_requiring_the_secondary_on_valid_holds_until_it_agrees(self):
        """This used to be its own flag. It is now what the default does:
        `required_confirmations: 2` says the same thing for every branch
        rather than only for the one the flag guarded."""
        policy = v.policy_for({"verification": {"required_confirmations": 2}})
        held = v.decide([ev("contactout", v.S_VALID)], policy)
        self.assertFalse(held["sendable"])
        agreed = v.decide([ev("contactout", v.S_VALID),
                           ev("deliverable", v.S_VALID)], policy)
        self.assertTrue(agreed["sendable"])


class TestTheWaterfallStopsEarly(ProviderTest):
    """Nothing is spent once the policy has enough."""

    def test_a_valid_primary_still_buys_a_second_opinion(self):
        """It used to call nobody else. That is exactly what changed: one
        provider saying valid is now one confirmation, not a verdict."""
        c = contact(email="tomislav.baric@meridian.test")
        v.verify(c, live=True)
        urls = " ".join(self.cassette.urls())
        self.assertIn("api.contactout.com/v1/email/verify", urls)
        self.assertGreaterEqual(c["verification"]["confirmation_count"], 1)

    def test_a_valid_primary_alone_is_not_enough_to_send(self):
        c = contact()
        v.apply(c, v.decide([ev("contactout", v.S_VALID)]),
                [ev("contactout", v.S_VALID)])
        self.assertFalse(c["sendable"])
        self.assertEqual(c["verification"]["confirmation_count"], 1)
        self.assertEqual(c["verification"]["required_confirmations"], 2)

    def test_an_invalid_primary_stops_all_further_spend(self):
        c = contact(email="gone@retired.test")
        v.verify(c, live=True)
        urls = " ".join(self.cassette.urls())
        self.assertNotIn("reoon", urls)
        self.assertFalse(c["sendable"])
        self.assertEqual(c["verification"]["state"], v.INVALID)

    def test_a_catch_all_goes_on_to_the_deep_check(self):
        c = contact(email="luka.peric@lumen.test")
        v.verify(c, live=True)
        self.assertIn("reoon", " ".join(self.cassette.urls()))
        self.assertFalse(c["sendable"])
        self.assertEqual(c["verification"]["state"], v.ACCEPT_ALL_UNCLEARED)

    def test_a_catch_all_cleared_by_reoon_alone_is_now_held(self):
        """A real behaviour change, and a deliberate one.

        ContactOut said `accept_all`, which is not a confirmation - it is the
        absence of one. Reoon clearing the catch-all is a single provider's
        opinion about a domain that accepts everything, which is exactly the
        case BUILD-SPEC section 9 trap 2 describes. One opinion is no longer
        enough for any address, and a catch-all is the last address that
        should be the exception.
        """
        c = contact(email="iris.hallow@catchall-safe.test")
        v.verify(c, live=True)
        self.assertFalse(c["sendable"])
        self.assertEqual(c["verification"]["confirmation_count"], 1)
        self.assertEqual(c["verification"]["confirmed_by"], ["reoon"])

    def test_a_cleared_catch_all_with_a_second_confirmation_sends(self):
        c = contact()
        evidence = [ev("contactout", v.S_ACCEPT_ALL, catch_all=True),
                    ev("reoon", v.S_VALID, safe_to_send=True, catch_all=True),
                    ev("deliverable", v.S_VALID)]
        v.apply(c, v.decide(evidence), evidence)
        self.assertTrue(c["sendable"])
        self.assertEqual(c["verification"]["confirmation_count"], 2)

    def test_stored_evidence_is_used_before_any_call(self):
        c = contact(email="tomislav.baric@meridian.test")
        v.verify(c, live=True)
        calls = len(self.cassette.calls)
        v.verify(c, live=True)
        self.assertEqual(len(self.cassette.calls), calls)

    def test_the_per_contact_cost_cap_stops_the_waterfall(self):
        policy = v.policy_for({"verification": {
            "max_verification_cost_per_contact": 1}})
        c = contact(email="luka.peric@lumen.test")
        v.verify(c, policy, live=True)
        self.assertNotIn("reoon", " ".join(self.cassette.urls()))
        self.assertFalse(c["sendable"])

    def test_a_dry_verification_calls_nothing(self):
        c = contact(email="luka.peric@lumen.test")
        v.verify(c, live=False)
        self.assertEqual(self.cassette.calls, [])
        self.assertFalse(c["sendable"])


class TestDiscoveryIsNotVerification(unittest.TestCase):
    """Part 10. Where an address came from is never why it may be used."""

    def unverified(self, source):
        return contact(email_source=source)

    def test_an_apify_email_is_not_sendable(self):
        c = self.unverified("apify")
        self.assertFalse(lint.sendable(c))
        self.assertFalse(v.is_sendable(c))

    def test_an_ai_ark_email_is_not_sendable(self):
        self.assertFalse(lint.sendable(self.unverified("aiark")))

    def test_a_pattern_derived_email_is_not_sendable(self):
        self.assertFalse(lint.sendable(
            self.unverified("pattern_from_verified_colleague")))

    def test_a_crm_email_is_not_sendable_on_origin_alone(self):
        self.assertFalse(lint.sendable(self.unverified("thread")))

    def test_a_model_written_email_is_never_sendable(self):
        self.assertFalse(lint.sendable(self.unverified("llm")))

    def test_a_hand_set_sendable_flag_is_ignored(self):
        c = contact(sendable=True, email_source="apify")
        self.assertFalse(v.is_sendable(c))

    def test_the_same_address_becomes_sendable_only_with_evidence(self):
        c = self.unverified("apify")
        self.assertFalse(v.is_sendable(c))
        evidence = [ev("contactout", v.S_VALID), ev("deliverable", v.S_VALID)]
        v.apply(c, v.decide(evidence), evidence)
        self.assertTrue(v.is_sendable(c))

    def test_a_contact_with_no_address_is_never_sendable(self):
        self.assertFalse(v.is_sendable(contact(email=None)))
        self.assertFalse(v.is_sendable({}))


class TestPlanningAndCost(unittest.TestCase):
    def test_a_fresh_address_plans_two_calls_and_one_conditional(self):
        """The secondary is expected now, not conditional: with two
        confirmations required it runs on every address the primary clears,
        and planning it as a maybe would under-report the bill by half."""
        ops = v.plan(contact())
        self.assertEqual([o["provider"] for o in ops],
                         ["contactout", "deliverable", "reoon"])
        self.assertEqual([o["conditional"] for o in ops], [False, False, True])
        for op in ops:
            self.assertTrue(op["reason"])

    def test_expected_and_maximum_cost_are_not_the_same_number(self):
        cost = v.exposure(v.plan(contact()))
        self.assertEqual(cost["expected"], 2)      # primary + secondary
        self.assertEqual(cost["maximum"], 3)       # plus the escalation

    def test_a_single_confirmation_policy_costs_one_less(self):
        policy = dict(v.DEFAULT_POLICY, required_confirmations=1)
        self.assertEqual(v.exposure(v.plan(contact(), policy))["expected"], 1)

    def test_a_settled_address_plans_nothing(self):
        """Settled means two confirmations, not one."""
        c = contact()
        evidence = [ev("contactout", v.S_VALID), ev("deliverable", v.S_VALID)]
        v.apply(c, v.decide(evidence), evidence)
        self.assertEqual(v.plan(c), [])

    def test_a_half_confirmed_address_still_plans_the_secondary(self):
        c = contact()
        v.apply(c, v.decide([ev("contactout", v.S_VALID)]),
                [ev("contactout", v.S_VALID)])
        self.assertEqual([o["provider"] for o in v.plan(c)],
                         ["deliverable", "reoon"])

    def test_an_invalid_address_plans_nothing_more(self):
        c = contact()
        v.apply(c, v.decide([ev("contactout", v.S_INVALID)]),
                [ev("contactout", v.S_INVALID)])
        self.assertEqual(v.plan(c), [])

    def test_a_contact_with_no_address_plans_nothing(self):
        self.assertEqual(v.plan(contact(email=None)), [])


class TestOnlyThisModuleDecides(unittest.TestCase):
    def test_lint_delegates_rather_than_deciding(self):
        import inspect
        source = inspect.getsource(lint.sendable)
        self.assertIn("verification", source)
        self.assertNotIn("accept_all", source)

    def test_no_other_module_assigns_sendable(self):
        import os
        import re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        offenders = []
        for dirpath, dirnames, names in os.walk(os.path.join(root, "src")):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in names:
                if not name.endswith(".py") or name == "verification.py":
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if re.search(r"\[[\"']sendable[\"']\]\s*=", line):
                            if "= False" in line:
                                continue          # refusing is always allowed
                            offenders.append(f"{os.path.relpath(path, root)}:{i}")
        self.assertEqual(offenders, [])

    def test_the_legacy_fields_are_a_projection_not_a_source(self):
        c = contact()
        evidence = [ev("contactout", v.S_ACCEPT_ALL, catch_all=True),
                    ev("reoon", v.S_VALID, safe_to_send=True, catch_all=True),
                    ev("deliverable", v.S_VALID)]
        v.apply(c, v.decide(evidence), evidence)
        self.assertEqual(c["verdict"], "accept_all")
        self.assertIs(c["reoon"]["is_safe_to_send"], True)
        self.assertTrue(c["sendable"])

        # A tampered legacy field cannot flip the decision. The evidence list
        # is the fact; `verdict` and `reoon` are a readable projection of it.
        c["verdict"] = "invalid"
        c["reoon"] = {"is_safe_to_send": False}
        self.assertTrue(v.is_sendable(c))

    def test_a_tampered_state_cannot_make_an_address_sendable(self):
        """The direction that matters, and the one that changed.

        `is_sendable` used to return `stored in SENDABLE_STATES` whenever a
        verification block existed, so anything that could write that string -
        a hand edit, a resumed run under an older policy, a future UI, a bug -
        could clear an address no provider had ever confirmed. It now
        recomputes from the evidence every time, so the state is a cached
        opinion and the cache has no vote.
        """
        c = contact()
        v.apply(c, v.decide([]), [])
        self.assertFalse(v.is_sendable(c))

        c["verification"]["state"] = v.VERIFIED
        c["verification"]["sendable"] = True
        c["verification"]["confirmation_count"] = 99
        c["sendable"] = True
        self.assertFalse(v.is_sendable(c),
                         "a written state cleared an address with no evidence")

    def test_a_tampered_state_cannot_bypass_the_confirmation_count(self):
        c = contact()
        evidence = [ev("contactout", v.S_VALID)]
        v.apply(c, v.decide(evidence), evidence)
        self.assertFalse(v.is_sendable(c))

        c["verification"]["state"] = v.VERIFIED
        c["verification"]["confirmation_count"] = 2
        c["sendable"] = True
        self.assertFalse(v.is_sendable(c))
        self.assertEqual(v.resolve(c)["confirmation_count"], 1)


class TestLegacyRecordsStillWork(unittest.TestCase):
    def test_a_record_written_before_this_module_is_read_as_evidence(self):
        """Still read as evidence - and now one confirmation short, because a
        record from before double verification was required has, by
        definition, only ever been asked once."""
        old = contact(verdict="valid")
        self.assertFalse(v.is_sendable(old))
        decision = v.decide(v.all_evidence(old))
        self.assertEqual(decision["confirmation_count"], 1)
        self.assertEqual(decision["confirmed_by"], ["contactout"])

    def test_a_legacy_record_still_clears_under_a_single_confirmation_policy(self):
        """The evidence is read correctly; it is the requirement that moved."""
        old = contact(verdict="valid")
        self.assertTrue(v.decide(v.all_evidence(old), SINGLE)["sendable"])

    def test_an_old_catch_all_with_a_passing_reoon_is_one_confirmation(self):
        old = contact(verdict="accept_all",
                      reoon={"is_safe_to_send": True, "is_catch_all": True})
        self.assertFalse(v.is_sendable(old))
        self.assertTrue(v.decide(v.all_evidence(old), SINGLE)["sendable"])

    def test_an_old_catch_all_without_one_is_not(self):
        old = contact(verdict="accept_all",
                      reoon={"is_safe_to_send": False, "is_catch_all": True})
        self.assertFalse(v.is_sendable(old))


if __name__ == "__main__":
    unittest.main()
