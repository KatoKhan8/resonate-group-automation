"""Mandatory double verification: the matrix, the counting, and the gate.

One verifier is a single point of failure with a commercial interest in saying
yes. The rule this file guards is one sentence - **an address may only be
written to when enough independent providers have confirmed it** - and the
tests are the ways that gets quietly broken: a second answer from the same
provider, a stale state on the record, a branch in the resolver that forgets,
or a payload builder that trusts what it was handed.

Everything is decided offline from normalised evidence. No provider is called.
"""
import contextlib
import unittest

from src import eligibility, lint, push, store, verification as v
from tests.base import FIXTURES, ProviderTest


@contextlib.contextmanager
def degraded_fixture():
    """Construct a record that was never fully verified.

    NOT a write under test. `store.transaction()` now runs the same loss
    guards as `save` - `refuse_evidence_loss` and `refuse_history_loss` - so
    the path that used to let a fixture delete paid verification evidence
    correctly refuses. These tests need a HALF-confirmed contact, and they
    were building one by degrading a fully-confirmed one, which is exactly
    the write the guard exists to stop.

    Writing the state directly keeps the fixture honest about what it is: a
    starting condition, not an operation the product performs.
    """
    recs = store.load()
    yield recs
    store._write(recs)


EMAIL = "someone@example.test"


def ev(provider, status, **fields):
    return v.result(provider, status, EMAIL, **fields)


def contact(*evidence):
    person = {"name": "Test Person", "key": "test-person", "email": EMAIL}
    evidence = list(evidence)
    person.pop("verification", None)   # a different contact, not a downgrade
    v.apply(person, v.decide(evidence), evidence)
    return person


class TestTheAgreementMatrix(unittest.TestCase):
    """Section 6, one test per row, asserted on the state and the count."""

    def outcome(self, *evidence):
        decision = v.decide(list(evidence))
        return decision["state"], decision["sendable"], decision["confirmation_count"]

    def test_valid_and_valid_passes(self):
        self.assertEqual(
            self.outcome(ev("contactout", v.S_VALID), ev("deliverable", v.S_VALID)),
            (v.VERIFIED, True, 2))

    def test_valid_and_invalid_never_sends(self):
        state, sendable, _ = self.outcome(ev("contactout", v.S_VALID),
                                          ev("deliverable", v.S_INVALID))
        self.assertFalse(sendable)
        self.assertEqual(state, v.HELD)

    def test_valid_and_invalid_is_reported_as_a_disagreement(self):
        """"They disagree" and "it is dead" are different facts about an
        address, and only one of them means stop looking."""
        decision = v.decide([ev("contactout", v.S_VALID),
                             ev("deliverable", v.S_INVALID)])
        self.assertTrue(decision["disagreement"])
        self.assertIn("disagree", decision["reason"])

    def test_valid_unknown_then_reoon_valid_passes(self):
        self.assertEqual(
            self.outcome(ev("contactout", v.S_VALID),
                         ev("deliverable", v.S_UNKNOWN),
                         ev("reoon", v.S_VALID, safe_to_send=True)),
            (v.VERIFIED, True, 2))

    def test_valid_unknown_then_reoon_invalid_blocks(self):
        _, sendable, count = self.outcome(ev("contactout", v.S_VALID),
                                          ev("deliverable", v.S_UNKNOWN),
                                          ev("reoon", v.S_INVALID))
        self.assertFalse(sendable)
        self.assertEqual(count, 1)

    def test_valid_unknown_unknown_holds(self):
        state, sendable, count = self.outcome(ev("contactout", v.S_VALID),
                                              ev("deliverable", v.S_UNKNOWN),
                                              ev("reoon", v.S_UNKNOWN))
        self.assertEqual(state, v.HELD)
        self.assertFalse(sendable)
        self.assertEqual(count, 1)

    def test_valid_accept_all_then_reoon_safe_passes(self):
        self.assertEqual(
            self.outcome(ev("contactout", v.S_VALID),
                         ev("deliverable", v.S_ACCEPT_ALL, catch_all=True),
                         ev("reoon", v.S_VALID, safe_to_send=True)),
            (v.VERIFIED, True, 2))

    def test_valid_accept_all_then_reoon_unsafe_blocks(self):
        _, sendable, _ = self.outcome(
            ev("contactout", v.S_VALID),
            ev("deliverable", v.S_ACCEPT_ALL, catch_all=True),
            ev("reoon", v.S_ACCEPT_ALL, catch_all=True, safe_to_send=False))
        self.assertFalse(sendable)

    def test_valid_accept_all_then_reoon_unknown_holds(self):
        state, sendable, _ = self.outcome(
            ev("contactout", v.S_VALID),
            ev("deliverable", v.S_ACCEPT_ALL, catch_all=True),
            ev("reoon", v.S_UNKNOWN))
        self.assertFalse(sendable)
        self.assertIn(state, (v.HELD, v.ACCEPT_ALL_UNCLEARED))

    def test_an_invalid_primary_blocks_whatever_follows(self):
        for second in (v.S_VALID, v.S_UNKNOWN, v.S_ACCEPT_ALL):
            _, sendable, _ = self.outcome(ev("contactout", v.S_INVALID),
                                          ev("deliverable", second))
            self.assertFalse(sendable, second)

    def test_an_unknown_primary_is_never_rescued_silently(self):
        state, sendable, _ = self.outcome(ev("contactout", v.S_UNKNOWN),
                                          ev("deliverable", v.S_VALID))
        self.assertFalse(sendable)
        self.assertEqual(state, v.HELD)

    def test_a_provider_error_is_a_conservative_hold(self):
        _, sendable, count = self.outcome(ev("contactout", v.S_VALID),
                                          ev("deliverable", v.S_ERROR))
        self.assertFalse(sendable)
        self.assertEqual(count, 1)

    def test_a_disagreement_never_picks_the_optimistic_answer(self):
        """Both orderings, so nothing depends on which provider answered first."""
        for first, second in (("contactout", "deliverable"),
                              ("deliverable", "contactout")):
            decision = v.decide([ev(first, v.S_VALID), ev(second, v.S_INVALID)])
            self.assertFalse(decision["sendable"], f"{first} then {second}")


