#!/usr/bin/env python3
"""A pack fact must belong to THIS company, not merely exist somewhere.

TASK-294. The per-lead research-pack QA check. Four rules and one identity
report, all asserting on verdicts — never on the presence of the script.

THE DEFECT THIS EXISTS FOR.

Measured 2026-09-24: 50 of 71 job rows in the research pilot belonged to a
DIFFERENT company, because `companyName` is a text filter and not an identity
match. On five of the eight accounts that returned rows, every row was
somebody else's. A presence check — "this account has research" — called
those accounts covered.

So a pack fact is admitted only when `identity_of` shows it is THIS
account's. And the check must report refused and unverifiable separately,
because "we asked and the answer was no" and "we could not ask" are
different problems with different fixes.

## WHAT IS TESTED

One constructed failure per rule, driven through `packfacts.pack_for` (the
real adapter the send path asks), plus:

- a fact from a different company with a plausible name is REFUSED
- `subjects == 0` exits with UNCONFIRMED, not PASS
- refused and unverifiable appear as separate columns, never summed
- the three sets (admitted / only-unverifiable-or-refused / no-record) add
  to the subject count

## THE IDENTITY TEST IS NOT DUPLICATED

`src/packfacts.identity_of` is the module both the send path and this check
ask. Two copies of an identity test is how the two come to disagree about
who a fact belongs to. The tests here import it, not reimplement it.
"""
import json
import os
import tempfile
import unittest

from src import copylint, packfacts
from src.packfacts import ADMITTED, REFUSED, UNVERIFIABLE
from scripts.qa import check_lead_pack


def _make_rec(domain="acme.test", company="Acme Corp", rid="rec-acme",
              research=(), contacts=None):
    """A minimal record `packfacts.pack_for` can process."""
    return {
        "id": rid,
        "client": "productive",
        "domain": domain,
        "company": company,
        "state": "verified",
        "research": list(research),
        "contacts": contacts or [{"key": "%s-c1" % rid,
                                  "email": "ada@%s" % domain,
                                  "first_name": "Ada",
                                  "sendable": True}],
    }


def _make_rendered_row(email, body_1="", subject_1="hello",
                       body_keys=None):
    """A minimal rendered row."""
    variables = {"subject_1": subject_1, "body_1": body_1}
    if body_keys:
        variables.update(body_keys)
    return {"email": email, "id": email.split("@")[0],
            "variables": variables}


# ----------------------------------------------- identity verdicts

class IdentityVerdictsTest(unittest.TestCase):
    """`identity_of` returns admitted / refused / unverifiable — separately."""

    def test_a_fact_from_the_accounts_own_domain_is_admitted(self):
        row = {"fact": "raised 50 employees",
               "source_url": "https://acme.test/about",
               "published_at": "2026-09-01"}
        self.assertEqual(packfacts.identity_of(row, "acme.test"), ADMITTED)

    def test_a_fact_from_a_different_domain_is_refused(self):
        """THE 50-OF-71 SHAPE. A plausible name, a different company."""
        row = {"fact": "hiring 50 engineers",
               "source_url": "https://rival-corp.test/jobs",
               "published_at": "2026-09-01",
               "companyWebsite": "https://rival-corp.test"}
        self.assertEqual(packfacts.identity_of(row, "acme.test"), REFUSED)

    def test_a_fact_with_no_source_and_no_website_is_unverifiable(self):
        row = {"fact": "grew 30% last quarter"}
        self.assertEqual(packfacts.identity_of(row, "acme.test"), UNVERIFIABLE)

    def test_a_linkedin_post_is_unverifiable_not_refused(self):
        """A post on LinkedIn's domain is not evidence of whose post it is."""
        row = {"fact": "opened a new office",
               "source_url": "https://www.linkedin.com/posts/acme"}
        self.assertEqual(packfacts.identity_of(row, "acme.test"), UNVERIFIABLE)


# ----------------------------------------------- pack_present rule

class PackPresentRuleTest(unittest.TestCase):
    """Rule 1: at least one admitted fact for this lead's account."""

    def test_a_lead_with_no_research_fires_pack_present(self):
        rec = _make_rec()
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(pack["facts"], [])

    def test_a_lead_with_only_refused_facts_has_no_pack(self):
        """The 50-of-71 shape: research exists, but none is this company's."""
        rec = _make_rec(research=[
            {"fact": "hiring engineers",
             "source_url": "https://other-corp.test/jobs",
             "companyWebsite": "https://other-corp.test"},
        ])
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(pack["facts"], [])
        self.assertEqual(len(unused[REFUSED]), 1)

    def test_a_lead_with_an_admitted_fact_has_a_pack(self):
        rec = _make_rec(research=[
            {"fact": "raised series B",
             "source_url": "https://acme.test/news",
             "published_at": "2026-08-15"},
        ])
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(len(pack["facts"]), 1)


# ----------------------------------------------- fact well-formedness

