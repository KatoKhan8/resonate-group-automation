"""Two steps in one sequence that say the same thing.

Each step passes lint alone; the sequence is the defect. The tests here are
mostly about the line between "the same email twice" and "two emails that
share a signature", because a check that cannot tell those apart is a check
somebody switches off in week one.
"""
import unittest

from src import campaigns, clients, demo, duplicates, qa, simulator, store
from tests.campaignbase import CampaignTest

BODY = ("Hi Ann,\n\n"
        "Noticed you opened a Vienna office and moved four delivery leads "
        "there. A second location usually means the numbers arrive later than "
        "the decisions do.\n\n"
        "Most operations leads we speak to lose the better part of a day every "
        "month reconciling time before they can answer a question anyone "
        "actually asked.\n\n"
        "Is that roughly how it works with you today?\n")

DIFFERENT = ("Hi Ann,\n\n"
             "One more note and then I will leave it. The teams I work with "
             "that look most like yours tend to stop reconciling hours after "
             "the fact and start seeing project margin while the work is still "
             "running.\n\n"
             "Would it be useful to see what that looked like for a team your "
             "size?\n")

SIGNATURE = "\n\nOperator\nResonate Group\nBook a time: https://cal.test/z\n"


class DuplicateTest(CampaignTest):
    def rec_with(self, *steps):
        """A record whose contact has the given email steps, in order."""
        rec = {"id": "acme", "client": "demo", "domain": "acme.test",
               "company": "Acme", "state": "drafted",
               "contacts": [{"key": "c0", "name": "Ann",
                             "email": "ann@acme.test"}]}
        rec["cadence"] = {"c0": {}}
        timeline = {"c0": {}}
        for i, (subject, body) in enumerate(steps):
            key = f"day{i * 5 + 1}"
            timeline["c0"][key] = {"channel": "email", "day": i * 5 + 1,
                                   "subject": subject, "body": body,
                                   "status": "unapproved"}
        # The contact-keyed map, which is the shape for_contact reads.
        return rec, timeline

    def findings(self, *steps):
        rec, timeline = self.rec_with(*steps)
        return duplicates.for_contact(rec, "c0", timeline, self.config)

    def codes(self, *steps):
        return [f["code"] for f in self.findings(*steps)]


class TestTheSevenCases(DuplicateTest):
    def test_exact_duplicate_blocks(self):
        codes = self.codes(("quick question", BODY), ("quick question", BODY))
        self.assertEqual(codes, [duplicates.DUPLICATE_BODY])

    def test_a_whitespace_only_difference_is_still_a_duplicate(self):
        spaced = BODY.replace("\n\n", "\n\n\n").replace("Hi Ann,", "Hi Ann,  ")
        codes = self.codes(("a", BODY), ("b", spaced))
        self.assertIn(duplicates.DUPLICATE_BODY, codes)

    def test_a_punctuation_only_difference_is_still_a_duplicate(self):
        tweaked = BODY.replace("today?", "today.").replace("Hi Ann,", "Hi Ann -")
        codes = self.codes(("a", BODY), ("b", tweaked))
        self.assertIn(duplicates.DUPLICATE_BODY, codes)

    def test_a_casing_difference_is_still_a_duplicate(self):
        codes = self.codes(("a", BODY), ("b", BODY.upper()))
        self.assertIn(duplicates.DUPLICATE_BODY, codes)

    def test_a_genuinely_different_follow_up_is_not_flagged(self):
        self.assertEqual(self.codes(("a", BODY), ("b", DIFFERENT)), [])

    def test_the_same_signature_and_cta_does_not_make_two_emails_duplicates(self):
        """The case that would make this check unusable if it got it wrong."""
        self.assertEqual(
            self.codes(("a", BODY + SIGNATURE), ("b", DIFFERENT + SIGNATURE)),
            [])

    def test_a_duplicate_subject_with_a_different_body_only_warns(self):
        codes = self.codes(("same subject", BODY), ("same subject", DIFFERENT))
        self.assertEqual(codes, [duplicates.DUPLICATE_SUBJECT])

    def test_a_duplicate_body_reports_the_shared_subject_alongside_it(self):
        findings = self.findings(("same", BODY), ("same", BODY))
        self.assertEqual(findings[0]["code"], duplicates.DUPLICATE_BODY)
        self.assertTrue(findings[0]["also_duplicate_subject"])