class TestConfirmationsAreCountedByProvider(unittest.TestCase):
    def test_one_provider_is_one_confirmation(self):
        self.assertEqual(v.decide([ev("contactout", v.S_VALID)])["confirmation_count"], 1)

    def test_asking_the_same_provider_twice_is_still_one(self):
        """Two answers from one source share whatever made the first wrong,
        which is the entire reason a second opinion is worth buying."""
        decision = v.decide([ev("contactout", v.S_VALID),
                             ev("contactout", v.S_VALID)])
        self.assertEqual(decision["confirmation_count"], 1)
        self.assertFalse(decision["sendable"])

    def test_three_answers_from_one_provider_are_still_one(self):
        evidence = [ev("contactout", v.S_VALID) for _ in range(3)]
        self.assertEqual(v.decide(evidence)["confirmation_count"], 1)

    def test_two_different_providers_are_two(self):
        decision = v.decide([ev("contactout", v.S_VALID),
                             ev("deliverable", v.S_VALID)])
        self.assertEqual(decision["confirmation_count"], 2)
        self.assertTrue(decision["sendable"])

    def test_only_valid_counts_as_a_confirmation(self):
        for status in (v.S_ACCEPT_ALL, v.S_UNKNOWN, v.S_ERROR, v.S_TIMEOUT):
            decision = v.decide([ev("contactout", v.S_VALID),
                                 ev("deliverable", status)])
            self.assertEqual(decision["confirmation_count"], 1, status)

    def test_the_confirming_providers_are_named(self):
        decision = v.decide([ev("contactout", v.S_VALID),
                             ev("deliverable", v.S_VALID)])
        self.assertEqual(sorted(decision["confirmed_by"]),
                         ["contactout", "deliverable"])

    def test_every_decision_carries_the_count_and_the_requirement(self):
        for evidence in ([], [ev("contactout", v.S_VALID)],
                         [ev("contactout", v.S_INVALID)],
                         [ev("contactout", v.S_ACCEPT_ALL, catch_all=True)]):
            decision = v.decide(evidence)
            self.assertIn("confirmation_count", decision)
            self.assertIn("required_confirmations", decision)


