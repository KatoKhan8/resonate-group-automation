#!/usr/bin/env python3
"""The word ceiling is enforced on the COMPOSED body, not the gate count.

THE RULE THIS PINS. Operator, 2026-10-15 21:25, TASK 0067:

    The contract stands: em1/em3 60/75/90, em4 45/60/90, hard ceiling 90,
    certification bound 88. What changes is where it is measured.
    Today the gate measures its own count, so a body can pass the gate and
    arrive over 90. From now the gate measures what the prospect receives.

MEASURED, NOT INHERITED, at 93162471d through the real renderer and composer
(`work/0067_offsets.py`, run 2026-10-15): what the prospect receives is the
bare body PLUS the CTA link (1 word) on a thread starter, the sender
signature (3 words) and the opt-out line (0 words - `countable_words`
replaces it with a space) - so as-sent is gate + 4 on a starter and gate + 3
on a thread reply, where the CTA is dropped. A draft at the top of its
contract, 90, therefore arrives at 94. Those offsets were restated wrongly
once before (+4 generalised to em3) and glm-b/0090 caught it, which is why
the numbers above are this tree's own measurement and why the tests below
re-count their own fixtures rather than trusting a constant.

THE DEFECT THIS CLOSES. Nothing on the staging path counts words AT ALL:
`copylint.check_batch` has no word-count rule, and the per-step contract in
`lint.check` runs on the DRAFT path, where it measures the bare body. So a
campaign whose every body is inside its contract could still be staged with
emails over the hard ceiling as sent - the exact gap between "the gate
passed" and "the prospect received".

WHAT EACH TEST HERE IS FOR, and none of them reads the source:

  - the pure check refuses a composed body over 90 by step and count, passes
    one at exactly 90, and REPORTS a step the contract does not name rather
    than silently passing it (module convention: absence is reported, never
    read as a pass);
  - the staging gate refuses a body that is INSIDE its contract on the draft
    count and over 90 as sent - both the starter shape (+4) and the reply
    shape (+3) - and passes at exactly 90 as sent;
  - the full chain refuses it on a dry run before any provider write, the
    control at exactly 90 reaches the dry-run projection, and bypassing the
    check makes the refusal disappear - so the refusal is this gate's and
    not another guard firing first;
  - and in every full-chain case the provider transport is NEVER reached.
"""
import unittest
from unittest import mock

from src import (bisonfactory, campaigns, lint, providers, sequencegate,
                 store, workspaces)
from src.skills import cold_email_writing as writercontract
from tests import packfixture
from tests.base import QueueTest
from tests.test_staging_a_campaign_twice_builds_one import (CID, COMPANY,
                                                           CONFIG, record)

#: The CTA the composed body carries on a thread starter. Same shape as
#: `test_the_offer_cta_link_reaches_the_prospect`: the offer is patched
#: because these tests assert what the composer does with one, not what the
#: operator's file currently selects.
LINK = "https://productive.io/get-started/"
OFFER_WITH_LINK = {"cta_link": LINK, "thread_reply_rungs": [2, 4]}

#: Five steps keyed the way the projection names them: em2 and em4 reply
#: inside a thread, the others open one. This is the pattern the CTA gate's
#: tests use, and the reply positions are what drop the CTA and make as-sent
#: + 3 rather than + 4.
SEQUENCE = ({"step_key": "em1", "thread_reply": False},
            {"step_key": "em2", "thread_reply": True},
            {"step_key": "em3", "thread_reply": False},
            {"step_key": "em4", "thread_reply": True},
            {"step_key": "em5", "thread_reply": False})

#: Bodies of an exact countable length, for the pure check. Neutral tokens:
#: no sign-off shape for `countable_words` to strip, nothing for any lint to
#: read into. The count is asserted below, not assumed.
FILLER = ["word%03d" % i for i in range(1, 101)]


def words(n):
    """A body of exactly `n` countable words (asserted by the tests)."""
    return " ".join(FILLER[:n])


