#!/usr/bin/env python3
"""The four production lint doors that pass NO step key, driven as doors.

WHY THIS FILE EXISTS. GLM's part-3 review failed
`task-word-contract-enforced` on one ground that survived measurement:

> "none of the four keyless production lint doors the contract exists to gate
>  is called by any test on the branch"

Four production callers reach `lint.check`/`lint.check_step` with no
`step_key`, so the per-step word contract applies to them ONLY through
`lint.step_key_of`, the recovery that infers the step from the record:

    src/approve.py:115          lint.check(rec, contact_key, step)
    src/eligibility.py:854      lint.check(rec, contact.get("key"), step)
    src/executionguard.py:615   lint.check_step(rec, contact["key"], step)
    src/campaigns.py:463        lint.check(rec, contact_key, step)

The branch tested that recovery DIRECTLY (`TestTheKeyIsRecovered` in
`tests/test_word_contract_enforced.py`), and the 295-line module that drove
the keyless path itself - `tests/test_a_thread_reply_has_its_own_word_range.py`
- was DELETED with the ruling it asserted. Nothing replaced it. So the gate
the contract exists to stand in front of was, for these four doors, covered by
a test of its helper rather than by a test of the door, which is the
"existence is not function" shape CLAUDE.md names: a thing computed correctly
that nothing downstream was proven to read.

HOW EACH TEST IS BUILT, and the two properties every one of them has:

  1. It calls the door THE WAY PRODUCTION CALLS IT - no `step_key` anywhere -
     with an under-contract body STORED on the record under its real cadence
     key, and asserts the contract refusal comes back out of the door.
  2. It carries a CONTROL at a legal length through the same door, because a
     door that refuses every body proves nothing about the contract. The
     control asserts the absence of THIS refusal, not the absence of all
     refusal: a later gate may still have something to say, and in two of
     these doors it does.

THE CANARY LENGTH IS THE OPERATOR'S OWN CASE. em2 at 41 words is the length
the approved canary copy actually shipped, four words under its 45 floor, and
the operator confirmed that it is correctly refused. 61 words is the control:
inside em2's 45-90 range, and also inside em1's 60-90, which is what makes it
a control for "the door applies a contract" rather than for "the door applies
em2's contract" - that second question is `TestBothDoorsAgree`'s, and this
file deliberately does not duplicate it.

THE CADENCE IS PINNED TO THE LIVE ONE, NOT TO THE FIXTURE DEFAULT. Measured:

    productive_li_heavy_v1     li1 em1 li2 em2 li3 em3 li4 em4 li5 em5  <- live
    productive_email_eight_v1  em1 .. em8
    productive_balanced_v1     day1 day3 day5 day8 day10 day15 day21

`tests/base.fixture_config` pins `productive_balanced_v1`, whose keys are
`day1`..`day21` - and `writercontract.word_range("day1")` is None, so under
that cadence the contract names no step and these tests would pass while
measuring nothing. Productive's own config says `productive_li_heavy_v1`, so
that is what is pinned here, and it is pinned rather than read so a client
editing their YAML cannot turn these tests green.
"""
import contextlib
import datetime
import unittest
from unittest import mock

from src import (approval, campaigns, cadence, clients, collision, configdiff,
                 eligibility, executionguard, lint, store)
from src.skills import cold_email_writing as writer
from tests.base import QueueTest, pin_client_config

LIVE_CADENCE = "productive_li_heavy_v1"
STEP = "em2"
UNDER = 41          # the canary's own em2, four words under its floor
LEGAL = 61          # inside em2's 45-90

NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
FRESH = (NOW - datetime.timedelta(minutes=1)).isoformat()
WS = 10


def body(n):
    """Exactly `n` countable words, and nothing else a lint rule reacts to."""
    return " ".join(["word"] * n)


def _contract_code(step_key=STEP, words=UNDER):
    """The refusal code the contract produces, built from the contract itself.

    Spelled from `WORD_CONTRACT` rather than typed out, so an edit to the
    numbers moves this expectation with them instead of leaving a test
    asserting a bound the system no longer has.
    """
    low, _, high = writer.WORD_CONTRACT[step_key]
    return "%s_body_%d_words_under_contract_%d_to_%d" % (
        step_key, words, low, high)


def _is_contract_refusal(text, step_key=STEP, words=UNDER):
    return _contract_code(step_key, words) in str(text)