class TestThePolicyIsConfigurable(unittest.TestCase):
    def test_the_default_is_two(self):
        self.assertEqual(v.DEFAULT_POLICY["required_confirmations"], 2)

    def test_the_default_order_is_contactout_deliverable_reoon(self):
        self.assertEqual(v.DEFAULT_POLICY["primary"], "contactout")
        self.assertEqual(v.DEFAULT_POLICY["secondary"], "deliverable")
        self.assertEqual(v.DEFAULT_POLICY["catch_all"], "reoon")

    def test_a_client_may_require_one(self):
        policy = v.policy_for({"verification": {"required_confirmations": 1}})
        self.assertTrue(v.decide([ev("contactout", v.S_VALID)], policy)["sendable"])

    def test_a_client_may_require_three(self):
        policy = v.policy_for({"verification": {"required_confirmations": 3}})
        two = [ev("contactout", v.S_VALID), ev("deliverable", v.S_VALID)]
        self.assertFalse(v.decide(two, policy)["sendable"])
        three = two + [ev("reoon", v.S_VALID, safe_to_send=True)]
        self.assertTrue(v.decide(three, policy)["sendable"])

    def test_a_client_may_name_a_different_secondary(self):
        policy = v.policy_for({"verification": {"secondary": "reoon"}})
        self.assertEqual(policy["secondary"], "reoon")

    def test_raising_the_requirement_can_only_ever_hold_more(self):
        """The downgrade is one-way: no confirmation setting opens the gate."""
        evidence = [ev("contactout", v.S_VALID), ev("deliverable", v.S_VALID)]
        for required in range(1, 6):
            policy = v.policy_for({"verification":
                                   {"required_confirmations": required}})
            decision = v.decide(evidence, policy)
            self.assertEqual(decision["sendable"], required <= 2, required)


class TestNothingTrustsTheStoredState(unittest.TestCase):
    def test_a_written_state_cannot_clear_an_address(self):
        person = contact()
        person["verification"]["state"] = v.VERIFIED
        person["verification"]["sendable"] = True
        person["verification"]["confirmation_count"] = 9
        person["sendable"] = True
        self.assertFalse(v.is_sendable(person))
        self.assertFalse(lint.sendable(person))

    def test_a_written_state_cannot_bypass_the_count(self):
        person = contact(ev("contactout", v.S_VALID))
        person["verification"]["confirmation_count"] = 2
        person["sendable"] = True
        self.assertFalse(lint.sendable(person))
        self.assertEqual(v.resolve(person)["confirmation_count"], 1)

    def test_the_evidence_survives_a_round_trip(self):
        person = contact(ev("contactout", v.S_VALID), ev("deliverable", v.S_VALID))
        block = person["verification"]
        self.assertEqual(block["confirmation_count"], 2)
        self.assertEqual(block["required_confirmations"], 2)
        self.assertEqual(sorted(block["results"]), ["contactout", "deliverable"])
        self.assertEqual(block["results"]["contactout"]["verdict"], "valid")
        self.assertTrue(block["results"]["contactout"]["checked_at"])


