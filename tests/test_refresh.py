"""What a weekly refresh would spend, and everything it refuses to spend on.

The failure this guards against is not a wrong number. It is a plan that
looks like maintenance and is actually first-time work, or one that reports
two hundred accounts out of nine hundred as though it were the answer, or
one that quietly buys person credits for a company nobody has qualified.
"""
import unittest

from src import accountpolicy as ap, enrich, icp, refresh, store


def excluded_count(found, reason):
    return next((r["count"] for r in found["excluded"]
                 if r["reason"] == reason), 0)
from tests.campaignbase import CampaignTest

TODAY = "2026-08-31"
YESTERDAY = "2026-08-30"
LAST_YEAR = "2025-01-05"


def fact(published_at, subject="company", contact_key=None):
    return {"evidence_id": f"ev_{published_at}_{subject}_{contact_key}",
            "fact": "Acme opened a Vienna delivery office last month.",
            "subject": subject, "contact_key": contact_key,
            "published_at": published_at, "relevance_score": 0.8,
            "freshness_bucket": "high", "quality": "strong",
            "source_url": "https://acme.test/news"}


def checked(at):
    return {"verification": {"evidence": [{"provider": "contactout",
                                           "status": "valid", "at": at}]}}


def a_record(research=(), contacts=None, verdict=icp.QUALIFIED, **kw):
    # `qualification.verdict.icp_status`, which is where `qualify.company`
    # writes it. One level below where a reader expects, and reading the
    # level above answers "not qualified" for every account in the estate
    # while looking exactly like a working check.
    rec = {"id": kw.pop("id", "a1"), "company": "Acme", "domain": "acme.test",
           "client": "demo",
           "qualification": {"verdict": {"icp_status": verdict,
                                         "icp_score": 70, "icp_tier": "A"}},
           "research": list(research),
           "contacts": contacts if contacts is not None
                       else [{"key": "a", "selected": True, **checked(TODAY)}]}
    rec.update(kw)
    return rec


class StalenessIsPerKind(unittest.TestCase):

    def rows(self, rec, today=TODAY):
        return {r["kind"]: r for r in refresh.staleness(rec, today=today)}

    def test_nothing_held_means_never_done_not_stale(self):
        """A record with no evidence has not gone stale. It has not
        happened, which costs the same and means something different."""
        rows = self.rows(a_record(contacts=[{"key": "a", "selected": True}]))
        for kind in refresh.KINDS:
            self.assertTrue(rows[kind]["never"], kind)
            self.assertIsNone(rows[kind]["age_days"], kind)
            self.assertTrue(rows[kind]["due"], kind)

    def test_work_done_yesterday_is_not_due(self):
        rec = a_record(research=[fact(YESTERDAY),
                                 fact(YESTERDAY, "person", "a")])
        rows = self.rows(rec)
        for kind in refresh.KINDS:
            self.assertFalse(rows[kind]["due"], kind)

    def test_the_thresholds_differ_by_kind(self):
        """A job change ages faster than an office opening, so one number
        for both would be a number nobody could defend."""
        rows = self.rows(a_record())
        self.assertGreater(rows[refresh.COMPANY_RESEARCH]["limit_days"],
                           rows[refresh.PERSON_RESEARCH]["limit_days"])

    def test_a_kind_falls_due_on_its_own_threshold(self):
        """75 days is past the person limit and inside the company one."""
        old = "2026-06-17"
        rec = a_record(research=[fact(old), fact(old, "person", "a")])
        rows = self.rows(rec)
        self.assertEqual(rows[refresh.PERSON_RESEARCH]["age_days"], 75)
        self.assertTrue(rows[refresh.PERSON_RESEARCH]["due"])
        self.assertFalse(rows[refresh.COMPANY_RESEARCH]["due"])

    def test_verification_takes_the_oldest_contact_not_the_newest(self):
        """One mailbox checked last week does not make the account current.
        The one nobody has looked at since is what a re-check is for."""
        rec = a_record(contacts=[
            {"key": "a", "selected": True, **checked(TODAY)},
            {"key": "b", "selected": True, **checked(LAST_YEAR)}])
        self.assertEqual(refresh._last_checked(rec["contacts"]),
                         LAST_YEAR)

    def test_a_contact_nobody_ever_checked_makes_it_never(self):
        rec = a_record(contacts=[{"key": "a", "selected": True, **checked(TODAY)},
                                 {"key": "b", "selected": True}])
        self.assertIsNone(refresh._last_checked(rec["contacts"]))


