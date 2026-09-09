"""The brief a person reads before a campaign goes anywhere.

Three properties, and every test is one of them:

**Supported and hypothetical never merge.** A pain the company's own
evidence fired and a pain that is merely typical for the vertical are
different kinds of thing. The pack keeps them apart all the way to the
screen, and names the ones no company in the campaign supports.

**Priority is not permission, at campaign scale.** The tier counts and the
count of accounts that cannot be written to are returned together. A
campaign of high-priority suppressed accounts is a campaign that will send
nothing, and one number without the other says otherwise.

**A signal is not a claim.** The evidence is quotable and right there,
which is exactly why the pack has to say that quoting it is not what it is
for. `outreachclaims` decides what a message may assert, and no claim type
it knows covers an observation.
"""
import datetime
import unittest

from src import (accountpolicy as ap, contextpack, events, priority,
                 signals as S, store, strategy)
from tests.campaignbase import CampaignTest

WS = "productive"
JOHN, SARAH = "john", "sarah"
NOW = datetime.datetime(2026, 8, 29, tzinfo=datetime.timezone.utc)


def days_ago(n):
    return (NOW - datetime.timedelta(days=n)).isoformat()


class PackTest(CampaignTest):

    def company(self, rid, name=None, segment="PRODUCTIVE-ABM",
                supported=(), hypothetical=(), score=80.0,
                status="qualified"):
        """One company with a verdict and a stored messaging strategy.

        The strategy is written the way `qualify.company` writes it,
        because the pack reads it rather than recomputing - a fixture that
        invented its own shape would be testing a different program.
        """
        rec = store.new_record(rid, "domains", WS, name or rid.title(),
                               f"{rid}.test")
        rec["contacts"] = [
            {"key": JOHN, "name": "John Smith", "title": "COO",
             "email": f"john@{rid}.test", "selected": True}]
        rec["qualification"] = {
            "segment_key": segment,
            "segment_reason": "services, UK, 50-200",
            "segment_rung": "full",
            "segment": {"vertical": "professional_services"},
            "verdict": {"icp_status": status, "icp_score": score,
                        "icp_tier": "A"},
            "messaging": {
                "vertical": "professional_services",
                "relevant_pain_categories": list(supported),
                "unsupported_hypotheses": list(hypothetical),
                "recommended_angles": list(supported),
            },
        }
        store.save([rec])
        return rec

    def assess(self, recs):
        return [priority.assess(r, WS, now=NOW) for r in recs]


class AnglesStaySplit(PackTest):

    def test_a_supported_pain_and_a_guess_are_not_one_list(self):
        recs = [self.company("acme", supported=[strategy.UTILIZATION],
                             hypothetical=[strategy.TOOL_SPRAWL])]
        out = contextpack.angles(recs)
        self.assertEqual([r["pain"] for r in out["supported"]],
                         [strategy.UTILIZATION])
        self.assertEqual([r["pain"] for r in out["hypotheses"]],
                         [strategy.TOOL_SPRAWL])

    def test_a_pain_nobody_supports_is_called_out(self):
        """The one most likely to reach copy on the strength of sounding
        right for the vertical."""
        recs = [self.company("acme", supported=[strategy.UTILIZATION],
                             hypothetical=[strategy.TOOL_SPRAWL]),
                self.company("borealis", supported=[strategy.UTILIZATION],
                             hypothetical=[strategy.TOOL_SPRAWL])]
        out = contextpack.angles(recs)
        self.assertEqual([r["pain"] for r in out["unsupported_anywhere"]],
                         [strategy.TOOL_SPRAWL])

    def test_a_pain_one_company_supports_is_not_called_unsupported(self):
        recs = [self.company("acme", supported=[strategy.TOOL_SPRAWL]),
                self.company("borealis", hypothetical=[strategy.TOOL_SPRAWL])]
        out = contextpack.angles(recs)
        self.assertEqual(out["unsupported_anywhere"], [])

    def test_it_counts_how_many_companies_have_any_evidence_at_all(self):
        recs = [self.company("acme", supported=[strategy.UTILIZATION]),
                self.company("borealis", hypothetical=[strategy.UTILIZATION])]
        out = contextpack.angles(recs)
        self.assertEqual(out["companies_with_supported_angle"], 1)
        self.assertEqual(out["companies"], 2)

    def test_a_campaign_with_no_evidenced_angle_says_so(self):
        recs = [self.company("acme", hypothetical=[strategy.UTILIZATION])]
        out = contextpack.build(recs, workspace=WS, now=NOW)
        self.assertEqual(out["angles"]["companies_with_supported_angle"], 0)
        self.assertTrue(any("hypothesis" in item["why"]
                            or "hypothesis" in item["what"]
                            for item in out["check"]))

    def test_the_pack_reads_the_strategy_rather_than_recomputing_it(self):
        """A second opinion about the angle would be a second angle."""
        rec = self.company("acme", supported=[strategy.PROJECT_MARGIN])
        rec["qualification"]["messaging"]["relevant_pain_categories"] = [
            strategy.BUDGET_CONTROL]
        store.save([rec])
        out = contextpack.angles([rec])
        self.assertEqual([r["pain"] for r in out["supported"]],
                         [strategy.BUDGET_CONTROL])