class TestTheWaterfallSpendsWhatItNeedsTo(unittest.TestCase):
    def test_an_invalid_primary_buys_nothing_more(self):
        person = contact(ev("contactout", v.S_INVALID))
        self.assertEqual(v.plan(person), [])

    def test_a_half_confirmed_address_plans_the_secondary(self):
        person = contact(ev("contactout", v.S_VALID))
        self.assertIn("deliverable", [o["provider"] for o in v.plan(person)])

    def test_a_confirmed_address_plans_nothing(self):
        person = contact(ev("contactout", v.S_VALID), ev("deliverable", v.S_VALID))
        self.assertEqual(v.plan(person), [])

    def test_the_secondary_is_expected_spend_not_conditional(self):
        ops = {o["provider"]: o for o in v.plan({"email": EMAIL})}
        self.assertFalse(ops["deliverable"]["conditional"])
        self.assertTrue(ops["reoon"]["conditional"])

    def test_needs_asks_the_escalation_when_the_secondary_could_not_answer(self):
        evidence = [ev("contactout", v.S_VALID), ev("deliverable", v.S_ERROR)]
        self.assertTrue(v.needs("reoon", evidence, v.DEFAULT_POLICY))

    def test_needs_does_not_ask_anybody_after_an_invalid(self):
        evidence = [ev("contactout", v.S_INVALID)]
        self.assertFalse(v.needs("deliverable", evidence, v.DEFAULT_POLICY))
        self.assertFalse(v.needs("reoon", evidence, v.DEFAULT_POLICY))


class TestTheDeliverableContractIsNotAssumed(unittest.TestCase):
    """Section 4: an unread response shape must not become a confirmation."""

    def test_the_module_still_refuses_an_unread_contract(self):
        from src.providers import ProviderError, deliverable
        if deliverable.result_shape_confirmed():
            self.skipTest("a real Deliverable response has been validated")
        with self.assertRaises(ProviderError):
            deliverable.require_contract()

    def test_a_refusal_becomes_an_error_result_and_never_a_valid_one(self):
        entry = v.call("deliverable", EMAIL)
        self.assertIn(entry["status"], (v.S_ERROR, v.S_UNKNOWN))
        self.assertNotEqual(entry["status"], v.S_VALID)

    def test_an_unreadable_secondary_holds_rather_than_clears(self):
        evidence = [ev("contactout", v.S_VALID), v.call("deliverable", EMAIL)]
        self.assertFalse(v.decide(evidence)["sendable"])


class TestTheEmailBisonGate(ProviderTest):
    """Section 15: the payload is the last cheap place to stop."""

    def setUp(self):
        super().setUp()
        import os
        import shutil
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="rga-dv-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self._shutil = shutil
        from tests.base import approve_everything
        approve_everything()

    def tearDown(self):
        import os
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        self._shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def item(self, person):
        rec = store.get("meridian")
        step = rec["cadence"][rec["contacts"][0]["key"]]["day1"]
        return {"record": rec, "contact": person,
                "contact_key": rec["contacts"][0]["key"], "step_key": "day1",
                "channel": "email", "step": step, "push_id": "x"}

    def person(self, *evidence):
        rec = store.get("meridian")
        person = dict(rec["contacts"][0])
        # Evidence is bound to the exact mailbox it was obtained for, and
        # this contact's address is meridian's, not the module-level EMAIL
        # the `ev` helper stamps. Restating it here keeps the fixture
        # honest: built the other way, these confirmations are about a
        # different address and correctly count for nothing.
        evidence = [dict(e, email=person["email"]) for e in (evidence or ())]
        person.pop("verification", None)   # a different contact, not a downgrade
        v.apply(person, v.decide(evidence), evidence)
        return person

    def test_a_double_confirmed_contact_builds_a_payload(self):
        person = self.person(ev("contactout", v.S_VALID),
                             ev("deliverable", v.S_VALID))
        person["email"] = store.get("meridian")["contacts"][0]["email"]
        rows = push.emailbison_rows([self.item(person)])
        self.assertEqual(len(rows), 1)

    def test_a_single_confirmed_contact_is_refused(self):
        person = self.person(ev("contactout", v.S_VALID))
        person["email"] = store.get("meridian")["contacts"][0]["email"]
        with self.assertRaises(AssertionError):
            push.emailbison_rows([self.item(person)])

    def test_a_tampered_state_does_not_get_past_the_payload_gate(self):
        person = self.person(ev("contactout", v.S_VALID))
        person["email"] = store.get("meridian")["contacts"][0]["email"]
        person["sendable"] = True
        person["verification"]["state"] = v.VERIFIED
        person["verification"]["sendable"] = True
        person["verification"]["confirmation_count"] = 2
        with self.assertRaises(AssertionError):
            push.emailbison_rows([self.item(person)])

    def test_the_refusal_names_the_shortfall(self):
        person = self.person(ev("contactout", v.S_VALID))
        person["email"] = store.get("meridian")["contacts"][0]["email"]
        with self.assertRaises(AssertionError) as caught:
            push.emailbison_rows([self.item(person)])
        self.assertIn("confirmation", str(caught.exception))

    def test_no_lead_in_a_real_push_is_under_confirmed(self):
        """The repository-level invariant, over the whole fixture batch."""
        payload = push.run(day=30, campaign_id=42,
                           linkedin_account_id=3)["payloads"]["emailbison"]
        by_email = {c["email"]: c for r in store.load()
                    for c in r.get("contacts") or [] if c.get("email")}
        self.assertTrue(payload["body"]["leads"])
        for lead in payload["body"]["leads"]:
            decision = v.resolve(by_email[lead["email"]])
            self.assertGreaterEqual(decision["confirmation_count"],
                                    decision["required_confirmations"],
                                    lead["email"])