class NeverDoneOutranksNearlyDue(unittest.TestCase):
    """A never-researched account has no age to divide, so ordering it by
    its urgency of 0.0 would put the work most worth doing at the bottom of
    the list - and the list is what a cap cuts."""

    def rank(self, recs):
        found = refresh.plan(recs, today=TODAY, suppressed=set(), assess=False)
        return [r["record_id"] for r in found["selected"]]

    def pair(self, other_id, company_fact):
        """Two accounts differing only in their company research.

        Everything else is current on both, so the ordering that comes out
        is the ordering of that one kind and not an accident of the rest.
        """
        common = {"research": [fact(YESTERDAY, "person", "a")],
                  "contacts": [{"key": "a", "selected": True,
                                **checked(TODAY)}]}
        never = a_record(id="never", **common)
        other = a_record(id=other_id, **{
            **common, "research": common["research"] + [company_fact]})
        return never, other

    def test_a_never_researched_account_comes_first(self):
        # 91 days: one day past its threshold, so due but barely.
        never, nearly = self.pair("nearly", fact("2026-06-01"))
        self.assertEqual(self.rank([nearly, never]), ["never", "nearly"])

    def test_but_not_ahead_of_something_years_overdue(self):
        """It sorts as if it were just past its limit, not as if it were
        the most urgent thing in the estate. Never done is due; it is not
        an emergency."""
        never, ancient = self.pair("ancient", fact(LAST_YEAR))
        self.assertEqual(self.rank([never, ancient]), ["ancient", "never"])


class PersonCreditsWaitForAVerdict(unittest.TestCase):
    """PLAYBOOK: no paid person-level call before a company reaches an
    explicit ICP verdict, and rejected, review and unknown all mean zero
    person credits."""

    def rows(self, verdict):
        return {r["kind"]: r
                for r in refresh.staleness(a_record(verdict=verdict),
                                           today=TODAY)}

    def test_an_unqualified_company_is_offered_no_person_work(self):
        for verdict in (icp.REJECTED, icp.REVIEW, icp.UNKNOWN, None):
            rows = self.rows(verdict)
            for kind in refresh.PERSON_LEVEL:
                self.assertFalse(rows[kind]["due"], f"{verdict}/{kind}")
                self.assertTrue(rows[kind]["blocked"], f"{verdict}/{kind}")

    def test_company_research_is_still_offered(self):
        """It is free, and it is how a company reaches a verdict."""
        rows = self.rows(icp.REVIEW)
        self.assertTrue(rows[refresh.COMPANY_RESEARCH]["due"])
        self.assertIsNone(rows[refresh.COMPANY_RESEARCH]["blocked"])

    def test_a_qualified_company_is_offered_all_of_it(self):
        rows = self.rows(icp.QUALIFIED)
        for kind in refresh.KINDS:
            self.assertIsNone(rows[kind]["blocked"], kind)


class ItRefusesToSpendOnSomeAccounts(unittest.TestCase):

    def test_a_dropped_record(self):
        self.assertEqual(refresh.excluded(a_record(state="dropped"), set()),
                         refresh.DROPPED)

    def test_a_pushed_record_is_not_excluded(self):
        """A campaign went out. That is a reason to refresh this account
        before the next one, not a reason to skip it."""
        self.assertIsNone(refresh.excluded(a_record(state="pushed"), set()))

    def test_a_suppressed_domain(self):
        self.assertEqual(refresh.excluded(a_record(), {"acme.test"}),
                         refresh.SUPPRESSED)

    def test_a_company_that_asked_us_to_stop(self):
        rec = a_record()
        rec["suppression"] = {"unsubscribed": True,
                              "reason": "the company asked us to stop"}
        self.assertEqual(ap.account_state(rec)[0], ap.SUPPRESS)
        self.assertEqual(refresh.excluded(rec, set()),
                         refresh.ASKED_US_TO_STOP)

    def test_a_company_already_in_a_live_conversation(self):
        """Somebody there replied. Cold research is not what that account
        needs, and it is a person's to work rather than this queue's."""
        rec = a_record()
        rec["paused"] = {"since": TODAY, "reason": "reply_received"}
        self.assertEqual(ap.account_state(rec)[0], ap.HOLD)
        self.assertEqual(refresh.excluded(rec, set()),
                         refresh.CONVERSATION_LIVE)

    def test_an_open_review_holds_it_too(self):
        rec = a_record()
        rec["review"] = {"open": True, "why": "a person has to look"}
        self.assertEqual(refresh.excluded(rec, set()),
                         refresh.CONVERSATION_LIVE)

    def test_an_ordinary_account_is_not_excluded(self):
        self.assertIsNone(refresh.excluded(a_record(), set()))

    def test_the_exclusion_carries_a_sentence(self):
        for reason in (refresh.DROPPED, refresh.SUPPRESSED,
                       refresh.ASKED_US_TO_STOP, refresh.CONVERSATION_LIVE,
                       refresh.BELOW_PRIORITY):
            self.assertTrue(refresh.EXCLUSION_LABEL[reason])


