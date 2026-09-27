#!/usr/bin/env python3
"""A CLIENT_SUPPLIED figure licenses a claim in NEITHER claim-validation gate.

OPERATOR DECISION "B", Zvonimir, 2026-09-28, as the IMMEDIATE, TEMPORARY,
CONSERVATIVE fix to `ISSUE-048`: the six `company_supplied` fact keys may go on
being used for qualification, segmentation, prioritisation, strategy, offer
selection and internal reasoning, and they MUST NOT license a prospect-facing
factual claim through EITHER claim-validation path. If the only evidence for a
claim is one of those keys, both gates fail closed and refuse.

## WHY THIS FILE EXISTS WHEN `test_a_client_csv_fact_cannot_license_a_claim`
## ALREADY PASSES

There are TWO independent claim gates in this repository, and that test covers
one of them.

  1. THE PACK PATH. `packfacts.pack_for` returns the claim licence as
     `pack["facts"]` and the client's own facts separately under
     `unused[CLIENT_SUPPLIED]`. `copylint.untraceable` and `sequencegate.check`
     both read `pack_for(rec)[0]`, so both are covered. Fixed and merged
     2026-09-27 night.
  2. `src/claims.py`. Its support model was EVERY `company_facts` key and
     value, so the same spreadsheet figure still ground an assertion here.
     Reproduced twice, 2026-09-27 and again before this change:

         "You have 4000 employees."  + company_facts{headcount: 4000}  -> clean
         "You have 4000 employees."  with that fact removed  -> "the figure
                                        4000 appears in no stored fact"

     Six live callers: `eligibility` x2, `executionguard`, `bisonfactory`,
     `heyreachfactory`, `generate`.

So the four things asserted below are the operator's four behavioural criteria,
and each one is worthless without the others:

  1. the figure is refused through BOTH gates;
  2. REMOVING the client-supplied value does not change that - it is refused
     either way, which is what proves the fix is not merely moving which
     message appears;
  3. the client-supplied employee count is STILL what qualification and
     strategy decide on, proved through `icp.score`, `segments.classify`,
     `qualify.company` and `qualify.dossier` rather than by reading the dict;
  4. and a claim backed by independently admitted evidence still ships. Without
     this control, 1 and 2 are indistinguishable from a validator that refuses
     everything - and this repository has shipped one of those.

## NO PROVIDER IS TOUCHED

The pack-path assertions run `bisonfactory.stage` with a `CountingBison`
installed over `bisonfactory.bison`, so provider writes are 0 by construction
and the counters assert it. Nothing here reaches a real provider or a model.

## WHY THE QUALIFICATION HALF USES `employee_range` AND NOT `headcount`

Both carry the client's employee count: `ingest.INGEST_TO_FACTS` maps
`company_size` to `employee_range` and `company_employee_count` to `headcount`.
The second is written as a bare STRING, and `headcount.block_of` /
`headcount.witnesses` assume a resolved dict block, so `qualify.company` raises
`AttributeError` on any such record. That is a PRE-EXISTING defect on master,
unrelated to this change and confirmed by running the same call with this
change stashed; it is reported rather than fixed here, because fixing
`src/headcount.py` is not this task. `employee_range` is therefore the field
the qualification assertions use, and `headcount` is asserted to be refused as
a claim licence and still recorded as CLIENT_SUPPLIED.
"""
import unittest

from src import (approval, bisonfactory, cadence, campaigns, claims, copylint,
                 eligibility, icp, packfacts, qualify, segments, store,
                 workspaces)
from tests.base import QueueTest, fixture_config, pin_client_config
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty
from tests.test_the_copy_lint_refuses_the_real_send_path import CountingBison

CID = "camp-client-supplied-figure"

