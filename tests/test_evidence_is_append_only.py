"""A provider answer that was bought is never deleted by a later write.

Three paid verifications for one address became `{"state": "unknown",
"reason": "no verification evidence", "evidence": []}` while the waterfall
ledger still showed the spend. `apply` wrote whatever list the caller handed
it, so a caller holding a shorter list deleted the difference.

The rule is NOT "unknown must never overwrite a verdict". That rule is unsafe:
when an operator corrects a bounced address, unknown is the truthful answer,
and a no-downgrade rule on `state` would make the new mailbox inherit the old
one's confirmations - the exact drift `evidence_for`'s address binding exists
to stop.

The rule is one level down, over the durable fact rather than the cached
opinion about it:

    the evidence list is append-only, and the state is recomputed from it.

`is_sendable` already documents that hierarchy. Given append-only evidence,
unknown-over-a-verdict becomes impossible except where it is true - which is
the carve-out a state-level rule cannot express, and the last test here is
that carve-out.
"""
import unittest

from src import enrich, verification as V

EMAIL = "pat@acme.test"


def rows(*statuses):
    return [V.result(p, s, EMAIL) for p, s in statuses]


def confirmed():
    """A contact two vendors approved."""
    person = {"key": "pat", "name": "Pat Doe", "email": EMAIL}
    ev = rows(("contactout", V.S_VALID), ("reoon", V.S_VALID))
    V.apply(person, V.decide(ev), ev)
    return person


class EvidenceIsAppendOnly(unittest.TestCase):

    def stored(self, person):
        return (person.get("verification") or {}).get("evidence") or []

    # ------------------------------------------------------------ the rule

    def test_an_empty_list_cannot_clear_the_evidence(self):
        person = confirmed()
        V.apply(person, V.decide([]), [])
        self.assertEqual(len(self.stored(person)), 2)

    def test_an_empty_list_cannot_clear_the_verdict(self):
        """The direct expression of what happened: a run that asked nobody
        published "no verification evidence" as though it were a finding."""
        person = confirmed()
        V.apply(person, V.decide([]), [])
        self.assertTrue(person["verification"]["sendable"])

    def test_a_shorter_list_keeps_what_it_did_not_restate(self):
        person = confirmed()
        one = rows(("contactout", V.S_VALID))
        V.apply(person, V.decide(one), one)
        providers = {e["provider"] for e in self.stored(person)}
        self.assertEqual(providers, {"contactout", "reoon"})

    def test_a_restated_row_is_not_duplicated(self):
        person = confirmed()
        again = [dict(self.stored(person)[0])]
        V.apply(person, V.decide(again), again)
        self.assertEqual(len(self.stored(person)), 2)

    def test_a_new_answer_is_appended(self):
        """Otherwise the guard freezes the record and proves nothing."""
        person = confirmed()
        more = rows(("deliverable", V.S_VALID))
        V.apply(person, V.decide(more), more)
        self.assertEqual(len(self.stored(person)), 3)

    # ------------------------------------------------- a stop is not a find

    def test_a_budget_stop_says_so_rather_than_reporting_a_finding(self):
        person = {"key": "pat", "name": "Pat Doe", "email": EMAIL}
        V.verify(person, V.DEFAULT_POLICY, live=True, rec=None,
                 budget=enrich.Budget(0))
        block = person.get("verification") or {}
        self.assertEqual(block.get("stopped"), "batch verification budget exhausted")
        self.assertIn("stopped early", block.get("reason") or "")

    # ------------------------------------------------------- the carve-out

    def test_a_corrected_address_is_unknown_and_keeps_the_history(self):
        """The reason the rule is not "unknown never overwrites a verdict".

        Evidence is bound to the address it was bought for, so a corrected
        mailbox is honestly unverified while the old address's answers
        survive as history.
        """
        person = confirmed()
        person["email"] = "p.doe@acme.test"
        V.apply(person, V.decide(V.all_evidence(person)), [])
        self.assertFalse(person["verification"]["sendable"])
        self.assertEqual(len(self.stored(person)), 2,
                         "history for the previous mailbox was destroyed")
        self.assertEqual(person["verification"]["providers"], [],
                         "the new address must not inherit confirmations")


if __name__ == "__main__":
    unittest.main()