class ThePlanSaysWhatItLeftOut(CampaignTest):

    def records(self, count, research=()):
        rows = []
        for i in range(count):
            rec = a_record(id=f"r{i}", research=research)
            rec["company"] = f"Company {i}"
            rec["domain"] = f"c{i}.test"
            rec["client"] = "demo"
            rows.append(rec)
        return rows

    def plan(self, recs, **kw):
        kw.setdefault("assess", False)
        return refresh.plan(recs, today=TODAY, config=self.config,
                            workspace="demo", suppressed=set(), **kw)

    def test_the_cap_is_applied_and_the_remainder_counted(self):
        found = self.plan(self.records(30), cap=10)
        self.assertEqual(len(found["selected"]), 10)
        self.assertEqual(found["below_the_line"], 20)
        self.assertEqual(found["cap"], 10)

    def test_the_scan_cap_is_reported_rather_than_implied(self):
        """A plan that described the first N of many without saying so
        would read as the whole answer."""
        recs = self.records(30)
        found = refresh.plan(recs, today=TODAY, config={"refresh":
                             {"scan_cap": 5}}, suppressed=set(), assess=False)
        self.assertTrue(found["capped_scan"])
        self.assertEqual(found["scanned"], 5)
        self.assertEqual(found["due"], 30)

    def test_an_uncapped_scan_says_so(self):
        found = self.plan(self.records(3))
        self.assertFalse(found["capped_scan"])

    def test_exclusions_are_counted_by_reason(self):
        recs = self.records(4)
        recs[0]["state"] = "dropped"
        recs[1]["state"] = "dropped"
        found = self.plan(recs)
        self.assertEqual(excluded_count(found, refresh.DROPPED), 2)
        self.assertEqual(found["considered"], 4)

    def test_never_done_work_is_counted_separately(self):
        found = self.plan(self.records(3))
        self.assertGreater(found["never_done"], 0)

    def test_work_already_done_is_not_counted_as_never(self):
        found = self.plan(self.records(3, research=[fact(YESTERDAY),
                                                    fact(YESTERDAY, "person",
                                                         "a")]))
        self.assertEqual(found["never_done"], 0)
        self.assertEqual(found["selected"], [])


class TheEstimateIsArithmeticOverTheRealCostTable(CampaignTest):

    def test_it_reads_the_ledgers_own_costs(self):
        """Not a second price list. `enrich.COSTS` is what the spend
        ledger charges against, and a copy here could drift from it."""
        for kind, call in refresh.CALL_OF.items():
            self.assertIn(call, enrich.COSTS, kind)

    def test_re_verification_is_priced_per_mailbox(self):
        rec = a_record(contacts=[{"key": "a", "selected": True},
                                 {"key": "b", "selected": True},
                                 {"key": "c", "selected": False}])
        rows = {r["kind"]: r for r in refresh.staleness(rec, today=TODAY)}
        row = rows[refresh.REVERIFICATION]
        self.assertEqual(row["units"], 2)
        self.assertEqual(row["credits"],
                         enrich.COSTS["email-verifier"] * 2)

    def test_free_work_costs_nothing(self):
        rows = {r["kind"]: r for r in refresh.staleness(a_record(),
                                                        today=TODAY)}
        self.assertEqual(rows[refresh.COMPANY_RESEARCH]["credits"], 0)

    def test_the_estimate_says_it_is_one(self):
        found = refresh.plan([a_record()], today=TODAY, config=self.config,
                             suppressed=set(), assess=False)
        self.assertIn("estimate", found["estimate"]["note"])

    def test_nothing_is_spent(self):
        found = refresh.plan([a_record()], today=TODAY, config=self.config,
                             suppressed=set(), assess=False)
        self.assertEqual(found["spent"], 0)


class ItPlansAndNeverSpends(unittest.TestCase):

    def test_it_calls_no_provider(self):
        import inspect

        source = inspect.getsource(refresh)
        for banned in ("providers.request", "urlopen", "requests.",
                       "http.client", "spend(", "live=True"):
            self.assertNotIn(banned, source, banned)

    def test_it_writes_no_state(self):
        for banned in ("store.save", "store.log", "events.record"):
            import inspect
            self.assertNotIn(banned, inspect.getsource(refresh), banned)

    def test_a_plan_does_not_mutate_the_records_it_reads(self):
        import copy

        recs = [a_record(research=[fact(LAST_YEAR)])]
        before = copy.deepcopy(recs)
        refresh.plan(recs, today=TODAY, suppressed=set(), assess=False)
        self.assertEqual(recs, before)