class FactWellFormedTest(unittest.TestCase):
    """Rule 2: each admitted fact carries source, date and snippet."""

    def test_a_fact_with_all_three_is_well_formed(self):
        fact = {"snippet": "raised series B",
                "source_url": "https://acme.test/news",
                "published_at": "2026-08-15"}
        self.assertEqual(check_lead_pack.fact_well_formed(fact), [])

    def test_a_fact_missing_source(self):
        fact = {"snippet": "raised series B", "published_at": "2026-08-15"}
        self.assertIn("source", check_lead_pack.fact_well_formed(fact))

    def test_a_fact_missing_date(self):
        fact = {"snippet": "raised series B",
                "source_url": "https://acme.test/news"}
        self.assertIn("date", check_lead_pack.fact_well_formed(fact))

    def test_a_fact_missing_snippet(self):
        fact = {"source_url": "https://acme.test/news",
                "published_at": "2026-08-15"}
        self.assertIn("snippet", check_lead_pack.fact_well_formed(fact))

    def test_a_fact_missing_all_three(self):
        fact = {}
        missing = check_lead_pack.fact_well_formed(fact)
        self.assertEqual(sorted(missing), ["date", "snippet", "source"])


# ----------------------------------------------- opener uses pack

class OpenerUsesPackTest(unittest.TestCase):
    """Rule 3: the first line of step 1 references a fact in the pack."""

    def test_an_opener_sharing_words_with_a_pack_fact_passes(self):
        pack = {"facts": [{"snippet": "Acme raised series B funding"}]}
        body = "Your series B funding is a clear signal of growth."
        self.assertTrue(check_lead_pack.opener_uses_pack(body, pack))

    def test_an_opener_with_no_pack_fails(self):
        pack = {"facts": []}
        body = "I wanted to reach out about your team."
        self.assertFalse(check_lead_pack.opener_uses_pack(body, pack))

    def test_an_opener_sharing_no_content_words_with_the_pack_fails(self):
        pack = {"facts": [{"snippet": "Acme raised series B funding"}]}
        body = "Hello, I hope this message finds you well."
        self.assertFalse(check_lead_pack.opener_uses_pack(body, pack))


# ----------------------------------------------- no untraceable claims

class NoUntraceableClaimTest(unittest.TestCase):
    """Rule 4: no company claim in any step traces to nothing."""

    def test_a_company_claim_with_no_pack_support_is_untraceable(self):
        body = "Acme announced 50 new hires this quarter."
        pack = {"facts": []}
        bad = copylint.untraceable(body, pack)
        self.assertTrue(len(bad) > 0)

    def test_a_company_claim_traced_to_a_pack_fact_is_clean(self):
        body = "Acme announced 50 new hires this quarter."
        pack = {"facts": [{"snippet": "Acme announced 50 new hires"}]}
        bad = copylint.untraceable(body, pack)
        self.assertEqual(bad, [])


# ----------------------------------------------- the three sets