class TheContractIsWhatIsBeingMeasured(unittest.TestCase):
    """Anchors every door test below, so none of them can pass vacuously."""

    def test_the_canary_length_is_actually_under_its_floor(self):
        low, _, high = writer.WORD_CONTRACT[STEP]
        self.assertLess(UNDER, low)
        self.assertTrue(low <= LEGAL <= high)

    def test_the_live_cadence_names_the_step_the_contract_names(self):
        """If this ever fails, the doors below are gating nothing.

        A cadence whose keys the contract does not name - `day1`..`day21`, the
        fixture default - makes `word_range` answer None and every door test
        here green for the wrong reason.
        """
        from src import cadencelibrary
        keys = [s["key"] for s in cadencelibrary.SEQUENCES[LIVE_CADENCE]]
        self.assertIn(STEP, keys)
        self.assertIsNotNone(writer.word_range(STEP))
        self.assertEqual(clients.load("productive").get("cadence"),
                         LIVE_CADENCE,
                         "the live cadence moved; this file pins the old one")

    def test_a_day_keyed_step_is_named_by_no_contract(self):
        """The reason the cadence above had to be pinned, as an assertion."""
        self.assertIsNone(writer.word_range("day1"))


class DoorTest(unittest.TestCase):
    """Isolates the store and pins the live cadence. One line per door class.

    THE STORE IS ISOLATED EVEN THOUGH NOTHING HERE WRITES. Two of these doors
    read state beside the queue - suppression, operator exclusions, bounces -
    and an unisolated read resolves against whichever tree the module was
    imported from: empty in a worktree, the real estate in the main checkout.
    A door test whose verdict depends on which of those it found is not a
    measurement of the contract.
    """

    def setUp(self):
        import tempfile
        self.addCleanup(store.use_directory(tempfile.mkdtemp(prefix="doors-")))
        self.config = pin_client_config(self, cadence=LIVE_CADENCE)


def _contact():
    """A verified contact carrying NO stored `mx` block, and that is deliberate.

    Measured while writing this file: giving the contact
    `mx: {"status": "known_allowed", "email_eligible": True}` makes
    `eligibility.decide` answer `skipped:email_channel_disabled`, because
    `mx.allows_email` RE-DERIVES the decision from the hostnames rather than
    trusting the stored status - and `meridian.test` publishes no MX record.
    With no block at all it answers "no MX check has been run for this
    contact" and allows. So a fixture that faked a clearance was refused two
    gates before the one these tests are about, which is the guard doing
    exactly what it should and a fixture asserting the wrong thing.
    """
    from src import verification
    c = {"key": "ivana-saric", "name": "Ivana Saric",
         "title": "Head of Finance", "email": "ivana.saric@meridian.test",
         "linkedin": "https://linkedin.com/in/ivana-saric",
         "angle": "finance", "persona": "champion", "selected": True,
         "verdict": "valid", "reoon": None}
    evidence = [verification.result("contactout", verification.S_VALID,
                                    c["email"]),
                verification.result("deliverable", verification.S_VALID,
                                    c["email"])]
    verification.apply(c, verification.decide(evidence), evidence)
    return c


def _record(words=UNDER, step_key=STEP, rec_id="meridian"):
    """One record whose STORED cadence holds one generated email.

    Stored under its real key and never handed to a door out of band: the
    whole question is whether a caller holding only the record gets the gate.
    """
    return {"id": rec_id, "lane": "cold", "client": "productive",
            "company": "Meridian", "domain": "meridian.test",
            "state": "drafted", "drop_reason": None,
            "contacts": [_contact()], "diagnosis": None,
            "hook": "raised a seed round in May", "log": [],
            "company_facts": {"industry": "Design",
                              "research_outcome": "HTTP_SUCCESS"},
            "cadence": {"ivana-saric": {
                step_key: {"channel": "email", "generated": True,
                           "subject": "a subject that is fine",
                           "body": body(words)}}}}


class DoorOneApproveWhyNot(DoorTest):
    """`approve.why_not` - the gate every approval path consults.

    `approve_step` raises on it, `approvable_steps` filters on it and
    `pending` reports it, so a contract failure here is the difference between
    a draft that cannot be stamped and one that is stamped and refused one
    step later by `eligibility`. That disagreement between the generation gate
    and the approval gate is the exact failure `step_key_of`'s docstring says
    it exists to prevent.
    """

    def _why_not(self, words):
        from src import approve
        rec = _record(words=words)
        step = rec["cadence"]["ivana-saric"][STEP]
        # No `step_key=` is passed to lint anywhere on this path: `why_not`
        # takes the cadence key for its own lookup and hands `lint.check`
        # only (rec, contact_key, step).
        return approve.why_not(rec, "ivana-saric", STEP, step=step,
                               config=self.config)

    def test_an_under_contract_step_is_not_approvable(self):
        self.assertTrue(_is_contract_refusal(self._why_not(UNDER)),
                        self._why_not(UNDER))

    def test_a_legal_length_is_approvable_through_the_same_door(self):
        """The control. A door that refuses every body gates nothing."""
        self.assertIsNone(self._why_not(LEGAL))