class PriorityIsNotPermissionAcrossACampaign(PackTest):

    def test_the_blocked_count_travels_with_the_tier_counts(self):
        recs = [self.company("acme"), self.company("borealis")]
        ap.apply_reply(recs[0], JOHN, ap.ACCOUNT_DNC, workspace=WS)
        store.save([recs[0]])
        out = contextpack.attention(self.assess(recs))
        self.assertEqual(out["accounts"], 2)
        self.assertEqual(out["blocked_count"], 1)
        self.assertEqual(out["workable"], 1)

    def test_a_suppressed_account_still_scores_and_still_cannot_be_written_to(self):
        """Both halves. Dropping either one is a different claim."""
        rec = self.company("acme", supported=[strategy.UTILIZATION])
        ap.apply_reply(rec, JOHN, ap.ACCOUNT_DNC, workspace=WS)
        store.save([rec])
        out = contextpack.attention(self.assess([rec]))
        self.assertGreater(out["top"][0]["score"], 0)
        self.assertFalse(out["top"][0]["eligible"])
        self.assertIn("stop", (out["blocked"][0]["why"] or "").lower())

    def test_every_top_row_says_whether_it_may_be_written_to(self):
        recs = [self.company("acme"), self.company("borealis")]
        out = contextpack.attention(self.assess(recs))
        for row in out["top"]:
            self.assertIn("eligible", row)

    def test_the_blocked_are_listed_not_merely_counted(self):
        """A count tells somebody there is a problem. The list tells them
        which account it is."""
        recs = [self.company("acme"), self.company("borealis")]
        ap.apply_reply(recs[1], JOHN, ap.ACCOUNT_DNC, workspace=WS)
        store.save([recs[1]])
        out = contextpack.attention(self.assess(recs))
        self.assertEqual([b["record_id"] for b in out["blocked"]],
                         ["borealis"])

    def test_the_checklist_raises_blocked_accounts(self):
        recs = [self.company("acme")]
        ap.apply_reply(recs[0], JOHN, ap.ACCOUNT_DNC, workspace=WS)
        store.save([recs[0]])
        out = contextpack.build(recs, workspace=WS, now=NOW)
        self.assertTrue(any("cannot be written to" in i["what"]
                            for i in out["check"]))