class OrderIsPriorityAndStalenessTogether(CampaignTest):

    def test_neither_half_can_win_alone(self):
        """The stalest account is not worth a credit if nobody would write
        to it, and the highest-priority one does not need refreshing the
        week after it was done."""
        recs = self.seed_records()
        for i, rec in enumerate(recs):
            rec["research"] = [fact(LAST_YEAR if i == 0 else YESTERDAY)]
        store.save(recs)
        found = refresh.plan(recs, today=TODAY, config=self.config,
                             workspace="demo", suppressed=set())
        self.assertTrue(found["selected"], "the fixture selected nothing")
        for row in found["selected"]:
            self.assertIsNotNone(row["priority"])
            self.assertGreater(row["urgency"], 0)
            self.assertEqual(row["rank"],
                             round(row["priority"] * row["urgency"], 2))

    def test_below_the_floor_only_free_work_survives(self):
        """Not dropped, reduced. A company scores low partly because
        nothing is known about it, and free research is how that stops
        being true - a floor that refused it would hold the account below
        the floor permanently and call the result thrift."""
        recs = self.seed_records()[:2]
        for rec in recs:
            rec["research"] = [fact(LAST_YEAR)]
        found = refresh.plan(recs, today=TODAY, workspace="demo",
                             config={"refresh": {"minimum_priority": 999.0}},
                             suppressed=set())
        self.assertTrue(found["selected"])
        self.assertEqual(found["floor_limited"], len(found["selected"]))
        for row in found["selected"]:
            self.assertTrue(row["floor_limited"])
            self.assertEqual(row["credits"], 0)
            for kind in row["due"]:
                self.assertEqual(kind["credits"], 0, kind["kind"])
        self.assertEqual(found["estimate"]["credits"], 0)

    def test_an_account_whose_only_work_costs_credits_is_dropped(self):
        """Research fresh on both subjects, verification long overdue: the
        only thing left to do costs a credit, so the floor is the whole
        answer rather than a reduction."""
        rec = a_record(research=[fact(YESTERDAY),
                                 fact(YESTERDAY, "person", "a")])
        rec["contacts"] = [{"key": "a", "selected": True, **checked(LAST_YEAR)}]
        due = [r["kind"] for r in refresh.staleness(rec, today=TODAY)
               if r["due"]]
        self.assertEqual(due, [refresh.REVERIFICATION])

        found = refresh.plan([rec], today=TODAY, workspace="demo",
                             config={"refresh": {"minimum_priority": 999.0}},
                             suppressed=set())
        self.assertEqual(found["selected"], [])
        self.assertEqual(excluded_count(found, refresh.BELOW_PRIORITY), 1)

    def test_a_paid_account_above_the_floor_keeps_its_paid_work(self):
        rec = a_record(research=[fact(YESTERDAY),
                                 fact(YESTERDAY, "person", "a")])
        rec["contacts"] = [{"key": "a", "selected": True, **checked(LAST_YEAR)}]
        found = refresh.plan([rec], today=TODAY, workspace="demo",
                             config={"refresh": {"minimum_priority": 0.0}},
                             suppressed=set())
        self.assertEqual(found["floor_limited"], 0)
        self.assertGreater(found["estimate"]["credits"], 0)

    def test_there_is_nothing_to_re_verify_without_selected_contacts(self):
        """Otherwise it reports as never done, due and free - a work item
        with no work in it, walking straight through the floor."""
        rows = {r["kind"]: r
                for r in refresh.staleness(a_record(contacts=[]), today=TODAY)}
        row = rows[refresh.REVERIFICATION]
        self.assertEqual(row["units"], 0)
        self.assertFalse(row["due"])
        self.assertTrue(row["blocked"])

    def test_the_selected_rows_carry_why(self):
        recs = self.seed_records()[:2]
        for rec in recs:
            rec["research"] = [fact(LAST_YEAR)]
        found = refresh.plan(recs, today=TODAY, config=self.config,
                             workspace="demo", suppressed=set(),
                             cap=1)
        self.assertEqual(len(found["selected"]), 1)
        for row in found["selected"]:
            self.assertTrue(row["why_now"])
            self.assertTrue(row["due"])


class ThereIsNoScheduler(unittest.TestCase):

    def test_the_module_says_so(self):
        """"Weekly" describes an intended cadence. A timer that does not
        exist must not be implied by a name."""
        self.assertIn("no scheduler", refresh.__doc__.lower())

    def test_nothing_here_schedules(self):
        import inspect

        source = inspect.getsource(refresh)
        for banned in ("cron", "schedule.every", "threading.Timer",
                       "time.sleep"):
            self.assertNotIn(banned, source, banned)


if __name__ == "__main__":
    unittest.main()