class TestTheNormalization(unittest.TestCase):
    def test_normalize_removes_what_a_reader_would_not_notice(self):
        self.assertEqual(duplicates.normalize("Hi, Ann!  How ARE you?"),
                         "hi ann how are you")

    def test_normalize_folds_accents(self):
        self.assertEqual(duplicates.normalize("Zoë Müller"),
                         duplicates.normalize("Zoe Muller"))

    def test_short_paragraphs_are_not_substantive(self):
        self.assertEqual(duplicates.substantive("Hi Ann,\n\nWorth a look?\n"),
                         [])

    def test_a_long_paragraph_is_substantive(self):
        text = ("Most operations leads we speak to lose the better part of a "
                "day every month reconciling time.")
        self.assertEqual(len(duplicates.substantive(text)), 1)

    def test_hard_wrapping_does_not_change_the_fingerprint(self):
        flat = ("Most operations leads we speak to lose the better part of a "
                "day every month reconciling time before they can answer.")
        wrapped = flat.replace(" lose", "\nlose").replace(" before", "\nbefore")
        self.assertEqual(duplicates.fingerprint(flat),
                         duplicates.fingerprint(wrapped))

    def test_an_all_boilerplate_body_has_an_empty_fingerprint(self):
        self.assertEqual(duplicates.fingerprint("Hi Ann,\n\nWorth a look?\n"),
                         "")

    def test_two_empty_fingerprints_are_not_a_duplicate(self):
        """Otherwise every short note matches every other short note."""
        note = "Hi Ann,\n\nWorth a look?\n"
        self.assertFalse(duplicates.same_body(note, note))

    def test_there_is_no_similarity_threshold(self):
        """Equality after normalisation, deliberately: a fuzzy ratio would
        need a number nobody can defend."""
        import inspect
        source = inspect.getsource(duplicates)
        for banned in ("SequenceMatcher", "ratio(", "difflib", "0.9"):
            self.assertNotIn(banned, source, banned)

    def test_the_difference_is_explained_in_words(self):
        self.assertIn("byte for byte", duplicates._difference(BODY, BODY))
        spaced = BODY.replace("\n\n", "\n\n\n")
        self.assertIn("line breaks", duplicates._difference(BODY, spaced))


class TestTheDemoFixtureRegression(CampaignTest):
    """Day 1 and Day 15 in the demo dataset are byte-identical.

    That is what prompted the check, and it stays as a regression: if the
    fixture is ever fixed the assertion should be updated deliberately rather
    than quietly passing for a new reason.
    """

    def demo(self):
        config = clients.load("demo")
        campaign, recs, cfg = demo.build(config)
        campaign["record_ids"] = [r["id"] for r in recs]
        return campaign, recs, cfg

    def test_the_day1_day15_duplication_is_detected(self):
        campaign, recs, cfg = self.demo()
        findings = duplicates.find(recs, cfg)
        pairs = {tuple(f["steps"]) for f in findings
                 if f["code"] == duplicates.DUPLICATE_BODY}
        self.assertIn(("day1", "day15"), pairs)

    def test_it_is_reported_as_byte_identical(self):
        campaign, recs, cfg = self.demo()
        body = [f for f in duplicates.find(recs, cfg)
                if f["code"] == duplicates.DUPLICATE_BODY][0]
        self.assertEqual(body["why"], "byte for byte identical")

    def test_every_drafted_demo_contact_is_affected(self):
        campaign, recs, cfg = self.demo()
        summary = duplicates.summarise(duplicates.find(recs, cfg))
        self.assertEqual(summary["duplicate_bodies"],
                         summary["contacts_with_duplicate_bodies"])
        self.assertGreater(summary["duplicate_bodies"], 0)


