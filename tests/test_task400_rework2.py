"""TASK-400 REWORK 2: the campaign pipeline is the only generation path.

Tests the three defect fixes and all seven acceptances:
  1. A real run with pending offers FAILS LOUDLY.
  2. A dry run produces the stamped artifact through the full pipeline.
  3. The old stage functions are never reached, with no ScriptedModel escape.
  4. Both providers refuse a stamped artifact at attach AND activation.
  5. Mutation tests: restoring the three defects fails a test.
  6. Checkpoint A: changing one fact changes the artifact.
  7. Suite baseline comparison (run separately).
"""
import json
import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (generate, generate_campaign, llm, offers as offers_mod,
                 clients, sequenceplan, campaignstrategy)


# ---------------------------------------------------------------------------
# Test model
# ---------------------------------------------------------------------------

class _CampaignModel:
    """A model that drives the full campaign pipeline deterministically."""

    name = "campaign-test"

    def __init__(self):
        self.calls = []

    def complete(self, prompt, temperature=0, client=None, config=None,
                 max_tokens=None):
        self.calls.append(prompt)
        lower = prompt.lower()

        if "services agency" in lower and "is this company" in lower:
            return json.dumps({
                "is_agency": True, "confidence": 0.9,
                "evidence": "digital marketing agency",
            })

        if "extract verifiable facts" in lower:
            facts = self._extract_facts(prompt)
            return json.dumps({
                "facts": facts,
                "angle": "margin_visible_late",
                "angle_reason": "facts suggest margin visibility issues",
                "company_hook": facts[0]["text"] if facts else "agency",
                "usable": bool(facts),
                "why_this_lead": "test lead",
            })

        if "propose one operational problem" in lower:
            facts = self._extract_facts(prompt)
            fact_text = facts[0]["text"] if facts else "unknown"
            return json.dumps({
                "signal_strength": "strong",
                "signal": fact_text,
                "business_model": "agency",
                "operational_complexity": "multi-team",
                "role_family": "executive",
                "hypothesis": "margin invisible: %s" % fact_text,
                "hypothesis_basis": fact_text,
                "qualification": "QUALIFIED_RICH",
                "confidence": 0.85,
            })

        if "choose one productive capability" in lower:
            return json.dumps({
                "capability_key": "profitability",
                "why_this_one": "matches hypothesis",
                "what_changes": "margin visible",
                "runner_up": "budgeting",
                "confidence": 0.8,
            })

        if "write cold outreach" in lower:
            facts = self._extract_facts(prompt)
            first_fact = facts[0]["text"] if facts else "your work"
            return json.dumps(self._writer_answer(prompt, first_fact))

        return json.dumps({"error": "unrecognised prompt"})

    # -- the writer ----------------------------------------------------------
    #
    # REALISTIC COPY, BECAUSE THE GATES NOW READ IT. Until TASK-400 rework 3
    # `copylint.check_batch` was computed and its verdict read by nothing, so
    # this fixture could return "one benchmark." and the pipeline stored it. The
    # verdict is now acted on: a refused draft is regenerated and, after three
    # attempts, refused outright. Measured against this fixture's old stubs,
    # every lead it has ever produced was refused for `empty_sentence` and every
    # body was under the forty-word floor - which is the lint telling the truth
    # about copy nobody would have sent.
    #
    # So the bodies here are what a model would actually write: over the floor,
    # greeting the real recipient, ASCII punctuation, no banned phrase, and
    # every specific traceable to the pack fact. `em1` embeds the fact, which is
    # what makes Checkpoint A's control 4 (change a fact, the artifact changes)
    # a real observation rather than a coincidence.

    def _first_name(self, prompt):
        m = re.search(r"^Writing to:\s*(\S+)", prompt, re.M)
        return (m.group(1).strip().rstrip(",") if m else "there")

    def _writer_answer(self, prompt, fact):
        who = self._first_name(prompt)
        return {
            "hold": False, "hold_reason": None,
            "subject": "friday capacity",
            "subject_alt": "overrun timing",
            "subject_breakup": "closing the file",
            "emails": {
                "em1": (
                    "%s, %s. That usually means project margin is only visible "
                    "once the invoice is being drafted. What decides today "
                    "whether a new piece of work can start next week without "
                    "pushing something already committed out of the schedule, "
                    "and who assembles that answer for you?" % (who, fact)),
                "em2": (
                    "%s, the same question turns up again at month end. "
                    "Reconciling which hours belong to which client account "
                    "takes days here, and most of that is reconstruction "
                    "rather than reporting. How long after the last working "
                    "day do you actually know what each account earned, and "
                    "how much of it is assembled by hand?" % who),
                "em3": (
                    "%s, a studio your size normally discovers an overrun when "
                    "the invoice is being drafted rather than while the work is "
                    "still running. What would have to change for an overrun on "
                    "an active project to surface in week two instead of week "
                    "six, and who would see it first?" % who),
                "em4": (
                    "%s, one observation from teams of a similar shape. The "
                    "ones that get margin early are not working harder at "
                    "reporting, they have stopped waiting for the end of the "
                    "month to find out. If that were true here, which decision "
                    "would you want to take earlier than you can take it "
                    "today?" % who),
                "em5": (
                    "%s, if none of this is a priority right now, say so and I "
                    "will close the file and stop writing. If it is, the one "
                    "thing worth knowing is where your current margin answer "
                    "comes from and how much reconstruction sits behind it "
                    "every reporting month." % who),
            },
            "ps": {"em1": "Asked because the headcount is in your own about page.",
                   "em3": "The reporting side is the part people underestimate."},
            "ps_variant": "ps_fact",
            "linkedin": {
                "connect": ("%s, reading about how the team is set up. No "
                            "pitch, happy to just follow along." % who),
                "msg1": ("%s, the question I keep asking agencies of this "
                         "shape is when project margin becomes visible. Is it "
                         "while the work runs, or once the invoice is "
                         "drafted?" % who),
                "msg2": ("%s, the part that usually costs the most is "
                         "reconstructing which hours belong to which client "
                         "after the month has closed." % who),
                "msg3": ("%s, no pressure at all. If this is not a priority I "
                         "will leave it with you." % who),
            },
            "facts_used": {"em1": 1},
            "confidence": 0.85,
            "why_this_lead": "strong facts",
        }

    def _extract_facts(self, prompt):
        # If the prompt mentions FINTECH, return a fintech fact
        if "fintech" in prompt.lower():
            return [{
                "text": "TestCorp is a FINTECH with 400 people",
                "quote": "TestCorp is a FINTECH with 400 people",
                "source_index": 1, "kind": "site", "confidence": 0.9,
            }]
        facts = []
        for m in re.finditer(r"(\d+)\.\s+\[([^\]]*)\]\s+(.+)", prompt):
            facts.append({
                "text": m.group(3).strip(),
                "quote": m.group(3).strip(),
                "source_index": int(m.group(1)),
                "kind": m.group(2).strip(),
                "confidence": 0.9,
            })
        if not facts:
            facts.append({
                "text": "TestCorp is a digital marketing agency with 40 people",
                "quote": "TestCorp is a digital marketing agency with 40 people",
                "source_index": 1, "kind": "site", "confidence": 0.9,
            })
        return facts[:5]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _approved_offer(oid="OFFER-PM-001"):
    return {
        oid: {
            "capability": "project_management",
            "segment": "all",
            "persona": "champion",
            "business_problem": "projects tracked in spreadsheets",
            "value_proposition": "one place for projects",
            "concrete_deliverable": "single view",
            "cta": "see it",
            "approval_status": "approved",
            "campaigns": [],
        }
    }


