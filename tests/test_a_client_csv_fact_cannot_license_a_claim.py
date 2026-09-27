#!/usr/bin/env python3
"""A client-CSV fact may qualify a company and may never license a claim.

OPERATOR DECISION, Zvonimir, 2026-09-27, verbatim in substance: facts from
Productive's own approved list (the 09-07 CSV) may enter the admitted pack, as
CLIENT_SUPPLIED with the source file AND ROW recorded, usable for qualification
and strategy; prospect-facing claims still need a public source or a stored
page, NEVER the CSV alone.

## WHAT WAS WRONG

`packfacts.pack_for` ended by appending the client's CSV facts straight into
`admitted`, WITHOUT passing `identity_of`, and `admitted` is exactly the pack
`copylint` licenses a prospect-facing claim from - `copylint.untraceable` is
called by `copylint.report` and by `sequencegate.check`, and both run on the
send path. So a headcount or a volume figure typed into an unverified client
spreadsheet could ground an assertion in an email to a stranger.

## THE TWO HALVES, AND WHY BOTH ARE HERE

A test that only proves the refusal would pass just as well if the fix had
DELETED the client's facts, which the decision forbids. A test that only proves
they are still readable would pass on the broken code. So:

  1. a draft whose only support is a CSV value is REFUSED through
     `bisonfactory.stage`, the real send path, with the provider untouched;
  2. the same value, on the account's own page, licenses the same draft - so
     the refusal is about provenance rather than about refusing everything;
  3. the same value is still what `qualify.company` classifies the company on
     and what the dossier a reviewer reads reports;
  4. and it is still recorded, with its file and its row, as CLIENT_SUPPLIED.

The provider is a fake object installed over `bisonfactory.bison`, so PROVIDER
WRITES ARE 0 by construction and the counters assert it.
"""
import unittest

from src import (approval, bisonfactory, cadence, campaigns, copylint, icp,
                 packfacts, qualify, store, workspaces)
from tests.base import QueueTest, fixture_config, pin_client_config
from tests.test_staging_a_campaign_twice_builds_one import FakeBison
from tests.test_staging_refuses_colliding_contacts import patch_collision_empty
from tests.test_the_copy_lint_refuses_the_real_send_path import CountingBison

CID = "camp-client-csv"

#: The one-step EmailBison sequence the staging fixtures are pinned to. Same
#: reason as `test_the_copy_lint_refuses_the_real_send_path`: the lint is told
#: THIS plan's length, so a one-step push is checked as one step.
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

#: One value from the client's own approved list. The 09-07 export's `headline`
#: column is a PHRASE and not a bare number, which is the case that matters: a
#: bare "35%" could never trace anyway, because `copylint._traces` needs two
#: shared content words, so a bare number would make this test pass for the
#: wrong reason. This one carries the words and the figure together.
CSV_HEADLINE = "Independent clinic booking software, 4,000 appointments a month"
CSV_INDUSTRY = "Health Care Software"

#: THE SAME WORDS, reached on the account's own website. `identity_of` admits
#: it on the host of the page it was read from, so this is a public source and
#: it IS a claim licence. Nothing here is a real company: `northwind.test` is a
#: reserved TLD and the person is invented.
STORED_PAGE_FACT = {
    "fact": ("Independent clinic booking software, 4,000 appointments a "
             "month."),
    "source_url": "https://northwind.test/product",
    "source_type": "local_http",
}

#: The claim. Sentence one asserts the CSV's figure about the prospect's own
#: business, which is what "prospect-facing claim" means. The rest is the
#: clean body the send-path lint fixtures already use, so nothing else in it
#: can fire a rule and take the refusal away from the claim.
BODY = (
    "Ada, your booking software handles 4,000 appointments a month.\n\n"
    "Most teams that size find the margin question answered after a project "
    "closes rather than while it is running. That is a visibility problem "
    "more than a delivery one.\n\n"
    "Is that roughly how it works for you today?")

LEAD = "rec-northwind/rec-northwind-c1"


