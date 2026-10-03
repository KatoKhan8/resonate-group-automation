"""`rec["research"]` IS A LIST OF EVIDENCE ENTRIES, and the generation path
reads that one.

THE DEFECT, measured on `8cdc9234` through `generate._generate_via_campaign`
with the real `productive` config and the real offer library, one shape per run:

    research = LIST (canonical)  AttributeError: 'list' object has no attribute
                                 'get' - raised at generate.py:2472, the bridge
    research = DICT {"sources"}  got past that line, then AttributeError: 'str'
                                 object has no attribute 'get' inside
                                 `claims.support_text`, reached through
                                 `_campaign_validator`, INSIDE
                                 `_process_contact`'s broad `except Exception`
                                 -> hold_kind="error", stored_pairs=0, for every
                                 contact, from a run that reported no crash
    research = [] or absent      copy produced, and the account research pack
                                 never reached the pipeline at all

So there was no shape for which the new path produced copy WITH the account's
research in it, and the middle row is why this mattered more than an ordinary
type error: the run looked complete and stored nothing.

WHICH SHAPE IS CANONICAL, counted rather than preferred. `SCHEMA.md` records a
list. `research.py` (the production crawl, three call sites), `companies`,
`demo`, `demo_outreach`, `benchmark`, `synthetic` and `web.demodata` write one.
`claims`, `dossier`, `eligibility`, `icp`, `packfacts`, `preview`, `qa`,
`qualify`, `quality`, `report`, `segments`, `personalization`, `llm`, `funnel`,
`simulator`, `web.api` and `generate`'s own `_evidence_fingerprint` and
`research_block` read one. And the production store agrees: of 1,582 records,
394 carry a populated list, 23 an empty list, 1,165 none, and NOT ONE a dict.
One reader disagreed, so the reader moved. Nothing here handles two shapes.

THE SECOND DEFECT, and it is the reason the first one survived a whole run: a
programming error inside `_process_contact` was converted into
`hold_kind="error"` for the contact. It now propagates as
`CampaignPipelineError`, the way `llm.ModelError` already did - so an operator
reading a run report can tell "this contact was held for a real reason" from
"the code broke", which is what `test_a_shape_error_is_not_a_hold` asserts
against controls in both directions.
"""
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (claims, clients, dossier, eligibility, evidence,
                 generate, generate_campaign, research)
from tests.base import (CampaignModel, QueueTest, RESEARCH_FACT,
                        canonical_research)

RECORD_ID = "research-shape-001"


def _client_config():
    return clients.load("productive")


def _contact_row():
    return {
        "name": "Jane Doe", "key": "jane-doe",
        "email": "jane@testcorp.test", "title": "CEO",
        "linkedin": "https://linkedin.com/in/janedoe",
        "verdict": "valid", "sendable": True,
        "verification": {
            "state": "verified", "sendable": True,
            "evidence": [
                {"provider": "contactout", "status": "valid",
                 "email": "jane@testcorp.test",
                 "at": "2026-09-01T00:00:00+00:00"},
                {"provider": "deliverable", "status": "valid",
                 "email": "jane@testcorp.test",
                 "reason": "second independent confirmation",
                 "at": "2026-09-01T00:00:00+00:00"},
            ],
        },
    }


def _rec(research_value="canonical"):
    """A record the production caller accepts, carrying one research shape."""
    rec = {
        "id": RECORD_ID,
        "client": "productive",
        "company": "TestCorp",
        "domain": "testcorp.test",
        "state": "verified",
        "persona": "champion",
        "contacts": [_contact_row()],
    }
    if research_value == "canonical":
        rec["research"] = canonical_research(RECORD_ID)
    elif research_value != "absent":
        rec["research"] = research_value
    return rec


def _contacts():
    return [{"email": "jane@testcorp.test", "first_name": "Jane",
             "last_name": "Doe", "title": "CEO", "contact_key": "jane-doe",
             "linkedin": "https://linkedin.com/in/janedoe"}]


