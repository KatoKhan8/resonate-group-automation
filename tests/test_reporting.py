"""Reporting: counted from events, and honest about what it cannot see.

The recurring temptation in outbound reporting is to infer. A positive reply
becomes a meeting; a prepared payload becomes a send. Both make the numbers
better and both are lies, so the tests here are mostly about what stays zero.
"""
import json
import unittest

from src import clients, demo, events, report, store
from tests.campaignbase import CampaignTest, contact


class ReportTest(CampaignTest):
    def seeded(self):
        campaign, recs, config = demo.build(self.config)
        store.save(recs)
        return campaign, store.load(), config


class TestTheFunnel(ReportTest):
    def test_every_stage_is_named(self):
        self.assertEqual(len(report.FUNNEL), 11)
        for stage in ("domain", "qualified", "contact_found", "selected",
                      "contactable", "approved", "active", "contacted",
                      "replied", "positive", "meeting"):
            self.assertIn(stage, report.FUNNEL)

    def test_domains_and_qualification_are_counted(self):
        campaign, recs, config = self.seeded()
        stages = report.funnel_for(recs, config=config)
        self.assertEqual(stages["domain"], 5)
        self.assertEqual(stages["qualified"], 4, "one record is dropped")

    def test_a_meeting_is_never_inferred_from_a_positive_reply(self):
        campaign, recs, config = self.seeded()
        rec = recs[0]
        events.record(rec, events.REPLY_RECEIVED, contact_key=rec["contacts"][0]["key"])
        events.record(rec, events.POSITIVE_REPLY_DETECTED,
                      contact_key=rec["contacts"][0]["key"])
        stages = report.funnel_for(recs, config=config)
        self.assertEqual(stages["positive"], 1)
        self.assertEqual(stages["meeting"], 0, "nothing here observes a calendar")

    def test_a_meeting_is_counted_only_when_somebody_marks_it(self):
        campaign, recs, config = self.seeded()
        events.record(recs[0], events.MEETING_MARKED,
                      contact_key=recs[0]["contacts"][0]["key"])
        self.assertEqual(report.funnel_for(recs, config=config)["meeting"], 1)

    def test_contacted_needs_a_real_push_not_a_prepared_payload(self):
        campaign, recs, config = self.seeded()
        events.record(recs[0], events.PUSH_PREPARED,
                      contact_key=recs[0]["contacts"][0]["key"])
        self.assertEqual(report.funnel_for(recs, config=config)["contacted"], 0)
        events.record(recs[0], events.PUSH_MARKED,
                      contact_key=recs[0]["contacts"][0]["key"])
        self.assertEqual(report.funnel_for(recs, config=config)["contacted"], 1)

    def test_active_requires_a_current_campaign_approval(self):
        campaign, recs, config = self.seeded()
        self.assertEqual(report.funnel_for(recs, campaign, config)["active"], 0)

    def test_a_campaign_scope_narrows_the_funnel(self):
        campaign, recs, config = self.seeded()
        campaign["record_ids"] = ["northwind"]
        self.assertEqual(report.funnel_for(recs, campaign, config)["domain"], 1)


class TestPersonaReporting(ReportTest):
    def test_it_splits_by_persona(self):
        campaign, recs, config = self.seeded()
        rows = report.by_persona(recs, config)
        self.assertIn("champion", rows)
        self.assertIn("economic_buyer", rows)
        self.assertGreater(rows["champion"]["contacts"], 0)

    def test_a_rate_is_absent_where_the_denominator_is_meaningless(self):
        campaign, recs, config = self.seeded()
        rows = report.by_persona(recs, config)
        for row in rows.values():
            if row["touches"] < report.MIN_DENOMINATOR:
                self.assertIsNone(row["positive_rate"])

    def test_a_rate_appears_once_there_is_enough_to_divide_by(self):
        campaign, recs, config = self.seeded()
        rec = recs[0]
        key = rec["contacts"][0]["key"]
        for n in range(report.MIN_DENOMINATOR):
            events.record(rec, events.PUSH_MARKED, contact_key=key,
                          id=f"touch-{n}")
        events.record(rec, events.POSITIVE_REPLY_DETECTED, contact_key=key)
        rows = report.by_persona(recs, config)
        persona = rec["contacts"][0]["persona"]
        self.assertIsNotNone(rows[persona]["positive_rate"])

    def test_sendable_is_counted_per_persona(self):
        campaign, recs, config = self.seeded()
        rows = report.by_persona(recs, config)
        self.assertGreaterEqual(rows["champion"]["sendable"], 1)