#: The one-step EmailBison sequence the staging fixtures are pinned to, for the
#: same reason `test_a_client_csv_fact_cannot_license_a_claim` pins it: the lint
#: is told THIS plan's length, so a one-step push is checked as one step.
CONFIG = {
    "email_sequence": {"title": "Resonate generated cadence",
                       "subject": "{SUBJECT}", "body": "<p>{BODY}</p>",
                       "wait_in_days": 3},
    "sending_window": {"days": ["monday", "tuesday", "wednesday", "thursday",
                                "friday"],
                       "start": "09:00", "end": "17:00",
                       "timezone": "Europe/Zagreb"},
    "providers": {"emailbison": {"workspace": 10}},
}

#: THE OPERATOR'S OWN REPRODUCTION, verbatim in substance. `company_employee_count`
#: from the client's 09-07 export lands in `company_facts["headcount"]`, and this
#: is the value.
CSV_HEADCOUNT = "4000"

#: The CSV's size band, from `company_size`. This is the field the qualification
#: assertions use - see the module docstring for why it is not `headcount`.
CSV_BAND = "1001-5000"
CSV_SMALL_BAND = "1-10"
CSV_INDUSTRY = "Health Care Software"

#: THE SAME FIGURE, reached on the account's own website. `packfacts.identity_of`
#: admits it on the host of the page it was read from, so it is a public source
#: and it IS a claim licence. `northwind.test` is a reserved TLD and Ada Tester
#: is invented; no real company or person appears in this file.
#:
#: WORDED TO SHARE WORDS WITH THE DRAFT, deliberately. `copylint._traces` binds
#: a claim to a pack SENTENCE and needs two shared non-stopword content words
#: since `TASK-330`, so a paraphrase that means the same thing would fail gate 1
#: for a reason that has nothing to do with provenance and would make the
#: control prove nothing.
STORED_PAGE_FACT = {
    "fact": "Northwind Studio has 4000 employees across nine studios.",
    "source_url": "https://northwind.test/about",
    "source_type": "local_http",
}

#: The claim. `you have 4000 employees` is the operator's own sentence and the
#: ONLY thing in either body or note that asserts anything checkable; the rest is
#: the clean copy the send-path fixtures already use, so no other rule can fire
#: and take the refusal away from the figure.
#:
#: `across nine studios` is carried because gate 1 needs TWO shared content words
#: between the draft sentence and the pack sentence (`copylint._traces`, since
#: `TASK-330`), and "Ada, you have 4000 employees." offers exactly one. Without
#: it the CONTROL below would fail on grounding mechanics rather than on
#: provenance, which would make the control prove nothing. It changes nothing
#: about gate 2: `claims.py` refuses this sentence on the figure.
CLAIM = "you have 4000 employees across nine studios"

BODY = (
    "Ada, %s.\n\n"
    "Most teams that size find the margin question answered after a project "
    "closes rather than while it is running. That is a visibility problem "
    "more than a delivery one.\n\n"
    "Is that roughly how it works for you today?" % CLAIM)

NOTE = ("hi Ada, %s. curious how utilisation is handled at that size. "
        "happy to connect." % CLAIM)

RID = "rec-northwind"
KEY = "rec-northwind-c1"
LEAD = "%s/%s" % (RID, KEY)

#: What the refusal must SAY. Asserted so that a refusal arriving from some
#: other guard, or for some other reason, cannot be mistaken for this one.
WHY = "the figure 4000 appears in no stored fact"


def _contact():
    return {"key": KEY, "email": "ada@northwind.test", "first_name": "Ada",
            "last_name": "Tester", "name": "Ada Tester",
            "title": "Operations Manager", "persona": "champion",
            "angle": "ops", "sendable": True, "verified": True,
            "linkedin": "https://www.linkedin.com/in/ada-tester",
            "selected_evidence_ids": []}


