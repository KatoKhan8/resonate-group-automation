"""Learning tags on every enrolled lead, and the nightly rate report.

Four properties, and every test is one of them:

**A tag that was not written at enrollment cannot be reconstructed.**
The schema must refuse unknown values rather than coerce them, because
a tag that silently accepts anything measures nothing.

**Leads enrolled before this task existed can be back-tagged.** The first
real cohort is already in the queue; if the schema cannot tag them from
their enrollment artifacts, they are permanently unmeasurable.

**Rates need denominators and denominators need honesty.** A reply rate
over enrolled is not a reply rate. Every rate names which denominator
it used. A cell with fewer than 30 sends refuses its percentage.

**A report that prints a percentage it cannot support will be believed.**
The under-30 refusal is not a suggestion; it is the property that
prevents two replies out of three sends from becoming a 67% reply rate.
"""
import unittest

from src import enrollmenttags


# ----------------------------------------------------------- vocabularies

PERSONA_VOCAB = ("champion", "economic_buyer")
ANGLE_VOCAB = ("finance", "delivery", "ops", "founder")
SUBJECT_VOCAB = ("pain_opener", "proof_opener", "question_opener")
SENDER_VOCAB = ("anna@resonate.test", "marko@resonate.test")

VOCABULARIES = {
    "persona": PERSONA_VOCAB,
    "angle": ANGLE_VOCAB,
    "subject_variant": SUBJECT_VOCAB,
    "sender": SENDER_VOCAB,
}


def valid_tags(**overrides):
    """A complete, valid tag set. Override any field."""
    base = {
        "persona": "champion",
        "angle": "finance",
        "subject_variant": "pain_opener",
        "sender": "anna@resonate.test",
        "timezone_cohort": "emea",
        "source": "supplier_file",
        "signal": "posted about time-tracking pain on LinkedIn",
    }
    base.update(overrides)
    return base


def make_record(rid="lead-1", state="queued", events=None, contacts=None):
    """A minimal record for testing."""
    return {
        "id": rid,
        "state": state,
        "events": events or [],
        "contacts": contacts or [],
    }


# ------------------------------------------------------------------ tests

class UnknownValuesAreRefused(unittest.TestCase):
    """A tag that silently accepts anything measures nothing."""

    def test_unknown_source_is_refused(self):
        tags = valid_tags(source="cold_email_tool")
        problems = enrollmenttags.validate(tags, VOCABULARIES)
        self.assertTrue(any("source" in p for p in problems))

    def test_unknown_timezone_cohort_is_refused(self):
        tags = valid_tags(timezone_cohort="mars")
        problems = enrollmenttags.validate(tags, VOCABULARIES)
        self.assertTrue(any("timezone_cohort" in p for p in problems))

    def test_unknown_persona_is_refused(self):
        tags = valid_tags(persona="intern")
        problems = enrollmenttags.validate(tags, VOCABULARIES)
        self.assertTrue(any("persona" in p for p in problems))

    def test_unknown_angle_is_refused(self):
        tags = valid_tags(angle="pricing")
        problems = enrollmenttags.validate(tags, VOCABULARIES)
        self.assertTrue(any("angle" in p for p in problems))

    def test_unknown_sender_is_refused(self):
        tags = valid_tags(sender="nobody@example.com")
        problems = enrollmenttags.validate(tags, VOCABULARIES)
        self.assertTrue(any("sender" in p for p in problems))

    def test_unknown_subject_variant_is_refused(self):
        tags = valid_tags(subject_variant="clickbait")
        problems = enrollmenttags.validate(tags, VOCABULARIES)
        self.assertTrue(any("subject_variant" in p for p in problems))

    def test_refuse_unknown_raises(self):
        tags = valid_tags(source="cold_email_tool")
        with self.assertRaises(enrollmenttags.UnknownTagValue):
            enrollmenttags.refuse_unknown(tags, VOCABULARIES)

    def test_valid_tags_pass(self):
        tags = valid_tags()
        problems = enrollmenttags.validate(tags, VOCABULARIES)
        self.assertEqual(problems, [])

    def test_signal_is_free_text(self):
        """Signal is recorded but never parsed for decisions."""
        tags = valid_tags(signal="anything goes here, even Unicode: \u2603")
        problems = enrollmenttags.validate(tags, VOCABULARIES)
        self.assertEqual(problems, [])

    def test_empty_signal_is_refused(self):
        tags = valid_tags(signal="")
        problems = enrollmenttags.validate(tags, VOCABULARIES)
        self.assertTrue(any("signal" in p for p in problems))

    def test_missing_vocabulary_for_dynamic_field_is_a_problem(self):
        """A dynamic field with no supplied vocabulary cannot be validated."""
        tags = valid_tags()
        problems = enrollmenttags.validate(tags, {})
        dynamic_problems = [p for p in problems
                            if any(f in p for f in enrollmenttags.CLOSED_DYNAMIC)]
        self.assertTrue(len(dynamic_problems) > 0)