class DoorTwoEligibilityDecide(DoorTest):
    """`eligibility.decide` - "may this one step go out right now".

    Its own docstring calls it the only authority on the question, and it is
    the door a payload in hand is linted at, so a body that reached here
    under-contract would be authorised for a real send.
    """

    def _decide(self, words):
        rec = _record(words=words)
        step = rec["cadence"]["ivana-saric"][STEP]
        return eligibility.decide(rec, rec["contacts"][0], STEP,
                                  channel="email", step=step,
                                  config=self.config)

    def test_an_under_contract_step_is_blocked_on_lint(self):
        out = self._decide(UNDER)
        self.assertEqual(out["verdict"], eligibility.BLOCKED, out)
        self.assertIn(eligibility.BLOCKED_LINT, out["reasons"], out)
        self.assertTrue(any(_is_contract_refusal(r) for r in out["reasons"]),
                        out["reasons"])

    def test_a_legal_length_is_not_blocked_on_lint(self):
        """The control, and it asserts the absence of THIS refusal only.

        A legal body is still `held:draft_not_approved` here, because nothing
        has stamped it - a later gate, and not this one. Asserting `eligible`
        would make the control a test of the whole gate stack and it would
        fail for reasons that have nothing to do with a word count.
        """
        out = self._decide(LEGAL)
        self.assertNotIn(eligibility.BLOCKED_LINT, out["reasons"], out)
        self.assertFalse([r for r in out["reasons"]
                          if _is_contract_refusal(r, STEP, LEGAL)
                          or "under_contract" in str(r)], out["reasons"])