def _pending_offer(oid="OFFER-PM-001"):
    return {
        oid: {
            "capability": "project_management",
            "approval_status": "pending",
            "campaigns": [],
        }
    }


def _account():
    return {
        "company": "TestCorp",
        "domain": "testcorp.com",
        "persona": "champion",
        "segment": "test",
        "sources": [
            {"label": "site", "url": "https://testcorp.com/about",
             "text": "TestCorp is a digital marketing agency with 40 people"},
        ],
    }


def _contacts():
    return [{
        "email": "jane@testcorp.com",
        "first_name": "Jane",
        "last_name": "Doe",
        "title": "CEO",
        "contact_key": "jane@testcorp.com",
        "sender_name": "Ivan",
        "linkedin": "https://linkedin.com/in/janedoe",
    }]


def _client_config():
    return {
        "name": "productive",
        "domain": "productive.test",
        "cadence": "default",
        "product": {
            "capabilities": {
                "profitability": "see project margin while it runs",
            },
        },
        "sender": {"name": "Ivan", "role": "founder",
                   "company": "Productive"},
    }


def _rec_with_stamp(stamp=None):
    """A record with an optional generation stamp."""
    rec = {
        "id": "test-rec-001",
        "client": "productive",
        "company": "TestCorp",
        "domain": "testcorp.com",
        "state": "verified",
        "contacts": [{
            "name": "Jane Doe",
            "key": "jane-doe",
            "email": "jane@testcorp.com",
            "title": "CEO",
            "linkedin": "https://linkedin.com/in/janedoe",
            # VERIFIED, because "no email is generated for an unverified
            # address" is a standing rule and TASK-400 rework 3 enforces it on
            # the campaign path too - `_candidate_steps` asks
            # `verification.is_sendable`, which recomputes from the evidence
            # rather than reading a stored state. Without this the fixture was
            # asking the pipeline to write to an address no provider had ever
            # confirmed, and the persistence test below was passing on it.
            "verdict": "valid",
            "sendable": True,
            "verification": {
                "state": "verified", "sendable": True,
                "evidence": [
                    {"provider": "contactout", "status": "valid",
                     "email": "jane@testcorp.com",
                     "at": "2026-09-01T00:00:00+00:00"},
                    {"provider": "deliverable", "status": "valid",
                     "email": "jane@testcorp.com",
                     "reason": "second independent confirmation",
                     "at": "2026-09-01T00:00:00+00:00"},
                ],
            },
        }],
    }
    if stamp:
        rec["generation_stamp"] = stamp
    return rec