def record(facts=None, research=(), body=BODY, note=NOTE, approve_note=False):
    """One ready record carrying one approved email step and one LinkedIn note.

    `facts` is `company_facts`, the canonical home of a client-supplied fact
    and what the qualification path reads. `research` is crawled evidence,
    which is what `packfacts.identity_of` judges.
    """
    step = {"channel": "email", "subject": "how booking work is tracked",
            "body": body}
    step["approval"] = {"by": "operator", "at": "2026-09-28T00:00:00Z",
                        "fingerprint": approval.fingerprint(step)}
    li = {"channel": "linkedin", "note": note, "day": 3, "status": "clean"}
    if approve_note:
        li["approval"] = {"by": "operator", "at": "2026-09-28T00:00:00Z",
                          "fingerprint": approval.fingerprint(li)}
    return {"id": RID, "client": "productive", "domain": "northwind.test",
            "company": "Northwind Studio", "lane": "domains", "state": "ready",
            # A record with contacts always carries an ICP verdict, and the
            # sequence gate refuses an absent one by design - a fixture
            # without it is refused one gate BEFORE the claim checks.
            "qualification": {"verdict": {"icp_status": icp.QUALIFIED}},
            "batch": {"id": "productive-09-07.csv-2026-09-07T00:00:00",
                      "source": "productive-09-07.csv", "row": 7,
                      "client": "productive", "lane": "domains"},
            "company_facts": dict(facts or {}),
            "research": [dict(r, record_id=RID) for r in research],
            "events": [], "log": [],
            "cadence": {KEY: {"day1": step, "day3": li}},
            "contacts": [_contact()]}


def _linkedin_decision(rec):
    """`eligibility.decide` on the LinkedIn step: the real `push.py` path.

    LinkedIn rather than email deliberately. `_linkedin_checks` runs the same
    `lint.check` + `claims.verify` pair as `_email_checks`, it is the channel
    the fabrication that created this module actually shipped on, and it needs
    no MX lookup - so nothing in this test reaches the network to decide
    whether a mailbox exists.
    """
    step = rec["cadence"][KEY]["day3"]
    got = eligibility.decide(rec, rec["contacts"][0], "day3",
                             channel="linkedin", step=step)
    return got["verdict"], got["reasons"]