def _account_from(rec):
    """The account dict the bridge builds, so the literal acceptance call
    (`generate_campaign.generate("productive", account, [contact])`) runs
    against the SAME projection production uses rather than a hand-made one."""
    return {
        "company": rec.get("company", ""),
        "domain": rec.get("domain", ""),
        "persona": rec.get("persona", "champion"),
        "segment": rec.get("segment", "productive"),
        "sources": generate._account_sources(rec),
    }


class HoldingModel(CampaignModel):
    """The writer HOLDS. A legitimate hold, and nothing is wrong with the code."""

    def complete(self, prompt, temperature=0, client=None, config=None,
                 max_tokens=None):
        if "write cold outreach" in prompt.lower():
            self.writer_prompts.append(prompt)
            return json.dumps({"hold": True,
                               "hold_reason": "nothing specific to say"})
        return super().complete(prompt, temperature=temperature, client=client,
                                config=config)


class UnparseableModel(CampaignModel):
    """The model answers with something that is not JSON at all.

    `_parse_json` raises `ValueError`, which is a model failure ON a record and
    still HOLDS the contact - operator decision 3. It is the control that says
    the narrowed `except` narrowed and did not widen.
    """

    def complete(self, prompt, temperature=0, client=None, config=None,
                 max_tokens=None):
        if "services agency" in prompt.lower():
            return "I am afraid I cannot answer that."
        return super().complete(prompt, temperature=temperature, client=client,
                                config=config)


class ResearchShapeTest(QueueTest):

    def setUp(self):
        super().setUp()
        from src import campaignstrategy
        campaignstrategy.clear_cache()
        generate.clear_company_cache()
        self.addCleanup(campaignstrategy.clear_cache)
        self.addCleanup(generate.clear_company_cache)


# ---------------------------------------------------------------------------
# ACCEPTANCE 1: the canonical LIST produces copy, and the pack ARRIVES
# ---------------------------------------------------------------------------

