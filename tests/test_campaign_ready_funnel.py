"""Tests for the campaign-ready funnel report.

Every funnel stage and every blocker category is tested with an invented
estate of known answers. The script reads work/queue.jsonl via src.store,
so tests point the QUEUE override at a temp directory.

Nothing here copies real client data. Every example is invented.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src import (approval, cadence, cadencelibrary, clients, store,
                 verification)

# Import the script under test.
import scripts.campaign_ready_funnel as funnel

EMAIL_KEYS = funnel.EMAIL_KEYS
LI_KEYS = funnel.LI_KEYS


def _make_contact(key, name="Tester", email=None, linkedin=None,
                  sendable=True, no_linkedin=False):
    """A contact with proper verification evidence."""
    email = email or f"{key}@example.test"
    person = {
        "key": key, "name": name, "email": email,
        "title": "Tester",
    }
    if no_linkedin:
        person["linkedin"] = None
    else:
        person["linkedin"] = linkedin or f"https://linkedin.com/in/{key}"
    if sendable:
        evidence = [
            verification.result("contactout", verification.S_VALID, email),
            verification.result("deliverable", verification.S_VALID, email),
        ]
    else:
        evidence = [
            verification.result("contactout", verification.S_ACCEPT_ALL,
                                email, catch_all=True),
        ]
    verification.apply(person, verification.decide(evidence), evidence)
    return person


def _make_record(rid, domain, company="Acme", client="productive",
                 qualified=True, contacts=None, cadence_steps=None):
    """A queue record with the given properties."""
    rec = store.new_record(rid, "cold", client, company, domain)
    rec["state"] = "drafted"
    rec["hook"] = f"{company} test hook"
    rec["company_facts"] = {"industry": "Tech", "employees": 50}
    if qualified:
        rec["qualification"] = {
            "verdict": {
                "icp_status": "qualified",
                "icp_confidence": "high",
                "positive_signals": ["signal_a"],
                "negative_signals": [],
            }
        }
    else:
        rec["qualification"] = {
            "verdict": {
                "icp_status": "rejected",
                "icp_confidence": "high",
                "positive_signals": [],
                "negative_signals": ["signal_x"],
            }
        }
    rec["contacts"] = contacts or []
    if cadence_steps:
        rec["cadence"] = cadence_steps
    return rec


<<<<<<< HEAD
=======
# SIX WHOLLY DIFFERENT BODIES, one per rung. Prefixing a shared paragraph was
# not enough: `quality.repetition_across_rungs` counts distinctive words shared
# between steps, so a common tail still collided. Every fixture contact failed
# repetition, and any test asserting a blocker that comes AFTER it got
# `step_fails_repetition` instead.
#
# Invented, and long enough to clear the word floor lint applies.
DISTINCT_BODIES = (
    "A question about how delivery gets planned where you are. Most teams "
    "your size decide allocation weekly and discover the consequences "
    "monthly, and the gap between those two is where the surprises live. "
    "How does that sequencing work for you today, or has it already been "
    "solved somewhere upstream of the schedule?",
    "A different angle entirely. Where does the month actually go once "
    "everything is booked? The teams we talk to find the answer sits in "
    "three systems that do not reconcile, and nobody owns the join. Is that "
    "roughly the shape of it there, or does one of them already win?",
    "One concrete example from an agency of about your headcount. They "
    "stopped reconstructing margin after delivery and started watching it "
    "during, which changed which projects got attention rather than which "
    "got explained. What would have to be true for that to be useful to "
    "you rather than merely interesting?",
    "A short note and a single question, because the last few have been "
    "long. When a project drifts, who notices first, and roughly how many "
    "days later than you would want? That number is usually the whole "
    "argument, and it is the only thing worth knowing here.",
    "Closing the loop and leaving it there. No new pitch and nothing to "
    "read. If this is not the year for it, an easy no is genuinely useful "
    "and I will stop. If it is worth revisiting later, say when and I will "
    "come back then rather than sooner.",
    "A last thought about resourcing before I stop writing. The constraint "
    "is rarely the tooling and almost always who is available in the week "
    "the work lands. If that is familiar, there may be something here; if "
    "not, I have misread it and will leave you alone.",
)


>>>>>>> master
def _approved_email_steps(contact_key, n, body="Hi there, I noticed your "
                          "company runs delivery across several teams and "
                          "the pattern we see in teams that size is that "
                          "utilisation and margin are only known at the end "
                          "of the month which is after the month when "
                          "anything could have been done about them and "
                          "most operations leads we speak to lose the best "
                          "part of a day every month reconciling time "
                          "before they can answer a question anyone actually "
                          "asked so I wanted to see if that is roughly how "
                          "it works with you today or have you already put "
                          "something in place for it"):
    """Build cadence steps with n email steps approved."""
    import hashlib
    steps = {}
    for i, key in enumerate(EMAIL_KEYS):
        if i < n:
<<<<<<< HEAD
            step = {"channel": "email", "subject": "Test subject",
                    "body": body, "generated": True}
=======
            # EACH STEP GETS ITS OWN WORDS. Every step carried the identical
            # body, so the moment the funnel started applying the repetition
            # gate - which is the gate that decides this cohort - every
            # fixture contact failed it, and tests asserting a LATER blocker
            # got `step_fails_repetition` instead. A fixture that repeats
            # itself cannot exercise anything downstream of the repetition
            # check.
            step = {"channel": "email",
                    "subject": f"Test subject {i + 1}",
                    "body": DISTINCT_BODIES[i % len(DISTINCT_BODIES)],
                    "generated": True}
>>>>>>> master
            fp_material = " ".join([
                str(step.get("channel") or ""),
                str(step.get("subject") or ""),
                str(step.get("body") or ""),
                str(step.get("note") or ""),
            ])
            fp = hashlib.sha256(fp_material.encode("utf-8")).hexdigest()[:16]
            step["approval"] = {"fingerprint": fp, "by": "test",
                                "at": "2026-09-14T00:00:00+00:00"}
            steps[key] = step
    return {contact_key: steps}


def _approved_li_steps(contact_key, n, has_url=True):
    """Build cadence steps with n LinkedIn steps approved."""
    import hashlib
    steps = {}
    for i, key in enumerate(LI_KEYS):
        if i < n:
            step = {"channel": "linkedin", "note": "Test note",
                    "generated": True}
            fp_material = " ".join([
                str(step.get("channel") or ""),
                str(step.get("subject") or ""),
                str(step.get("body") or ""),
                str(step.get("note") or ""),
            ])
            fp = hashlib.sha256(fp_material.encode("utf-8")).hexdigest()[:16]
            step["approval"] = {"fingerprint": fp, "by": "test",
                                "at": "2026-09-14T00:00:00+00:00"}
            steps[key] = step
    return {contact_key: steps}


def _merge_cadence(*cadence_maps):
    """Merge multiple cadence maps for the same contact."""
    result = {}
    for cmap in cadence_maps:
        for contact_key, steps in cmap.items():
            result.setdefault(contact_key, {}).update(steps)
    return result


class FunnelStageTests(unittest.TestCase):
    """Each funnel stage with a known-answer estate."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-funnel-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._old_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue

    def tearDown(self):
        if self._old_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._old_queue
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _save(self, recs):
        store.save(recs)

    def test_empty_queue(self):
        """No records: every funnel stage is zero."""
        self._save([])
        result = funnel.compute_funnel(store.load(), client="productive")
        f = result["funnel"]
        self.assertEqual(f["productive_domains"], 0)
        self.assertEqual(f["icp_pass"], 0)
        self.assertEqual(f["email_ready"], 0)
        self.assertEqual(f["linkedin_ready"], 0)

    def test_domains_count_all_records_for_client(self):
        """productive_domains counts every record for the client."""
        recs = [_make_record(f"r{i}", f"d{i}.test") for i in range(5)]
        self._save(recs)
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(result["funnel"]["productive_domains"], 5)

    def test_icp_pass_counts_qualified(self):
        """icp_pass counts only qualified records."""
        recs = [
            _make_record("r1", "d1.test", qualified=True),
            _make_record("r2", "d2.test", qualified=True),
            _make_record("r3", "d3.test", qualified=False),
        ]
        self._save(recs)
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(result["funnel"]["icp_pass"], 2)

    def test_verified_sendable_contact(self):
        """A qualified record with a sendable contact counts."""
        c = _make_contact("c1", sendable=True)
        rec = _make_record("r1", "d1.test", qualified=True, contacts=[c])
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(result["funnel"]["verified_sendable_contact"], 1)

    def test_unverified_contact_does_not_count(self):
        """A contact that is not sendable does not count."""
        c = _make_contact("c1", sendable=False)
        rec = _make_record("r1", "d1.test", qualified=True, contacts=[c])
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(result["funnel"]["verified_sendable_contact"], 0)

    def test_email_steps_approved_count(self):
        """A contact with all email steps approved counts."""
        c = _make_contact("c1", sendable=True)
        cad = _approved_email_steps("c1", len(EMAIL_KEYS))
        rec = _make_record("r1", "d1.test", qualified=True,
                           contacts=[c], cadence_steps=cad)
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(
            result["funnel"]["contacts_with_email_steps_approved"], 1)

    def test_partial_email_steps_do_not_count(self):
        """A contact with only 3 of 5 email steps approved does not count."""
        c = _make_contact("c1", sendable=True)
        cad = _approved_email_steps("c1", 3)
        rec = _make_record("r1", "d1.test", qualified=True,
                           contacts=[c], cadence_steps=cad)
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(
            result["funnel"]["contacts_with_email_steps_approved"], 0)

    def test_linkedin_steps_with_url(self):
        """A contact with all LI steps approved AND a URL counts."""
        c = _make_contact("c1", sendable=True,
                          linkedin="https://linkedin.com/in/c1")
        cad = _approved_li_steps("c1", len(LI_KEYS))
        rec = _make_record("r1", "d1.test", qualified=True,
                           contacts=[c], cadence_steps=cad)
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(
            result["funnel"]["contacts_with_li_steps_approved_and_url"], 1)

    def test_linkedin_steps_without_url_do_not_count(self):
        """A contact with all LI steps approved but no URL does not count."""
        c = _make_contact("c1", sendable=True, no_linkedin=True)
        cad = _approved_li_steps("c1", len(LI_KEYS))
        rec = _make_record("r1", "d1.test", qualified=True,
                           contacts=[c], cadence_steps=cad)
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(
            result["funnel"]["contacts_with_li_steps_approved_and_url"], 0)