def countable(text):
    """The gate's own counter - `lint.countable_words` returns a list."""
    return len(lint.countable_words(text))


def _lead(bodies, persona="economic_buyer"):
    """One plan lead whose copy says exactly `bodies` ({step_key: body})."""
    return {"record_id": "rec-1", "contact_key": "c-1", "persona": persona,
            "copy": [{"step_key": node["step_key"],
                      "subject": "Subject %s" % node["step_key"],
                      "body": bodies[node["step_key"]], "ps": ""}
                     for node in SEQUENCE if node["step_key"] in bodies]}


def _plan(bodies):
    return {"leads": [_lead(bodies)], "provider_sequence": [dict(s) for s in SEQUENCE],
            "sender": {"name": "Anna Kowalski", "company": "Productive"}}


# ------------------------------------------------ (a) the pure check

class TestThePureCheck(unittest.TestCase):
    """`sequencegate.check_composed_length` on composed strings directly."""

    def test_a_step_over_the_ceiling_as_sent_fails_by_name(self):
        result = sequencegate.check_composed_length({"em1": words(91)})
        self.assertFalse(result["passed"])
        self.assertEqual(1, len(result["failures"]))
        failure = result["failures"][0]
        self.assertEqual("composed_ceiling", failure["check"])
        self.assertEqual("em1", failure["step"])
        self.assertIn("91", failure["why"])
        self.assertIn("90", failure["why"])

    def test_a_step_at_exactly_the_ceiling_passes(self):
        """90 as sent is the ceiling, not one under it."""
        result = sequencegate.check_composed_length({"em1": words(90)})
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual([], result["failures"])

    def test_a_step_the_contract_does_not_name_is_reported_not_refused(self):
        """A cadence step outside em1..em5 has no declared ceiling. The
        module's convention for a question it cannot answer is to REPORT it,
        not to refuse and not to pass silently."""
        result = sequencegate.check_composed_length({"step_2": words(91)})
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual([], result["failures"])
        self.assertEqual(["step_2"], [w["step"] for w in result["warnings"]])

    def test_no_composed_step_at_all_is_refused_not_passed(self):
        """A check handed nothing must not read as a check that passed -
        the failure mode this repository keeps paying for."""
        result = sequencegate.check_composed_length({})
        self.assertFalse(result["passed"])
        self.assertEqual(["composed_ceiling"],
                         [f["check"] for f in result["failures"]])

    def test_an_empty_body_is_not_a_length_failure(self):
        """Emptiness is not a length question: missing copy is refused by
        name elsewhere (`_ensure_leads`, `_refuse_copylint`'s stand-aside),
        and a length gate that invented its own emptiness refusal would
        report the same defect twice in two vocabularies."""
        result = sequencegate.check_composed_length({"em1": ""})
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual([], result["failures"])


# --------------------------------------------- (b) the staging gate

