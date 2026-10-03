"""TASK-400 REWORK 3: the four behaviours the operator decided, by EFFECT.

Operator decision, 2026-09-27, all four APPROVED and not open questions:

1. COPYLINT RETRY STAYS. A draft that fails copylint is REGENERATED and never
   proceeds toward sending. Never widen a lint rule to make a draft pass.
2. A draft that failed a gate is NEVER stored as a send candidate.
3. A MODEL ERROR HOLDS THE RECORD. No fail-open. Passing silently with no copy
   is fail-open and is refused.
4. UNAPPROVED drafts MAY be regenerated. APPROVED or SENT drafts are NEVER
   overwritten, because regeneration after approval invalidates the approval
   hash: the approval stays bound to exactly the approved copy.

EVERYTHING HERE GOES THROUGH `generate.run`, the real entrypoint, and asserts on
the RECORD afterwards. Nothing reads source text and nothing asserts that a
function exists. Every test is paired with a mutation in
`docs/TASK-400-REWORK3-MUTATIONS.md`: the behaviour is broken in production, the
named test is confirmed to fail, and the failure is confirmed to be the intended
one rather than a different guard firing first.

No model and no provider is called: the model is scripted and the campaign path
touches no provider at all.
"""
import copy
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import (approval, campaignstrategy, copylint, generate,
                 generate_campaign, lint, llm, stepstate, store)
from tests.base import FIXTURES, install_fixture, pin_approved_offer, pin_fixture_clients
from tests.test_generate import (CampaignModel, HARBOURLINE_SEQUENCES,
                                HARBOURLINE_SUBJECTS, same_body_everywhere)

#: A body `src/lint.py` accepts and `src/copylint.py` refuses. "streamline" is
#: in `copylint.BUZZWORDS` and is NOT in `lint.BANNED_PHRASES`, so this isolates
#: behaviour 1 to the batch lint: if the retry happens, copylint caused it.
BUZZWORD_EM1 = (
    "Rowan, on 17 October Jesse asked to run the key against a realistic list "
    "of companies and the reply pivoted to booking a call, so the question "
    "itself was never answered. We could streamline the whole thing by raising "
    "a key with a sane limit and pointing it at a list you choose. Is that "
    "still the test you would want to run?")


def buzzword_set():
    """The clean set with a buzzword in em1 and nothing else changed."""
    seqs = dict(HARBOURLINE_SEQUENCES)
    seqs["em1"] = BUZZWORD_EM1
    return seqs


class Rework3Test(unittest.TestCase):
    """The same estate and pins as `tests/test_generate.py`'s GenerateTest."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-400r3-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        install_fixture("phase5.jsonl", self.queue)
        self._prev = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue
        self.addCleanup(self._restore_queue)

        self.config = pin_fixture_clients(self, linkedin_connection_note=None)
        pin_approved_offer(self)
        campaignstrategy.clear_cache()
        self.addCleanup(campaignstrategy.clear_cache)

    def _restore_queue(self):
        if self._prev is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rec(self, rid="harbourline"):
        return store.get(rid)

    def seed(self, rid, contact_key, steps):
        """Put steps into a record's cadence on disk, exactly as stored."""
        with store.transaction() as rows:
            target = next(r for r in rows if r["id"] == rid)
            target.setdefault("cadence", {}).setdefault(contact_key, {}).update(
                copy.deepcopy(steps))

    def step_of(self, sequences, subjects, step_key, rid="harbourline"):
        """The step the adapter WOULD build for `step_key` from this writer set."""
        rec = self.rec(rid)
        contact = rec["contacts"][0]
        sequence = generate.sequence_for(rec, self.config, contact, None)
        pairs = dict(generate._candidate_steps(
            {"contact_key": lint.contact_key(contact),
             "sequences": sequences, "subjects": subjects}, sequence))
        return pairs[step_key]

    def lead_for(self, sequences, subjects):
        """The batch-lint lead the campaign path builds from a writer answer."""
        subj = {"em1": "A", "em2": "A", "em3": "B", "em4": "B", "em5": "C"}
        return {
            "id": "rowan-blake",
            "steps": [{"subject": subjects[subj[k]],
                       "body": sequences.get(k, "")}
                      for k in ("em1", "em2", "em3", "em4", "em5")],
            "ps": {},
            "linkedin": {k: sequences.get(k, "")
                         for k in ("connect", "msg1", "msg2", "msg3")},
            "pack": {"facts": [{"snippet": "offices in Zagreb HR"}]},
        }