class BlockerTests(unittest.TestCase):
    """Each blocker category with a known-answer estate."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-funnel-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._old_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue

    def tearDown(self):
        if self._old_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._old_queue
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _save(self, recs):
        store.save(recs)

    def test_dropped_record_blocker(self):
        rec = _make_record("r1", "d1.test", qualified=True)
        rec["state"] = "dropped"
        rec["drop_reason"] = "out of geo"
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(len(result["blocked_accounts"]), 1)
        self.assertEqual(result["blocked_accounts"][0]["blocker"],
                         funnel.RECORD_DROPPED)

    def test_suppressed_record_blocker(self):
        rec = _make_record("r1", "d1.test", qualified=True)
        rec["suppression"] = {"suppressed": True}
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(len(result["blocked_accounts"]), 1)
        self.assertEqual(result["blocked_accounts"][0]["blocker"],
                         funnel.SUPPRESSED)

    def test_icp_not_qualified_blocker(self):
        rec = _make_record("r1", "d1.test", qualified=False)
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(len(result["blocked_accounts"]), 1)
        self.assertEqual(result["blocked_accounts"][0]["blocker"],
                         funnel.ICP_NOT_QUALIFIED)

    def test_no_company_blocker(self):
        c = _make_contact("c1", sendable=True)
        rec = _make_record("r1", "d1.test", company="", qualified=True,
                           contacts=[c])
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(len(result["blocked_accounts"]), 1)
        self.assertEqual(result["blocked_accounts"][0]["blocker"],
                         funnel.NO_USABLE_COMPANY)

    def test_no_contact_blocker(self):
        rec = _make_record("r1", "d1.test", qualified=True, contacts=[])
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        self.assertEqual(len(result["blocked_accounts"]), 1)
        self.assertEqual(result["blocked_accounts"][0]["blocker"],
                         funnel.NO_CONTACT)

    def test_not_sendable_blocker(self):
        c = _make_contact("c1", sendable=False)
        rec = _make_record("r1", "d1.test", qualified=True, contacts=[c])
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        blocked = result["blocked_accounts"]
        self.assertEqual(len(blocked), 1)
        contact_blockers = [cd["blocker"] for cd in blocked[0]["contacts"]]
        self.assertIn(funnel.NOT_SENDABLE, contact_blockers)

    def test_missing_email_steps_blocker(self):
        c = _make_contact("c1", sendable=True)
        cad = _approved_email_steps("c1", 2)
        rec = _make_record("r1", "d1.test", qualified=True,
                           contacts=[c], cadence_steps=cad)
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        blocked = result["blocked_accounts"]
        self.assertEqual(len(blocked), 1)
        contact_blockers = [cd["blocker"] for cd in blocked[0]["contacts"]]
        self.assertIn(funnel.MISSING_EMAIL_STEPS, contact_blockers)

    def test_missing_li_steps_blocker(self):
        c = _make_contact("c1", sendable=True)
        cad = _approved_email_steps("c1", len(EMAIL_KEYS))
        cad_li = _approved_li_steps("c1", 2)
        merged = _merge_cadence(cad, cad_li)
        rec = _make_record("r1", "d1.test", qualified=True,
                           contacts=[c], cadence_steps=merged)
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        blocked = result["blocked_accounts"]
        self.assertEqual(len(blocked), 1)
        contact_blockers = [cd["blocker"] for cd in blocked[0]["contacts"]]
        self.assertIn(funnel.MISSING_LI_STEPS, contact_blockers)


class GenerationPriorityTests(unittest.TestCase):
    """The 'next best generation run' list."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-funnel-")
        self.queue = os.path.join(self.tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(self.queue), exist_ok=True)
        self._old_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = self.queue

    def tearDown(self):
        if self._old_queue is None:
            os.environ.pop("QUEUE", None)
        else:
            os.environ["QUEUE"] = self._old_queue
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _save(self, recs):
        store.save(recs)

    def test_missing_steps_appear_in_generation_list(self):
        """A contact missing email steps should appear in the gen list."""
        c = _make_contact("c1", sendable=True)
        cad = _approved_email_steps("c1", 2)
        rec = _make_record("r1", "d1.test", qualified=True,
                           contacts=[c], cadence_steps=cad)
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        gen = result["generation_priority"]
        self.assertEqual(len(gen), 1)
        self.assertEqual(gen[0]["domain"], "d1.test")
        self.assertEqual(gen[0]["contacts_to_generate"], 1)

    def test_not_sendable_does_not_appear_in_generation_list(self):
        """A contact blocked on verification is not a generation problem."""
        c = _make_contact("c1", sendable=False)
        rec = _make_record("r1", "d1.test", qualified=True, contacts=[c])
        self._save([rec])
        result = funnel.compute_funnel(store.load(), client="productive")
        gen = result["generation_priority"]
        self.assertEqual(len(gen), 0)

    def test_generation_list_sorted_by_contacts_to_generate(self):
        """More contacts to generate = higher priority."""
        c1 = _make_contact("c1", sendable=True)
        c2 = _make_contact("c2", sendable=True)
        c3 = _make_contact("c3", sendable=True)
        cad1 = _approved_email_steps("c1", 1)
        cad2 = _approved_email_steps("c2", 1)
        cad3 = _approved_email_steps("c3", 1)
        merged = _merge_cadence(cad1, cad2, cad3)
        rec = _make_record("r1", "d1.test", qualified=True,
                           contacts=[c1, c2, c3], cadence_steps=merged)

        c4 = _make_contact("c4", sendable=True)
        cad4 = _approved_email_steps("c4", 1)
        rec2 = _make_record("r2", "d2.test", qualified=True,
                            contacts=[c4], cadence_steps=cad4)

        self._save([rec, rec2])
        result = funnel.compute_funnel(store.load(), client="productive")
        gen = result["generation_priority"]
        self.assertGreaterEqual(len(gen), 2)
        self.assertEqual(gen[0]["domain"], "d1.test")
        self.assertEqual(gen[0]["contacts_to_generate"], 3)
        self.assertEqual(gen[1]["domain"], "d2.test")
        self.assertEqual(gen[1]["contacts_to_generate"], 1)