class TestChannelBehaviour(unittest.TestCase):
    """Section 10: verification closes email and never the person."""

    def test_a_held_email_leaves_the_linkedin_reason_empty(self):
        from src import channels
        person = contact(ev("contactout", v.S_VALID))
        person["linkedin"] = "https://www.linkedin.com/in/test-person"
        rec = {"id": "r", "client": "demo", "domain": "example.test",
               "contacts": [person]}
        verdicts = channels.evaluate(rec, person, {})
        self.assertFalse(verdicts["email_eligible"])
        self.assertTrue(verdicts["linkedin_eligible"])
        self.assertEqual(verdicts["mode"], channels.LINKEDIN_ONLY)
        self.assertFalse(verdicts["held"])

    def test_a_disagreement_leaves_linkedin_alone(self):
        from src import channels
        person = contact(ev("contactout", v.S_VALID),
                         ev("deliverable", v.S_INVALID))
        person["linkedin"] = "https://www.linkedin.com/in/test-person"
        rec = {"id": "r", "client": "demo", "domain": "example.test",
               "contacts": [person]}
        self.assertTrue(channels.evaluate(rec, person, {})["linkedin_eligible"])

    def test_the_shortfall_has_its_own_reason_code(self):
        """"Nobody could tell us" and "one told us and we need two" are
        different problems: the first needs a better address, the second needs
        one more call. A reviewer given only `verification_unknown` goes
        looking for the wrong fix."""
        self.assertTrue(eligibility.HELD_INSUFFICIENT_CONFIRMATIONS)
        self.assertNotEqual(eligibility.HELD_INSUFFICIENT_CONFIRMATIONS,
                            eligibility.HELD_VERIFICATION_UNKNOWN)
        self.assertTrue(
            eligibility.HELD_INSUFFICIENT_CONFIRMATIONS.startswith("held:"))

    pass