class TheCanonicalListProducesCopy(ResearchShapeTest):

    def test_the_canonical_list_shape_produces_copy(self):
        """Acceptance 1, through the production caller.

        Before this fix the same call raised `AttributeError: 'list' object has
        no attribute 'get'`. `stored_pairs` is asserted non-empty because a run
        that returns a plan and stores nothing is the outcome this whole task is
        about - and `stored_pairs` is what `generate_record` reads to decide
        whether a step was written.
        """
        rec = _rec()
        model = CampaignModel()
        plan = generate._generate_via_campaign(
            rec, model, _client_config(), live=False)

        entry = plan["contacts"][0]
        self.assertIsNone(entry.get("hold_kind"), entry.get("held"))
        self.assertTrue(plan.get("stored_pairs"),
                        "the run produced no stored copy at all")
        self.assertTrue((entry.get("sequences") or {}).get("em1"),
                        "no opening email was written")
        # The copy reached the RECORD, not just the plan.
        stored = (rec.get("cadence") or {}).get("jane-doe") or {}
        self.assertTrue(stored.get("em1", {}).get("body"),
                        "nothing was written into the record's cadence")

    def test_the_pack_reaches_the_prompts_and_carries_its_provenance(self):
        """CONSUMER, not existence. The pack must change what the model sees.

        Without this the fix could "work" while handing the pipeline an empty
        source list - which is exactly what the absent-research row of the
        measurement did, and it produced copy too.
        """
        rec = _rec()
        model = CampaignModel()
        plan = generate._generate_via_campaign(
            rec, model, _client_config(), live=False)

        carrying = [p for p in model.prompts if RESEARCH_FACT in p]
        self.assertGreaterEqual(
            len(carrying), 2,
            "the research fact reached %d prompts; the ICP and extract stages "
            "are both given the source pack" % len(carrying))

        facts = plan["contacts"][0].get("facts") or []
        self.assertTrue(facts)
        self.assertEqual(
            [rec["research"][0]["source_url"]],
            sorted({f.get("source_url") for f in facts}),
            "the extracted fact must carry the URL of the source block it came "
            "from, resolved from our own list by `copyprompts.source_url_for`")

    def test_the_literal_acceptance_call_produces_copy(self):
        """Acceptance 1 again, as the operator's criterion words it:
        `generate_campaign.generate("productive", account, [contact],
        live=False)` - the client as a NAME, the real library, the real config."""
        account = _account_from(_rec())
        self.assertTrue(account["sources"], "the account carries a pack")
        plan = generate_campaign.generate(
            "productive", account, _contacts(),
            model=CampaignModel(), live=False)
        entry = plan["contacts"][0]
        self.assertIsNone(entry.get("hold_kind"), entry.get("held"))
        self.assertTrue(entry["sequences"]["em1"])
        self.assertEqual(sorted(plan["offers"]), ["OFFER-B-OPERATIONS"])

    def test_the_projection_is_the_canonical_one_and_not_a_second_reading(self):
        """ONE TRUTH. `_account_sources` must be a projection of
        `research.for_prompt`, the existing "evidence a prompt may see", and not
        a second opinion about which rows a prompt is shown."""
        rec = _rec()
        canonical = research.for_prompt(rec)
        sources = generate._account_sources(rec)
        self.assertEqual(len(canonical), len(sources))
        self.assertEqual([e.get("source_url") for e in canonical],
                         [s.get("url") for s in sources])
        self.assertEqual([e.get("fact") for e in canonical],
                         [s.get("text") for s in sources])

    def test_changing_a_research_fact_changes_what_the_pipeline_is_given(self):
        """THE PRECONDITION `TASK-425` CRITERION 1B RESTS ON.

        "One fact changed -> the angle and the copy change" is only askable if
        the fact reaches the pipeline at all, and under the dict read it never
        did: every shape either raised or delivered an empty pack. This asserts
        the causal link this code owns - a different stored fact is a different
        prompt and a different resolved provenance. What the MODEL then does with
        it is the model's, and a scripted one deliberately does nothing.
        """
        first = _rec()
        second = _rec()
        second["research"] = canonical_research(
            RECORD_ID,
            fact="TestCorp opened a Berlin studio and is hiring 30 resourcing "
                 "and billing specialists",
            source_url="https://testcorp.test/careers", field="careers")

        prompts = []
        for rec in (first, second):
            model = CampaignModel()
            generate._generate_via_campaign(
                rec, model, _client_config(), live=False)
            prompts.append([p for p in model.prompts
                            if "Source material follows" in p])
            generate.clear_company_cache()

        self.assertTrue(prompts[0] and prompts[1])
        self.assertNotEqual(prompts[0], prompts[1],
                            "a different stored fact must reach the extractor "
                            "as a different source pack")
        self.assertIn("careers", prompts[1][0],
                      "the source block is labelled with the page it came from")

    def test_a_row_the_quality_filter_refuses_is_not_shown_to_the_model(self):
        """The projection NARROWS and never widens. An unusable row - the 239
        navigation-text rows in the production store are this - is not a source,
        and it must not become one by travelling through a different door."""
        rec = _rec()
        rec["research"] = [evidence.make(
            "Skip to the content About Clients Archive Menu",
            "https://testcorp.test/", "crawl", "free-crawler", RECORD_ID)]
        self.assertEqual(evidence.UNUSABLE, rec["research"][0]["quality"])
        self.assertEqual([], generate._account_sources(rec))


# ---------------------------------------------------------------------------
# ACCEPTANCE 2: absence is not an error
# ---------------------------------------------------------------------------

