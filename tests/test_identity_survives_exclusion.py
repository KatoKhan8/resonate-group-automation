"""A key is an identity, not a membership, and two people are two events.

`identity.assign_keys` ran only in `personas.select`, over `rec["contacts"]` -
the *selection*. So excluding somebody stripped their key, every event written
under it pointed at nobody, and contacts created by enrichment had no key at
all until personas ran two stages later.

Both halves cost real data.

**Orphans.** 19 events across two records named keys that resolved to nothing.
`report.by_persona` and `by_angle` drop them silently; `audit.why_contacted`
answers "no verification evidence is stored for this address" for a person who
cost four verifier credits; and `eligibility`'s reply block matches on the same
key, so a rekey would stop recognising somebody who had told us to stop.

**Silent deduplication, which is worse because it is invisible.**
`events.record` includes the contact in the identity it hashes, precisely so
two touches to two people in the same second do not collide. Passing `None`
reintroduces that: two contacts at one domain, keyless, in the same second,
produced ONE stored event and the second was lost with nothing reporting it.

The repair is to restore identity, never to move an event. Migrating one
person's MX block onto another would assert a check that never ran against
their address - forging the support that "a message may only claim what the
event log supports" depends on.
"""
import os
import shutil
import tempfile
import unittest

from src import enrich, events, identity, personas, store


def person(name, email, title="Chief Operating Officer"):
    return {"name": name, "email": email, "title": title}


class IdentitySurvivesExclusion(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rga-identity-")
        self._prev = {k: os.environ.get(k)
                      for k in ("QUEUE",) + store.STATE_OVERRIDES}
        store.use_directory(os.path.join(self.tmp, "work"))

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def record(self):
        rec = store.new_record("acme", "domains", "c", "Acme Ltd", "acme.test")
        rec["company_facts"] = {"name": "Acme Ltd"}
        return rec

    # -------------------------------------------------- keys at entry

    def test_enrichment_keys_a_contact_before_anybody_can_name_it(self):
        rec = self.record()
        added, _ = enrich.merge_contacts(
            rec, [dict(person("Pat Doe", "pat@acme.test"), company="Acme Ltd")],
            "provider")
        self.assertTrue(all(c.get("key") for c in added))

    def test_two_contacts_at_one_domain_get_two_keys(self):
        """The precondition for two events. Keyless, they were one identity."""
        rec = self.record()
        added, _ = enrich.merge_contacts(rec, [
            dict(person("Pat Doe", "pat@acme.test"), company="Acme Ltd"),
            dict(person("Sam Roe", "sam@acme.test"), company="Acme Ltd")],
            "provider")
        keys = [c["key"] for c in added]
        self.assertEqual(len(set(keys)), 2, keys)

    def test_two_contacts_in_one_second_produce_two_events(self):
        """The silent loss, reproduced. `events.record` hashes the contact into
        the identity, so a null key made two lookups collide into one."""
        rec = self.record()
        added, _ = enrich.merge_contacts(rec, [
            dict(person("Pat Doe", "pat@acme.test"), company="Acme Ltd"),
            dict(person("Sam Roe", "sam@acme.test"), company="Acme Ltd")],
            "provider")
        rec["contacts"] = added
        at = "2026-09-08T15:49:45+00:00"
        for contact in rec["contacts"]:
            events.record(rec, events.MX_LOOKUP_STARTED,
                          contact_key=contact["key"], at=at,
                          email_domain="acme.test")
        started = [e for e in rec["events"]
                   if e.get("type") == events.MX_LOOKUP_STARTED]
        self.assertEqual(len(started), 2, "one contact's lookup was swallowed")
        self.assertEqual(len({e["id"] for e in started}), 2)

    # ------------------------------------------- identity outlives selection

    def test_excluding_somebody_does_not_take_their_key(self):
        rec = self.record()
        contact = dict(person("Pat Doe", "pat@acme.test"), key="pat-doe")
        rec["contacts"] = [contact]
        aside = personas.set_aside(contact, "over the cap")
        self.assertEqual(aside.get("key"), "pat-doe")

    def test_an_event_naming_nobody_is_a_validation_problem(self):
        rec = self.record()
        rec["contacts"] = [dict(person("Pat Doe", "pat@acme.test"),
                                key="pat-doe")]
        events.record(rec, events.MX_LOOKUP_STARTED, contact_key="ghost")
        problems = store.validate(rec)
        self.assertTrue(any("names no contact" in p for p in problems), problems)

    def test_a_contact_with_no_key_is_a_validation_problem(self):
        rec = self.record()
        rec["excluded"] = [person("Pat Doe", "pat@acme.test")]
        self.assertTrue(any("no key" in p for p in store.validate(rec)))

    def test_two_contacts_sharing_a_key_is_a_validation_problem(self):
        rec = self.record()
        rec["contacts"] = [dict(person("A", "a@acme.test"), key="same")]
        rec["excluded"] = [dict(person("B", "b@acme.test"), key="same")]
        self.assertTrue(any("held by 2" in p for p in store.validate(rec)))

    def test_a_well_formed_record_reports_nothing(self):
        """Otherwise the invariant fails everything and proves nothing."""
        rec = self.record()
        rec["contacts"] = [dict(person("Pat Doe", "pat@acme.test"),
                                key="pat-doe")]
        rec["excluded"] = [dict(person("Sam Roe", "sam@acme.test"),
                                key="sam-roe", why="over the cap")]
        events.record(rec, events.MX_LOOKUP_STARTED, contact_key="sam-roe")
        self.assertEqual(store.validate(rec), [])

    def test_an_excluded_contact_can_still_own_an_event(self):
        """The whole argument: the event is true, the person was real, and
        exclusion is a decision about them rather than a different person."""
        rec = self.record()
        rec["contacts"] = []
        rec["excluded"] = [dict(person("Pat Doe", "pat@acme.test"),
                                key="pat-doe", why="over the cap")]
        events.record(rec, events.MX_LOOKUP_STARTED, contact_key="pat-doe")
        self.assertEqual(store.validate(rec), [])


if __name__ == "__main__":
    unittest.main()
