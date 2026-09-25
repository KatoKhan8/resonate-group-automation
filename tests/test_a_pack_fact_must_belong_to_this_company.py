"""A pack fact must belong to THIS company - identity, not presence.

THE MEASURED PRECEDENT: 50 of 71 job rows in the research pilot belonged to
a DIFFERENT company, because `companyName` is a text filter and not an
identity match. On five of eight accounts that returned rows, every row was
somebody else's. A presence check - "this account has research" - called
those accounts covered.

So this test file proves:
  - identity_of admits a fact from this company's domain
  - identity_of refuses a fact from a different company's domain
  - identity_of marks unverifiable a fact with no domain signal
  - the check reports all three verdicts separately
  - each of the four QA rules fires on a constructed failure
  - each of the four QA rules passes on a clean lead
  - subjects == 0 exits VACUOUS with a stated reason
  - the 50-of-71 shape: a fact with a plausible name but wrong domain
"""
import json
import os
import tempfile
import unittest

from src import copylint, packfacts
from src.packfacts import ADMITTED, REFUSED, UNVERIFIABLE

from scripts.qa import check_lead_pack as clp


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _make_workspace(tmpdir, records=None, rendered=None):
    """Create a minimal work/ tree with queue and rendered copy."""
    work = os.path.join(tmpdir, "work")
    stage = os.path.join(work, "stage")
    os.makedirs(stage)
    if records is not None:
        _write_jsonl(os.path.join(work, "queue.jsonl"), records)
    if rendered is not None:
        _write_jsonl(os.path.join(stage, "s7-copy.jsonl"), rendered)
    return tmpdir


def _rec(rec_id="rec-1", domain="acme.com", research=None, contacts=None):
    return {"id": rec_id, "domain": domain,
            "contacts": contacts or [{"email": "jane@acme.com"}],
            "research": research or []}


def _fact(snippet="Acme opened a Berlin office",
          source_url="https://acme.com/news",
          published_at="2026-09-01", record_id="rec-1"):
    return {"fact": snippet, "source_url": source_url,
            "published_at": published_at, "record_id": record_id}


def _rendered(email="jane@acme.com", lead_id="lead-1",
              body_1="Saw Acme opened a Berlin office.",
              body_2="Step 2 body with enough length.",
              body_3="Step 3 body with enough length.",
              body_4="Step 4 body with enough length.",
              subject_1="Re: Acme Berlin"):
    return {"id": lead_id, "email": email,
            "variables": {"body_1": body_1, "body_2": body_2,
                          "body_3": body_3, "body_4": body_4,
                          "subject_1": subject_1}}


class IdentityOfTests(unittest.TestCase):
    """The one test, three answers. Import, do not reimplement."""

    def test_admitted_when_domain_matches(self):
        row = {"companyWebsite": "https://acme.com/about",
               "source_url": "https://acme.com/news"}
        self.assertEqual(packfacts.identity_of(row, "acme.com"), ADMITTED)

    def test_refused_when_domain_differs(self):
        row = {"companyWebsite": "https://other.com/page",
               "source_url": "https://other.com/page"}
        self.assertEqual(packfacts.identity_of(row, "acme.com"), REFUSED)

    def test_unverifiable_when_no_domain_signal(self):
        row = {"source_url": "https://linkedin.com/post/123"}
        self.assertEqual(packfacts.identity_of(row, "acme.com"), UNVERIFIABLE)

    def test_www_is_not_identity(self):
        row = {"companyWebsite": "https://www.acme.com/page"}
        self.assertEqual(packfacts.identity_of(row, "acme.com"), ADMITTED)

    def test_no_domain_at_all_is_refused(self):
        row = {"companyWebsite": "https://acme.com/page"}
        self.assertEqual(packfacts.identity_of(row, ""), REFUSED)