class AbsenceIsNotAnError(ResearchShapeTest):

    def test_a_record_with_no_research_still_produces_copy(self):
        """Acceptance 2. Absence behaves exactly as it did before the fix."""
        rec = _rec("absent")
        plan = generate._generate_via_campaign(
            rec, CampaignModel(), _client_config(), live=False)
        entry = plan["contacts"][0]
        self.assertIsNone(entry.get("hold_kind"), entry.get("held"))
        self.assertTrue(plan.get("stored_pairs"))

    def test_an_empty_list_is_the_same_as_absent(self):
        rec = _rec([])
        plan = generate._generate_via_campaign(
            rec, CampaignModel(), _client_config(), live=False)
        self.assertIsNone(plan["contacts"][0].get("hold_kind"))
        self.assertEqual([], generate._account_sources(rec))

    def test_missing_evidence_is_never_positive_evidence(self):
        """No pack means no source block and NO INVENTED PROVENANCE.

        `copyprompts.source_url_for` resolves a URL from our own list, so with
        no list there is nothing to resolve and the fact carries None. A fact
        that arrived with a URL from nowhere would be the worse failure.
        """
        rec = _rec("absent")
        model = CampaignModel()
        plan = generate._generate_via_campaign(
            rec, model, _client_config(), live=False)
        self.assertEqual([], generate._account_sources(rec))
        self.assertEqual([], [p for p in model.prompts if RESEARCH_FACT in p])
        for fact in plan["contacts"][0].get("facts") or []:
            self.assertIsNone(fact.get("source_url"))


# ---------------------------------------------------------------------------
# ACCEPTANCE 3: a shape error is not a hold
# ---------------------------------------------------------------------------

class AShapeErrorIsNotAHold(ResearchShapeTest):

    def test_an_unreadable_research_shape_is_refused_by_name(self):
        """A shape this pipeline cannot read REFUSES, naming the record.

        It is not read as an empty pack: that is the silent failure - copy
        written from evidence that was dropped on the way in, reported as
        success.
        """
        rec = _rec({"sources": [{"label": "site", "url": "https://x.test",
                                 "text": "TestCorp is an agency"}]})
        with self.assertRaises(generate_campaign.CampaignPipelineError) as e:
            generate._generate_via_campaign(
                rec, CampaignModel(), _client_config(), live=False)
        message = str(e.exception)
        self.assertIn(RECORD_ID, message)
        self.assertIn("dict", message)
        self.assertIn("LIST", message)
        # FAIL CLOSED: nothing was written, and no draft was left behind.
        self.assertFalse(rec.get("cadence"))

    def test_a_programming_error_in_a_gate_is_not_a_per_contact_hold(self):
        """THE SECOND DEFECT, asserted through the exact seam that hid the first.

        `claims.support_text` raised `AttributeError: 'str' object has no
        attribute 'get'` through the `validate` callback and came back as
        `hold_kind="error"` on every contact. The same failure now propagates as
        `CampaignPipelineError`, so the run cannot report itself complete.
        """
        def boom(contact_result):
            raise AttributeError("'str' object has no attribute 'get'")

        with self.assertRaises(generate_campaign.CampaignPipelineError) as e:
            generate_campaign.generate(
                _client_config(), _account_from(_rec()), _contacts(),
                model=CampaignModel(), live=False, validate=boom)
        message = str(e.exception)
        self.assertIn("AttributeError", message)
        self.assertIn("jane-doe", message)

    def test_a_legitimate_hold_is_still_a_hold_and_still_returns_a_plan(self):
        """THE CONTROL IN THE OTHER DIRECTION, and the point of the whole item:
        the two outcomes are now tellable apart. A writer that holds, and a
        draft every gate refuses, both come back ON the plan."""
        plan = generate_campaign.generate(
            _client_config(), _account_from(_rec()), _contacts(),
            model=HoldingModel(), live=False)
        entry = plan["contacts"][0]
        self.assertEqual("writer_hold", entry.get("hold_kind"))
        self.assertIn("nothing specific to say", str(entry.get("held")))

        refused = generate_campaign.generate(
            _client_config(), _account_from(_rec()), _contacts(),
            model=CampaignModel(), live=False,
            validate=lambda r: ["em1: the figure 12 appears in no stored fact"])
        entry = refused["contacts"][0]
        self.assertEqual("copy_refused", entry.get("hold_kind"))
        self.assertEqual({}, entry["sequences"])

    def test_a_model_answer_that_is_not_json_still_holds_the_contact(self):
        """The narrowing NARROWED. `ValueError` from `_parse_json` is a model
        failure on a record and holds it, exactly as before - operator decision
        3, and the reason `ValueError` is not in `PIPELINE_DEFECTS`."""
        plan = generate_campaign.generate(
            _client_config(), _account_from(_rec()), _contacts(),
            model=UnparseableModel(), live=False)
        entry = plan["contacts"][0]
        self.assertEqual("error", entry.get("hold_kind"))
        self.assertIn("ValueError", str(entry.get("held")))

    def test_the_defect_types_are_the_ones_that_mean_the_code_is_wrong(self):
        """`ValueError` must never join that tuple: it is how a model failure
        arrives, and holding the contact for it is the recorded decision."""
        self.assertIn(AttributeError, generate_campaign.PIPELINE_DEFECTS)
        self.assertIn(TypeError, generate_campaign.PIPELINE_DEFECTS)
        self.assertNotIn(ValueError, generate_campaign.PIPELINE_DEFECTS)