class TestTheStagingGate(unittest.TestCase):
    """`_refuse_composed_ceiling` on a plan, with no transport at all.

    The bodies are filler, so no copy lint has an opinion about them - the
    only thing that can refuse here is the gate under test.
    """

    def test_a_body_inside_the_gate_count_but_over_the_ceiling_as_sent_is_refused(self):
        """THE BORN-RED CASE. em1 of 87 words is INSIDE its contract
        (60..90) on the draft count, and 91 as sent (+ 4: CTA, signature,
        opt-out). Before TASK 0067 nothing measured the 91."""
        low, ceiling = writercontract.word_range("em1")
        self.assertEqual((60, 90), (low, ceiling))
        bodies = {"em1": words(87), "em2": words(20), "em3": words(20),
                  "em4": words(20), "em5": words(20)}
        self.assertTrue(low <= countable(bodies["em1"]) <= ceiling,
                        "the fixture must pass the gate count to prove the "
                        "gap, and it does not")
        report = {"client": "productive"}
        with mock.patch.object(bisonfactory, "_offer_for",
                               return_value=("OFFER-TEST", OFFER_WITH_LINK)):
            with self.assertRaises(bisonfactory.FactoryRefused) as caught:
                bisonfactory._refuse_composed_ceiling(
                    {"client": "productive"}, _plan(bodies), [], report)
        message = str(caught.exception)
        self.assertIn("em1", message)
        self.assertIn("91", message)
        self.assertIn("90", message)
        self.assertIn("rec-1/c-1", message)
        self.assertFalse(report["length_gate"]["passed"])
        self.assertEqual(
            ["em1"],
            [f["step"] for f in report["length_gate"]["leads"][0]["failures"]])

    def test_a_thread_reply_over_the_ceiling_as_sent_is_refused(self):
        """The reply shape: no CTA, so as-sent is gate + 3. em2 of 88 words
        is inside its contract on the draft count and 91 as sent."""
        bodies = {"em1": words(60), "em2": words(88), "em3": words(20),
                  "em4": words(20), "em5": words(20)}
        report = {"client": "productive"}
        with mock.patch.object(bisonfactory, "_offer_for",
                               return_value=("OFFER-TEST", OFFER_WITH_LINK)):
            with self.assertRaises(bisonfactory.FactoryRefused) as caught:
                bisonfactory._refuse_composed_ceiling(
                    {"client": "productive"}, _plan(bodies), [], report)
        self.assertIn("em2", str(caught.exception))
        self.assertEqual(
            ["em2"],
            [f["step"] for f in report["length_gate"]["leads"][0]["failures"]])

    def test_the_gate_passes_at_exactly_the_ceiling_as_sent(self):
        """The control: 86 words + 4 as sent is exactly 90, and the gate
        measures what arrives, so it passes. Without this the tests above
        would pass for a gate that refused everything."""
        bodies = {"em1": words(86), "em2": words(20), "em3": words(20),
                  "em4": words(20), "em5": words(20)}
        report = {"client": "productive"}
        with mock.patch.object(bisonfactory, "_offer_for",
                               return_value=("OFFER-TEST", OFFER_WITH_LINK)):
            bisonfactory._refuse_composed_ceiling(
                {"client": "productive"}, _plan(bodies), [], report)
        self.assertTrue(report["length_gate"]["passed"])

    def test_a_step_the_contract_does_not_name_warns_and_does_not_refuse(self):
        """An unnamed step is warned about on the report, so a run that
        skipped a body is observable, but it is not refused here."""
        # A single-step lead whose copy names a step outside em1..em5: the
        # single-step path keys the composed body off the copy node itself.
        plan = {"leads": [{"record_id": "rec-1", "contact_key": "c-1",
                           "persona": "economic_buyer",
                           "copy": [{"step_key": "step_2",
                                     "subject": "Subject",
                                     "body": words(87), "ps": ""}]}],
                "provider_sequence": [dict(s) for s in SEQUENCE],
                "sender": {"name": "Anna Kowalski", "company": "Productive"}}
        report = {"client": "productive"}
        with mock.patch.object(bisonfactory, "_offer_for",
                               return_value=("OFFER-TEST", OFFER_WITH_LINK)):
            bisonfactory._refuse_composed_ceiling(
                {"client": "productive"}, plan, [], report)
        self.assertTrue(report["length_gate"]["passed"])
        self.assertEqual(
            ["step_2"],
            [w["step"] for w in report["length_gate"]["leads"][0]["warnings"]])

    def test_a_lead_with_no_offer_is_still_measured(self):
        """The gate measures words, not the CTA. A persona with no selected
        offer still gets a signature and an opt-out line (+ 3), and 88 words
        of draft is still 91 as sent."""
        bodies = {"em1": words(88), "em2": words(20), "em3": words(20),
                  "em4": words(20), "em5": words(20)}
        report = {"client": "productive"}
        with mock.patch.object(bisonfactory, "_offer_for",
                               return_value=(None, None)):
            with self.assertRaises(bisonfactory.FactoryRefused):
                bisonfactory._refuse_composed_ceiling(
                    {"client": "productive"}, _plan(bodies), [], report)
        self.assertFalse(report["length_gate"]["passed"])