class BackTaggingFromEnrollmentArtifact(unittest.TestCase):
    """A lead enrolled before this task existed can be tagged afterwards.

    The first real cohort is already in the queue. If the schema cannot
    tag them from their enrollment artifacts, they are permanently
    unmeasurable.
    """

    def test_backfill_from_artifact(self):
        record = make_record()
        artifact = {
            "persona": "champion",
            "angle": "finance",
            "subject_variant": "pain_opener",
            "sender": "anna@resonate.test",
            "timezone_cohort": "emea",
            "source": "supplier_file",
            "signal": "posted about time-tracking pain",
        }
        enrollmenttags.backfill(record, artifact, VOCABULARIES)
        tags = enrollmenttags.tags_on(record)
        self.assertEqual(tags["persona"], "champion")
        self.assertEqual(tags["source"], "supplier_file")
        self.assertEqual(tags["signal"], "posted about time-tracking pain")

    def test_backfill_refuses_unknown_values(self):
        """Back-tagging is not a bypass for validation."""
        record = make_record()
        artifact = valid_tags(source="cold_email_tool")
        with self.assertRaises(enrollmenttags.UnknownTagValue):
            enrollmenttags.backfill(record, artifact, VOCABULARIES)

    def test_backfill_partial_artifact(self):
        """An artifact missing some fields tags only what it has."""
        record = make_record()
        artifact = {"persona": "champion", "source": "reengagement"}
        enrollmenttags.backfill(record, artifact, VOCABULARIES)
        tags = enrollmenttags.tags_on(record)
        self.assertEqual(tags["persona"], "champion")
        self.assertEqual(tags["source"], "reengagement")
        self.assertNotIn("angle", tags)

    def test_apply_writes_tags_to_record(self):
        record = make_record()
        tags = valid_tags()
        enrollmenttags.apply(record, tags, VOCABULARIES)
        stored = enrollmenttags.tags_on(record)
        self.assertEqual(stored["persona"], "champion")
        self.assertEqual(stored["angle"], "finance")

    def test_tags_on_empty_record(self):
        record = make_record()
        self.assertEqual(enrollmenttags.tags_on(record), {})


class UnderThirtyRefusesPercentage(unittest.TestCase):
    """A cell with fewer than 30 sends refuses its percentage.

    Two replies out of three sends is not a 67% reply rate and a report
    that prints it will be believed.
    """

    def _record_with_outcomes(self, rid, sent=False, replied=False,
                               positive=False, bounced=False,
                               unsubscribed=False, tags=None):
        events = []
        contacts = []
        if sent:
            events.append({"type": "confirmed_touch", "contact": "k1"})
        if replied:
            events.append({"type": "reply", "contact": "k1",
                           "sentiment": "positive" if positive else "neutral"})
        if bounced:
            events.append({"type": "bounce", "contact": "k1"})
        if unsubscribed:
            events.append({"type": "unsubscribe", "contact": "k1"})
        rec = make_record(rid=rid, events=events, contacts=contacts)
        if tags:
            rec[enrollmenttags.TAG_KEY] = tags
        return rec

    def test_below_30_sends_refuses_rate(self):
        tags = valid_tags()
        records = [
            self._record_with_outcomes(f"lead-{i}", sent=True, replied=True,
                                       tags=tags)
            for i in range(5)
        ]
        report = enrollmenttags.nightly_report(records)
        cells = [c for c in report["overall"]
                 if c["tag_field"] == "source"
                 and c["tag_value"] == "supplier_file"]
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        for rate_name, rate in cell["rates"].items():
            self.assertTrue(rate["refused"],
                            f"{rate_name} should be refused with "
                            f"{cell['counts']['sent']} sends")
            self.assertIsNone(rate["value"])

    def test_at_30_sends_rate_is_computed(self):
        tags = valid_tags()
        records = [
            self._record_with_outcomes(f"lead-{i}", sent=True,
                                       replied=(i < 3),
                                       tags=tags)
            for i in range(30)
        ]
        report = enrollmenttags.nightly_report(records)
        cells = [c for c in report["overall"]
                 if c["tag_field"] == "source"
                 and c["tag_value"] == "supplier_file"]
        self.assertEqual(len(cells), 1)
        cell = cells[0]
        reply_rate = cell["rates"]["reply_rate"]
        self.assertFalse(reply_rate["refused"])
        self.assertAlmostEqual(reply_rate["value"], 3 / 30)

    def test_refused_rate_still_shows_counts(self):
        tags = valid_tags()
        records = [
            self._record_with_outcomes("lead-0", sent=True, replied=True,
                                       tags=tags),
            self._record_with_outcomes("lead-1", sent=True, replied=True,
                                       tags=tags),
        ]
        report = enrollmenttags.nightly_report(records)
        cell = [c for c in report["overall"]
                if c["tag_field"] == "source"][0]
        rate = cell["rates"]["reply_rate"]
        self.assertTrue(rate["refused"])
        self.assertEqual(rate["numerator"], 2)
        self.assertEqual(rate["denominator"], 2)
        self.assertIn("below the", rate["reason"])