def record(research=(), facts=None, body=BODY, rid="rec-northwind"):
    """One ready record with one approved step.

    `facts` is `company_facts` - the canonical home of a client-supplied fact
    and what the qualification path reads. `research` is the crawled evidence,
    which is what `packfacts.identity_of` judges.
    """
    key = "%s-c1" % rid
    step = {"channel": "email", "subject": "how booking work is tracked",
            "body": body}
    step["approval"] = {"by": "operator", "at": "2026-09-27T00:00:00Z",
                        "fingerprint": approval.fingerprint(step)}
    return {"id": rid, "client": "productive", "domain": "northwind.test",
            "company": "Northwind Studio", "state": "ready",
            # A record with contacts always carries an ICP verdict, and the
            # sequence gate refuses an absent one by design - a fixture
            # without it is refused one gate BEFORE the lint this is about.
            "qualification": {"verdict": {"icp_status": icp.QUALIFIED}},
            "batch": {"id": "productive-09-07.csv-2026-09-07T00:00:00",
                      "source": "productive-09-07.csv", "row": 7,
                      "client": "productive", "lane": "domains"},
            "company_facts": dict(facts or {}),
            "research": [dict(r, record_id=rid) for r in research],
            "cadence": {key: {"day1": step}},
            "contacts": [{"key": key, "email": "ada@northwind.test",
                          "first_name": "Ada", "last_name": "Tester",
                          "sendable": True, "verified": True}]}