class DoorThreeExecutionGuard(QueueTest):
    """`executionguard.authorize` gate 4 - the last door before a provider write.

    The heaviest of the four to reach, and the one that matters most: every
    gate before it has to be satisfied for the copy gate to be consulted at
    all. Tenancy, collision and MX are stubbed - they ask the network - and
    `lint` is deliberately NOT stubbed, which is the one difference from
    `tests/test_compliance_gate.py`, whose harness this follows.

    Opt-out is satisfied through `campaign["compliance"]["unsubscribe_via"]`
    rather than a link in the body, so the compliance gate (which runs
    immediately BEFORE the copy gate) passes without putting a URL into the
    text whose word count is the thing under test.

    MEASURED WHILE WRITING THIS, AND IT CHANGED THE TESTS: the guard's OWN
    `lint.check_step` at `src/executionguard.py:615` is NOT the gate that
    fires for a word-contract failure. `authorize` calls
    `eligibility.decide(...)` at line 571, forty-four lines earlier, and that
    call - which passes no `step` either, so it rebuilds the timeline and
    lints the expanded step - already refuses:

        NotAuthorized(gate="eligibility",
            "eligibility says blocked: ['blocked:lint_failed',
             'blocked:lint:em2_body_41_words_under_contract_45_to_90']")

    So the `copy` gate is SHADOWED here for this class of failure. Both are
    driven anyway, because they are two different claims: that the guard
    refuses at all (the production path, first test) and that line 615's own
    keyless call carries the contract too (second test, with eligibility
    stubbed eligible so the copy gate is what answers). Asserting only the
    first would leave line 615 exactly as unproven as the review found it;
    asserting only the second would prove a gate that nothing can reach.
    """

    def setUp(self):
        super().setUp()
        self.config = pin_client_config(self, cadence=LIVE_CADENCE)
        self.step_data = {"channel": "email", "generated": True,
                          "subject": "a subject that is fine",
                          "body": body(UNDER)}
        self._install(self.step_data)

    def _install(self, step_data):
        """Put the record and an approval that binds exactly this body."""
        rec = store.new_record("rec-doors", "domains", "productive",
                               "Meridian", "meridian.test")
        rec["state"] = "verified"
        rec["company_facts"] = {"industry": "Design",
                                "research_outcome": "HTTP_SUCCESS"}
        rec["contacts"] = [_contact()]
        fingerprint = approval.fingerprint(step_data)
        with store.transaction() as rows:
            rows.append(rec)
            for row in rows:
                if row["id"] == "rec-doors":
                    row.setdefault("cadence", {}).setdefault(
                        "ivana-saric", {})[STEP] = dict(
                            step_data,
                            approval={
                                "by": "operator", "at": store.now(),
                                "fingerprint": fingerprint,
                                "sender_fingerprint":
                                    approval.sender_fingerprint(self.config)})
        self.rec = store.get("rec-doors")
        self.contact = self.rec["contacts"][0]
        self.campaign = self._campaign()

    def _campaign(self):
        campaign = campaigns.new_campaign(
            "doors-test", "productive", "CLIENT - DOORS",
            created_by="operator")
        campaign.update({
            "bison_campaign_id": 487,
            "record_ids": ["rec-doors"],
            "senders": {"email": [{"id": 116968, "daily_limit": 1}],
                        "linkedin": []},
            "daily_volume": {"email": 1, "linkedin": 0},
            "org_unit": 118832,
            # The provider-level opt-out route, NAMED. An unnamed reliance is
            # refused by the compliance gate and would never reach the copy
            # gate this class is about.
            "compliance": {"unsubscribe_via": "emailbison.unsubscribe_text"},
        })
        from src import senderidentity
        with senderidentity.transaction() as rows:
            rows.append(senderidentity.new_sender(
                "productive", "mina", "Mina Ruzicic"))
            rows.append(senderidentity.new_linkedin_account(
                "productive", "li-116968", "mina",
                "https://www.linkedin.com/in/mina-ruzicic-b4422438a",
                provider="emailbison", provider_account_id="116968",
                active=True, daily_limit=40, health="ok"))
        current = campaigns.fingerprint(campaign, store.load(), self.config)
        campaign["approval"] = {"action": "approve", "by": "operator",
                                "at": store.now(), "fingerprint": current}
        campaign["fingerprint"] = current
        campaign["status"] = campaigns.APPROVED
        return campaign

    def _readback(self):
        return configdiff.Readback(
            diff={"verdict": configdiff.PASS, "failures": []},
            approved={}, provider={}, campaign_id="doors-test",
            channel="email", provider_campaign_id=487, verified_at=FRESH)

    @contextlib.contextmanager
    def _network_stubbed(self):
        """Everything that asks the network. `lint` is NOT in this list."""
        from src.providers import bison
        from src import mx
        with mock.patch.object(bison, "require_workspace",
                               lambda expected: expected), \
             mock.patch.object(collision, "check_address",
                               return_value=(collision.CLEAR, {})), \
             mock.patch.object(collision, "check_account",
                               return_value={"verdict": collision.CLEAR,
                                             "people": [],
                                             "emails_sent_total": 0}), \
             mock.patch.object(mx, "allows_email",
                               return_value=(True, "test stub")):
            yield

    def _authorize(self):
        return executionguard.authorize(
            operation="email_send", channel="email", campaign=self.campaign,
            rec=self.rec, contact=self.contact, step_key=STEP,
            workspace=WS, config=self.config, now=NOW,
            readback=self._readback())

    def test_the_guard_refuses_an_under_contract_body(self):
        """The production path. Named gate asserted, not merely "it refused".

        `test_compliance_gate` records the mutation that makes naming the gate
        necessary: a later gate refuses the same call and carries the same
        passed-gate trace, so "something refused" cannot tell the intended
        gate from the one after it. Here the gate is `eligibility`, for the
        reason in the class docstring, and the CODE is what ties the refusal
        to the contract rather than to anything else eligibility checks.
        """
        with self._network_stubbed():
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self._authorize()
        self.assertEqual(caught.exception.gate, "eligibility",
                         str(caught.exception))
        self.assertTrue(_is_contract_refusal(caught.exception),
                        str(caught.exception))

    def test_the_guards_own_copy_gate_also_carries_the_contract(self):
        """Line 615's keyless `lint.check_step`, reached by stubbing its shadow.

        `eligibility.decide` is stubbed ELIGIBLE - the only stub in this file
        that is not a network call - so the copy gate is what answers. Without
        this test, the guard's own lint call would stay exactly as unproven as
        GLM found it: shadowed by an earlier gate that happens to agree.
        """
        eligible = {"verdict": "eligible", "reasons": [], "reason": None,
                    "step": STEP, "channel": "email"}
        with self._network_stubbed(), \
             mock.patch.object(executionguard.eligibility, "decide",
                               return_value=eligible):
            with self.assertRaises(executionguard.NotAuthorized) as caught:
                self._authorize()
        self.assertEqual(caught.exception.gate, "copy", str(caught.exception))
        self.assertTrue(_is_contract_refusal(caught.exception),
                        str(caught.exception))
        # And the compliance gate, which runs immediately before it, passed -
        # so the refusal is about the words and not about opt-out.
        self.assertIn("compliance", list(caught.exception.passed or []),
                      caught.exception.passed)

    def test_a_legal_length_is_refused_by_neither_gate(self):
        """The control. A later gate may refuse; these two may not.

        Reinstalled at `LEGAL` words rather than edited in place, because the
        approval fingerprint binds the body and a stamp for a different one is
        stale by construction - the record would be refused at `approval`,
        gates before the ones under test, and the control would pass without
        ever reaching them.
        """
        self._install(dict(self.step_data, body=body(LEGAL)))
        with self._network_stubbed():
            try:
                self._authorize()
            except executionguard.NotAuthorized as refused:
                self.assertNotIn("under_contract", str(refused), str(refused))
                self.assertNotEqual(refused.gate, "copy", str(refused))