# ---------------------------------------------------------------------------
# ACCEPTANCE 4: every canonical reader still reads the canonical shape
# ---------------------------------------------------------------------------

class EveryCanonicalReaderStillWorks(ResearchShapeTest):
    """EXISTENCE IS NOT FUNCTION: each reader is asserted on its ANSWER, with a
    control that removes the row and shows the answer changes. A reader that
    merely does not raise proves nothing about whether it read anything."""

    def setUp(self):
        super().setUp()
        self.rec = _rec()
        self.row = self.rec["research"][0]
        self.contact = self.rec["contacts"][0]

    def test_claims_licenses_a_figure_only_while_the_research_row_is_there(self):
        sentence = "You are hiring 12 delivery project managers."
        support = claims.support_text(self.rec, self.contact)
        ok, why = claims.check_sentence(sentence, support)
        self.assertTrue(ok, why)

        without = copy.deepcopy(self.rec)
        without["research"] = []
        ok, why = claims.check_sentence(
            sentence, claims.support_text(without, self.contact))
        self.assertFalse(ok, "the claim must lose its licence with the row")
        self.assertIn("12", str(why))

    def test_dossier_reports_the_row_with_its_provenance(self):
        report = dossier.company_research(self.rec)
        self.assertEqual(1, report["fact_count"])
        self.assertEqual(RESEARCH_FACT, report["facts"][0]["fact"])
        self.assertEqual(self.row["source_url"],
                         report["facts"][0]["provenance"]["source_url"])

        without = copy.deepcopy(self.rec)
        without["research"] = []
        self.assertEqual(0, dossier.company_research(without)["fact_count"])

    def test_dossier_resolves_a_selected_evidence_id_against_the_list(self):
        contact = dict(self.contact, personalization={
            "selected_evidence_ids": [self.row["evidence_id"]]})
        got = dossier.personalization_evidence(self.rec, contact)
        self.assertEqual([RESEARCH_FACT],
                         [row["fact"] for row in got["selected"]])
        self.assertEqual([], got["dangling_evidence_ids"])
        self.assertEqual(1, got["considered"])

    def test_eligibility_reads_the_list_to_age_a_cited_fact(self):
        contact = dict(self.contact, personalization={
            "selected_evidence_ids": [self.row["evidence_id"]]})
        self.assertFalse(
            eligibility._evidence_aged_out(self.rec, contact),
            "a fresh, usable row this record carries is not aged out")

        without = copy.deepcopy(self.rec)
        without["research"] = []
        self.assertTrue(
            eligibility._evidence_aged_out(without, contact),
            "a draft citing evidence the record cannot produce is refused")

    def test_generate_reads_the_list_for_the_prompt_and_the_fingerprint(self):
        block = generate.research_block(self.rec)
        self.assertEqual([RESEARCH_FACT], [row["fact"] for row in block])

        moved = copy.deepcopy(self.rec)
        moved["research"][0]["source_url"] = "https://testcorp.test/careers"
        self.assertNotEqual(generate._evidence_fingerprint(self.rec),
                            generate._evidence_fingerprint(moved),
                            "the fingerprint must move when the rows move")

        self.assertEqual(1, len(generate._account_sources(self.rec)))


if __name__ == "__main__":
    unittest.main()