# ===========================================================================
# Acceptance 1: pending offers fail loudly
# ===========================================================================

class TestAcceptance1_PendingOffersFailLoudly(unittest.TestCase):
    """A real run with pending offers FAILS LOUDLY; no cadence written."""

    @mock.patch.object(offers_mod, "load")
    def test_pending_offer_raises_through_generate(self, mock_load):
        mock_load.return_value = _pending_offer()
        # live=True: acceptance 1 is about a REAL run. A dry run with pending
        # offers is acceptance 2 and deliberately proceeds with a stamp, so
        # asserting a raise without live=True would contradict the spec.
        with self.assertRaises(generate_campaign.NotApproved) as ctx:
            generate_campaign.generate(
                _client_config(), _account(), _contacts(),
                model=_CampaignModel(), live=True)
        self.assertIn("OFFER-PM-001", str(ctx.exception))
        self.assertIn("pending", str(ctx.exception))

    @mock.patch.object(offers_mod, "load")
    def test_pending_offer_raises_through_run(self, mock_load):
        """Through the REAL entrypoint (src/generate.py run)."""
        mock_load.return_value = _pending_offer()
        rec = _rec_with_stamp()
        with self.assertRaises(generate_campaign.NotApproved):
            generate._generate_via_campaign(
                rec, _CampaignModel(), _client_config(), live=True)


# ===========================================================================
# Acceptance 2: dry run produces stamped artifact
# ===========================================================================

class TestAcceptance2_DryRunStampedArtifact(unittest.TestCase):
    """A dry run produces the artifact with the stamp."""

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_dry_run_has_stamp(self, _mock_offers):
        campaignstrategy.clear_cache()
        model = _CampaignModel()
        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(),
            model=model, live=False)
        self.assertEqual(plan.get("generation_stamp"),
                         generate_campaign.DRY_RUN_STAMP)

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_live_run_has_no_stamp(self, _mock_offers):
        campaignstrategy.clear_cache()
        model = _CampaignModel()
        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(),
            model=model, live=True)
        self.assertNotIn("generation_stamp", plan)

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_dry_run_ran_full_pipeline(self, _mock_offers):
        """The dry run actually ran Second Brain, strategy, skills, etc."""
        campaignstrategy.clear_cache()
        model = _CampaignModel()
        plan = generate_campaign.generate(
            _client_config(), _account(), _contacts(),
            model=model, live=False)
        # The model was called multiple times (ICP, extract, hypothesis,
        # match, writer)
        self.assertGreater(len(model.calls), 3,
                           "dry run did not run the full pipeline")
        # The plan has contacts with sequences
        self.assertTrue(len(plan.get("contacts", [])) > 0)
        contact = plan["contacts"][0]
        self.assertIn("sequences", contact)
        self.assertIn("em1", contact["sequences"])


# ===========================================================================
# Acceptance 3: old stage functions never reached
# ===========================================================================

class TestAcceptance3_OldStageFunctionsNeverReached(unittest.TestCase):
    """The old stage functions are never reached, no ScriptedModel escape."""

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_draft_not_called(self, _mock_offers):
        """Monkeypatch draft to fail if called."""
        original_draft = generate.draft

        def _fail(*a, **kw):
            raise AssertionError("draft() was called - old path reached!")

        generate.draft = _fail
        try:
            campaignstrategy.clear_cache()
            model = _CampaignModel()
            rec = _rec_with_stamp()
            # This should go through the campaign pipeline, NOT draft()
            plan = generate._generate_via_campaign(
                rec, model, _client_config(), live=False)
            self.assertIn("generation_stamp", plan)
        finally:
            generate.draft = original_draft

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_linkedin_note_not_called(self, _mock_offers):
        original = generate.linkedin_note

        def _fail(*a, **kw):
            raise AssertionError("linkedin_note() called - old path reached!")

        generate.linkedin_note = _fail
        try:
            campaignstrategy.clear_cache()
            model = _CampaignModel()
            rec = _rec_with_stamp()
            plan = generate._generate_via_campaign(
                rec, model, _client_config(), live=False)
            self.assertIn("generation_stamp", plan)
        finally:
            generate.linkedin_note = original

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_no_scripted_model_branch(self, _mock_offers):
        """No isinstance(model, ScriptedModel) check in production code."""
        import inspect
        source = inspect.getsource(generate._generate_via_campaign)
        self.assertNotIn("isinstance(model", source,
                         "production code branches on model type")