class TestAngleReporting(ReportTest):
    def test_it_splits_by_angle(self):
        campaign, recs, config = self.seeded()
        rows = report.by_angle(recs)
        self.assertIn("ops", rows)
        self.assertIn("founder", rows)

    def test_it_counts_how_many_had_evidence_behind_them(self):
        campaign, recs, config = self.seeded()
        rows = report.by_angle(recs)
        self.assertGreater(sum(r["with_evidence"] for r in rows.values()), 0)

    def test_an_angle_with_no_touches_reports_no_rate(self):
        campaign, recs, config = self.seeded()
        for row in report.by_angle(recs).values():
            self.assertIsNone(row["positive_rate"])


class TestClientReporting(ReportTest):
    def test_it_answers_the_questions_a_client_asks(self):
        campaign, recs, config = self.seeded()
        result = report.for_client("demo", recs, rows=[])
        for field in ("domains_uploaded", "domains_qualified", "contacts_found",
                      "contacts_selected", "contacts_verified",
                      "contacts_mx_blocked", "contacts_email_only",
                      "contacts_linkedin_only", "contacts_multichannel",
                      "emails_planned", "emails_pushed", "replies",
                      "positive_replies", "companies_paused", "funnel",
                      "by_persona", "by_angle"):
            self.assertIn(field, result, field)

    def test_unobservable_metrics_are_none_rather_than_zero(self):
        campaign, recs, config = self.seeded()
        result = report.for_client("demo", recs, rows=[])
        self.assertIsNone(result["meetings"])
        self.assertIsNone(result["provider_spend"])

    def test_another_clients_records_are_not_counted(self):
        campaign, recs, config = self.seeded()
        result = report.for_client("productive", recs, rows=[])
        self.assertEqual(result["domains_uploaded"], 0)

    def test_channel_split_adds_up(self):
        campaign, recs, config = self.seeded()
        result = report.for_client("demo", recs, rows=[])
        split = (result["contacts_email_only"] + result["contacts_linkedin_only"]
                 + result["contacts_multichannel"])
        self.assertLessEqual(split, result["contacts_found"])

    def test_it_calls_no_provider(self):
        campaign, recs, config = self.seeded()
        report.for_client("demo", recs, rows=[])
        self.assertEqual(self.cassette.calls, [])

    def test_the_result_is_json_serialisable(self):
        campaign, recs, config = self.seeded()
        json.dumps(report.for_client("demo", recs, rows=[]))


class TestNothingIsInvented(ReportTest):
    def test_an_empty_queue_reports_zeros_not_estimates(self):
        stages = report.funnel_for([], config={})
        self.assertEqual(set(stages.values()), {0})

    def test_the_unavailable_list_still_names_meetings(self):
        self.assertIn("meetings_booked", report.unavailable())

    def test_reporting_reads_and_never_writes(self):
        import inspect
        source = inspect.getsource(report)
        for banned in ("store.save", "campaigns.save", "push.run",
                       "providers.request"):
            self.assertNotIn(banned, source, banned)


class QualificationReportTest(CampaignTest):
    """A qualified batch, before anybody has been looked up."""

    def qualified(self, size=60):
        from src import companies, qualify
        recs = companies.dataset(size)
        store.save(recs)
        result = qualify.run(config=self.config)
        store.save([e["record"] for e in result["companies"]])
        return store.load()


class TestTheQualificationFunnel(QualificationReportTest):
    def test_every_uploaded_company_is_accounted_for(self):
        recs = self.qualified()
        funnel = report.qualification_funnel(recs)
        self.assertEqual(funnel["uploaded"], len(recs))
        self.assertEqual(funnel["classified"] + funnel["not_yet_classified"],
                         funnel["uploaded"])

    def test_the_four_statuses_sum_to_the_classified_count(self):
        recs = self.qualified()
        funnel = report.qualification_funnel(recs)
        self.assertEqual(sum(funnel["by_status"].values()),
                         funnel["classified"])

    def test_only_the_four_declared_statuses_appear(self):
        from src import icp
        funnel = report.qualification_funnel(self.qualified())
        for status in funnel["by_status"]:
            self.assertIn(status, (icp.QUALIFIED, icp.REVIEW, icp.REJECTED,
                                   icp.UNKNOWN), status)

    def test_review_and_unknown_are_what_needs_a_human(self):
        funnel = report.qualification_funnel(self.qualified())
        self.assertEqual(funnel["needs_manual_review"],
                         funnel["by_status"].get("review", 0)
                         + funnel["by_status"].get("unknown", 0))

    def test_an_unqualified_batch_reports_nothing_classified(self):
        from src import companies
        recs = companies.dataset(20)
        funnel = report.qualification_funnel(recs)
        self.assertEqual(funnel["classified"], 0)
        self.assertEqual(funnel["not_yet_classified"], 20)
        self.assertEqual(funnel["by_status"], {})