class BlockerRankingTests(unittest.TestCase):
    """Blocked accounts are ranked by closeness to ready."""

    def test_lint_failure_ranks_above_missing_steps(self):
        """A contact that fails lint is closer to ready than one missing
        steps entirely."""
        rank_lint = funnel._blocker_rank(funnel.STEP_FAILS_LINT)
        rank_missing = funnel._blocker_rank(funnel.MISSING_EMAIL_STEPS)
        self.assertLess(rank_lint, rank_missing)

    def test_missing_steps_ranks_above_not_sendable(self):
        rank_missing = funnel._blocker_rank(funnel.MISSING_EMAIL_STEPS)
        rank_sendable = funnel._blocker_rank(funnel.NOT_SENDABLE)
        self.assertLess(rank_missing, rank_sendable)

    def test_not_sendable_ranks_above_no_contact(self):
        rank_sendable = funnel._blocker_rank(funnel.NOT_SENDABLE)
        rank_no_contact = funnel._blocker_rank(funnel.NO_CONTACT)
        self.assertLess(rank_sendable, rank_no_contact)


class FormatReportTests(unittest.TestCase):
    """The report formatter produces readable output."""

    def test_report_contains_funnel_stages(self):
        result = {
            "client": "productive",
            "funnel": {
                "productive_domains": 300,
                "icp_pass": 113,
                "verified_sendable_contact": 54,
                "usable_company_name": 45,
                "contacts_with_email_steps_approved": 20,
                "email_ready": 8,
                "contacts_with_li_steps_approved_and_url": 13,
                "linkedin_ready": 9,
            },
            "blocked_accounts": [],
            "generation_priority": [],
        }
        report = funnel.format_report(result)
        self.assertIn("productive domains", report)
        self.assertIn("300", report)
        self.assertIn("EMAIL-READY", report)
        self.assertIn("8", report)
        self.assertIn("LINKEDIN-READY", report)
        self.assertIn("9", report)

    def test_report_with_blocked_accounts(self):
        result = {
            "client": "productive",
            "funnel": {
                "productive_domains": 10,
                "icp_pass": 5,
                "verified_sendable_contact": 3,
                "usable_company_name": 3,
                "contacts_with_email_steps_approved": 1,
                "email_ready": 0,
                "contacts_with_li_steps_approved_and_url": 1,
                "linkedin_ready": 0,
            },
            "blocked_accounts": [
                {"record_id": "r1", "domain": "d1.test",
                 "company": "Acme", "blocker": "missing_email_steps",
                 "detail": "3 email step(s) not approved",
                 "rank": 2,
                 "contacts": [{"contact_key": "c1", "status": "blocked",
                               "blocker": "missing_email_steps",
                               "detail": "3 of 5"}]},
            ],
            "generation_priority": [
                {"domain": "d1.test", "company": "Acme",
                 "contacts_to_generate": 1, "total_contacts": 1,
                 "blockers": ["missing_email_steps"]},
            ],
        }
        report = funnel.format_report(result)
        self.assertIn("BLOCKED ACCOUNTS", report)
        self.assertIn("d1.test", report)
        self.assertIn("NEXT BEST GENERATION RUN", report)