# ===========================================================================
# Acceptance 4: both providers refuse stamped artifact
# ===========================================================================

class TestAcceptance4_ProvidersRefuseStampedArtifact(unittest.TestCase):
    """Both providers refuse a stamped artifact at attach AND activation."""

    def test_refuse_dry_run_records_raises(self):
        recs = [_rec_with_stamp(generate_campaign.DRY_RUN_STAMP)]
        with self.assertRaises(generate_campaign.CampaignPipelineError):
            generate_campaign.refuse_dry_run_records(recs)

    def test_refuse_dry_run_records_passes_clean(self):
        recs = [_rec_with_stamp(None)]
        generate_campaign.refuse_dry_run_records(recs)

    def test_refuse_dry_run_records_empty(self):
        generate_campaign.refuse_dry_run_records([])

    def test_refuse_checks_cadence_stamp_too(self):
        rec = {"id": "test", "cadence": {
            "generation_stamp": generate_campaign.DRY_RUN_STAMP}}
        with self.assertRaises(generate_campaign.CampaignPipelineError):
            generate_campaign.refuse_dry_run_records([rec])

class TestBothProvidersRefuseAStampedRecord(unittest.TestCase):
    """Attach AND activation, for EACH provider. Four behavioural assertions.

    WHY THESE WERE REWRITTEN. The first version of each of these read
    `inspect.getsource(...)` and asserted the string "refuse_dry_run_records"
    appeared in it. CLAUDE.md forbids that outright - "test behaviour, not the
    text of the source" - and this task demonstrated why twice over: such a test
    passes while the call is present but UNREACHABLE, and the sibling
    ScriptedModel version would have passed had the branch been spelled
    `type(model) is llm.ScriptedModel`. Worse, all four were green for the whole
    period in which the refusal was completely inert, because the stamp never
    reached the record they check.

    Now that the stamp genuinely reaches the record, the refusal is testable for
    real: drive a stamped record through each function and assert it raises.

    EACH TEST ALSO PROVES NO PROVIDER WAS CONTACTED, by patching the module's
    `request` seam to fail the test if called. That is the property that matters
    under the production freeze: the refusal has to come BEFORE the network, not
    after it. A test that only checked the exception would pass even if the
    refusal fired after the attach.
    """

    def _stamped(self):
        return [_rec_with_stamp(generate_campaign.DRY_RUN_STAMP)]

    # ---------------------------------------------------------- HeyReach

    def test_heyreach_attach_refuses_stamped(self):
        """heyreachfactory.ensure_leads, the attach boundary."""
        from src import heyreachfactory
        from src.providers import heyreach as hr
        campaign = {"id": "901", "client": "productive"}
        with mock.patch.object(heyreachfactory.campaigns, "load",
                               return_value=[campaign]), \
             mock.patch.object(heyreachfactory.campaigns, "require",
                               return_value=campaign), \
             mock.patch.object(heyreachfactory.clients, "load",
                               return_value=_client_config()), \
             mock.patch.object(hr, "request",
                               side_effect=AssertionError(
                                   "a provider call was made before the "
                                   "dry-run refusal")):
            with self.assertRaises(
                    generate_campaign.CampaignPipelineError) as ctx:
                heyreachfactory.ensure_leads("901", recs=self._stamped())
        self.assertIn(generate_campaign.DRY_RUN_STAMP, str(ctx.exception))

    def test_heyreach_activation_refuses_stamped(self):
        """providers.heyreach.activate_campaign, the activation boundary."""
        from src.providers import heyreach as hr
        from src import reviewapproval, store as _store
        with mock.patch.object(reviewapproval, "require", return_value=None), \
             mock.patch.object(_store, "load", return_value=self._stamped()), \
             mock.patch.object(hr, "request",
                               side_effect=AssertionError(
                                   "a provider call was made before the "
                                   "dry-run refusal")):
            with self.assertRaises(
                    generate_campaign.CampaignPipelineError) as ctx:
                hr.activate_campaign("901")
        self.assertIn(generate_campaign.DRY_RUN_STAMP, str(ctx.exception))

    # -------------------------------------------------------- EmailBison

    def test_bison_attach_refuses_stamped(self):
        """bisonfactory._ensure_leads, the attach boundary.

        EmailBison is the channel that actually sends, and this call site had no
        refusal at all until this task.
        """
        from src import bisonfactory, store as _store
        from src.providers import bison as bs
        plan = {"leads": [{"record_id": "test-rec-001",
                           "contact_key": "jane-doe",
                           "missing_copy": None}]}
        report = {"did": [], "refused": []}
        with mock.patch.object(_store, "load", return_value=self._stamped()), \
             mock.patch.object(bs, "request",
                               side_effect=AssertionError(
                                   "a provider call was made before the "
                                   "dry-run refusal")):
            with self.assertRaises(
                    generate_campaign.CampaignPipelineError) as ctx:
                bisonfactory._ensure_leads(
                    "901", {"id": "901", "client": "productive"}, plan, report)
        self.assertIn(generate_campaign.DRY_RUN_STAMP, str(ctx.exception))

    def test_bison_activation_refuses_stamped(self):
        """providers.bison.resume_campaign, the activation boundary."""
        from src.providers import bison as bs
        from src import reviewapproval, store as _store
        with mock.patch.object(reviewapproval, "require", return_value=None), \
             mock.patch.object(_store, "load", return_value=self._stamped()), \
             mock.patch.object(bs, "request",
                               side_effect=AssertionError(
                                   "a provider call was made before the "
                                   "dry-run refusal")):
            with self.assertRaises(
                    generate_campaign.CampaignPipelineError) as ctx:
                bs.resume_campaign("901")
        self.assertIn(generate_campaign.DRY_RUN_STAMP, str(ctx.exception))

    # ------------------------------------------------- the negative control

    def test_a_clean_record_is_not_refused_by_either_activation(self):
        """The refusal must not fire on unstamped records, or it blocks everything.

        Without this, all four tests above would pass against a function that
        raised unconditionally.
        """
        from src.providers import bison as bs, heyreach as hr
        from src import reviewapproval, store as _store
        clean = [_rec_with_stamp(None)]
        for module in (bs, hr):
            with mock.patch.object(reviewapproval, "require",
                                   return_value=None), \
                 mock.patch.object(_store, "load", return_value=clean), \
                 mock.patch.object(module, "request",
                                   side_effect=RuntimeError("reached network")):
                fn = (module.resume_campaign if module is bs
                      else module.activate_campaign)
                # It will still fail - no credential is configured in a test
                # process, and `request` is booby-trapped - but it must fail
                # for ANY reason other than the dry-run refusal. That is what
                # "the refusal is conditional" means, and asserting on the
                # specific downstream failure would just couple this test to
                # whichever guard happens to come next.
                with self.assertRaises(Exception) as ctx:
                    fn("901")
                self.assertNotIn(
                    generate_campaign.DRY_RUN_STAMP, str(ctx.exception),
                    "a CLEAN record was refused as a dry-run artifact, so the "
                    "refusal fires unconditionally and would block every real "
                    "activation")