class TestTheReasonCodeReachesTheCaller(ProviderTest):
    """Asserted on the real fixture, where a day-1 step actually exists."""

    def setUp(self):
        super().setUp()
        import os
        import shutil
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="rga-dv-reason-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self._shutil = shutil

    def tearDown(self):
        import os
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        self._shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def test_a_half_confirmed_contact_reports_the_shortfall_code(self):
        from src import cadence, clients
        config = clients.load("productive")
        with degraded_fixture() as recs:
            rec = store.get("meridian", recs)
            person = rec["contacts"][0]
            evidence = [ev("contactout", v.S_VALID)]
            evidence[0]["email"] = person["email"]
            # Building this person half confirmed. `apply` is append-only, so
            # without the reset the demo estate's own evidence stays and the
            # contact is fully confirmed rather than short by one.
            person.pop("verification", None)
            v.apply(person, v.decide(evidence), evidence)

        rec = store.get("meridian")
        person = rec["contacts"][0]
        timeline = cadence.build(rec, config, recs=[rec])
        step = timeline["contacts"][person["key"]]["day1"]
        decision = eligibility.decide(rec, person, "day1", channel="email",
                                      recs=[rec], config=config, step=step)
        self.assertFalse(decision.eligible)
        self.assertIn(eligibility.HELD_INSUFFICIENT_CONFIRMATIONS,
                      decision["reasons"])

    def test_a_double_confirmed_contact_does_not_report_it(self):
        from src import cadence, clients
        from tests.base import approve_everything
        config = clients.load("productive")
        approve_everything()
        rec = store.get("meridian")
        person = rec["contacts"][0]
        timeline = cadence.build(rec, config, recs=[rec])
        step = timeline["contacts"][person["key"]]["day1"]
        decision = eligibility.decide(rec, person, "day1", channel="email",
                                      recs=[rec], config=config, step=step)
        self.assertNotIn(eligibility.HELD_INSUFFICIENT_CONFIRMATIONS,
                         decision["reasons"])


if __name__ == "__main__":
    unittest.main()


class TestTheLaunchChecklist(ProviderTest):
    """Section 12: a campaign is not launch-ready with an unconfirmed email."""

    def setUp(self):
        super().setUp()
        import os
        import shutil
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="rga-dv-launch-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, "phase7.jsonl"), self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self._shutil = shutil
        from tests.base import approve_everything
        approve_everything()

    def tearDown(self):
        import os
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        self._shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def campaign(self):
        from src import clients
        recs = store.load()
        return ({"campaign_id": "c1", "client": "productive",
                 "record_ids": [r["id"] for r in recs],
                 "senders": {"email": [{"id": "a"}], "linkedin": [{"id": "b"}]},
                 "daily_volume": {"email": 10, "linkedin": 10},
                 "bison_campaign_id": "1", "heyreach_campaign_id": "2",
                 "launch": {"state": "not_launched"}, "events": [], "log": []},
                recs, clients.load("productive"))

    def check(self):
        from src import campaigns
        campaign, recs, config = self.campaign()
        return campaigns.check_double_verification(campaign, recs, config)

    def test_the_check_is_in_the_launch_checklist(self):
        from src import campaigns
        names = [name for name, _ in campaigns.CHECKS]
        self.assertIn("double verification", names)

    def test_a_fully_confirmed_batch_passes(self):
        ok, detail = self.check()
        self.assertTrue(ok, detail)

    def test_an_under_confirmed_recipient_fails_the_check(self):
        with degraded_fixture() as recs:
            rec = store.get("meridian", recs)
            person = rec["contacts"][0]
            evidence = [v.result("contactout", v.S_VALID, person["email"])]
            person.pop("verification", None)   # half confirmed, deliberately
            v.apply(person, v.decide(evidence), evidence)
        ok, detail = self.check()
        self.assertFalse(ok)
        self.assertIn("meridian", detail)
        self.assertIn("1/2", detail)

    def test_the_failure_names_the_shortfall_not_a_bad_address(self):
        """"Not sendable" sends a reviewer looking for a broken address. The
        truth is usually that the address is fine and one call is missing."""
        with degraded_fixture() as recs:
            rec = store.get("meridian", recs)
            person = rec["contacts"][0]
            evidence = [v.result("contactout", v.S_VALID, person["email"])]
            person.pop("verification", None)   # half confirmed, deliberately
            v.apply(person, v.decide(evidence), evidence)
        _, detail = self.check()
        self.assertIn("confirmations", detail)

    def test_a_linkedin_only_contact_does_not_block_the_launch(self):
        """An unverified contact reached on LinkedIn is not holding anything up."""
        with store.transaction() as recs:
            rec = store.get("meridian", recs)
            for person in rec["contacts"]:
                person["email"] = None
        ok, detail = self.check()
        self.assertTrue(ok, detail)
