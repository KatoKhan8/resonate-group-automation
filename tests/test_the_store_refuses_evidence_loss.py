"""A write that would delete paid provider answers is refused.

`verification.apply` keeps the evidence list append-only, but it can only
defend the field. It never sees a contact dict being replaced wholesale - and
that is what happened: a discovery run re-minted three people from a provider
payload, and the evidence-bearing dicts went with them. Four paid verifier
calls became "no verification evidence" while the waterfall ledger still showed
the spend.

Every writer goes through `store`, including an ad-hoc operator script, which
is why the second guard lives here. It is the only one that would have caught
the incident.

It refuses rather than repairing. The writer is holding a list that has already
lost the rows, so putting them back means guessing which ones - and a guessed
provider answer is indistinguishable from a real one to `decide`, to the spend
audit and to every reviewer afterwards.
"""
import os
import shutil
import tempfile
import unittest

from src import store, verification as V

EMAIL = "pat@acme.test"


class TheStoreRefusesEvidenceLoss(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-evloss-")
        self._prev = {k: os.environ.get(k)
                      for k in ("QUEUE",) + store.STATE_OVERRIDES}
        store.use_directory(os.path.join(self.tmp, "work"))
        rec = store.new_record("acme", "domains", "c", "Acme Ltd", "acme.test")
        person = {"key": "pat", "name": "Pat Doe", "email": EMAIL}
        ev = [V.result("contactout", V.S_VALID, EMAIL),
              V.result("reoon", V.S_VALID, EMAIL)]
        V.apply(person, V.decide(ev), ev)
        rec["contacts"] = [person]
        store.save([rec])

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def stored(self):
        rec = store.load()[0]
        return (rec["contacts"][0].get("verification") or {}).get("evidence") or []

    # ------------------------------------------------------------ the guard

    def test_replacing_a_contact_with_a_bare_dict_is_refused(self):
        """The incident, exactly: a provider payload minted a fresh contact."""
        rec = store.load()[0]
        rec["contacts"] = [{"key": "pat", "name": "Pat Doe", "email": EMAIL,
                            "verdict": None}]
        with self.assertRaises(store.EvidenceLost):
            store.save([rec])

    def test_nothing_is_written_by_the_refusal(self):
        rec = store.load()[0]
        rec["contacts"] = [{"key": "pat", "name": "Pat Doe", "email": EMAIL}]
        try:
            store.save([rec])
        except store.EvidenceLost:
            pass
        self.assertEqual(len(self.stored()), 2)

    def test_dropping_the_contact_entirely_is_refused(self):
        rec = store.load()[0]
        rec["contacts"] = []
        with self.assertRaises(store.EvidenceLost):
            store.save([rec])

    def test_the_refusal_names_the_address_and_provider(self):
        rec = store.load()[0]
        rec["contacts"] = []
        try:
            store.save([rec])
        except store.EvidenceLost as e:
            self.assertIn(EMAIL, str(e))
            self.assertIn("contactout", str(e))
        else:
            self.fail("the write was not refused")

    # -------------------------------------------- and honest writes proceed

    def test_adding_evidence_is_allowed(self):
        """Otherwise the guard freezes the record instead of protecting it."""
        rec = store.load()[0]
        person = rec["contacts"][0]
        more = [V.result("deliverable", V.S_VALID, EMAIL)]
        V.apply(person, V.decide(more), more)
        store.save([rec])
        self.assertEqual(len(self.stored()), 3)

    def test_excluding_the_contact_keeps_the_evidence_and_is_allowed(self):
        """An exclusion moves somebody out of the selection. It does not
        un-buy what was spent on them, and `set_aside` keeps them whole."""
        rec = store.load()[0]
        rec["excluded"] = [dict(rec["contacts"][0], why="over the cap")]
        rec["contacts"] = []
        store.save([rec])
        kept = (store.load()[0]["excluded"][0].get("verification") or {})
        self.assertEqual(len(kept.get("evidence") or []), 2)

    def test_an_unrelated_record_is_unaffected(self):
        rec = store.load()[0]
        other = store.new_record("other", "domains", "c", "Other", "other.test")
        store.save([rec, other])
        self.assertEqual(len(store.load()), 2)


class TheTimestampIsProvenanceNotIdentity(unittest.TestCase):
    """The guard keyed evidence on `(address, provider, at, status)`, and `at`
    is stamped by `verification.result` with `store.now()`.

    So rebuilding the same answer a second later produced a different key and
    the original read as deleted. It surfaced as one intermittent failure in a
    6,380-test run - `test_cadence_sequence` rebuilding a contact that
    `seed_records` had just written - and passed alone, as a class, and in the
    next full run, because it only fires when the two calls straddle a clock
    tick.

    A false positive on a safety guard is worse than it sounds. It appears at
    random, it blocks a write that lost nothing, and the fastest way to make it
    stop is to weaken the guard - which is the one thing that must not happen
    to this one.
    """

    def person(self, at, providers=("contactout", "deliverable")):
        person = {"key": "k", "name": "N", "email": "champ@acme.test"}
        evidence = [V.result(name, V.S_VALID, "champ@acme.test", at=at)
                    for name in providers]
        V.apply(person, V.decide(evidence), evidence)
        return person

    def rec(self, *contacts):
        return [{"id": "acme", "contacts": list(contacts)}]

    def test_the_same_answer_restamped_is_not_a_loss(self):
        self.assertTrue(store.refuse_evidence_loss(
            self.rec(self.person("2026-09-09T10:00:00Z")),
            self.rec(self.person("2026-09-09T10:00:01Z"))))

    def test_a_dropped_provider_is_still_a_loss(self):
        """The strictness that mattered has to survive the fix."""
        with self.assertRaises(store.EvidenceLost):
            store.refuse_evidence_loss(
                self.rec(self.person("2026-09-09T10:00:00Z")),
                self.rec(self.person("2026-09-09T10:00:01Z",
                                     ("contactout",))))

    def test_wiping_the_evidence_is_still_a_loss(self):
        with self.assertRaises(store.EvidenceLost):
            store.refuse_evidence_loss(
                self.rec(self.person("2026-09-09T10:00:00Z")),
                self.rec({"key": "k", "name": "N",
                          "email": "champ@acme.test"}))

    def test_two_answers_collapsing_into_one_is_a_loss(self):
        """Counted rather than set-compared: both rows share a key once `at`
        is out of it, so a set would have called this unchanged."""
        twice = self.person("2026-09-09T10:00:00Z", ("contactout",))
        second = V.result("contactout", V.S_VALID, "champ@acme.test",
                          at="2026-09-09T11:00:00Z")
        V.apply(twice, V.decide([second]), [second])
        self.assertEqual(len(V.evidence_of(twice)), 2)
        with self.assertRaises(store.EvidenceLost):
            store.refuse_evidence_loss(
                self.rec(twice),
                self.rec(self.person("2026-09-09T12:00:00Z", ("contactout",))))

    def test_a_different_verdict_from_one_provider_is_its_own_answer(self):
        """valid then invalid are two answers, not one re-stamped."""
        with self.assertRaises(store.EvidenceLost):
            store.refuse_evidence_loss(
                self.rec(self.person("2026-09-09T10:00:00Z", ("contactout",))),
                self.rec({"key": "k", "name": "N",
                          "email": "champ@acme.test",
                          "verification": {"evidence": [
                              V.result("contactout", V.S_INVALID,
                                       "champ@acme.test",
                                       at="2026-09-09T11:00:00Z")]}}))


if __name__ == "__main__":
    unittest.main()