class ASignalIsNotAClaim(PackTest):

    def test_the_pack_says_so_where_the_evidence_is_shown(self):
        rec = self.company("acme")
        S.record(S.signal(WS, S.HIRING_SURGE, record_id="acme",
                          evidence="7 open delivery roles on the careers page",
                          source=S.MANUAL, observed_at=days_ago(3)))
        out = contextpack.live_signals(self.assess([rec]))
        self.assertIn("not permission", out["note"])

    def test_the_claim_block_names_the_gap(self):
        """No claim type covers an observation. Said plainly, because the
        pack is where somebody would go looking for permission."""
        out = contextpack.claims()
        self.assertIn("observation", out["not_a_claim_type"])

    def test_every_claim_type_is_reported_with_its_policy(self):
        from src import outreachclaims
        out = contextpack.claims()
        self.assertEqual({r["claim"] for r in out["claims"]},
                         set(outreachclaims.POLICY_KEYS))

    def test_evidence_is_quoted_rather_than_characterised(self):
        """"Three accounts are hiring" is a claim. "7 open delivery roles"
        is a thing that was seen."""
        rec = self.company("acme")
        S.record(S.signal(WS, S.HIRING_SURGE, record_id="acme",
                          evidence="7 open delivery roles on the careers page",
                          source=S.MANUAL, observed_at=days_ago(3)))
        out = contextpack.live_signals(self.assess([rec]))
        quoted = out["external"][0]["evidence"][0]["evidence"]
        self.assertEqual(quoted,
                         "7 open delivery roles on the careers page")

    def test_our_own_touches_are_not_listed_as_things_happening_at_them(self):
        """The circular one. Having written to somebody is not evidence
        that they were worth writing to, so it belongs in a block of its
        own rather than under "what is happening at this account"."""
        rec = self.company("acme")
        events.record(rec, events.PUSH_MARKED, contact_key=JOHN,
                      channel="email", at=days_ago(4), sender_id="anna",
                      step="d1")
        store.save([rec])
        out = contextpack.live_signals(self.assess([rec]))
        self.assertEqual(out["external"], [])
        self.assertEqual(out["external_live"], 0)
        self.assertEqual([r["type"] for r in out["engagement"]],
                         [S.ENGAGED_CONTACTED])

    def test_an_observation_is_external_and_a_reply_is_not(self):
        rec = self.company("acme")
        S.record(S.signal(WS, S.HIRING_SURGE, record_id="acme",
                          evidence="7 open delivery roles on the careers page",
                          source=S.MANUAL, observed_at=days_ago(3)))
        events.record(rec, events.PUSH_MARKED, contact_key=JOHN,
                      channel="email", at=days_ago(9), sender_id="anna",
                      step="d1")
        store.save([rec])
        out = contextpack.live_signals(self.assess([rec]))
        self.assertEqual([r["type"] for r in out["external"]],
                         [S.HIRING_SURGE])
        self.assertEqual(out["external_live"], 1)
        self.assertTrue(out["engagement"])
        self.assertEqual(out["accounts_with_external"], 1)

    def test_an_account_we_have_only_contacted_counts_as_no_observation(self):
        """The number the campaign headline shows. A campaign whose only
        "signals" are its own touches has nothing observed about it."""
        rec = self.company("acme")
        events.record(rec, events.PUSH_MARKED, contact_key=JOHN,
                      channel="email", at=days_ago(4), sender_id="anna",
                      step="d1")
        store.save([rec])
        out = contextpack.live_signals(self.assess([rec]))
        self.assertEqual(out["accounts_with_external"], 0)

    def test_stale_signals_are_excluded_from_the_counts_and_reported(self):
        rec = self.company("acme")
        S.record(S.signal(WS, S.WEBSITE_CHANGE, record_id="acme",
                          evidence="services page rewritten around retainers",
                          source=S.MANUAL, observed_at=days_ago(400)))
        out = contextpack.live_signals(self.assess([rec]))
        self.assertEqual(out["external"], [])
        self.assertEqual(out["stale"], 1)

    def test_a_hand_entered_signal_is_raised_for_a_person_to_read(self):
        rec = self.company("acme")
        S.record(S.signal(WS, S.FUNDING, record_id="acme",
                          evidence="Series A reported in the trade press",
                          source=S.MANUAL, observed_at=days_ago(5)))
        out = contextpack.build([rec], workspace=WS, now=NOW)
        self.assertTrue(any("entered by a person" in i["what"]
                            for i in out["check"]))