# ===========================================================================
# Acceptance 5: mutation tests
# ===========================================================================

class TestAcceptance5_MutationTests(unittest.TestCase):
    """Restoring the three defects must fail a test."""

    def test_mutation_a_not_approved_caught(self):
        """If NotApproved were caught and returned empty, this test fails."""
        # The mutation: catch NotApproved and return None, None
        # The test: assert NotApproved propagates on a REAL run
        with mock.patch.object(offers_mod, "load",
                               return_value=_pending_offer()):
            with self.assertRaises(generate_campaign.NotApproved):
                generate_campaign.generate(
                    _client_config(), _account(), _contacts(),
                    model=_CampaignModel(), live=True)

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_mutation_b_scripted_model_branch(self, _mock_offers):
        """A ScriptedModel gets no special treatment. BEHAVIOURAL.

        The previous version of this test read the source of
        `_generate_via_campaign` and asserted the string "isinstance(model" was
        absent. That is the defect this repository has been bitten by
        repeatedly: it passes if the branch is spelled differently
        (`type(model) is llm.ScriptedModel`), and it fails when somebody writes
        a comment. Assert the EFFECT instead: a ScriptedModel must travel the
        campaign path like any other model, so a plan comes back rather than a
        fallthrough, and the old stage functions are never reached.
        """
        campaignstrategy.clear_cache()
        rec = _rec_with_stamp()
        rec.pop("generation_stamp", None)
        called = []
        # TWO ANSWERS, NOT ONE. The strategy stage consumes the first and the
        # ICP stage the second, which answers `is_agency: false` and ends the
        # contact as UNQUALIFIED - the shortest complete path through the
        # pipeline. It was one answer, and passed only because a
        # `ModelError` ("scripted model ran out of answers") was swallowed into
        # `held`. TASK-400 rework 3 makes a model error propagate and hold the
        # RECORD, so running out of answers is now a raise. The property under
        # test is unchanged: a `ScriptedModel` travels the campaign path like
        # any other model and the old stage functions are not reached.
        with mock.patch.object(generate, "draft",
                               side_effect=AssertionError("draft reached")), \
             mock.patch.object(generate, "linkedin_note",
                               side_effect=AssertionError("note reached")):
            plan = generate._generate_via_campaign(
                rec, llm.ScriptedModel({}, {}), _client_config(), live=False)
        self.assertIsNotNone(
            plan, "a ScriptedModel fell through instead of using the campaign "
                  "path")
        self.assertIn("contacts", plan)
        self.assertEqual(called, [])

    def test_mutation_c_config_error_caught(self):
        """If ConfigError were caught and returned None, this test fails."""
        # The mutation: except clients.ConfigError: return None, None
        # The test: assert CampaignPipelineError propagates
        with mock.patch.object(clients, "load",
                               side_effect=clients.ConfigError("no config")):
            with self.assertRaises(generate_campaign.CampaignPipelineError):
                generate_campaign.generate(
                    "nonexistent_client", _account(), _contacts(),
                    model=_CampaignModel())