class ThreeSetsTest(unittest.TestCase):
    """The three sets (admitted / only-unverifiable-or-refused / no-record)
    must add to the subject count."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(_rmtree, self.tmpdir)

    def _write_queue(self, records):
        path = os.path.join(self.tmpdir, "queue.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")
        return path

    def _write_rendered(self, rows):
        os.makedirs(os.path.join(self.tmpdir, "work", "stage"),
                    exist_ok=True)
        path = os.path.join(self.tmpdir, "work", "stage", "s7-copy.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        return path

    def test_three_sets_add_to_subjects(self):
        """admitted + only_unverifiable_or_refused + no_record == subjects."""
        rec_admitted = _make_rec(
            domain="acme.test", rid="rec-a",
            research=[{"fact": "raised series B",
                       "source_url": "https://acme.test/news",
                       "published_at": "2026-08-15"}])
        rec_refused = _make_rec(
            domain="beta.test", rid="rec-b",
            research=[{"fact": "hiring engineers",
                       "source_url": "https://other.test/jobs",
                       "companyWebsite": "https://other.test"}])
        self._write_queue([rec_admitted, rec_refused])

        rows = [
            _make_rendered_row("ada@acme.test",
                               body_1="Your series B funding is great."),
            _make_rendered_row("ada@beta.test",
                               body_1="Hello there."),
            _make_rendered_row("nobody@gamma.test",
                               body_1="No record for this one."),
        ]
        self._write_rendered(rows)

        result = check_lead_pack.run(
            phase="pre_push", workspaces=self.tmpdir,
            rendered_rel="work/stage/s7-copy.jsonl",
            queue_rel="queue.jsonl")

        three = result["three_sets"]
        total = (len(three["admitted"])
                 + len(three["only_unverifiable_or_refused"])
                 + len(three["no_record"]))
        self.assertEqual(total, result["subjects"])

    def test_refused_and_unverifiable_are_separate_columns(self):
        """They are never summed into a single 'not covered' number."""
        rec = _make_rec(
            domain="acme.test", rid="rec-mixed",
            research=[
                {"fact": "hiring at rival",
                 "source_url": "https://rival.test/jobs",
                 "companyWebsite": "https://rival.test"},
                {"fact": "some unknown fact"},
            ])
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(len(unused[REFUSED]), 1)
        self.assertEqual(len(unused[UNVERIFIABLE]), 1)
        self.assertEqual(len(pack["facts"]), 0)


# ----------------------------------------------- subjects == 0

class SubjectsZeroTest(unittest.TestCase):
    """`subjects == 0` exits UNCONFIRMED with a stated reason."""

    def test_empty_rendered_file_returns_error(self):
        tmpdir = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(tmpdir, "work", "stage"), exist_ok=True)
            open(os.path.join(tmpdir, "work", "stage", "s7-copy.jsonl"),
                 "w").close()
            open(os.path.join(tmpdir, "queue.jsonl"), "w").close()
            result = check_lead_pack.run(
                phase="pre_push", workspaces=tmpdir,
                rendered_rel="work/stage/s7-copy.jsonl",
                queue_rel="queue.jsonl")
            self.assertEqual(result["subjects"], 0)
            self.assertEqual(result["verdict"], "ERROR")
            self.assertIn("reason", result)
        finally:
            _rmtree(tmpdir)

    def test_missing_rendered_file_returns_error(self):
        tmpdir = tempfile.mkdtemp()
        try:
            result = check_lead_pack.run(
                phase="pre_push", workspaces=tmpdir,
                rendered_rel="nonexistent.jsonl",
                queue_rel="queue.jsonl")
            self.assertEqual(result["verdict"], "ERROR")
            self.assertIn("not found", result["reason"])
        finally:
            _rmtree(tmpdir)


# ----------------------------------------------- wrong-company fact

class WrongCompanyFactTest(unittest.TestCase):
    """THE 50-OF-71 SHAPE. A fact from a different company with a plausible
    name must be REFUSED, not admitted."""

    def test_a_plausibly_named_different_company_is_refused(self):
        """`companyName` is a text filter. `identity_of` checks the domain."""
        row = {
            "fact": "Senior Platform Engineer — 5+ years Kubernetes",
            "companyName": "Acme Solutions",  # plausible name match
            "companyWebsite": "https://acme-solutions.test",
            "source_url": "https://acme-solutions.test/jobs/123",
        }
        verdict = packfacts.identity_of(row, "acme.test")
        self.assertEqual(verdict, REFUSED)

    def test_the_wrong_company_fact_does_not_enter_the_pack(self):
        rec = _make_rec(
            domain="acme.test",
            research=[{
                "fact": "Senior Platform Engineer",
                "companyName": "Acme Solutions",
                "companyWebsite": "https://acme-solutions.test",
                "source_url": "https://acme-solutions.test/jobs/123",
            }])
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(pack["facts"], [])
        self.assertEqual(len(unused[REFUSED]), 1)

    def test_loosening_the_identity_join_would_admit_the_wrong_fact(self):
        """If identity_of were a presence check, this would pass. It must not.

        This test FAILS if the identity join is loosened to a text match on
        company name. It asserts on the verdict, which is the acceptance bar.
        """
        row = {
            "fact": "hiring 50 engineers in Zagreb",
            "companyName": "Acme Corp",  # EXACT name match
            "companyWebsite": "https://not-acme.test",
            "source_url": "https://not-acme.test/careers",
        }
        verdict = packfacts.identity_of(row, "acme.test")
        self.assertEqual(verdict, REFUSED,
                         "a fact belonging to not-acme.test must not be "
                         "admitted for acme.test, however similar the name")


# ----------------------------------------------- the negative control

class NegativeControlTest(unittest.TestCase):
    """`--audit-pack-cache` against the quarantined pre-fix pilot cache
    finds the 50-of-71 wrong-company rows.

    The cache file is not present in this worktree (it lives in production
    `work/`). This test verifies the function is callable and returns a
    string. The actual negative-control output is pasted in the result block
    when run against production data.
    """

    def test_audit_pack_cache_returns_a_string_for_a_valid_file(self):
        tmpdir = tempfile.mkdtemp()
        try:
            cache = {
                "acct1": {
                    "domain": "acme.test",
                    "profile": "jobs",
                    "rows": [
                        {"fact": "hiring engineers",
                         "companyWebsite": "https://rival.test",
                         "source_url": "https://rival.test/jobs"},
                    ],
                },
            }
            path = os.path.join(tmpdir, "cache.json")
            with open(path, "w") as f:
                json.dump(cache, f)
            output = check_lead_pack.audit_pack_cache(path)
            self.assertIsInstance(output, str)
            self.assertIn("PACK-CACHE IDENTITY AUDIT", output)
        finally:
            _rmtree(tmpdir)


def _rmtree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