# ===========================================================================
# BEHAVIOUR 1 - COPYLINT REFUSES, THE WRITER IS ASKED AGAIN
# ===========================================================================

class TestBehaviour1CopylintRetryStays(Rework3Test):

    def test_the_isolation_holds_before_anything_else_is_claimed(self):
        """Per-draft lint ACCEPTS this body and copylint REFUSES it.

        Without this, the test below proves only that something refused the
        draft. With it, the only gate that can have caused the regeneration is
        the batch lint - which is what behaviour 1 is about.
        """
        step = self.step_of(buzzword_set(), HARBOURLINE_SUBJECTS, "day1")
        rec = self.rec()
        rec["diagnosis"] = json.loads(
            '{"died_on": "2024-10-17", "died_because": "the question was never '
            'answered", "failure_mode": "unanswered_question", '
            '"last_position": null, "what_changed": null}')
        self.assertEqual(lint.check(rec, "rowan-blake", step), [],
                         "src/lint.py already refuses this body, so a retry "
                         "would not isolate copylint")
        report = copylint.check_batch([self.lead_for(buzzword_set(),
                                                    HARBOURLINE_SUBJECTS)])
        self.assertTrue(report["refused"], "copylint accepts the buzzword body")
        self.assertIn("rowan-blake", report["offenders"]["buzzword"])

    def test_a_draft_copylint_refuses_is_regenerated_and_never_stored(self):
        model = CampaignModel(
            (buzzword_set(), HARBOURLINE_SUBJECTS),
            (HARBOURLINE_SEQUENCES, HARBOURLINE_SUBJECTS))
        generate.run(model=model, live=True, ids=["harbourline"])

        self.assertEqual(len(model.writer_prompts), 2,
                         "the writer was not asked again, so a draft copylint "
                         "refused went straight through")
        stored = (self.rec()["cadence"].get("rowan-blake") or {}).get("day1")
        self.assertIsNotNone(stored, "the regenerated draft was not stored")
        self.assertNotIn("streamline", stored["body"],
                         "the copy copylint refused is on the record")
        self.assertEqual(stored["body"], HARBOURLINE_SEQUENCES["em1"])

    def test_the_rule_was_not_widened_to_let_it_through(self):
        """The refusal still refuses, afterwards. CLAUDE.md's standing rule."""
        self.assertIn("streamline", copylint.BUZZWORDS)
        report = copylint.check_batch([self.lead_for(buzzword_set(),
                                                    HARBOURLINE_SUBJECTS)])
        self.assertTrue(report["refused"])


# ===========================================================================
# BEHAVIOUR 2 - A DRAFT THAT FAILED A GATE IS NOT A SEND CANDIDATE
# ===========================================================================