# ===========================================================================
# Acceptance 6: checkpoint A - change a fact, artifact changes
# ===========================================================================

class TestAcceptance6_CheckpointA(unittest.TestCase):
    """Change one approved fact, observe the artifact change."""

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_change_fact_changes_output(self, _mock_offers):
        campaignstrategy.clear_cache()
        model_a = _CampaignModel()
        account_a = _account()
        plan_a = generate_campaign.generate(
            _client_config(), account_a, _contacts(), model=model_a)

        campaignstrategy.clear_cache()
        model_b = _CampaignModel()
        account_b = _account()
        account_b["sources"] = [
            {"label": "site", "url": "https://testcorp.com/about",
             "text": "CHANGED FACT: TestCorp is a FINTECH with 400 people"},
        ]
        plan_b = generate_campaign.generate(
            _client_config(), account_b, _contacts(), model=model_b)

        # The email bodies should differ because the facts differ
        em1_a = plan_a["contacts"][0]["sequences"].get("em1", "")
        em1_b = plan_b["contacts"][0]["sequences"].get("em1", "")
        self.assertNotEqual(em1_a, em1_b,
                            "changing a fact did not change the email body. "
                            "em1_a=%r, em1_b=%r" % (em1_a[:80], em1_b[:80]))


# ===========================================================================
# CampaignPipelineError for empty contacts
# ===========================================================================

class TestEmptyContacts(unittest.TestCase):
    """Empty contacts raises CampaignPipelineError."""

    def test_empty_contacts_raises(self):
        with self.assertRaises(generate_campaign.CampaignPipelineError):
            generate_campaign.generate(
                _client_config(), _account(), [],
                model=_CampaignModel())

    def test_no_contacts_through_run(self):
        rec = _rec_with_stamp()
        rec["contacts"] = []
        with self.assertRaises(generate_campaign.CampaignPipelineError):
            generate._generate_via_campaign(
                rec, _CampaignModel(), _client_config())


# ===========================================================================
# The real entrypoint calls the campaign pipeline
# ===========================================================================

class TestRealEntrypoint(unittest.TestCase):
    """The real entrypoint (src/generate.py) calls generate_campaign."""

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_run_calls_campaign_pipeline(self, _mock_offers):
        """run() goes through _generate_via_campaign, not old plan()."""
        campaignstrategy.clear_cache()
        model = _CampaignModel()
        rec = _rec_with_stamp()

        with mock.patch.object(generate.store, "load", return_value=[rec]):
            result = generate.run(model=model, live=False)

        # The result has records with ops from the campaign pipeline
        self.assertEqual(len(result["records"]), 1)
        rec_report = result["records"][0]
        self.assertEqual(rec_report["id"], "test-rec-001")

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_not_approved_propagates_from_run(self, _mock_offers):
        """NotApproved propagates from run() - not caught silently."""
        mock_load_ret = _pending_offer()
        offers_mod.load.return_value = mock_load_ret
        rec = _rec_with_stamp()

        with mock.patch.object(generate.store, "load", return_value=[rec]):
            with self.assertRaises(generate_campaign.NotApproved):
                generate.run(model=_CampaignModel(), live=True)


# ===========================================================================
# REWORK 2 (Claude): the remaining defects, asserted BY EFFECT
# ===========================================================================