class TestTheDistributions(QualificationReportTest):
    def test_every_dimension_counts_every_classified_company(self):
        recs = self.qualified()
        classified = sum(1 for r in recs if r.get("qualification"))
        distribution = report.qualification_distribution(recs)
        for dimension, counts in distribution.items():
            self.assertEqual(sum(counts.values()), classified, dimension)

    def test_unclassifiable_companies_are_reported_not_dropped(self):
        """A distribution that omits UNKNOWN reads as complete when it is not."""
        distribution = report.qualification_distribution(self.qualified())
        self.assertIn("UNKNOWN", distribution["subvertical"])

    def test_the_size_bands_are_the_canonical_ones(self):
        from src import segments
        distribution = report.qualification_distribution(self.qualified())
        known = set(segments.BAND_NAMES) | {"UNKNOWN"}
        for band in distribution["employee_band"]:
            self.assertIn(band, known, band)


class TestPlannedIsNeverReportedAsActual(QualificationReportTest):
    """Section 24: planned, actual and unavailable must not share a bucket."""

    def test_before_enrichment_nothing_has_been_found(self):
        result = report.decision_makers(self.qualified())
        self.assertGreater(result["planned_contacts"], 0)
        self.assertEqual(result["found_contacts"], 0)
        self.assertFalse(result["enrichment_has_run"])

    def test_planned_contacts_never_exceed_the_tier_caps(self):
        from src import routing
        recs = self.qualified()
        biggest = max(routing.DEFAULT_CAPS.values())
        for rec in recs:
            plan = (rec.get("qualification") or {}).get("persona_plan") or {}
            self.assertLessEqual(plan.get("max_contacts_to_enrich") or 0,
                                 biggest, rec["id"])

    def test_every_company_with_no_plan_costs_nothing(self):
        recs = self.qualified()
        result = report.decision_makers(recs)
        credits = report.credit_exposure(recs, config=self.config)
        self.assertEqual(result["companies_with_no_planned_spend"],
                         credits["companies_skipped"])

    def test_actual_credits_are_absent_rather_than_zero(self):
        """Zero would read as "we spent nothing"; absent reads as "nobody knows"."""
        credits = report.credit_exposure(self.qualified(), config=self.config)
        self.assertIsNone(credits["actual_credits"])
        self.assertTrue(credits["actual_note"])

    def test_maximum_exposure_is_never_below_expected(self):
        credits = report.credit_exposure(self.qualified(), config=self.config)
        self.assertGreaterEqual(credits["maximum_credits"],
                                credits["expected_credits"])

    def test_fallback_exposure_is_the_gap_between_them(self):
        credits = report.credit_exposure(self.qualified(), config=self.config)
        self.assertEqual(credits["fallback_exposure"],
                         credits["maximum_credits"]
                         - credits["expected_credits"])

    def test_what_cannot_be_known_is_named(self):
        absent = report.unavailable()
        self.assertIn("decision_makers_found", absent)
        self.assertIn("email_and_linkedin_eligibility", absent)
        for reason in absent.values():
            self.assertTrue(reason)


class TestSegmentReporting(QualificationReportTest):
    def test_every_segmented_company_is_counted(self):
        recs = self.qualified()
        result = report.campaign_segments(recs)
        counted = sum(result["by_segment"].values())
        keyed = sum(1 for r in recs
                    if (r.get("qualification") or {}).get("segment_key"))
        self.assertEqual(counted, keyed)

    def test_a_qualified_batch_produces_segments(self):
        """Which is only true because the key is persisted onto the record."""
        self.assertGreater(report.campaign_segments(self.qualified())["segments"],
                           0)

    def test_rejected_companies_are_not_given_a_segment(self):
        from src import icp
        for rec in self.qualified():
            qualification = rec.get("qualification") or {}
            status = (qualification.get("verdict") or {}).get("icp_status")
            if status == icp.REJECTED:
                self.assertIsNone(qualification.get("segment_key"), rec["id"])


class TestTheWholeReport(QualificationReportTest):
    def test_it_assembles_without_a_provider(self):
        result = report.qualification_report(recs=self.qualified(),
                                             config=self.config)
        for key in ("funnel", "distribution", "decision_makers", "credits",
                    "segments", "unavailable"):
            self.assertIn(key, result)

    def test_it_is_json_serialisable(self):
        result = report.qualification_report(recs=self.qualified(),
                                             config=self.config)
        json.dumps(result)


if __name__ == "__main__":
    unittest.main()