# ---------------------------------------- (c) the full chain, dry run

#: Two email steps, em2 replying in em1's thread: the config shape the
#: sequence-gate dry-run module uses, reused so this module's full-chain
#: fixture differs from that one's in ONE thing only - what em1 says.
from tests.test_a_dry_run_runs_the_sequence_gate import (  # noqa: E402
    TWO_STEPS, two_step_config)


#: The em1 bodies. First line and closing question are `packfixture.opener`'s
#: verbatim - proven grounded in `packfixture.own_fact` and clean under every
#: other lint - and only the middle paragraph grows, so the count is the one
#: thing that moves. Counts measured before this file was written
#: (`work/0067_probe.py`, 93162471d): 87 and 86 countable words; as sent with
#: the CTA offer below they compose to 91 and 90 (+ 4: link 1, signature 3,
#: opt-out 0).
OPENER_87 = (
    "Ada, your site says Example runs delivery scheduling for independent "
    "clinics.\n\n"
    "Most teams that size only see project margin once a project has "
    "closed, which is after the point where anything could be done about "
    "it.\n\n"
    "The same gap tends to hide delivery work that was never billed. "
    "Weekly reporting usually arrives too late to change any of it. "
    "Another pattern shows up once project managers own the schedule "
    "instead of the finance team. Both habits cost margin.\n\n"
    "Is that roughly how it works for you today?")

OPENER_86 = OPENER_87.replace("Both habits cost margin.", "Habits cost margin.")


def gated_record(em1_body):
    """One stageable record whose FIRST step's words are the variable.

    Modelled on `two_step_record`: everything else held constant - the same
    account, the same pack fact, the same approvals, the same em2 - so the
    only thing that can move a run from refused to staged is how long em1
    is as sent.
    """
    from src import approval as _approval

    rec = record("rec-1", "one@example.com", "Ada")
    key = "rec-1-c1"
    opener = {"channel": "email", "subject": "how margin shows up",
              "body": "<p>%s</p>" % em1_body}
    opener["approval"] = {"by": "operator", "at": "2026-09-13T00:00:00Z",
                          "fingerprint": _approval.fingerprint(opener)}
    second = {"channel": "email", "subject": "a follow-up",
              "body": packfixture.html_followup("em2")}
    second["approval"] = {"by": "operator", "at": "2026-09-13T00:00:00Z",
                          "fingerprint": _approval.fingerprint(second)}
    rec["cadence"] = {key: {"em1": opener, "em2": second}}
    return rec


class AProviderRequestWasMade(AssertionError):
    """The transport was reached. On a dry run that is always a failure."""