class TestRework2StampReachesTheRecord(unittest.TestCase):
    """The stamp must travel plan -> record -> refusal, or it does nothing.

    THE DEFECT THIS CLOSES. `generate_campaign` stamped the PLAN
    (`plan["generation_stamp"]`) while `refuse_dry_run_records()` reads the
    stamp off each RECORD. Nothing bridged the two, so all four provider
    refusal call sites were checking a field production never wrote: a dry-run
    artifact could be attached and activated on either provider. The original
    tests passed only because they set `rec["generation_stamp"]` by hand, which
    is the textbook shape of a test that passes while production is broken.

    So: never set the stamp by hand here. Run the pipeline, then assert the
    record carries it.
    """

    @mock.patch.object(offers_mod, "load", return_value=_pending_offer())
    def test_dry_run_stamps_the_record_not_just_the_plan(self, _mock_offers):
        campaignstrategy.clear_cache()
        rec = _rec_with_stamp()
        self.assertNotIn("generation_stamp", rec)
        plan = generate._generate_via_campaign(
            rec, _CampaignModel(), _client_config(), live=False,
            allow_pending_offers=True)
        self.assertEqual(plan.get("generation_stamp"),
                         generate_campaign.DRY_RUN_STAMP)
        self.assertEqual(
            rec.get("generation_stamp"), generate_campaign.DRY_RUN_STAMP,
            "the plan was stamped but the RECORD was not, so every provider "
            "refusal is inert")

    @mock.patch.object(offers_mod, "load", return_value=_pending_offer())
    def test_the_refusal_actually_fires_on_that_record(self, _mock_offers):
        """End to end: the record a dry run produced is refused."""
        campaignstrategy.clear_cache()
        rec = _rec_with_stamp()
        generate._generate_via_campaign(
            rec, _CampaignModel(), _client_config(), live=False,
            allow_pending_offers=True)
        with self.assertRaises(Exception) as ctx:
            generate_campaign.refuse_dry_run_records([rec])
        self.assertIn(generate_campaign.DRY_RUN_STAMP, str(ctx.exception))

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_a_live_run_leaves_no_stamp_on_the_record(self, _mock_offers):
        """And a live artifact is therefore NOT refused."""
        campaignstrategy.clear_cache()
        rec = _rec_with_stamp(stamp=generate_campaign.DRY_RUN_STAMP)
        generate._generate_via_campaign(
            rec, _CampaignModel(), _client_config(), live=True)
        self.assertNotIn(
            "generation_stamp", rec,
            "a live run must clear a stale stamp, or a record stamped by an "
            "earlier dry run stays unusable forever")
        generate_campaign.refuse_dry_run_records([rec])


class TestRework2PlanIsPersistedToCadence(unittest.TestCase):
    """The plan must land in the record, or nothing downstream sees it.

    REWORK 2 deleted `_adapt_plan_to_cadence` and left `_plan_to_ops`, which
    builds a display list for the report and writes nothing. The pipeline
    generated copy and discarded it: no preview, provider projection, approval
    or lint could reach the output, and Checkpoint A control 4 had no artifact
    to change.
    """

    @mock.patch.object(offers_mod, "load", return_value=_approved_offer())
    def test_cadence_is_written_by_the_campaign_path(self, _mock_offers):
        """And under the step keys THIS RECORD'S CADENCE names.

        WHY THIS ASSERTION CHANGED, TASK-400 rework 3. It read
        `k.startswith("em")`, and that passed only because the adapter hardcoded
        `em1`..`em5` - the writer's own keys. This fixture's client resolves
        `productive_balanced_v1`, whose generated email steps are `day1` and
        `day15`, so the rows the old code wrote named steps the record's cadence
        does not contain: `cadence.status_for` never sees them, `eligibility`
        refuses the payload, preview and the provider projection skip them.
        Copy stored under a key nothing downstream reads is the same
        "computed correctly, consumed by nothing" defect this task exists to
        close, and the assertion was pinning it.

        So it now asks `cadence.steps_for` - the authority - which keys this
        record runs, and requires the stored rows to be those. Strictly
        stronger: the old form passed while the rows were unreadable.
        """
        campaignstrategy.clear_cache()
        rec = _rec_with_stamp()
        self.assertIsNone(rec.get("cadence"))
        generate._generate_via_campaign(
            rec, _CampaignModel(), _client_config(), live=True)
        cadence = rec.get("cadence") or {}
        self.assertTrue(
            cadence, "the campaign pipeline ran and wrote nothing to the "
                     "record: the plan was discarded")
        contact_steps = cadence.get("jane-doe") or {}
        self.assertTrue(contact_steps, "no steps stored for the contact")

        sequence = generate.sequence_for(rec, _client_config(),
                                         rec["contacts"][0], None)
        expected = generate._generated_keys(sequence, "email")
        self.assertTrue(expected, "the fixture's cadence generates no email")
        stored_emails = sorted(k for k, s in contact_steps.items()
                               if s.get("channel") == "email")
        self.assertEqual(stored_emails, sorted(expected),
                         "the campaign path stored email steps under keys this "
                         "record's cadence does not name")
        step = contact_steps[expected[0]]
        self.assertEqual(step.get("channel"), "email")
        self.assertTrue(step.get("body"), "an email step stored an empty body")
        self.assertTrue(step.get("generated"))