class WhyTheseCompanies(PackTest):

    def test_one_segment_is_recognised_as_one_story(self):
        recs = [self.company("acme"), self.company("borealis")]
        out = contextpack.why_these(recs)
        self.assertTrue(out["one_segment"])

    def test_a_campaign_spanning_segments_is_flagged(self):
        recs = [self.company("acme", segment="A"),
                self.company("borealis", segment="B")]
        out = contextpack.why_these(recs)
        self.assertFalse(out["one_segment"])
        self.assertTrue(any("spans" in i["what"] for i
                            in contextpack.checklist(recs, self.assess(recs))))

    def test_an_unqualified_company_is_counted_not_hidden(self):
        """It scores zero on fit, which reads as low priority rather than
        as an unanswered question."""
        recs = [self.company("acme")]
        bare = store.new_record("nowhere", "domains", WS, "Nowhere",
                                "nowhere.test")
        store.save([bare])
        recs.append(bare)
        out = contextpack.why_these(recs)
        self.assertEqual(out["unqualified"], 1)
        self.assertTrue(any("no ICP verdict" in i["what"] for i
                            in contextpack.checklist(recs, self.assess(recs))))


class TheChecklistIsNotARitual(PackTest):

    def test_an_orderly_campaign_produces_a_short_list(self):
        """A checklist that always says the same six things is one nobody
        reads."""
        recs = [self.company("acme", supported=[strategy.UTILIZATION]),
                self.company("borealis", supported=[strategy.UTILIZATION])]
        out = contextpack.build(recs, workspace=WS, now=NOW)
        self.assertEqual(out["check"], [])

    def test_each_item_says_what_and_why(self):
        recs = [self.company("acme", segment="A"),
                self.company("borealis", segment="B")]
        for item in contextpack.checklist(recs, self.assess(recs)):
            self.assertTrue(item["what"])
            self.assertTrue(item["why"])


class TheWholePack(PackTest):

    def test_it_carries_every_block(self):
        recs = [self.company("acme", supported=[strategy.UTILIZATION])]
        out = contextpack.build(recs, {"campaign_id": "c1", "name": "Q3",
                                       "status": "draft"}, WS, now=NOW)
        for key in ("campaign", "companies", "why_these", "attention",
                    "signals", "angles", "claims", "check"):
            self.assertIn(key, out)
        self.assertEqual(out["campaign"]["campaign_id"], "c1")

    def test_it_works_without_a_campaign(self):
        """A segment about to become one is the same question asked
        earlier."""
        recs = [self.company("acme")]
        out = contextpack.build(recs, workspace=WS, now=NOW)
        self.assertIsNone(out["campaign"])

    def test_an_empty_campaign_does_not_raise(self):
        out = contextpack.build([], workspace=WS, now=NOW)
        self.assertEqual(out["companies"], 0)
        self.assertEqual(out["attention"]["accounts"], 0)


class ItOnlyReadsWhatItWasHanded(PackTest):

    def test_a_record_outside_the_list_is_not_counted(self):
        """The pack never widens its input. Scoping is the caller's, and
        the caller is `repo.records()`."""
        mine = self.company("acme")
        self.company("theirs", segment="OTHER")
        out = contextpack.build([mine], workspace=WS, now=NOW)
        self.assertEqual(out["companies"], 1)
        self.assertEqual([s["segment_key"]
                          for s in out["why_these"]["segments"]],
                         ["PRODUCTIVE-ABM"])

    def test_signals_from_another_workspace_do_not_reach_the_pack(self):
        rec = self.company("acme")
        S.record(S.signal("contactout", S.FUNDING, record_id="acme",
                          evidence="Series B reported elsewhere",
                          source=S.MANUAL, observed_at=days_ago(2)))
        out = contextpack.build([rec], workspace=WS, now=NOW)
        self.assertEqual(out["signals"]["live"], 0)


if __name__ == "__main__":
    unittest.main()