class TestTheDryRunEnforcesIt(QueueTest):

    def setUp(self):
        super().setUp()
        # THE BOOBY TRAP, installed before anything else.
        self.requests = []

        def refuse_every_request(method, url, headers, body, timeout):
            self.requests.append((method, url))
            raise AProviderRequestWasMade(
                f"a provider request was made: {method} {url}. A dry run "
                f"performs zero provider writes and zero provider reads")

        providers.set_transport(refuse_every_request)
        self.addCleanup(providers.reset_transport)

        # `sending.live` ON, deliberately: the killswitch must not be what
        # stops this run, or these tests would pass with the gate inert.
        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

    def given(self, em1_body):
        store.save([gated_record(em1_body)])
        row = campaigns.new_campaign(CID, "productive", "Composed ceiling")
        row["cadence_steps"] = [dict(s) for s in TWO_STEPS]
        row["record_ids"] = ["rec-1"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

    def dry_run(self):
        """The real production entrypoint, zero-write mode, with an offer
        selected so em1 is composed with its CTA link - the + 4 shape.

        The config carries a sender block the way the real client config
        does. Without one the plan composes no signature and the composed
        body is draft + opt-out only, which never reaches the ceiling from
        a draft that passed the gate count."""
        config = dict(two_step_config(),
                      sender={"name": "Anna Kowalski",
                              "role": "Head of Delivery",
                              "company": "Productive"})
        with mock.patch.object(bisonfactory, "_offer_for",
                               return_value=("OFFER-TEST", OFFER_WITH_LINK)):
            return bisonfactory.stage(CID, config=config, live=False)

    def assertNothingReachedTheProvider(self):
        self.assertEqual([], self.requests,
                         "a dry run reached the provider transport")

    def test_the_booby_trap_actually_fires(self):
        """Every zero-write claim in this module rests on this one."""
        with self.assertRaises(AProviderRequestWasMade):
            providers.request("GET", "http://example.invalid/armed",
                              headers={}, body=None, timeout=1)
        self.assertEqual([("GET", "http://example.invalid/armed")],
                         self.requests)
        self.requests.clear()

    def test_a_body_that_passes_the_gate_count_and_exceeds_90_as_sent_is_refused(self):
        """em1 of 87 words is inside its contract on the draft count and
        91 as sent. The dry run must refuse it before any provider write,
        naming the gate, the step, the count and the ceiling."""
        low, ceiling = writercontract.word_range("em1")
        self.assertEqual((60, 90), (low, ceiling))
        self.assertEqual(87, countable(OPENER_87))
        self.assertTrue(low <= 87 <= ceiling,
                        "the fixture must pass the gate count to prove the "
                        "gap, and it does not")
        self.given(OPENER_87)
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.dry_run()
        message = str(caught.exception)
        self.assertIn("em1", message)
        self.assertIn("91", message)
        self.assertIn("90", message)
        self.assertIn("rec-1/rec-1-c1", message)
        gate = caught.exception.report["length_gate"]
        self.assertFalse(gate["passed"])
        self.assertEqual(
            ["em1"],
            [f["step"] for f in gate["leads"][0]["failures"]])
        self.assertNothingReachedTheProvider()

    def test_a_body_at_exactly_90_as_sent_reaches_the_projection(self):
        """WITHOUT THIS THE TEST ABOVE PROVES NOTHING. The same fixture with
        one word fewer - 86 words, 90 as sent, exactly the ceiling - must
        run all the way to the dry-run projection, and the gate's verdict
        must be ON the report so a check that never ran cannot look like
        one that passed."""
        self.assertEqual(86, countable(OPENER_86))
        self.given(OPENER_86)
        report = self.dry_run()
        self.assertFalse(report["live"])
        self.assertIn("dry run: nothing was sent", report["did"])
        self.assertEqual(["em1", "em2"],
                         [step["step_key"]
                          for step in report["plan"]["provider_sequence"]])
        self.assertEqual([], report["plan"]["leads"][0]["missing_copy"])
        self.assertTrue(report["length_gate"]["passed"])
        self.assertNothingReachedTheProvider()

    def test_the_length_gate_is_what_refuses_and_not_another_guard(self):
        """Bypass the check and the same over-ceiling campaign reaches the
        projection. Without this the refusal could be the copy lint, the
        sequence gate or the CTA gate firing first, and these tests would
        prove nothing about the length check."""
        self.given(OPENER_87)
        with self.assertRaises(bisonfactory.FactoryRefused):
            self.dry_run()

        def passes_everything(composed):
            return {"passed": True, "checks": [], "failures": [],
                    "warnings": []}

        with mock.patch.object(sequencegate, "check_composed_length",
                               passes_everything):
            report = self.dry_run()
        self.assertEqual(["em1", "em2"],
                         [step["step_key"]
                          for step in report["plan"]["provider_sequence"]],
                         "with the length check bypassed the run still did "
                         "not reach the projection, so the gate is not what "
                         "refuses and these tests prove nothing about it")
        self.assertNothingReachedTheProvider()


if __name__ == "__main__":
    unittest.main()