class PackForTests(unittest.TestCase):
    """pack_for builds the pack from a record's research."""

    def test_admitted_facts_go_in_the_pack(self):
        rec = _rec(research=[_fact()])
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(len(pack["facts"]), 1)
        self.assertEqual(len(unused[REFUSED]), 0)
        self.assertEqual(len(unused[UNVERIFIABLE]), 0)

    def test_refused_facts_stay_out(self):
        rec = _rec(research=[
            _fact(source_url="https://other.com/x", record_id=None)])
        rec["research"][0]["companyWebsite"] = "https://other.com/x"
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(len(pack["facts"]), 0)
        self.assertEqual(len(unused[REFUSED]), 1)

    def test_unverifiable_facts_stay_out_but_are_separate(self):
        rec = _rec(research=[
            _fact(source_url="https://linkedin.com/post/1",
                  record_id=None)])
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(len(pack["facts"]), 0)
        self.assertEqual(len(unused[UNVERIFIABLE]), 1)
        self.assertEqual(len(unused[REFUSED]), 0)


class TheFiftyOfSeventyOneShape(unittest.TestCase):
    """THE CONSTRUCTED FAILURE: a fact from a different company with a
    plausible name. companyName matched; the domain did not. Every
    presence-only check called this covered. identity_of refuses it."""

    def test_fact_belonging_to_a_different_company_is_refused(self):
        rec = _rec(domain="acme.com", research=[
            {"fact": "Senior Platform Engineer at Acme Solutions",
             "companyWebsite": "https://acme-solutions.com",
             "source_url": "https://acme-solutions.com/jobs/1",
             "published_at": "2026-09-10", "record_id": "rec-1"}])
        pack, unused = packfacts.pack_for(rec)
        self.assertEqual(len(pack["facts"]), 0,
                         "a stranger's job must not enter this account's pack")
        self.assertEqual(len(unused[REFUSED]), 1)
        verdict = packfacts.identity_of(rec["research"][0], "acme.com")
        self.assertEqual(verdict, REFUSED)

    def test_check_reports_the_lead_as_having_no_admitted_fact(self):
        rec = _rec(domain="acme.com", research=[
            {"fact": "Senior Platform Engineer at Acme Solutions",
             "companyWebsite": "https://acme-solutions.com",
             "source_url": "https://acme-solutions.com/jobs/1",
             "published_at": "2026-09-10", "record_id": "rec-1"}])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec],
                            rendered=[_rendered()])
            result = clp.run(tmp)
        self.assertIn("lead-1",
                      result["offenders"]["pack_present"])


class PackPresentRule(unittest.TestCase):

    def test_a_lead_with_an_admitted_fact_passes(self):
        rec = _rec(research=[_fact()])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec],
                            rendered=[_rendered()])
            result = clp.run(tmp)
        self.assertEqual(result["counts"]["pack_present"], 0)
        self.assertNotIn("lead-1",
                         result["offenders"]["pack_present"])

    def test_a_lead_with_no_research_fires(self):
        rec = _rec(research=[])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec],
                            rendered=[_rendered(body_1="Generic opener.")])
            result = clp.run(tmp)
        self.assertIn("lead-1",
                      result["offenders"]["pack_present"])

    def test_a_lead_with_only_refused_facts_fires(self):
        rec = _rec(domain="acme.com", research=[
            _fact(source_url="https://other.com/x",
                  record_id=None)])
        rec["research"][0]["companyWebsite"] = "https://other.com/x"
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec],
                            rendered=[_rendered(body_1="Generic opener.")])
            result = clp.run(tmp)
        self.assertIn("lead-1",
                      result["offenders"]["pack_present"])


class FactHasSourceDateSnippet(unittest.TestCase):

    def test_a_fact_missing_source_fires(self):
        rec = _rec(research=[
            _fact(source_url="https://acme.com/news",
                  published_at="2026-09-01")])
        rec["research"][0]["companyWebsite"] = "https://acme.com/about"
        del rec["research"][0]["source_url"]
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[_rendered()])
            result = clp.run(tmp)
        self.assertIn("lead-1",
                      result["offenders"]["fact_has_source_date_snippet"])
        self.assertEqual(result["source_date_snippet"]["missing_source"], 1)

    def test_a_fact_missing_date_fires(self):
        rec = _rec(research=[
            _fact(source_url="https://acme.com/news", published_at="")])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[_rendered()])
            result = clp.run(tmp)
        self.assertIn("lead-1",
                      result["offenders"]["fact_has_source_date_snippet"])
        self.assertEqual(result["source_date_snippet"]["missing_date"], 1)

    def test_a_fact_with_both_passes(self):
        rec = _rec(research=[_fact()])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[_rendered()])
            result = clp.run(tmp)
        self.assertEqual(
            result["counts"]["fact_has_source_date_snippet"], 0)