class TestBehaviour2NeverStoredAsASendCandidate(Rework3Test):

    def test_a_set_that_never_passes_leaves_no_row_anywhere(self):
        model = CampaignModel((buzzword_set(), HARBOURLINE_SUBJECTS))
        generate.run(model=model, live=True, ids=["harbourline"])

        rec = self.rec()
        self.assertEqual((rec.get("cadence") or {}).get("rowan-blake", {}), {})
        # AND NOTHING DOWNSTREAM CAN SEE IT. `lint.email_steps` is what the
        # approval queue, the preview and both provider projections walk, so an
        # empty walk is the operational form of "not a send candidate".
        self.assertEqual(list(lint.email_steps(rec)), [])
        self.assertNotEqual(rec.get("state"), "drafted",
                            "a record with no copy was moved to drafted")
        self.assertTrue(any("no draft passed lint" in e["note"]
                            for e in rec["log"]),
                        "the refusal left no trace on the record")

    def test_the_budget_is_bounded_rather_than_a_loop(self):
        model = CampaignModel((buzzword_set(), HARBOURLINE_SUBJECTS))
        generate.run(model=model, live=True, ids=["harbourline"])
        self.assertEqual(len(model.writer_prompts),
                         generate_campaign.MAX_WRITER_ATTEMPTS)

    def test_the_store_door_refuses_on_its_own(self):
        """The SECOND door, asserted independently of the writer's retry.

        There are two: the writer is asked again when a gate refuses, and the
        adapter refuses to write a step that fails a gate. The first makes the
        second unreachable in the wired path, which is exactly the condition
        under which a guard rots unnoticed - so it is driven directly here, with
        a plan whose copy `src/lint.py` refuses. It must store nothing. A caller
        that reaches `_adapt_plan_to_cadence` with no validator (the retry
        never ran) must not get bad copy onto the record either.
        """
        rec = self.rec()
        rec["diagnosis"] = {"died_on": None, "died_because": "a real reason",
                            "failure_mode": "no_pass_mark",
                            "last_position": None, "what_changed": None}
        plan = {"contacts": [{"contact_key": "rowan-blake",
                              "first_name": "Rowan",
                              "qualification": "QUALIFIED_RICH",
                              "held": None,
                              "sequences": same_body_everywhere(
                                  "[FIRST NAME], screenshot attached below."),
                              "subjects": HARBOURLINE_SUBJECTS}]}
        written = generate._adapt_plan_to_cadence(rec, plan, self.config)
        self.assertEqual(written, [])
        self.assertEqual((rec.get("cadence") or {}).get("rowan-blake", {}), {})


# ===========================================================================
# BEHAVIOUR 3 - A MODEL ERROR HOLDS THE RECORD
# ===========================================================================

class WriterFails(CampaignModel):
    """Answers every stage and fails at the writer, the way a 500 does."""

    def complete(self, prompt, temperature=0, client=None, config=None,
                 max_tokens=None):
        if "write cold outreach" in prompt.lower():
            self.prompts.append(prompt)
            raise llm.ModelError("the endpoint returned 500")
        return super().complete(prompt, temperature, client, config)


class UnavailableModel(CampaignModel):
    """A fault of OURS: over quota. Never the prospect's problem."""

    def complete(self, prompt, temperature=0, client=None, config=None,
                 max_tokens=None):
        if "write cold outreach" in prompt.lower():
            self.prompts.append(prompt)
            raise llm.ModelUnavailable("429 free-models-per-day")
        return super().complete(prompt, temperature, client, config)


class TestBehaviour3AModelErrorHoldsTheRecord(Rework3Test):

    def test_a_writer_failure_holds_the_record_and_stores_no_copy(self):
        generate.run(model=WriterFails(), live=True, ids=["harbourline"])
        rec = self.rec()
        self.assertEqual(rec["state"], "held",
                         "a model failure passed silently with no copy, which "
                         "is fail-open")
        self.assertEqual((rec.get("cadence") or {}).get("rowan-blake", {}), {})
        self.assertTrue(rec.get("hold_reason"),
                        "held with no reason recorded")

    def test_a_fault_of_ours_stops_the_run_rather_than_blaming_the_record(self):
        """A rate limit is not a property of the company.

        `generate_record` raises on `ModelUnavailable` and `NoModelConfigured`
        precisely so eighteen records do not get parked forever for something
        that lasted an hour. The campaign path swallowed BOTH into a per-contact
        hold, because they are `ModelError` subclasses and it caught the parent.
        """
        with self.assertRaises(llm.ModelUnavailable):
            generate.run(model=UnavailableModel(), live=True,
                         ids=["harbourline"])
        self.assertNotEqual(self.rec()["state"], "held",
                            "our own rate limit was written into the record as "
                            "the record's fault")