class DoorFourCampaignsLintClean(DoorTest):
    """`campaigns.check_lint_clean` - a launch blocker over the whole campaign.

    It builds each record's timeline itself and lints every email step in it,
    so it is the one door of the four that reaches an EXPANDED step rather
    than the stored object - which is why `step_key_of`'s body fallback, and
    not its identity check, is what carries the contract here.
    """

    def _check(self, words):
        rec = _record(words=words)
        campaign = campaigns.new_campaign("doors", "productive", "X",
                                          created_by="operator")
        campaign["record_ids"] = [rec["id"]]
        return campaigns.check_lint_clean(campaign, [rec], self.config)

    def test_an_under_contract_step_fails_the_launch_check(self):
        ok, why = self._check(UNDER)
        self.assertFalse(ok, why)
        self.assertTrue(_is_contract_refusal(why), why)

    def test_a_legal_length_passes_the_same_check(self):
        ok, why = self._check(LEGAL)
        self.assertTrue(ok, why)

    def test_the_step_the_door_linted_was_the_expanded_one(self):
        """Names the mechanism, so a reader knows which recovery is load-bearing.

        The timeline step is a NEW object carrying the stored body alongside a
        status, a day and a variant the stored one does not have, so it is
        identical to nothing and equal to nothing. Only the body matches.
        """
        rec = _record(words=UNDER)
        stored = rec["cadence"]["ivana-saric"][STEP]
        campaign = campaigns.new_campaign("doors", "productive", "X",
                                          created_by="operator")
        campaign["record_ids"] = [rec["id"]]
        timeline = cadence.build(rec, self.config, campaign=campaign)
        expanded = (timeline["contacts"].get("ivana-saric") or {})[STEP]
        self.assertIsNot(expanded, stored)
        self.assertNotEqual(expanded, stored)
        self.assertEqual(expanded.get("body"), stored.get("body"))
        # And the key is still recovered from it, with no key passed.
        self.assertEqual(
            lint.step_key_of(rec, "ivana-saric", expanded), STEP)


class TheFourDoorsAgree(DoorTest):
    """One body, four doors, one verdict.

    The failure this guards is not a door missing the contract - each test
    above covers its own - but the doors DISAGREEING, which is the shape the
    deleted module was written for and the one this repository keeps paying
    for: a draft that generation accepts, approval refuses, and the launch
    check reports differently again.
    """

    def _verdicts(self, words):
        from src import approve
        rec = _record(words=words)
        step = rec["cadence"]["ivana-saric"][STEP]
        campaign = campaigns.new_campaign("doors", "productive", "X",
                                          created_by="operator")
        campaign["record_ids"] = [rec["id"]]
        decided = eligibility.decide(rec, rec["contacts"][0], STEP,
                                     channel="email", step=step,
                                     config=self.config)
        ok, why = campaigns.check_lint_clean(campaign, [rec], self.config)
        return {
            "approve": _is_contract_refusal(
                approve.why_not(rec, "ivana-saric", STEP, step=step,
                                config=self.config) or "", STEP, words),
            "eligibility": any(_is_contract_refusal(r, STEP, words)
                               for r in decided["reasons"]),
            "campaigns": (not ok) and _is_contract_refusal(why, STEP, words),
        }

    def test_all_three_record_level_doors_refuse_the_same_body(self):
        verdicts = self._verdicts(UNDER)
        self.assertEqual(set(verdicts.values()), {True}, verdicts)

    def test_and_none_of_them_refuses_a_legal_one(self):
        verdicts = self._verdicts(LEGAL)
        self.assertEqual(set(verdicts.values()), {False}, verdicts)


if __name__ == "__main__":
    unittest.main()
