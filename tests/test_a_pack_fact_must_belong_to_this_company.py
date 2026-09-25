"""A pack fact must belong to THIS company, not merely exist.

TASK-294.  The 50-of-71 shape: a fact that belongs to a DIFFERENT company
with a plausible name must be REFUSED, not admitted.  `identity_of` is the
one test and this test imports it; a second copy is how the send path and
the check come to disagree about who a fact belongs to.

One constructed failure per rule, plus the identity shape, plus the
arithmetic invariant, plus the vacuous-exit contract.
"""
import json
import os
import shutil
import tempfile
import unittest

from scripts.qa import check_lead_pack
from src.packfacts import ADMITTED, REFUSED, UNVERIFIABLE, identity_of


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class _WorkspaceTest(unittest.TestCase):
    """A temp workspace per test, torn down after."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="qa-lead-pack-")
        self.ws = os.path.join(self.tmp, "work")
        os.makedirs(os.path.join(self.ws, "stage"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _populate(self, records, rendered):
        _write_jsonl(os.path.join(self.ws, "queue.jsonl"), records)
        _write_jsonl(os.path.join(self.ws, "stage", "s7-copy.jsonl"), rendered)


class TestPackPresent(_WorkspaceTest):
    """Rule 1: a lead with no admitted facts fires pack_present."""

    def test_lead_with_zero_admitted_facts_fires(self):
        rec = {
            "id": "rec-001",
            "domain": "example.com",
            "contacts": [{"email": "jane@example.com"}],
            "research": [
                {"fact": "Acme Corp raised $5M",
                 "companyWebsite": "other.com",
                 "source_url": "https://other.com/news",
                 "published_at": "2026-01-01"},
            ],
        }
        rendered = [{
            "id": "lead-001",
            "email": "jane@example.com",
            "variables": {
                "body_1": "Hi Jane, I noticed your company.",
                "body_2": "Would love to chat.",
            },
        }]
        self._populate([rec], rendered)
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("lead-001", result["offenders"]["pack_present"])
        self.assertEqual(result["three_set_counts"]["uncovered"], 1)
        self.assertEqual(result["three_set_counts"]["admitted"], 0)
        self.assertEqual(result["three_set_counts"]["no_record"], 0)
        self.assertEqual(
            sum(result["three_set_counts"].values()), result["subjects"])


class TestFactWellFormed(_WorkspaceTest):
    """Rule 2: each admitted fact must carry source, date AND snippet."""

    def test_fact_missing_source_fires(self):
        rec = {
            "id": "rec-002",
            "domain": "example.com",
            "contacts": [{"email": "bob@example.com"}],
            "research": [
                {"fact": "Acme launched a new product",
                 "companyWebsite": "example.com",
                 "source_url": "",
                 "published_at": "2026-03-15"},
            ],
        }
        rendered = [{
            "id": "lead-002",
            "email": "bob@example.com",
            "variables": {
                "body_1": "Hi Bob, saw Acme launched a new product.",
                "body_2": "Let's talk.",
            },
        }]
        self._populate([rec], rendered)
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertIn("lead-002",
                       result["offenders"]["fact_has_source_date_snippet"])
        self.assertEqual(result["missing_elements"]["source"], 1)

    def test_fact_missing_date_fires(self):
        rec = {
            "id": "rec-003",
            "domain": "example.com",
            "contacts": [{"email": "carol@example.com"}],
            "research": [
                {"fact": "Acme expanded to Berlin",
                 "companyWebsite": "example.com",
                 "source_url": "https://example.com/blog",
                 "published_at": ""},
            ],
        }
        rendered = [{
            "id": "lead-003",
            "email": "carol@example.com",
            "variables": {
                "body_1": "Hi Carol, Acme expanded to Berlin recently.",
                "body_2": "Chat soon?",
            },
        }]
        self._populate([rec], rendered)
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertIn("lead-003",
                       result["offenders"]["fact_has_source_date_snippet"])
        self.assertEqual(result["missing_elements"]["date"], 1)

    def test_fact_with_all_three_does_not_fire(self):
        rec = {
            "id": "rec-004",
            "domain": "example.com",
            "contacts": [{"email": "dan@example.com"}],
            "research": [
                {"fact": "Acme grew 40 percent year over year",
                 "companyWebsite": "example.com",
                 "source_url": "https://example.com/press",
                 "published_at": "2026-06-01"},
            ],
        }
        rendered = [{
            "id": "lead-004",
            "email": "dan@example.com",
            "variables": {
                "body_1": "Hi Dan, Acme grew 40 percent year over year.",
                "body_2": "Would love to help.",
            },
        }]
        self._populate([rec], rendered)
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertEqual(
            result["counts"]["fact_has_source_date_snippet"], 0)


class TestOpenerUsesPackFact(_WorkspaceTest):
    """Rule 3: the first line of step 1 must reference a pack fact."""

    def test_generic_opener_fires(self):
        rec = {
            "id": "rec-005",
            "domain": "example.com",
            "contacts": [{"email": "eve@example.com"}],
            "research": [
                {"fact": "Acme opened a Berlin office",
                 "companyWebsite": "example.com",
                 "source_url": "https://example.com/news",
                 "published_at": "2026-02-01"},
            ],
        }
        rendered = [{
            "id": "lead-005",
            "email": "eve@example.com",
            "variables": {
                "body_1": "Hi, I wanted to reach out about growth.",
                "body_2": "Let me know.",
            },
        }]
        self._populate([rec], rendered)
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertIn("lead-005",
                       result["offenders"]["opener_uses_a_pack_fact"])

    def test_opener_referencing_pack_fact_does_not_fire(self):
        rec = {
            "id": "rec-006",
            "domain": "example.com",
            "contacts": [{"email": "frank@example.com"}],
            "research": [
                {"fact": "Acme opened a Berlin office last quarter",
                 "companyWebsite": "example.com",
                 "source_url": "https://example.com/news",
                 "published_at": "2026-02-01"},
            ],
        }
        rendered = [{
            "id": "lead-006",
            "email": "frank@example.com",
            "variables": {
                "body_1": "Hi Frank, Acme opened a Berlin office last quarter.",
                "body_2": "Would love to help.",
            },
        }]
        self._populate([rec], rendered)
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertEqual(
            result["counts"]["opener_uses_a_pack_fact"], 0)


class TestNoClaimOutsidePack(_WorkspaceTest):
    """Rule 4: no company claim with untraceable specifics."""

    def test_invented_specific_fires(self):
        rec = {
            "id": "rec-007",
            "domain": "example.com",
            "contacts": [{"email": "grace@example.com"}],
            "research": [
                {"fact": "Acme raised Series B",
                 "companyWebsite": "example.com",
                 "source_url": "https://example.com/press",
                 "published_at": "2026-04-01"},
            ],
        }
        rendered = [{
            "id": "lead-007",
            "email": "grace@example.com",
            "variables": {
                "body_1": "Hi Grace, Acme raised Series B.",
                "body_2": "You raised $50 million which is impressive.",
            },
        }]
        self._populate([rec], rendered)
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertIn("lead-007",
                       result["offenders"]["no_claim_outside_the_pack"])


class TestIdentityNotPresence(_WorkspaceTest):
    """The 50-of-71 shape: a fact belonging to a different company.

    `companyName` is a text filter and not an identity match.  A fact
    about "Acme Analytics" when the account is "Acme Corp" must be
    REFUSED, not admitted.  `identity_of` is the one test.
    """

    def test_fact_from_different_company_is_refused(self):
        row = {
            "fact": "Acme Analytics hired 20 engineers",
            "companyWebsite": "acme-analytics.com",
            "source_url": "https://acme-analytics.com/careers",
        }
        verdict = identity_of(row, "acme-corp.com")
        self.assertEqual(verdict, REFUSED)

    def test_plausible_name_same_domain_is_admitted(self):
        row = {
            "fact": "Acme Corp opened Berlin office",
            "companyWebsite": "acme-corp.com",
            "source_url": "https://acme-corp.com/blog/berlin",
        }
        verdict = identity_of(row, "acme-corp.com")
        self.assertEqual(verdict, ADMITTED)

    def test_no_website_no_source_is_unverifiable(self):
        row = {
            "fact": "Some company did something",
            "source_url": "",
        }
        verdict = identity_of(row, "example.com")
        self.assertEqual(verdict, UNVERIFIABLE)

    def test_refused_fact_does_not_count_as_admitted(self):
        rec = {
            "id": "rec-008",
            "domain": "acme-corp.com",
            "contacts": [{"email": "hank@acme-corp.com"}],
            "research": [
                {"fact": "Acme Analytics hired 20 engineers",
                 "companyWebsite": "acme-analytics.com",
                 "source_url": "https://acme-analytics.com/careers",
                 "published_at": "2026-05-01"},
            ],
        }
        rendered = [{
            "id": "lead-008",
            "email": "hank@acme-corp.com",
            "variables": {
                "body_1": "Hi Hank, I noticed your company.",
                "body_2": "Chat soon?",
            },
        }]
        self._populate([rec], rendered)
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertEqual(result["identity_totals"][REFUSED], 1)
        self.assertEqual(result["identity_totals"][ADMITTED], 0)
        self.assertIn("lead-008", result["offenders"]["pack_present"])
        self.assertEqual(result["three_set_counts"]["uncovered"], 1)

    def test_unverifiable_is_not_a_pass(self):
        rec = {
            "id": "rec-009",
            "domain": "acme-corp.com",
            "contacts": [{"email": "iris@acme-corp.com"}],
            "research": [
                {"fact": "Someone did something",
                 "source_url": "",
                 "published_at": "2026-01-01"},
            ],
        }
        rendered = [{
            "id": "lead-009",
            "email": "iris@acme-corp.com",
            "variables": {
                "body_1": "Hi Iris, I noticed your company.",
                "body_2": "Chat?",
            },
        }]
        self._populate([rec], rendered)
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertEqual(result["identity_totals"][UNVERIFIABLE], 1)
        self.assertEqual(result["identity_totals"][ADMITTED], 0)
        self.assertIn("lead-009", result["offenders"]["pack_present"])
        self.assertIn("lead-009",
                       result["three_sets"]["uncovered"])


class TestNoRecord(_WorkspaceTest):
    """A rendered row matching no queue record is reported, not dropped."""

    def test_unmatched_row_lands_in_no_record(self):
        rendered = [{
            "id": "lead-010",
            "email": "nobody@unknown.com",
            "variables": {
                "body_1": "Hello.",
                "body_2": "Bye.",
            },
        }]
        self._populate([], rendered)
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertEqual(result["three_set_counts"]["no_record"], 1)
        self.assertIn("lead-010", result["three_sets"]["no_record"])
        self.assertEqual(
            sum(result["three_set_counts"].values()), result["subjects"])


class TestThreeSetsAddUp(_WorkspaceTest):
    """The three sets must sum to subjects."""

    def test_mixed_sets_sum_to_subjects(self):
        rec_admitted = {
            "id": "rec-011",
            "domain": "good.com",
            "contacts": [{"email": "a@good.com"}],
            "research": [
                {"fact": "Good Corp grew revenue",
                 "companyWebsite": "good.com",
                 "source_url": "https://good.com/news",
                 "published_at": "2026-01-01"},
            ],
        }
        rec_refused = {
            "id": "rec-012",
            "domain": "bad.com",
            "contacts": [{"email": "b@bad.com"}],
            "research": [
                {"fact": "Other Corp did something",
                 "companyWebsite": "other.com",
                 "source_url": "https://other.com/news",
                 "published_at": "2026-01-01"},
            ],
        }
        rendered = [
            {"id": "lead-011", "email": "a@good.com",
             "variables": {"body_1": "Good Corp grew revenue.",
                           "body_2": "Chat?"}},
            {"id": "lead-012", "email": "b@bad.com",
             "variables": {"body_1": "Hello.", "body_2": "Bye."}},
            {"id": "lead-013", "email": "nobody@nowhere.com",
             "variables": {"body_1": "Hello.", "body_2": "Bye."}},
        ]
        self._populate([rec_admitted, rec_refused], rendered)
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertEqual(result["subjects"], 3)
        self.assertEqual(
            sum(result["three_set_counts"].values()), 3)
        self.assertEqual(result["three_set_counts"]["admitted"], 1)
        self.assertEqual(result["three_set_counts"]["uncovered"], 1)
        self.assertEqual(result["three_set_counts"]["no_record"], 1)
        self.assertTrue(result["arithmetic_ok"])


class TestVacuousExit(_WorkspaceTest):
    """subjects == 0 exits 2 with a stated reason."""

    def test_empty_rendered_is_vacuous(self):
        self._populate([], [])
        result = check_lead_pack.run(workspaces=self.ws)

        self.assertEqual(result["verdict"], "VACUOUS")
        self.assertEqual(result["subjects"], 0)


class TestAuditPackCache(unittest.TestCase):
    """The negative control finds the 50-of-71 shape."""

    def test_missing_file_reports_not_found(self):
        out = check_lead_pack.audit_pack_cache("/nonexistent/path.json")
        self.assertIn("FILE NOT FOUND", out)

    def test_cache_with_wrong_company_rows_reports_them(self):
        cache = {
            "entry1": {
                "domain": "acme-corp.com",
                "profile": "open_roles",
                "rows": [
                    {"fact": "Acme Analytics hired engineers",
                     "companyWebsite": "acme-analytics.com",
                     "source_url": "https://acme-analytics.com/jobs"},
                    {"fact": "Other Corp hired designers",
                     "companyWebsite": "other-corp.com",
                     "source_url": "https://other-corp.com/careers"},
                ],
            },
        }
        tmp = tempfile.mkdtemp(prefix="qa-cache-")
        path = os.path.join(tmp, "cache.json")
        with open(path, "w") as fh:
            json.dump(cache, fh)
        try:
            out = check_lead_pack.audit_pack_cache(path)
            self.assertIn("accounts where NO row was this company: 1", out)
            self.assertIn("refused", out.lower())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestIdentityOfDirectly(unittest.TestCase):
    """`identity_of` is the one test.  These assert its three answers."""

    def test_admitted_when_domain_matches(self):
        row = {"companyWebsite": "example.com"}
        self.assertEqual(identity_of(row, "example.com"), ADMITTED)

    def test_refused_when_domain_differs(self):
        row = {"companyWebsite": "other.com"}
        self.assertEqual(identity_of(row, "example.com"), REFUSED)

    def test_unverifiable_when_no_identity_signal(self):
        row = {"fact": "something happened"}
        self.assertEqual(identity_of(row, "example.com"), UNVERIFIABLE)

    def test_www_is_not_identity(self):
        row = {"companyWebsite": "www.example.com"}
        self.assertEqual(identity_of(row, "example.com"), ADMITTED)

    def test_record_id_mismatch_is_refused(self):
        row = {"record_id": "rec-999", "companyWebsite": "example.com"}
        self.assertEqual(identity_of(row, "example.com",
                                     record_id="rec-001"), REFUSED)

    def test_source_url_host_used_as_fallback(self):
        row = {"source_url": "https://example.com/blog/post"}
        self.assertEqual(identity_of(row, "example.com"), ADMITTED)

    def test_linkedin_host_is_unverifiable_not_refused(self):
        row = {"source_url": "https://www.linkedin.com/posts/something"}
        self.assertEqual(identity_of(row, "example.com"), UNVERIFIABLE)

    def test_empty_domain_is_refused(self):
        row = {"companyWebsite": "example.com"}
        self.assertEqual(identity_of(row, ""), REFUSED)


class TestReportLines(unittest.TestCase):
    """The report says unverifiable is NOT a pass."""

    def test_report_contains_not_a_pass(self):
        result = check_lead_pack._error("test")
        result["identity_totals"] = {ADMITTED: 0, REFUSED: 0,
                                     UNVERIFIABLE: 5}
        lines = check_lead_pack.report_lines(result)
        text = "\n".join(lines)
        self.assertIn("NOT a pass", text)


if __name__ == "__main__":
    unittest.main()