class RateNamesItsDenominator(unittest.TestCase):
    """Every rate says what it divided by.

    A reply rate over enrolled is not a reply rate. The report must
    name which denominator each rate used, so a reader can tell whether
    they are looking at replies/sent or replies/enrolled.
    """

    def _record_with_outcomes(self, rid, sent=False, replied=False,
                               tags=None):
        events = []
        if sent:
            events.append({"type": "confirmed_touch", "contact": "k1"})
        if replied:
            events.append({"type": "reply", "contact": "k1",
                           "sentiment": "positive"})
        rec = make_record(rid=rid, events=events)
        if tags:
            rec[enrollmenttags.TAG_KEY] = tags
        return rec

    def test_rate_definitions_name_their_denominator(self):
        for name, defn in enrollmenttags.RATE_DEFINITIONS.items():
            self.assertIn("denominator", defn,
                          f"{name} has no denominator")
            self.assertIn("numerator", defn,
                          f"{name} has no numerator")
            self.assertIn("label", defn,
                          f"{name} has no label")

    def test_report_includes_rate_definitions(self):
        report = enrollmenttags.nightly_report([])
        self.assertIn("rate_definitions", report)
        for name in enrollmenttags.RATE_DEFINITIONS:
            self.assertIn(name, report["rate_definitions"])
            defn = report["rate_definitions"][name]
            self.assertIn("denominator", defn)
            self.assertIn("label", defn)

    def test_each_rate_carries_its_denominator(self):
        tags = valid_tags()
        records = [
            self._record_with_outcomes(f"lead-{i}", sent=True, replied=True,
                                       tags=tags)
            for i in range(30)
        ]
        report = enrollmenttags.nightly_report(records)
        cell = report["overall"][0]
        for rate_name, rate in cell["rates"].items():
            self.assertIn("denominator", rate,
                          f"{rate_name} has no denominator in output")
            self.assertIn("numerator", rate,
                          f"{rate_name} has no numerator in output")
            self.assertIn("label", rate,
                          f"{rate_name} has no label in output")
            self.assertEqual(rate["denominator"], 30)

    def test_reply_rate_uses_sent_as_denominator_not_enrolled(self):
        """A reply rate over enrolled is not a reply rate."""
        defn = enrollmenttags.RATE_DEFINITIONS["reply_rate"]
        self.assertEqual(defn["denominator"], enrollmenttags.SENT)
        self.assertNotEqual(defn["denominator"], enrollmenttags.ENROLLED)

    def test_enrolled_count_is_in_counts_not_used_as_rate_denominator(self):
        tags = valid_tags()
        records = [
            self._record_with_outcomes("lead-0", sent=False, tags=tags),
            self._record_with_outcomes("lead-1", sent=True, replied=True,
                                       tags=tags),
        ]
        report = enrollmenttags.nightly_report(records)
        cell = [c for c in report["overall"]
                if c["tag_field"] == "source"][0]
        self.assertEqual(cell["counts"]["enrolled"], 2)
        self.assertEqual(cell["counts"]["sent"], 1)
        reply_rate = cell["rates"]["reply_rate"]
        self.assertEqual(reply_rate["denominator"], 1)


class ReportStructure(unittest.TestCase):
    """The report has the shape an operator can read."""

    def _tagged_record(self, rid, source="supplier_file", sent=False):
        events = []
        if sent:
            events.append({"type": "confirmed_touch", "contact": "k1"})
        rec = make_record(rid=rid, events=events)
        rec[enrollmenttags.TAG_KEY] = valid_tags(source=source)
        return rec

    def test_report_has_generated_at(self):
        report = enrollmenttags.nightly_report([])
        self.assertIn("generated_at", report)

    def test_report_has_minimum_sends(self):
        report = enrollmenttags.nightly_report([])
        self.assertEqual(report["minimum_sends_for_rate"], 30)

    def test_report_separates_per_campaign_and_overall(self):
        report = enrollmenttags.nightly_report([])
        self.assertIn("cells", report)
        self.assertIn("overall", report)

    def test_records_without_tags_are_excluded(self):
        records = [make_record("lead-1")]
        report = enrollmenttags.nightly_report(records)
        self.assertEqual(report["cells"], [])
        self.assertEqual(report["overall"], [])

    def test_per_campaign_cells(self):
        records = [self._tagged_record("lead-1", sent=True)]
        campaigns = [{"campaign_id": "camp-1", "record_ids": ["lead-1"]}]
        report = enrollmenttags.nightly_report(records, campaigns=campaigns)
        campaign_cells = [c for c in report["cells"]
                          if c["campaign_id"] == "camp-1"]
        self.assertTrue(len(campaign_cells) > 0)


if __name__ == "__main__":
    unittest.main()