class TheClaimsGateRefusesAClientSuppliedFigure(unittest.TestCase):
    """Gate 2 of 2: `src/claims.py`, through `eligibility.decide`."""

    # ------------------------------------ criterion 1: it is refused at all

    def test_a_figure_whose_only_evidence_is_the_client_csv_is_refused(self):
        """The whole decision, in the operator's own sentence.

        The record HAS 4000. It has it from the client's spreadsheet, so it may
        not say it to a stranger.
        """
        verdict, reasons = _linkedin_decision(
            record(facts={"headcount": CSV_HEADCOUNT}))
        self.assertEqual(verdict, eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_UNSUPPORTED_CLAIM, reasons)
        self.assertTrue(any(WHY in r for r in reasons), reasons)

    def test_no_other_guard_fires_first(self):
        """WHICH gate refused, not merely that something did.

        A lint failure, a missing profile, a stale approval or an account
        fatigue hold would all satisfy "it was blocked" while proving nothing
        about claim licensing.
        """
        verdict, reasons = _linkedin_decision(
            record(facts={"headcount": CSV_HEADCOUNT}))
        self.assertEqual(reasons[0], eligibility.BLOCKED_UNSUPPORTED_CLAIM)
        self.assertNotIn(eligibility.BLOCKED_LINT, reasons)
        self.assertNotIn(eligibility.BLOCKED_NO_PROFILE, reasons)
        self.assertNotIn(eligibility.HELD_APPROVAL_MISSING, reasons)

    def test_every_one_of_the_six_keys_is_refused_and_the_list_is_not_retyped(self):
        """The POLICY, not one instance of it.

        Each of the six keys is given the figure as its only evidence, one at a
        time, and each is refused. The keys come from
        `packfacts.INGEST_FACT_KEYS` - the same object `src/ingest.py` fills -
        so a key added there is covered here with no edit to this file, and the
        two gates cannot drift apart.
        """
        self.assertEqual(claims.CLIENT_SUPPLIED_FACT_KEYS,
                         packfacts.INGEST_FACT_KEYS)
        self.assertTrue(packfacts.INGEST_FACT_KEYS)
        for key in sorted(packfacts.INGEST_FACT_KEYS):
            with self.subTest(fact_key=key):
                verdict, reasons = _linkedin_decision(
                    record(facts={key: "4000 employees"}))
                self.assertEqual(verdict, eligibility.BLOCKED)
                self.assertIn(eligibility.BLOCKED_UNSUPPORTED_CLAIM, reasons)

    # --------------------- criterion 2: removing the value changes nothing

    def test_removing_the_client_supplied_value_changes_nothing(self):
        """The test that proves this is a fix and not a relabelling.

        Before the change these two disagreed: with the fact stored the draft
        was clean, and without it the refusal named the figure. Now the verdict
        and the reason are IDENTICAL, which is the only shape that means the
        client's spreadsheet buys nothing.
        """
        with_fact = _linkedin_decision(record(facts={"headcount":
                                                     CSV_HEADCOUNT}))
        without = _linkedin_decision(record(facts={}))
        self.assertEqual(with_fact, without)
        self.assertEqual(with_fact[0], eligibility.BLOCKED)
        self.assertTrue(any(WHY in r for r in with_fact[1]), with_fact)

    def test_the_support_blob_itself_no_longer_contains_the_value(self):
        """The seam, stated once at the level it is implemented.

        `support_text` is the single blob every rule in `claims.py` searches, so
        a value's absence from it is the structural fact the behaviour above
        rests on - and its presence for a NON-client key in the same call is
        what proves the exclusion is by key and not by emptying the blob.
        """
        rec = record(facts={"headcount": CSV_HEADCOUNT,
                            "industry": CSV_INDUSTRY,
                            "offices": ["Zagreb", "Vienna"]})
        support = claims.support_text(rec, rec["contacts"][0])
        self.assertNotIn(CSV_HEADCOUNT, support)
        self.assertNotIn(CSV_INDUSTRY.lower(), support)
        self.assertIn("zagreb", support)          # not a client-CSV key
        self.assertIn("northwind", support)       # identity is still support

    # ---------------------------- criterion 4: the control, admitted evidence

    def test_the_same_figure_on_the_accounts_own_page_still_ships(self):
        """Without this, the two tests above are a validator that refuses
        everything - and this repository has shipped one of those.

        Identical note, identical figure, and the only difference is that a
        page on the account's own domain states it. It reaches ELIGIBLE, which
        means every later gate passed too.
        """
        rec = record(research=(STORED_PAGE_FACT,), approve_note=True)
        verdict, reasons = _linkedin_decision(rec)
        self.assertEqual(verdict, eligibility.ELIGIBLE, reasons)
        self.assertEqual(reasons, [])

    def test_an_unsupported_fabrication_is_still_refused(self):
        """The guard's original job, unchanged: a figure nothing states."""
        rec = record(research=(STORED_PAGE_FACT,), approve_note=True,
                     note=("hi Ada, you have 912 designers. happy to "
                           "connect."))
        verdict, reasons = _linkedin_decision(rec)
        self.assertEqual(verdict, eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_UNSUPPORTED_CLAIM, reasons)