class OpenerUsesAPackFact(unittest.TestCase):

    def test_an_opener_referencing_the_pack_passes(self):
        rec = _rec(research=[_fact(snippet="Acme opened a Berlin office")])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[_rendered(
                body_1="Saw Acme opened a Berlin office.")])
            result = clp.run(tmp)
        self.assertEqual(
            result["counts"]["opener_uses_a_pack_fact"], 0)

    def test_a_generic_opener_fires(self):
        rec = _rec(research=[_fact(snippet="Acme opened a Berlin office")])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[_rendered(
                body_1="I wanted to reach out about your growth.")])
            result = clp.run(tmp)
        self.assertIn("lead-1",
                      result["offenders"]["opener_uses_a_pack_fact"])

    def test_a_lead_with_no_pack_fires_the_opener_rule_too(self):
        rec = _rec(research=[])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[_rendered(
                body_1="Saw your company online.")])
            result = clp.run(tmp)
        self.assertIn("lead-1",
                      result["offenders"]["opener_uses_a_pack_fact"])


class NoClaimOutsideThePack(unittest.TestCase):

    def test_an_untraceable_specific_in_a_company_claim_fires(self):
        rec = _rec(research=[_fact(
            snippet="Acme opened a Berlin office",
            source_url="https://acme.com/news")])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[_rendered(
                body_1="Saw Acme opened a Berlin office.",
                body_2="You raised $50M in Series C funding.")])
            result = clp.run(tmp)
        self.assertIn("lead-1",
                      result["offenders"]["no_claim_outside_the_pack"])

    def test_a_supported_specific_passes(self):
        rec = _rec(research=[_fact(
            snippet="Acme raised $50M in Series C",
            source_url="https://acme.com/news")])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[_rendered(
                body_1="Saw Acme raised $50M in Series C.",
                body_2="Step 2 body with enough length.")])
            result = clp.run(tmp)
        self.assertEqual(
            result["counts"]["no_claim_outside_the_pack"], 0)


class IdentityColumnsReportedSeparately(unittest.TestCase):
    """refused and unverifiable appear as separate columns everywhere."""

    def test_all_three_verdicts_apart_in_the_result(self):
        rec = _rec(domain="acme.com", research=[
            _fact(snippet="Acme opened Berlin",
                  source_url="https://acme.com/news"),
            _fact(snippet="Other company news",
                  source_url="https://other.com/x",
                  record_id=None),
            _fact(snippet="LinkedIn post snippet",
                  source_url="https://linkedin.com/post/1",
                  record_id=None),
        ])
        rec["research"][1]["companyWebsite"] = "https://other.com/x"
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[_rendered()])
            result = clp.run(tmp)
        it = result["identity_totals"]
        self.assertEqual(it["admitted"], 1)
        self.assertEqual(it["refused"], 1)
        self.assertEqual(it["unverifiable"], 1)

    def test_per_lead_identity_shows_the_breakdown(self):
        rec = _rec(domain="acme.com", research=[
            _fact(), _fact(source_url="https://other.com/x", record_id=None)])
        rec["research"][1]["companyWebsite"] = "https://other.com/x"
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[_rendered()])
            result = clp.run(tmp)
        pli = result["per_lead_identity"]
        self.assertEqual(len(pli), 1)
        self.assertEqual(pli[0]["lead"], "lead-1")
        self.assertEqual(pli[0]["admitted"], 1)
        self.assertEqual(pli[0]["refused"], 1)