class AClientCsvFactCannotLicenseAProspectFacingClaim(QueueTest):

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

        row = campaigns.new_campaign(CID, "productive", "Client CSV test")
        # DECLARED, NOT INHERITED. `_require_declared_cadence` runs inside
        # `_plan`, before the lint, so a campaign with no stored cadence is
        # refused one gate earlier and the guard under test is never reached.
        row["cadence_steps"] = [dict(s) for s in
                                cadence.steps_for(None, config=CONFIG)]
        row["record_ids"] = ["rec-northwind"]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        campaigns.save([row])

    def given(self, *records):
        store.save(list(records))

    def stage(self, live=True):
        return bisonfactory.stage(CID, config=CONFIG, live=live)

    def refusal(self):
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage()
        return str(caught.exception)

    # ------------------------------------------------- 1. the claim is refused

    def test_a_claim_supported_only_by_the_client_csv_is_refused(self):
        """The record HAS the fact. It has it from the CSV, so it may not say it.

        This is the whole decision. `company_facts` carries the figure, the
        draft asserts the figure about the prospect, and nothing public or
        stored says it - so the push is refused before any provider write.
        """
        self.given(record(facts={"headline": CSV_HEADLINE}))
        said = self.refusal()
        self.assertIn("the batch copy lint refuses this push", said)
        self.assertIn("untraceable_company_claim", said)
        self.assertIn(LEAD, said)
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    def test_the_rule_that_fires_is_the_traceability_rule_and_it_names_the_lead(self):
        """WHICH gate refused, not just that something did.

        A refusal from the cadence, the qualification, the tenancy check or
        `empty_step` would satisfy "it raised" while proving nothing about
        claim licensing. The refusal carries the lint's structured verdict, so
        the offending rule is asserted by name against the offending lead.

        THE DRY RUN NOW REFUSES, AND THIS TEST GOT STRONGER RATHER THAN
        DIFFERENT. It read the verdict off the RETURN value of
        `stage(live=False)`, because a dry run ran the lint and declined to
        raise on it. Under the operator's rule of 2026-09-27 - a dry run
        executes the real decision and safety path without provider writes - it
        raises in both modes, so the verdict is read off the refusal instead.
        Every assertion below is the one that was here before, and the run is
        still a zero-write one through the real entrypoint.
        """
        self.given(record(facts={"headline": CSV_HEADLINE}))
        with self.assertRaises(bisonfactory.FactoryRefused) as caught:
            self.stage(live=False)
        found = caught.exception.report["copylint"]
        self.assertTrue(found["refused"])
        self.assertIn(LEAD, found["offenders"]["untraceable_company_claim"])
        self.assertEqual(found["offenders"]["empty_step"], [])
        self.assertEqual(found["offenders"]["dash"], [])
        self.assertEqual(found["offenders"]["buzzword"], [])
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    def test_the_csv_value_is_not_in_the_pack_that_licenses_a_claim(self):
        """The seam itself: the licence and the client's list are two lists."""
        rec = record(facts={"headline": CSV_HEADLINE})
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(pack["facts"], [])
        self.assertNotIn(CSV_HEADLINE, copylint.pack_text(pack))
        supplied = unused[packfacts.CLIENT_SUPPLIED]
        self.assertEqual([f["snippet"] for f in supplied], [CSV_HEADLINE])

    # ----------------------------------- 2. the same words, a public source

    def test_the_same_figure_on_the_accounts_own_page_does_license_it(self):
        """The control. Without it, test 1 is indistinguishable from a gate
        that refuses everything - and this repository has shipped one.

        Identical draft, identical figure, and the only difference is that a
        page on the account's own domain states it. The push is staged.
        """
        self.given(record(facts={"headline": CSV_HEADLINE},
                          research=(STORED_PAGE_FACT,)))
        report = self.stage()
        self.assertFalse(report["copylint"]["refused"],
                         copylint.report_lines(report["copylint"]))
        self.assertEqual(report["copylint"]["leads_with_a_pack"], 1)
        self.assertEqual(self.bison.created_leads, 1)

    def test_a_page_on_somebody_elses_domain_does_not_license_it(self):
        """And identity still decides, which the CSV change must not soften."""
        self.given(record(facts={"headline": CSV_HEADLINE},
                          research=(dict(STORED_PAGE_FACT,
                                         source_url="https://southgale.test/"
                                                    "product"),)))
        said = self.refusal()
        self.assertIn("untraceable_company_claim", said)
        self.assertEqual(self.bison.touched(), CountingBison.UNTOUCHED)

    # ------------------------- 3. still visible to qualification and strategy

    def test_the_csv_fact_still_classifies_the_company(self):
        """`qualify.company` is the real qualification entrypoint and it reads
        the client-supplied industry through `segments.classify`.

        This is the half the decision protects. A fix that hid the CSV from
        the copy path by dropping it would pass every refusal test above and
        fail here.
        """
        pin_client_config(self)
        config = fixture_config()
        rec = record(facts={"headline": CSV_HEADLINE,
                            "industry": CSV_INDUSTRY})
        entry = qualify.company(rec, config)
        self.assertEqual(entry["segment"]["industry"], CSV_INDUSTRY)
        self.assertEqual(
            rec["qualification"]["segment"]["industry"], CSV_INDUSTRY)

    def test_the_csv_fact_reaches_the_dossier_a_reviewer_reads(self):
        """The strategy surface. `qualify.dossier` is the object an operator
        reads to decide whether to spend anything, and the client's own facts
        are its evidence block."""
        pin_client_config(self)
        config = fixture_config()
        rec = record(facts={"headline": CSV_HEADLINE,
                            "industry": CSV_INDUSTRY})
        entry = qualify.company(rec, config)
        dossier = qualify.dossier(entry, config)
        facts = dossier["evidence"]["company_facts"]
        self.assertEqual(facts["headline"], CSV_HEADLINE)
        self.assertEqual(facts["industry"], CSV_INDUSTRY)

    def test_changing_the_csv_fact_changes_the_qualification(self):
        """Consumed, not merely present. Two records differing only in the
        client-supplied value classify differently."""
        pin_client_config(self)
        config = fixture_config()
        a = qualify.company(record(facts={"industry": CSV_INDUSTRY}), config)
        b = qualify.company(record(facts={"industry": "Construction"}), config)
        self.assertNotEqual(a["segment"]["industry"], b["segment"]["industry"])

    # ------------------------------ 4. the file and the row are both recorded

    def test_the_provenance_names_the_file_and_the_row(self):
        rec = record(facts={"headline": CSV_HEADLINE})
        supplied = packfacts.client_supplied_facts(rec)
        self.assertEqual(len(supplied), 1)
        self.assertEqual(supplied[0]["verification"],
                         packfacts.CLIENT_SUPPLIED)
        self.assertEqual(supplied[0]["source"], "productive-09-07.csv")
        self.assertEqual(supplied[0]["source_row"], 7)


if __name__ == "__main__":
    unittest.main()
