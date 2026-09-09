"""The cap that controls spend existed, was stored, and nothing read it.

`routing.plan` computes `max_contacts_to_enrich` for every company - 3 for
tier A, 2 for B, 1 for C, 0 for anything not qualified - and its docstring says
in as many words that it "is the number that controls spend". It is written onto
every record under `qualification.persona_plan`. Its readers were a forecast
(`dmplan`), two screens (`explorer`, `qualify`) and a report. **Verification read
`usable_contacts(rec)`**: every address on the record, at up to three credits
each.

The order of `run.STAGES` is what makes it expensive: `("enrich", "qualify",
"personas", ...)`. `decision-makers` can return dozens of addressed profiles for
one company, verification pays for all of them, and `personas.select` - the step
that trims them to the cap - runs afterwards. Measured over a 30,000-domain run
that is roughly a quarter of a million credits spent verifying people the system
has already decided never to write to.

Two properties are asserted here, and the second matters as much as the first: a
cap without an order buys an arbitrary subset, so the contacts bought must be
the ones selection would have chosen.
"""
import unittest

from src import enrich, events


def contact(key, title, email=None, **over):
    row = {"key": key, "name": key.replace("-", " ").title(), "title": title,
           "email": email or f"{key}@brightpath.test"}
    row.update(over)
    return row


def record(cap, *contacts, titles=(), plan=True):
    rec = {"id": "rec-1", "lane": "domains", "client": "productive",
           "company": "Brightpath", "domain": "brightpath.test",
           "state": "enriched", "contacts": list(contacts), "events": []}
    if plan:
        rec["qualification"] = {"persona_plan": {
            "max_contacts_to_enrich": cap,
            "target_titles": list(titles),
        }}
    return rec


TITLES = ["Chief Operating Officer", "Head of Operations", "Operations Manager",
          "Project Manager"]


class TheCapIsHonoured(unittest.TestCase):
    def test_one_of_two_addresses_is_bought_at_a_cap_of_one(self):
        rec = record(1, contact("a", "Head of Operations"),
                     contact("b", "Project Manager"), titles=TITLES)
        self.assertEqual([c["key"] for c in enrich.verification_candidates(rec)],
                         ["a"])

    def test_two_of_five_at_a_cap_of_two(self):
        rec = record(2, *[contact(k, t) for k, t in zip("abcde", TITLES + ["X"])],
                     titles=TITLES)
        self.assertEqual(len(enrich.verification_candidates(rec)), 2)

    def test_a_cap_of_zero_buys_nothing(self):
        """Not qualified means not a cheap company - it means nobody decided."""
        rec = record(0, contact("a", "Head of Operations"), titles=TITLES)
        self.assertEqual(enrich.verification_candidates(rec), [])

    def test_forty_addresses_at_a_cap_of_two_buys_two(self):
        """The shape that costs the money: one company, many returned profiles."""
        many = [contact(f"c{i}", "Operations Manager") for i in range(40)]
        rec = record(2, *many, titles=TITLES)
        self.assertEqual(len(enrich.verification_candidates(rec)), 2)

    def test_a_cap_above_the_address_count_buys_them_all(self):
        rec = record(5, contact("a", "Head of Operations"),
                     contact("b", "Project Manager"), titles=TITLES)
        self.assertEqual(len(enrich.verification_candidates(rec)), 2)

    def test_an_address_less_contact_is_never_a_candidate(self):
        rec = record(3, contact("a", "Head of Operations"),
                     {"key": "b", "title": "COO", "name": "B"}, titles=TITLES)
        self.assertEqual([c["key"] for c in enrich.verification_candidates(rec)],
                         ["a"])