class ThreeSetsAddToRendered(unittest.TestCase):
    """The 128 are reported by name in three sets that must add to the
    rendered row count."""

    def test_the_three_sets_partition_the_rendered_rows(self):
        rec_ok = _rec(rec_id="rec-1", domain="acme.com",
                       research=[_fact()],
                       contacts=[{"email": "jane@acme.com"}])
        rec_bad = _rec(rec_id="rec-2", domain="other.com", research=[],
                        contacts=[{"email": "bob@other.com"}])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec_ok, rec_bad], rendered=[
                _rendered(email="jane@acme.com", lead_id="lead-1"),
                _rendered(email="bob@other.com", lead_id="lead-2",
                          body_1="Generic opener with no fact."),
                _rendered(email="nobody@void.com", lead_id="lead-3",
                          body_1="Generic opener."),
            ])
            result = clp.run(tmp)
        ts = result["three_sets"]
        total = (len(ts["admitted"])
                 + len(ts["only_unverifiable_or_refused"])
                 + len(ts["no_record"]))
        self.assertEqual(total, 3)
        self.assertIn("lead-1", ts["admitted"])
        self.assertIn("lead-3", ts["no_record"])


class SubjectsZeroIsVacuous(unittest.TestCase):
    """subjects == 0 exits 2 with a stated reason."""

    def test_no_rendered_file_is_error_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "work")
            os.makedirs(work)
            _write_jsonl(os.path.join(work, "queue.jsonl"), [])
            result = clp.run(tmp)
        self.assertEqual(result["verdict"], "ERROR")
        self.assertTrue(result.get("vacuum_reason"))

    def test_no_match_is_vacuous_with_reason(self):
        rec = _rec(contacts=[{"email": "jane@acme.com"}])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[
                _rendered(email="nobody@void.com"),
            ])
            result = clp.run(tmp)
        self.assertEqual(result["verdict"], "VACUOUS")
        self.assertTrue(result.get("vacuum_reason"))
        self.assertEqual(result["subjects"], 0)


class ArithmeticCloses(unittest.TestCase):
    """clean + |offenders union unverifiable| == subjects."""

    def test_it_closes_on_a_mixed_batch(self):
        rec_ok = _rec(rec_id="rec-1", domain="acme.com",
                       research=[_fact()],
                       contacts=[{"email": "jane@acme.com"}])
        rec_bad = _rec(rec_id="rec-2", domain="acme.com", research=[],
                        contacts=[{"email": "bob@acme.com"}])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec_ok, rec_bad], rendered=[
                _rendered(email="jane@acme.com", lead_id="lead-1"),
                _rendered(email="bob@acme.com", lead_id="lead-2",
                          body_1="Generic opener no fact."),
            ])
            result = clp.run(tmp)
        all_offending = set()
        for ids in result["offenders"].values():
            all_offending.update(ids)
        self.assertEqual(
            result["clean"] + len(all_offending),
            result["subjects"])


class JoinKeyReported(unittest.TestCase):
    """The join key, match count both directions."""

    def test_join_reports_key_and_counts(self):
        rec = _rec(research=[_fact()],
                    contacts=[{"email": "jane@acme.com"}])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[
                _rendered(email="jane@acme.com"),
                _rendered(email="nobody@void.com", lead_id="lead-2",
                          body_1="Generic opener."),
            ])
            result = clp.run(tmp)
        self.assertEqual(result["join"]["key"], "email")
        self.assertEqual(result["join"]["matched"], 1)
        self.assertEqual(result["join"]["unmatched"], 1)


class RulesKeysConsistent(unittest.TestCase):
    """Every key in counts/offenders exists in rules, and vice versa."""

    def test_keys_match(self):
        rec = _rec(research=[_fact()])
        with tempfile.TemporaryDirectory() as tmp:
            _make_workspace(tmp, records=[rec], rendered=[_rendered()])
            result = clp.run(tmp)
        for name in result["rules"]:
            self.assertIn(name, result["counts"])
            self.assertIn(name, result["offenders"])
        for name in result["counts"]:
            self.assertIn(name, result["rules"])


class NoProviderCalls(unittest.TestCase):
    """The check is READ ONLY. No Apify, no EmailBison, no HeyReach."""

    def test_no_provider_import(self):
        import importlib
        mod = importlib.import_module("scripts.qa.check_lead_pack")
        with open(mod.__file__, encoding="utf-8") as fh:
            source = fh.read()
        for provider in ("apify", "bison", "heyreach", "providerwrites"):
            self.assertNotIn(
                "import src.%s" % provider, source,
                "check_lead_pack must not import any provider module")


if __name__ == "__main__":
    unittest.main()