# ===========================================================================
# BEHAVIOUR 4 - UNAPPROVED MAY BE REGENERATED, APPROVED AND SENT MAY NOT
# ===========================================================================

#: A stored draft that fails lint, so `plan` asks for it again. One substituted
#: character and nothing else, which is how a tightened rule breaks a draft.
STALE_BODY = HARBOURLINE_SEQUENCES["em1"] + " you’re right"


def approved(step, by="operator@example.test"):
    step = dict(step)
    step["approval"] = {"by": by, "at": "2026-09-20T09:00:00+00:00",
                        "fingerprint": approval.fingerprint(step)}
    return step


class TestBehaviour4ApprovedAndSentAreNeverOverwritten(Rework3Test):

    def stale(self, **over):
        step = {"channel": "email", "generated": True,
                "subject": "an older subject", "body": STALE_BODY}
        step.update(over)
        return step

    def run_whole_set(self):
        generate.run(model=CampaignModel((HARBOURLINE_SEQUENCES,
                                          HARBOURLINE_SUBJECTS)),
                     live=True, ids=["harbourline"],
                     allow_whole_set_regeneration=True)

    def test_the_fixture_really_is_stale(self):
        """Otherwise nothing below is a regeneration at all."""
        self.seed("harbourline", "rowan-blake", {"day1": self.stale()})
        rec = self.rec()
        rec["diagnosis"] = {"died_on": None, "died_because": "a real reason",
                            "failure_mode": "no_pass_mark",
                            "last_position": None, "what_changed": None}
        self.assertEqual(
            lint.classify(lint.check(rec, "rowan-blake",
                                     rec["cadence"]["rowan-blake"]["day1"])),
            "failed")

    def test_an_unapproved_draft_is_regenerated(self):
        self.seed("harbourline", "rowan-blake", {"day1": self.stale()})
        self.run_whole_set()
        stored = self.rec()["cadence"]["rowan-blake"]["day1"]
        self.assertEqual(stored["body"], HARBOURLINE_SEQUENCES["em1"],
                         "an UNAPPROVED draft was not regenerated")

    def test_an_approved_draft_is_never_overwritten(self):
        self.seed("harbourline", "rowan-blake",
                  {"day1": approved(self.stale())})
        self.run_whole_set()
        rec = self.rec()
        stored = rec["cadence"]["rowan-blake"]["day1"]
        self.assertEqual(stored["body"], STALE_BODY,
                         "APPROVED copy was overwritten, which invalidates the "
                         "approval hash the operator's yes is bound to")
        self.assertTrue(
            approval.is_approved(rec, "rowan-blake", "day1", stored),
            "the approval no longer applies to the stored copy")
        # And the run still did its job on the step nobody had approved.
        self.assertEqual(rec["cadence"]["rowan-blake"]["day15"]["body"],
                         HARBOURLINE_SEQUENCES["em3"],
                         "protecting the approved step blocked the unapproved "
                         "sibling as well")

    def test_a_sent_draft_is_never_overwritten(self):
        self.seed("harbourline", "rowan-blake",
                  {"day1": self.stale(status=stepstate.PUSHED)})
        self.run_whole_set()
        stored = self.rec()["cadence"]["rowan-blake"]["day1"]
        self.assertEqual(stored["body"], STALE_BODY,
                         "copy that has already been SENT was rewritten")
        self.assertEqual(stored.get("status"), stepstate.PUSHED)

    def test_partial_regeneration_still_refuses_loudly_by_default(self):
        """Without the explicit whole-set flag, the campaign path REFUSES.

        Kept from rework 2 and asserted here through the real entrypoint: the
        writer emits eleven artifacts per call and receives none of
        `prior_contact`, `already_sent`, `siblings`, `sender_identity` or
        `purpose`. Defaulting `sender_identity` would manufacture the standing
        empty-signature launch blocker, so this refuses instead, and the refusal
        NAMES what is missing.
        """
        self.seed("harbourline", "rowan-blake", {"day1": self.stale()})
        with self.assertRaises(generate_campaign.CampaignPipelineError) as ctx:
            generate.run(model=CampaignModel((HARBOURLINE_SEQUENCES,
                                              HARBOURLINE_SUBJECTS)),
                         live=True, ids=["harbourline"])
        for field in generate._CONTEXT_THE_CAMPAIGN_PATH_LACKS:
            self.assertIn(field, str(ctx.exception))
        self.assertEqual(
            self.rec()["cadence"]["rowan-blake"]["day1"]["body"], STALE_BODY,
            "the refusal still let the record be changed")