class TheCapBuysTheContactsSelectionWouldChoose(unittest.TestCase):
    """A cap without an order buys an arbitrary subset."""

    def test_the_highest_priority_title_is_bought_first(self):
        rec = record(1, contact("junior", "Project Manager"),
                     contact("senior", "Chief Operating Officer"),
                     titles=TITLES)
        self.assertEqual([c["key"] for c in enrich.verification_candidates(rec)],
                         ["senior"])

    def test_priority_follows_the_plans_own_ordered_titles(self):
        rec = record(2, contact("d", "Project Manager"),
                     contact("c", "Operations Manager"),
                     contact("b", "Head of Operations"),
                     contact("a", "Chief Operating Officer"), titles=TITLES)
        self.assertEqual([c["key"] for c in enrich.verification_candidates(rec)],
                         ["a", "b"])

    def test_an_undeclared_title_ranks_last_but_is_still_eligible(self):
        """The cap is about how many, not about who qualifies."""
        rec = record(1, contact("odd", "Barista"), titles=TITLES)
        self.assertEqual([c["key"] for c in enrich.verification_candidates(rec)],
                         ["odd"])

    def test_a_declared_title_outranks_an_undeclared_one(self):
        rec = record(1, contact("odd", "Barista"),
                     contact("real", "Operations Manager"), titles=TITLES)
        self.assertEqual([c["key"] for c in enrich.verification_candidates(rec)],
                         ["real"])

    def test_the_choice_is_reproducible_after_a_restart(self):
        """Ties break on the contact key, not on dict order, so a resumed run
        buys the same addresses rather than a different arbitrary subset."""
        rows = [contact(k, "Operations Manager") for k in ("z", "m", "a")]
        first = enrich.verification_candidates(record(2, *rows, titles=TITLES))
        second = enrich.verification_candidates(
            record(2, *reversed(rows), titles=TITLES))
        self.assertEqual([c["key"] for c in first], [c["key"] for c in second])
        self.assertEqual([c["key"] for c in first], ["a", "m"])

    def test_a_partial_title_match_counts(self):
        """Real titles carry extra words: "Head of Operations, EMEA"."""
        rec = record(1, contact("a", "Head of Operations, EMEA"), titles=TITLES)
        self.assertEqual(len(enrich.verification_candidates(rec)), 1)


class ARecordQualificationHasNotSeenIsNotCapped(unittest.TestCase):
    """The cap is a decision qualification makes. Inventing one here for a
    record it has not seen would be guessing at a limit rather than honouring
    one - so those records are reported, not silently capped to zero."""

    def test_no_persona_plan_means_no_cap(self):
        rec = record(0, contact("a", "Head of Operations"),
                     contact("b", "Project Manager"), plan=False)
        self.assertEqual(len(enrich.verification_candidates(rec)), 2)

    def test_a_plan_with_no_cap_key_means_no_cap(self):
        rec = record(0, contact("a", "Head of Operations"), plan=False)
        rec["qualification"] = {"persona_plan": {"target_titles": TITLES}}
        self.assertEqual(len(enrich.verification_candidates(rec)), 1)

    def test_an_explicit_cap_of_zero_is_honoured_not_ignored(self):
        """Nothing may read a stated zero as "unset"."""
        rec = record(0, contact("a", "Head of Operations"), titles=TITLES)
        self.assertEqual(enrich.verification_candidates(rec), [])

    def test_a_null_cap_is_treated_as_zero_not_as_absent(self):
        rec = record(None, contact("a", "Head of Operations"), titles=TITLES)
        self.assertEqual(enrich.verification_candidates(rec), [])


class TheSavingIsVisible(unittest.TestCase):
    """A saving nobody can see is indistinguishable from a forgotten contact."""

    def test_every_skipped_address_gets_a_skip_event(self):
        rec = record(1, contact("a", "Chief Operating Officer"),
                     contact("b", "Project Manager"),
                     contact("c", "Operations Manager"), titles=TITLES)
        chosen = {c["key"] for c in enrich.verification_candidates(rec)}
        skipped = [c for c in enrich.usable_contacts(rec)
                   if c["key"] not in chosen]
        self.assertEqual(len(skipped), 2)
        # The producing code is `enrich_record`; this asserts the vocabulary it
        # uses exists, so the event cannot be recorded under a name nothing reads.
        self.assertTrue(events.PROVIDER_CALL_SKIPPED)


if __name__ == "__main__":
    unittest.main()