class TheClientSuppliedFigureStillDecidesQualification(unittest.TestCase):
    """Criterion 3, through the real entrypoints rather than the dict.

    This is the half the operator's decision PROTECTS, and a fix that hid the
    client's facts by deleting them would pass every refusal test above and
    fail every test here.
    """

    def setUp(self):
        pin_client_config(self)
        self.config = fixture_config()

    def _qualifiable(self, band=CSV_BAND, industry=CSV_INDUSTRY):
        rec = record(facts={"employee_range": band, "industry": industry,
                            "headline": "Independent clinic booking software",
                            "products": "booking software"})
        rec.pop("qualification", None)       # let the scorer decide it
        return rec

    def test_icp_score_names_the_client_supplied_field_as_its_evidence(self):
        """`icp.score` is the scoring entrypoint, and its structural employees
        criterion says out loud which field answered it."""
        found = icp.score(self._qualifiable(), self.config)
        criterion = found["structural"]["criteria"]["employees"]
        self.assertEqual(criterion["source"], "company_facts.employee_range")
        self.assertEqual(criterion["status"], "pass")
        self.assertIn("1001", criterion["why"])

    def test_changing_the_client_supplied_count_changes_the_icp_verdict(self):
        """Consumed, not merely present: the only difference between these two
        records is the client's own employee count, and the verdict flips."""
        big = icp.score(self._qualifiable(), self.config)
        small = icp.score(self._qualifiable(band=CSV_SMALL_BAND), self.config)
        self.assertEqual(big["structural"]["criteria"]["employees"]["status"],
                         "pass")
        self.assertEqual(small["structural"]["criteria"]["employees"]["status"],
                         "fail")
        self.assertNotEqual(big["icp_status"], small["icp_status"])

    def test_segments_classify_still_reads_the_client_supplied_industry(self):
        segment = segments.classify(self._qualifiable(), self.config)
        self.assertEqual(segment["industry"], CSV_INDUSTRY)

    def test_qualify_company_records_the_verdict_it_reached_on_that_value(self):
        """`qualify.company` is the production qualification entrypoint."""
        rec = self._qualifiable()
        entry = qualify.company(rec, self.config)
        self.assertEqual(entry["segment"]["industry"], CSV_INDUSTRY)
        self.assertEqual(rec["qualification"]["segment"]["industry"],
                         CSV_INDUSTRY)
        other = qualify.company(self._qualifiable(band=CSV_SMALL_BAND),
                                self.config)
        self.assertNotEqual(entry["verdict"]["icp_status"],
                            other["verdict"]["icp_status"])

    def test_the_dossier_a_reviewer_reads_still_carries_them(self):
        """The strategy surface: what an operator reads before spending."""
        entry = qualify.company(self._qualifiable(), self.config)
        facts = qualify.dossier(entry, self.config)["evidence"]["company_facts"]
        self.assertEqual(facts["employee_range"], CSV_BAND)
        self.assertEqual(facts["industry"], CSV_INDUSTRY)
        self.assertEqual(facts["products"], "booking software")

    def test_the_headcount_string_is_still_on_the_record_and_still_provenanced(self):
        """The `company_employee_count` half of the client's employee count.

        It cannot be run through `qualify.company` - see the module docstring
        for the pre-existing `headcount.block_of` type defect - so what is
        asserted is that this change neither deletes it nor strips its
        provenance: it is still stored, and still reported as CLIENT_SUPPLIED
        with its file and its row.
        """
        rec = record(facts={"headcount": CSV_HEADCOUNT})
        self.assertEqual(rec["company_facts"]["headcount"], CSV_HEADCOUNT)
        supplied = packfacts.client_supplied_facts(rec)
        self.assertEqual([f["fact_key"] for f in supplied], ["headcount"])
        self.assertEqual(supplied[0]["snippet"], CSV_HEADCOUNT)
        self.assertEqual(supplied[0]["verification"],
                         packfacts.CLIENT_SUPPLIED)
        self.assertEqual(supplied[0]["source"], "productive-09-07.csv")
        self.assertEqual(supplied[0]["source_row"], 7)