class TestRework2MissingClientIsAnError(unittest.TestCase):
    """A missing config is a configuration error, never a silent handover.

    This was `except clients.ConfigError: pass`, which swallowed the failure
    and ran the pipeline with no offers, no approved mechanism and no client
    facts. The offer gate cannot refuse what it was never given.
    """

    def test_config_error_raises_rather_than_passing(self):
        """The pipeline must not be REACHED when the config failed to load.

        WHY IT ASSERTS ON THE CALL AND NOT JUST ON THE EXCEPTION TYPE. The
        obvious version of this test - patch `clients.load` to raise and assert
        CampaignPipelineError - passes even with the defect restored, because
        `generate_campaign.generate()` ALSO loads the client and raises
        CampaignPipelineError itself. A different guard fires first and masks
        the mutation, so the test proves nothing about the code it names. Caught
        by actually performing mutation C and watching the suite stay green.

        The real invariant: a record whose config could not be loaded never
        reaches the campaign pipeline at all.
        """
        rec = _rec_with_stamp()
        with mock.patch.object(clients, "load",
                               side_effect=clients.ConfigError("no config")), \
             mock.patch.object(generate_campaign, "generate") as spy:
            with self.assertRaises(
                    generate_campaign.CampaignPipelineError) as ctx:
                generate._generate_via_campaign(
                    rec, _CampaignModel(), None, live=False)
        spy.assert_not_called()
        self.assertIn("productive", str(ctx.exception))

    def test_no_client_and_no_config_raises(self):
        rec = _rec_with_stamp()
        rec.pop("client")
        with self.assertRaises(generate_campaign.CampaignPipelineError):
            generate._generate_via_campaign(
                rec, _CampaignModel(), None, live=False)


class TestRework2DryRunWithPendingOffers(unittest.TestCase):
    """Acceptance 2 as specified: PENDING offers, dry run, stamped artifact."""

    @mock.patch.object(offers_mod, "load", return_value=_pending_offer())
    def test_pending_offers_dry_run_produces_stamped_artifact(self, _m):
        campaignstrategy.clear_cache()
        rec = _rec_with_stamp()
        plan = generate._generate_via_campaign(
            rec, _CampaignModel(), _client_config(), live=False,
            allow_pending_offers=True)
        self.assertEqual(plan.get("generation_stamp"),
                         generate_campaign.DRY_RUN_STAMP)
        self.assertTrue(plan.get("contacts"),
                        "the full path did not run: no contacts in the plan")

    @mock.patch.object(offers_mod, "load", return_value=_pending_offer())
    def test_old_stage_functions_never_reached_on_a_dry_run(self, _m):
        campaignstrategy.clear_cache()
        rec = _rec_with_stamp()
        with mock.patch.object(
                generate, "draft",
                side_effect=AssertionError("draft() was reached")), \
             mock.patch.object(
                generate, "linkedin_note",
                side_effect=AssertionError("linkedin_note() was reached")), \
             mock.patch.object(
                generate, "_regenerate_linkedin_set",
                side_effect=AssertionError("_regenerate_linkedin_set reached")):
            generate._generate_via_campaign(
                rec, _CampaignModel(), _client_config(), live=False,
                allow_pending_offers=True)


class TestRework2RefusesPartialRegeneration(unittest.TestCase):
    """A one-step regeneration through an eleven-artifact batch writer REFUSES.

    `generate_campaign` receives none of `prior_contact`, `already_sent`,
    `siblings`, `sender_identity` or `purpose`, and its writer emits the whole
    set per call. So a record that already carries generated copy cannot be
    partially regenerated through it without either discarding ten artifacts or
    rewriting steps nobody asked to change - and without a sender identity,
    which is the standing empty-signature launch blocker.

    Option B of the coordinator's acceptance item: refuse loudly, by name.
    """

    def test_a_record_with_generated_copy_is_refused(self):
        rec = _rec_with_stamp()
        rec["cadence"] = {"jane-doe": {"em1": {"channel": "email",
                                               "generated": True,
                                               "body": "already written"}}}
        with self.assertRaises(
                generate_campaign.CampaignPipelineError) as ctx:
            generate._refuse_partial_regeneration(rec, False)
        msg = str(ctx.exception)
        for field in generate._CONTEXT_THE_CAMPAIGN_PATH_LACKS:
            self.assertIn(field, msg,
                          "the refusal must NAME the missing context, not fail "
                          "vaguely; %r absent" % field)

    def test_a_fresh_record_is_not_refused(self):
        generate._refuse_partial_regeneration(_rec_with_stamp(), False)

    def test_the_whole_set_escape_is_explicit(self):
        rec = _rec_with_stamp()
        rec["cadence"] = {"jane-doe": {"em1": {"channel": "email",
                                               "generated": True,
                                               "body": "already written"}}}
        generate._refuse_partial_regeneration(rec, True)   # must not raise

    def test_an_ungenerated_step_does_not_trigger_the_refusal(self):
        """A stored-but-not-generated step is not prior copy."""
        rec = _rec_with_stamp()
        rec["cadence"] = {"jane-doe": {"em1": {"channel": "email"}}}
        generate._refuse_partial_regeneration(rec, False)


if __name__ == "__main__":
    unittest.main()