class TestItBlocksApproval(CampaignTest):
    def demo_campaign(self):
        config = clients.load("demo")
        campaign, recs, cfg = demo.build(config)
        campaign["record_ids"] = [r["id"] for r in recs]
        store.save(recs)
        return campaign, store.load(), cfg

    def test_the_campaign_check_refuses(self):
        campaign, recs, cfg = self.demo_campaign()
        ok, detail = campaigns.check_no_duplicate_copy(campaign, recs, cfg)
        self.assertFalse(ok)
        self.assertIn("duplicate email body", detail)

    def test_the_check_is_part_of_validation(self):
        self.assertIn("no duplicate copy", [name for name, _ in campaigns.CHECKS])

    def test_validation_names_it_as_a_blocker(self):
        campaign, recs, cfg = self.demo_campaign()
        result = campaigns.validate(campaign["campaign_id"], recs, cfg,
                                    campaign=campaign, ignore_status=True)
        self.assertFalse(result["ok"])
        self.assertIn("no duplicate copy", result["blockers"])

    def test_the_refusal_says_to_regenerate_rather_than_to_edit(self):
        """Do not silently rewrite the email to make the check pass."""
        campaign, recs, cfg = self.demo_campaign()
        _, detail = campaigns.check_no_duplicate_copy(campaign, recs, cfg)
        self.assertIn("Regenerate", detail)

    def test_qa_blocks_on_it(self):
        campaign, recs, cfg = self.demo_campaign()
        result = qa.report(campaign, recs, cfg)
        self.assertEqual(result["verdict"], qa.BLOCK)
        self.assertTrue(any("same message twice" in r
                            for r in result["reasons"]))

    def test_qa_counts_bodies_and_subjects_separately(self):
        campaign, recs, cfg = self.demo_campaign()
        result = qa.report(campaign, recs, cfg)
        self.assertGreater(result["copy"]["duplicate_bodies"], 0)
        self.assertIn("duplicate_subjects", result["copy"])

    def test_a_duplicate_subject_alone_warns_rather_than_blocks(self):
        campaign, recs, cfg = self.demo_campaign()
        config = dict(cfg)
        config["qa"] = {"block_on": {"duplicate_email_body": False,
                                     "lint_failures": False,
                                     "unresolved_placeholders": False,
                                     "unsupported_claims": False,
                                     "stale_approval": False}}
        result = qa.report(campaign, recs, config)
        self.assertNotEqual(result["verdict"], qa.BLOCK)
        self.assertTrue(any("share a subject line" in r
                            for r in result["reasons"]))

    def test_the_blocker_can_be_switched_off_but_never_silently(self):
        campaign, recs, cfg = self.demo_campaign()
        config = dict(cfg)
        config["qa"] = {"block_on": {"duplicate_email_body": False}}
        result = qa.report(campaign, recs, config)
        self.assertFalse(any("same message twice" in r
                            for r in result["reasons"]))

    def test_the_issue_is_critical_and_names_both_steps(self):
        campaign, recs, cfg = self.demo_campaign()
        issues = [i for i in qa.report(campaign, recs, cfg)["issues"]
                  if "same email" in i["message"]]
        self.assertTrue(issues)
        self.assertEqual(issues[0]["severity"], "critical")
        self.assertIn("day1 and day15", issues[0]["message"])


class TestItIsVisibleEverywhere(CampaignTest):
    def result(self):
        config = clients.load("demo")
        campaign, recs, cfg = demo.build(config)
        campaign["record_ids"] = [r["id"] for r in recs]
        return simulator.simulate(recs=recs, campaign=campaign,
                                  config=cfg), campaign, cfg

    def test_the_headline_carries_the_count(self):
        result, _, _ = self.result()
        self.assertIn("duplicate_bodies", simulator.HEADLINE)
        self.assertGreater(result["headline"]["duplicate_bodies"], 0)

    def test_the_qa_metrics_split_bodies_from_subjects(self):
        result, _, _ = self.result()
        metrics = simulator.qa_metrics(result)
        self.assertGreater(metrics["duplicate_email_bodies"], 0)
        self.assertIn("duplicate_email_subjects", metrics)
        self.assertGreater(metrics["contacts_with_duplicate_copy"], 0)

    def test_the_affected_steps_are_marked_on_the_timeline(self):
        result, _, _ = self.result()
        card = next(c for company in result["companies"]
                    for c in company["cards"] if c["duplicate_bodies"])
        marked = [row for row in card["timeline"] if row.get("duplicate")]
        self.assertEqual({row["step"] for row in marked}, {"day1", "day15"})
        for row in marked:
            self.assertIn("the same email as", row["duplicate_of"])

    def test_the_slack_preview_says_it_blocks(self):
        result, campaign, cfg = self.result()
        payload = simulator.slack_preview(result, campaign, cfg)
        joined = " ".join(payload["preview_lines"])
        self.assertIn("BLOCKED", joined)
        self.assertIn("same message twice", joined)

    def test_a_clean_campaign_says_so_rather_than_staying_silent(self):
        result, campaign, cfg = self.result()
        clean = dict(result)
        clean["headline"] = dict(result["headline"])
        clean["headline"]["duplicate_bodies"] = 0
        clean["headline"]["duplicate_subjects"] = 0
        payload = simulator.slack_preview(clean, campaign, cfg)
        self.assertIn("no two email steps send the same message",
                      " ".join(payload["preview_lines"]))

    def test_the_event_type_is_registered(self):
        from src import events
        self.assertIn(events.DUPLICATE_COPY_DETECTED, events.KNOWN)


if __name__ == "__main__":
    unittest.main()
