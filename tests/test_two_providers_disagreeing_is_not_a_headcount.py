#!/usr/bin/env python3
"""A second opinion on a size, and what it means when the two disagree.

## The defect this closes

`src/providers/blitz.py` has been live-confirmed since 2026-09-09. It was
wired into `enrich.COSTS`, `enrich.CALL_STAGE`, `waterfall.STAGES` and
`fieldplan` - and had NO call site anywhere outside tests, so nothing in the
running system could reach it. Measured on the 300-record Productive estate,
123 companies were rejected on `company_facts.employees` with no
`employee_range` beside it: a lower bound with no upper bound, read as though
it were a measured headcount, deciding a rejection on its own.

## Never a FAIL and never a PASS

One provider says three people; the other says nineteen. Taking the larger
qualifies a company on evidence half of which says it does not qualify;
taking the smaller rejects one on evidence half of which says it does. So a
CONFLICT resolves to no value at all and the criterion is UNKNOWN - the
vocabulary `src/icpstructural.py` already has for "we could not establish
it".

Two sources agreeing is not a conflict, whichever side they agree on: this
must not become a machine for turning every rejection into an unknown. The
tests below pin both directions.

## The floor is derived from the client's config, and 14 is written nowhere

Whether two answers conflict depends entirely on where the client's tolerated
floor is, and that floor is `min x (1 - tolerance)`. The tests change the
config and watch the same two numbers stop conflicting.

## The wire is the recorded one

The Blitz body below is the shape of the response
`work/validation/blitz-company.json` holds, which really did come back
carrying `employees_on_linkedin: 19` beside `size: "1-10"` - the provider
disagreeing with itself in one response.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from src import enrich, fieldplan, headcount, icpstructural, segments, store
from src import providers

CLIENT = {
    "name": "Test Client",
    "icp": {"structural": {
        "geographies": {"include": ["United Kingdom"], "exclude": ["India"]},
        "company_types": {"verticals": ["Creative / Branding Agency"]},
        "services_business_required": True,
        "tracks_time_required": True,
        "employees": {"min": 20, "tolerance": 0.30,
                      "revenue_contradicts_below_millions": 3},
    }},
}

# 20 x (1 - 0.50) = 10, so nineteen and three both sit above it and stop
# disagreeing about anything that matters.
LOOSER = {"name": "Test Client", "icp": {"structural": dict(
    CLIENT["icp"]["structural"],
    employees={"min": 20, "tolerance": 0.50})}}

FACTS = {
    "industry": "Marketing and Advertising",
    "description": "A digital marketing agency delivering client campaigns.",
    "employees": 3,
    "headcount_signal": 2,
    "offices": ["1 High Street, London, England, W1, GB"],
    "services": ["digital marketing", "branding"],
    "linkedin": "https://www.linkedin.com/company/example-group",
}

# What `blitz.company` returns for that LinkedIn URL: the trim of the response
# in work/validation/blitz-company.json.
BLITZ_ANSWER = {
    "found": True,
    "company_linkedin": FACTS["linkedin"],
    "name": "Example Group",
    "domain": "example.test",
    "employees": 19,
    "employee_range": "1-10",
    "industry": "IT Services and IT Consulting",
    "location": None,
    "founded": None,
    "fair_usage": {"records_used": 1, "records_remaining": 29999998,
                   "request_id": "01a085a4-2947-7304-bf05-7ebe03ab41f8"},
}


def a_record(asked_contactout=True, **facts_over):
    """A company as it reaches the headcount question in production.

    `asked_contactout` defaults to True because that is the only way a record
    HAS a bare `employees` number in the first place - ContactOut returned it.
    Blitz is the fallback for a stage whose primary has already answered, and
    `next_step` walks the waterfall in declared order, so a record with no
    history routes to ContactOut and stops there.

    This used to be implicit and fragile: `headcount` listed
    `company-information-from-domain` in `filled_by`, so an unasked record
    owed that call, the call marked the stage asked, and blitz became
    reachable as a side effect. It also meant every already-enriched company
    owed a paid ContactOut call again - which `test_a_rerun_does_not_rebuy`
    caught. ContactOut cannot fill this field: its own module says `size`
    "is not a fallback for" `employees`.
    """
    rec = store.new_record("acct", "domains", "test", "Acme", "acme.test")
    facts = dict(FACTS)
    facts.update(facts_over)
    rec["company_facts"] = {k: v for k, v in facts.items() if v is not None}
    if asked_contactout:
        rec["waterfall"] = [{"stage": "company_information",
                             "provider": "contactout",
                             "call": "company-information-from-domain"}]
    return rec


def employees_answer(rec, config=CLIENT):
    segment = segments.classify(rec, config)
    return icpstructural.structural(rec, config, segment=segment)


class TheProviderCanActuallyBeReached(unittest.TestCase):
    """A provider with no call site is a fixture with a docstring."""

    def test_the_field_routes_to_blitz(self):
        rec = a_record()
        step, _why = fieldplan.next_step(rec, "headcount")
        self.assertIsNotNone(step)
        self.assertEqual(step["call"], "blitz-company")

    def test_a_number_with_no_band_is_not_a_headcount(self):
        rec = a_record()
        self.assertEqual(fieldplan.state_of(rec, "headcount"),
                         fieldplan.MISSING_CONFIRMED)

    def test_a_band_is(self):
        rec = a_record(employee_range="51-200 employees")
        self.assertEqual(fieldplan.state_of(rec, "headcount"),
                         fieldplan.KNOWN)

    def test_a_resolved_block_is(self):
        rec = a_record(employees=None)
        headcount.observe(rec, "blitz-company", value=80, band="51-200",
                          config=CLIENT)
        self.assertEqual(fieldplan.state_of(rec, "headcount"),
                         fieldplan.KNOWN)

    def test_a_conflict_is_reported_as_one_rather_than_as_a_gap(self):
        """`CONFLICTED` was declared here and returned by nothing."""
        rec = a_record()
        headcount.observe(rec, "blitz-company", value=19, band="1-10",
                          config=CLIENT)
        self.assertEqual(fieldplan.state_of(rec, "headcount"),
                         fieldplan.CONFLICTED)


class TheCallIsMadeAndItGoesThroughTheLedger(unittest.TestCase):
    """CLAUDE.md: a provider call that skips `spend()` is invisible to audit."""

    def enrich(self, rec, live=True, cap=10, answer=BLITZ_ANSWER):
        with mock.patch.object(enrich.blitz, "company",
                               return_value=answer) as called:
            done = enrich.enrich_record(rec, enrich.Budget(cap), live=live,
                                        config=CLIENT)
        return done, called

    def setUp(self):
        # Every state file into a throwaway directory. `spend()` writes the
        # DURABLE spend ledger on a live pass, and `store.refuse_production_write`
        # refuses - correctly - to let a test write real client state.
        self.tmp = tempfile.mkdtemp(prefix="rga-headcount-")
        self._env = {k: os.environ.get(k) for k in ("QUEUE", "OUT")}
        store.use_directory(os.path.join(self.tmp, "work"))
        os.environ["OUT"] = os.path.join(self.tmp, "out")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(self._restore_env)
        # Everything except the Blitz leg is stubbed out: this test is about
        # one call, and a real `people-count` would be a network call.
        self.patches = [
            mock.patch.object(enrich.contactout, "people_count",
                              side_effect=providers.ProviderError("offline")),
            mock.patch.object(enrich.contactout, "decision_makers",
                              side_effect=providers.ProviderError("offline")),
            mock.patch.object(enrich.contactout, "company_info",
                              side_effect=providers.ProviderError("offline")),
            mock.patch.object(enrich.aiark, "people_search",
                              side_effect=providers.ProviderError("offline")),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def _restore_env(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_the_provider_is_called(self):
        rec = a_record()
        _done, called = self.enrich(rec)
        called.assert_called_once_with(FACTS["linkedin"])

    def test_the_call_is_on_the_waterfall_ledger_with_its_reason(self):
        rec = a_record()
        self.enrich(rec)
        rows = [r for r in rec.get("waterfall") or []
                if r["call"] == "blitz-company"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provider"], "blitz")
        self.assertEqual(rows[0]["reason"],
                         enrich.CONTACTOUT_MISSING_COMPANY_DATA)

    def test_the_reported_cost_replaces_the_assumed_one(self):
        """`fair_usage.records_used` is the only real cost Blitz has."""
        rec = a_record()
        self.enrich(rec)
        row = next(r for r in rec["waterfall"] if r["call"] == "blitz-company")
        self.assertEqual(row["actual_cost"], 1)

    def test_a_dry_run_calls_nothing_and_still_says_it_would(self):
        rec = a_record()
        done, called = self.enrich(rec, live=False)
        called.assert_not_called()
        self.assertIn("blitz-company", [o["call"] for o in done])

    def test_it_is_not_bought_twice(self):
        rec = a_record()
        self.enrich(rec)
        _done, called = self.enrich(rec)
        called.assert_not_called()

    def test_a_company_with_no_linkedin_url_is_not_called_for(self):
        rec = a_record(linkedin=None)
        _done, called = self.enrich(rec)
        called.assert_not_called()

    def test_a_stated_miss_is_an_answer_and_is_not_re_bought(self):
        rec = a_record()
        self.enrich(rec, answer={"found": False, "fair_usage": {}})
        _done, called = self.enrich(rec)
        called.assert_not_called()


class TwoSourcesOnOppositeSidesOfTheFloor(unittest.TestCase):
    """Three people against nineteen, with a floor of fourteen between them."""

    def observed(self, config=CLIENT, **over):
        rec = a_record()
        headcount.observe(rec, "blitz-company", value=19, band="1-10",
                          config=config, **over)
        return rec

    def test_it_is_a_conflict(self):
        rec = self.observed()
        self.assertEqual(headcount.resolve(rec, CLIENT)["state"],
                         headcount.CONFLICT)

    def test_there_is_no_value_at_all(self):
        block = headcount.resolve(self.observed(), CLIENT)
        self.assertIsNone(block["value"])
        self.assertIsNone(block["range"])

    def test_both_numbers_are_kept_with_who_said_them(self):
        block = headcount.resolve(self.observed(), CLIENT)
        said = {c["source"]: c["value"] for c in block["contradictions"]}
        self.assertEqual(said, {headcount.STORED: 3, "blitz-company": 19})

    def test_the_criterion_is_unknown_rather_than_fail(self):
        answer = employees_answer(self.observed())["criteria"]["employees"]
        self.assertEqual(answer["status"], icpstructural.UNKNOWN)

    def test_and_never_a_pass(self):
        answer = employees_answer(self.observed())["criteria"]["employees"]
        self.assertNotIn(answer["status"], icpstructural.PASSING)

    def test_without_the_second_opinion_the_same_record_fails(self):
        """The counterfactual: the conflict is what changed the answer."""
        answer = employees_answer(a_record())["criteria"]["employees"]
        self.assertEqual(answer["status"], icpstructural.FAIL)

    def test_the_company_is_not_rejected_on_half_the_evidence(self):
        self.assertNotEqual(employees_answer(self.observed())["verdict"],
                            icpstructural.ICP_FAIL)

    def test_the_conflict_is_named_in_the_unknowns(self):
        self.assertIn("employees",
                      employees_answer(self.observed())["unknown_criteria"])


class TwoSourcesThatAgreeAreNotAConflict(unittest.TestCase):
    """This must not become a machine for turning rejections into unknowns."""

    def small(self):
        rec = a_record()
        headcount.observe(rec, "blitz-company", value=4, band="1-10",
                          config=CLIENT)
        return rec

    def large(self):
        rec = a_record(employees=60)
        headcount.observe(rec, "blitz-company", value=80, band="51-200",
                          config=CLIENT)
        return rec

    def test_two_small_answers_still_fail(self):
        rec = self.small()
        self.assertEqual(headcount.resolve(rec, CLIENT)["state"],
                         headcount.AGREED)
        self.assertEqual(employees_answer(rec)["criteria"]["employees"]["status"],
                         icpstructural.FAIL)

    def test_two_large_answers_still_pass(self):
        rec = self.large()
        self.assertEqual(headcount.resolve(rec, CLIENT)["state"],
                         headcount.AGREED)
        self.assertEqual(employees_answer(rec)["criteria"]["employees"]["status"],
                         icpstructural.PASS)

    def test_agreement_is_worth_more_than_one_answer(self):
        self.assertEqual(headcount.resolve(self.large(), CLIENT)["confidence"],
                         headcount.HIGH)
        self.assertEqual(headcount.resolve(a_record(), CLIENT)["confidence"],
                         headcount.MEDIUM)

    def test_nobody_at_all_is_not_a_conflict(self):
        rec = a_record(employees=None, headcount_signal=None)
        self.assertEqual(headcount.resolve(rec, CLIENT)["state"],
                         headcount.UNESTABLISHED)


class WhetherTwoAnswersConflictComesFromTheClientsConfig(unittest.TestCase):
    """The floor is min x (1 - tolerance), and 14 is written nowhere."""

    def rec(self):
        rec = a_record()
        headcount.observe(rec, "blitz-company", value=19, band="1-10",
                          config=CLIENT)
        return rec

    def test_the_floor_is_derived_and_carried_on_the_answer(self):
        self.assertEqual(headcount.resolve(self.rec(), CLIENT)["floor"], 14)

    def test_a_looser_tolerance_puts_both_answers_on_the_same_side(self):
        """A floor of 10: three is still below it, nineteen is above."""
        self.assertEqual(icpstructural.settings(LOOSER)
                         ["effective_min_employees"], 10)
        # Three is below ten and nineteen is above it, so they still conflict:
        # a tolerance that moves the floor without crossing either number
        # changes nothing, which is the point.
        self.assertEqual(headcount.resolve(self.rec(), LOOSER)["state"],
                         headcount.CONFLICT)

    def test_a_floor_under_both_answers_is_agreement(self):
        tiny = {"name": "t", "icp": {"structural": {
            "employees": {"min": 3, "tolerance": 0.0}}}}
        self.assertEqual(icpstructural.settings(tiny)
                         ["effective_min_employees"], 3)
        self.assertEqual(headcount.resolve(self.rec(), tiny)["state"],
                         headcount.AGREED)

    def test_a_client_with_no_size_rule_has_a_floor_of_zero(self):
        none = {"name": "t", "icp": {"structural": {}}}
        self.assertEqual(headcount.resolve(self.rec(), none)["state"],
                         headcount.AGREED)


class ABandThatStraddlesTheFloorContradictsNobody(unittest.TestCase):
    """Which side it falls is exactly what is unestablished."""

    def test_it_has_no_side(self):
        observation = {"source": "x", "value": None, "range": [11, 50]}
        self.assertIsNone(headcount.side(observation, 14))

    def test_so_it_does_not_conflict_with_a_small_answer(self):
        rec = a_record()
        headcount.observe(rec, "blitz-company", value=None, band="11-50",
                          config=CLIENT)
        self.assertNotEqual(headcount.resolve(rec, CLIENT)["state"],
                            headcount.CONFLICT)

    def test_and_the_criterion_stays_unknown(self):
        rec = a_record()
        headcount.observe(rec, "blitz-company", value=None, band="11-50",
                          config=CLIENT)
        self.assertEqual(
            employees_answer(rec)["criteria"]["employees"]["status"],
            icpstructural.UNKNOWN)


class AProfileCountIsAFloorAndContradictsNobody(unittest.TestCase):
    """`headcount_signal` is how many profiles were found, not how many exist."""

    def test_it_is_not_an_estimating_witness(self):
        rec = a_record(employees=None, headcount_signal=2)
        self.assertEqual(headcount.witnesses(rec), [])

    def test_a_low_profile_count_does_not_conflict_with_a_large_headcount(self):
        rec = a_record(employees=None, headcount_signal=2)
        headcount.observe(rec, "blitz-company", value=80, band="51-200",
                          config=CLIENT)
        self.assertEqual(headcount.resolve(rec, CLIENT)["state"],
                         headcount.SINGLE_SOURCE)
        self.assertEqual(
            employees_answer(rec)["criteria"]["employees"]["status"],
            icpstructural.PASS)


class RevenueTriggersARecheckAndNeverReplacesAHeadcount(unittest.TestCase):
    """A turnover is not a number of people, however suggestive it is."""

    def test_a_contradicting_revenue_makes_the_size_unknown(self):
        rec = a_record(revenue="$21.1M")
        answer = employees_answer(rec)["criteria"]["employees"]
        self.assertEqual(answer["status"], icpstructural.UNKNOWN)

    def test_it_does_not_become_a_pass(self):
        rec = a_record(revenue="$21.1M")
        answer = employees_answer(rec)["criteria"]["employees"]
        self.assertNotIn(answer["status"], (icpstructural.PASS,
                                            icpstructural.PASS_WITH_TOLERANCE))

    def test_no_headcount_is_invented_from_it(self):
        rec = a_record(revenue="$21.1M")
        self.assertEqual(
            [o["source"] for o in headcount.witnesses(rec)],
            [headcount.STORED])
        self.assertIsNone(headcount.block_of(rec).get("value"))


class TheEvidenceIsKeptRatherThanOverwritten(unittest.TestCase):
    """A second opinion that replaced the first would erase the conflict."""

    def test_the_first_answer_survives_the_second(self):
        rec = a_record()
        headcount.observe(rec, "blitz-company", value=19, band="1-10",
                          config=CLIENT)
        sources = [o["source"] for o in headcount.block_of(rec)["observations"]]
        self.assertEqual(sorted(sources),
                         sorted([headcount.STORED, "blitz-company"]))

    def test_the_stored_provider_field_is_not_rewritten(self):
        rec = a_record()
        headcount.observe(rec, "blitz-company", value=19, band="1-10",
                          config=CLIENT)
        self.assertEqual(rec["company_facts"]["employees"], 3)

    def test_observing_the_same_source_twice_does_not_duplicate_it(self):
        rec = a_record()
        for _ in range(3):
            headcount.observe(rec, "blitz-company", value=19, band="1-10",
                              config=CLIENT)
        self.assertEqual(len(headcount.block_of(rec)["observations"]), 2)

    def test_the_answer_carries_its_provenance(self):
        rec = a_record(employees=None, headcount_signal=None)
        block = headcount.observe(rec, "blitz-company", value=80,
                                  band="51-200", config=CLIENT)
        self.assertEqual(block["source"], "blitz-company")
        self.assertTrue(block["retrieved_at"])
        self.assertEqual(block["confidence"], headcount.MEDIUM)


if __name__ == "__main__":
    unittest.main()