class CallerVerification(unittest.TestCase):
    """THE RULE THAT DECIDED THREE REVIEWS: the script must be consumed,
    not merely exist. These tests prove the script is the entry point
    the operator would run."""

    def test_main_returns_zero(self):
        """The CLI entry point runs and returns 0."""
        tmp = tempfile.mkdtemp(prefix="rga-funnel-")
        queue = os.path.join(tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(queue), exist_ok=True)
        old_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = queue
        try:
            store.save([])
            rc = funnel.main(["--client", "productive", "--queue", queue])
            self.assertEqual(rc, 0)
        finally:
            if old_queue is None:
                os.environ.pop("QUEUE", None)
            else:
                os.environ["QUEUE"] = old_queue
            shutil.rmtree(tmp, ignore_errors=True)

    def test_json_output_is_valid(self):
        """The --json flag produces valid JSON."""
        import io
        tmp = tempfile.mkdtemp(prefix="rga-funnel-")
        queue = os.path.join(tmp, "work", "queue.jsonl")
        os.makedirs(os.path.dirname(queue), exist_ok=True)
        old_queue = os.environ.get("QUEUE")
        os.environ["QUEUE"] = queue
        try:
            store.save([])
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                funnel.main(["--client", "productive", "--json",
                             "--queue", queue])
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout
            parsed = json.loads(output)
            self.assertIn("funnel", parsed)
            self.assertIn("blocked_accounts", parsed)
            self.assertIn("generation_priority", parsed)
        finally:
            if old_queue is None:
                os.environ.pop("QUEUE", None)
            else:
                os.environ["QUEUE"] = old_queue
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