# ===========================================================================
# THE COPY REACHES A REAL CONSUMER, AND CHANGING IT CHANGES THE OUTPUT
# ===========================================================================

class TestTheCopyReachesTheApprovalQueue(Rework3Test):
    """§4, consumer before producer: wired means changing valid upstream
    information changes downstream production output THROUGH the real
    entrypoint. A module, a passing unit test and `A imports B` are not wiring.

    `approve.pending` is the next stage of the critical path after generation
    (PREVIEW -> APPROVAL HASH) and it walks the record's cadence. If the copy the
    campaign writer produced does not appear there, nothing a person can approve
    was produced - which is what "zero production callers" looked like before
    this task.
    """

    def queue_for(self, subjects):
        from src import approve
        generate.run(model=CampaignModel((HARBOURLINE_SEQUENCES, subjects)),
                     live=True, ids=["harbourline"])
        rows = approve.pending([self.rec()], campaign_rows=[])["waiting"]
        return {r["step"]: r.get("subject") for r in rows
                if r.get("contact") == "rowan-blake"}

    def test_changing_the_writers_subject_changes_the_approval_queue(self):
        first = self.queue_for(HARBOURLINE_SUBJECTS)
        self.assertEqual(first.get("day1"), HARBOURLINE_SUBJECTS["A"],
                         "the generated opener never reached the approval queue")
        self.assertEqual(first.get("day15"), HARBOURLINE_SUBJECTS["B"])

        # Same record, same entrypoint, one upstream value changed.
        changed = dict(HARBOURLINE_SUBJECTS)
        changed["B"] = "one loose end from last autumn"
        # A CLEAN ESTATE, so the second run is a generation and not a
        # regeneration - which the campaign path refuses by design.
        install_fixture("phase5.jsonl", self.queue)
        campaignstrategy.clear_cache()
        second = self.queue_for(changed)
        self.assertEqual(second.get("day15"), "one loose end from last autumn",
                         "changing the writer's subject did not change what a "
                         "person is asked to approve")
        self.assertNotEqual(first.get("day15"), second.get("day15"))


# ===========================================================================
# DRY-RUN MODE IS NOT APPROVABLE AND NOT PROVIDER-READY
# ===========================================================================

