"""When a cap forces a choice, the strategy's own priority decides it.

`qualification.persona_plan.persona_priority` is
`["operations", "finance", "resource_management", "founder"]` for an
operations-led account, with a stated reason: past about fifty people,
resourcing stops fitting in one head and an operations lead owns the problem
before finance does.

`personas.py` had zero references to `qualification`, `persona_plan` or
`routing`. The priority was computed by `routing.plan`, stored on the record,
read by `campaignseg` and `strategy` for segment keys and angles - and never
reached the one decision it was written to govern. So `cap_per_domain: 1` on
a bucket holding both CEO and COO titles kept the wrong person, twice, for two
different reasons:

**The spelling accident.** `title_score` measures how a title is *written*,
not seniority. "Chief Executive Officer" matches the config entry exactly (3);
"President & COO" only contains "COO" (2). Both people are unambiguously the
role they state; one is spelled the way the config spells it.

**The enrichment-order accident.** With equal scores the tie fell to
`0 if contact.get("email") else 1` - so the winner of a cap contest depended
on which person enrichment had reached an address for first. The same record
selected the COO before addresses arrived and the CEO after. Selection was not
stable under enrichment.

`routing`'s own title lists carried the bug `productive.yaml` documents having
fixed in the client vocabulary: `title_score("Chief Operating Officer", "COO")`
is 0 - no exact match, "coo" is not a substring, and the word arm skips words
of three characters or fewer. So the abbreviations are transcribed there too,
and only ever the expansion of one already in that same list.

This reorders an already-capped bucket. It does not change who is eligible and
it does not change how many people are contacted anywhere.
"""
import unittest

from src import clients, personas, routing


def contact(key, title, email=None):
    row = {"key": key, "name": key.replace("-", " ").title(), "title": title}
    if email:
        row["email"] = email
    return row


def record(contacts, priority=("operations", "finance",
                               "resource_management", "founder"),
           strategy="operations_led"):
    return {"id": "r1", "client": "productive", "lane": "domains",
            "domain": "acme.test", "contacts": list(contacts),
            "qualification": {"persona_plan": {
                "strategy": strategy,
                "persona_priority": list(priority)}}}


class TheCapKeepsWhoThePlanRanksFirst(unittest.TestCase):

    def setUp(self):
        self.config = clients.load("productive")

    def kept(self, rec):
        keep, _ = personas.select_domains(rec, self.config)
        return [c.get("title") for c in keep]

    # ------------------------------------------------------------ the defect

    def test_the_coo_beats_the_ceo_when_operations_leads(self):
        rec = record([contact("ceo", "CEO", "a@acme.test"),
                      contact("coo", "Chief Operating Officer", "b@acme.test")])
        self.assertEqual(self.kept(rec), ["Chief Operating Officer"])

    def test_a_president_and_coo_beats_an_exactly_spelled_ceo(self):
        """The spelling accident: 3 against 2 on title_score alone."""
        rec = record([contact("ceo", "Chief Executive Officer", "a@acme.test"),
                      contact("coo", "President & COO", "b@acme.test")])
        self.assertEqual(self.kept(rec), ["President & COO"])

    def test_the_winner_does_not_depend_on_who_has_an_address_yet(self):
        """Selection must be stable across an enrichment boundary."""
        before = record([contact("ceo", "CEO"),
                         contact("coo", "Chief Operating Officer")])
        after = record([contact("ceo", "CEO", "a@acme.test"),
                        contact("coo", "Chief Operating Officer", "b@acme.test")])
        self.assertEqual(self.kept(before), self.kept(after))

    def test_a_title_no_family_recognises_never_ranks_first(self):
        """Unmatched sorts last, not first.

        "Owner" is eligible - it is in `economic_buyer.titles` - and matches
        no routing family under this strategy. It must lose to a title the
        priority does recognise, rather than winning by defaulting to rank 0.
        An eligible title is used deliberately: an ineligible one is dropped
        by `classify` before ranking, so it would pass this test without the
        guard being involved at all.
        """
        # The unmatched contact is given every other advantage - the same
        # title score, an address, and a key that sorts first - so the persona
        # rank is the only thing that can decide against it. Without that, the
        # alphabetical tiebreak would pick the right answer by luck and this
        # test would pass while proving nothing.
        rec = record([contact("aaa-owner", "Owner", "a@acme.test"),
                      contact("zzz-coo", "Chief Operating Officer",
                              "b@acme.test")])
        self.assertEqual(self.kept(rec), ["Chief Operating Officer"])

    def test_a_stale_stored_plan_still_gets_the_current_spellings(self):
        """The plan is a snapshot; how a title is spelled is code.

        `qualify._inputs_fingerprint` digests company facts, so a corrected
        title list never reaches a record whose facts have not moved.
        """
        rec = record([contact("ceo", "CEO", "a@acme.test"),
                      contact("coo", "Chief Operating Officer", "b@acme.test")])
        rec["qualification"]["persona_plan"]["personas"] = {
            "operations": ["COO"]}          # the stale snapshot, abbreviation only
        self.assertEqual(self.kept(rec), ["Chief Operating Officer"])

    def test_every_family_listing_an_abbreviation_lists_it_spelled_out(self):
        strategies = routing.settings({})["strategies"]
        for name, strategy in strategies.items():
            for family, titles in (strategy.get("personas") or {}).items():
                for short, full in (("COO", "Chief Operating Officer"),
                                    ("CEO", "Chief Executive Officer"),
                                    ("CFO", "Chief Financial Officer")):
                    if short in titles:
                        self.assertIn(full, titles, f"{name}.{family}")

    # ------------------------------------------------- and it stays bounded

    def test_the_cap_still_bounds_the_fan_out(self):
        """Reordering a bucket must never widen it."""
        rec = record([contact("ceo", "CEO", "a@acme.test"),
                      contact("coo", "Chief Operating Officer", "b@acme.test"),
                      contact("md", "Managing Director", "c@acme.test")])
        self.assertEqual(len(self.kept(rec)), 1)

    def test_a_routing_family_match_does_not_make_anybody_eligible(self):
        """The client config decides who is eligible; the plan only breaks a
        tie among people already eligible."""
        rec = record([contact("an", "Chief Vibes Officer", "a@acme.test")])
        keep, excluded = personas.select_domains(rec, self.config)
        self.assertEqual(keep, [])
        self.assertTrue(excluded)

    def test_with_no_plan_the_order_is_exactly_what_it_was(self):
        """The term is inert when nothing computed a priority."""
        rec = record([contact("ceo", "Chief Executive Officer", "a@acme.test"),
                      contact("coo", "President & COO", "b@acme.test")])
        rec.pop("qualification")
        self.assertEqual(self.kept(rec), ["Chief Executive Officer"])


if __name__ == "__main__":
    unittest.main()