class ThePackGateRefusesTheSameFigure(QueueTest):
    """Gate 1 of 2, on the same sentence, through the real send path.

    `bisonfactory.stage` runs `copylint.check_batch` over the pack
    `packfacts.pack_for` returns. The dry run is used so the STRUCTURED verdict
    is available and the offending rule can be named: a raised
    `FactoryRefused` proves only that something refused.

    The provider is a `CountingBison` installed over `bisonfactory.bison`, so
    PROVIDER WRITES ARE 0 by construction and the counters assert it.
    """

    def setUp(self):
        super().setUp()
        self.bison = CountingBison()
        real = bisonfactory.bison
        bisonfactory.bison = self.bison
        self.addCleanup(setattr, bisonfactory, "bison", real)
        patch_collision_empty(self)

        ws = workspaces.new_workspace("productive", "Productive",
                                      client="productive")
        ws["settings"] = {"policy": {"sending.live": "on"}}
        workspaces.save([ws])

        row = campaigns.new_campaign(CID, "productive", "Client-supplied figure")
        # DECLARED, NOT INHERITED. `_require_declared_cadence` runs inside
        # `_plan`, before the lint, so a campaign with no stored cadence is
        # refused one gate earlier and the guard under test is never reached.
        row["cadence_steps"] = [dict(s) for s in
                                cadence.steps_for(None, config=CONFIG)]
        row["record_ids"] = [RID]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

    def _stage(self, rec, live=False):
        store.save([rec])
        return bisonfactory.stage(CID, config=CONFIG, live=live)

    def test_the_pack_gate_refuses_a_figure_only_the_csv_states(self):
        found = self._stage(record(facts={"headcount": CSV_HEADCOUNT}))["copylint"]
        self.assertTrue(found["refused"])
        self.assertIn(LEAD, found["offenders"]["untraceable_company_claim"])
        self.assertEqual(found["offenders"]["empty_step"], [])
        self.assertEqual(found["offenders"]["dash"], [])
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    def test_removing_the_csv_value_changes_nothing_here_either(self):
        found = self._stage(record(facts={}))["copylint"]
        self.assertTrue(found["refused"])
        self.assertIn(LEAD, found["offenders"]["untraceable_company_claim"])
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    def test_the_same_figure_on_the_accounts_own_page_passes_this_gate_too(self):
        """The control for gate 1. The pack now holds a sentence that states
        the figure, on the account's own domain, and the push is staged."""
        report = self._stage(record(research=(STORED_PAGE_FACT,)), live=True)
        found = report["copylint"]
        self.assertFalse(found["refused"], copylint.report_lines(found))
        self.assertEqual(found["leads_with_a_pack"], 1)
        self.assertEqual(self.bison.created_leads, 1)

    def test_a_page_on_somebody_elses_domain_does_not_license_it(self):
        """Identity still decides, and this change must not have softened it.

        Asserted on GATE 1, which is where identity is decided:
        `packfacts.identity_of` is what admits or refuses a research row, and
        `claims.support_text` has never judged the identity of `rec["research"]`
        at all. That asymmetry is pre-existing, is outside decision B - which is
        about the six client-CSV keys - and is reported rather than changed
        here, so this test is placed where the guarantee actually lives instead
        of asserting it somewhere it was never true.
        """
        other = dict(STORED_PAGE_FACT,
                     source_url="https://southgale.test/about")
        found = self._stage(record(research=(other,)))["copylint"]
        self.assertTrue(found["refused"])
        self.assertIn(LEAD, found["offenders"]["untraceable_company_claim"])
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    def test_the_csv_value_is_in_neither_gates_licence(self):
        """One assertion tying the two gates to the same seam: the value is
        absent from the pack `copylint` licenses from AND from the blob
        `claims.py` searches, and present in the client's own list."""
        rec = record(facts={"headcount": CSV_HEADCOUNT})
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(pack["facts"], [])
        self.assertNotIn(CSV_HEADCOUNT, copylint.pack_text(pack))
        self.assertNotIn(CSV_HEADCOUNT,
                         claims.support_text(rec, rec["contacts"][0]))
        self.assertEqual(
            [f["snippet"] for f in unused[packfacts.CLIENT_SUPPLIED]],
            [CSV_HEADCOUNT])


if __name__ == "__main__":
    unittest.main()