class TestADryRunArtifactIsNotApprovable(Rework3Test):
    """The operator's TASK-400 wording: NOT APPROVABLE *and* NOT
    PROVIDER-READY.

    The provider half was already wired at four call sites. The approval half was
    not: a dry-run artifact could be read, approved and hashed, and the only
    thing between that and a prospect was the provider refusal. An approval is a
    person's name against exact words, so taking one over words nobody intended
    to send is the same defect as sending them.
    """

    def a_dry_run(self):
        """A record the DRY RUN produced. The stamp is never set by hand here."""
        generate.run(model=CampaignModel((HARBOURLINE_SEQUENCES,
                                          HARBOURLINE_SUBJECTS)),
                     live=False, ids=["harbourline"])
        # `live=False` persists nothing, by contract, so the stamped artifact is
        # the in-memory one the pipeline produced.
        rec = self.rec()
        rec["diagnosis"] = {"died_on": None, "died_because": "a real reason",
                            "failure_mode": "no_pass_mark",
                            "last_position": None, "what_changed": None}
        plan = generate._generate_via_campaign(
            rec, CampaignModel((HARBOURLINE_SEQUENCES, HARBOURLINE_SUBJECTS)),
            self.config, live=False)
        self.assertEqual(plan.get("generation_stamp"),
                         generate_campaign.DRY_RUN_STAMP)
        self.assertEqual(rec.get("generation_stamp"),
                         generate_campaign.DRY_RUN_STAMP,
                         "the dry run did not stamp the record")
        self.assertTrue(rec["cadence"]["rowan-blake"].get("day1"),
                        "the dry run produced no artifact to refuse")
        return rec

    def test_the_approval_gate_refuses_it_by_name(self):
        from src import approve

        rec = self.a_dry_run()
        step = rec["cadence"]["rowan-blake"]["day1"]
        reason = approve.why_not(rec, "rowan-blake", "day1", step=step,
                                 config=self.config)
        self.assertIsNotNone(reason, "a dry-run artifact was approvable")
        self.assertIn(generate_campaign.DRY_RUN_STAMP, reason)
        with self.assertRaises(approve.NotApprovable):
            approve.approve_step(rec, "rowan-blake", "day1",
                                 by="operator@example.test", config=self.config,
                                 step=step)
        self.assertIsNone(step.get("approval"),
                          "an approval hash was taken over dry-run copy")

    def test_the_same_artifact_is_refused_by_the_provider_boundary(self):
        rec = self.a_dry_run()
        with self.assertRaises(generate_campaign.CampaignPipelineError) as ctx:
            generate_campaign.refuse_dry_run_records([rec])
        self.assertIn(generate_campaign.DRY_RUN_STAMP, str(ctx.exception))

    def test_a_live_artifact_is_approvable(self):
        """Or the gate above would just be a broken approval path."""
        from src import approve

        generate.run(model=CampaignModel((HARBOURLINE_SEQUENCES,
                                          HARBOURLINE_SUBJECTS)),
                     live=True, ids=["harbourline"])
        rec = self.rec()
        self.assertIsNone(rec.get("generation_stamp"))
        step = rec["cadence"]["rowan-blake"]["day1"]
        self.assertIsNone(approve.why_not(rec, "rowan-blake", "day1",
                                          step=step, config=self.config))


class TestTheCommandLineReachesBothDeliberateChoices(Rework3Test):
    """A refusal with no documented way past it gets weakened in a hurry.

    `allow_whole_set_regeneration` and `allow_pending_offers` are the two
    deliberate choices the pipeline exposes, and `main()` passed neither - so the
    escape `_refuse_partial_regeneration` names in its own error message existed
    only for library callers. Asserted on what `main` PASSES rather than on the
    source, because what was missing was an argument that was not passed. This is
    the shape `TheRunnerActuallyBuildsAModel` in tests/test_generate.py already
    established for the same class of defect.
    """

    def seen_kwargs(self, argv):
        seen = {}
        real = generate.run

        def spy(*a, **kw):
            seen.update(kw)
            return {"records": [], "live": kw.get("live"), "model": "spy",
                    "stale_steps": 0, "stale_with_approval": 0,
                    "regen_stale_ladder": False}

        generate.run = spy
        try:
            generate.main(argv)
        finally:
            generate.run = real
        return seen

    def test_the_flags_reach_run(self):
        seen = self.seen_kwargs(["--regenerate-whole-set",
                                 "--allow-pending-offers"])
        self.assertIs(seen.get("allow_whole_set_regeneration"), True)
        self.assertIs(seen.get("allow_pending_offers"), True)

    def test_neither_is_on_by_default(self):
        seen = self.seen_kwargs([])
        self.assertIs(seen.get("allow_whole_set_regeneration"), False)
        self.assertIs(seen.get("allow_pending_offers"), False)


if __name__ == "__main__":
    unittest.main()
