#!/usr/bin/env python3
"""`domains_contact_no_angle` asks about people who can be written to.

THE DEFECT, MEASURED 2026-09-30.

The rule refused a draft if ANY contact on the record lacked an angle:

    if lane == "domains" and any(not c.get("angle") for c in rec["contacts"])

Its purpose, stated in `personas.default_angle`, is that a person with no angle
is "held rather than written to with the wrong words". That is a fact about the
person being written to. The LinkedIn half of `lint` has always scoped it to the
recipient. The email half did not.

It became load-bearing the day generation was scoped to a single contact. On the
three canary candidate records: every SENDABLE contact carried an angle - one
per record - and every contact without one was NOT sendable: 23, 20 and 4 of
them. The gate fired entirely on people who can never be emailed, and blocked
the one person whose angle was correct. `generate.plan` only sets angles for
workable contacts, so a record holding one unpersonaed, unverified contact could
never satisfy the old rule at all.

This is a SCOPE correction and not a relaxation. The four cases the operator
required are the four classes below, and (a) is the one that proves the gate
still bites.

No real person appears in this file.
"""
import unittest

from src import lint


def _contact(key, angle=None, sendable=True, verified=True,
             email=None, excluded=False):
    email = email or f"{key}@example.test"
    contact = {
        "key": key,
        "name": key.replace("-", " ").title(),
        "first_name": key.split("-")[0].title(),
        "email": email,
        "title": "Chief Financial Officer",
        "persona": "economic_buyer",
        "sendable": sendable,
        "primary": True,
    }
    if angle:
        contact["angle"] = angle
    if excluded:
        contact["excluded"] = True
    if verified:
        contact["verification"] = {
            "state": "verified", "sendable": True,
            "evidence": [{"provider": name, "status": "valid", "email": email,
                          "at": "2026-09-30T12:00:00+00:00"}
                         for name in ("deliverable", "reoon")]}
    else:
        contact["verification"] = {"state": "unknown", "sendable": False,
                                   "evidence": []}
    return contact


def _step(first_name):
    return {
        "channel": "email",
        "subject": "margin visibility while projects are active",
        "body": (f"{first_name}, I work with Marketing teams on margin "
                 "visibility while projects are active, and I do not know how "
                 "Example Agency handles it\n\nIs that roughly how it works at "
                 "Example Agency today, or have you already put something in "
                 "place for it?"),
    }


def _record(contacts, excluded=()):
    return {
        "id": "example-test",
        "client": "productive",
        "lane": "domains",
        "company": "Example Agency",
        "domain": "example.test",
        "state": "ready",
        "contacts": list(contacts),
        "excluded": list(excluded),
    }


def _codes(record, contact):
    return lint.check(record, contact["key"], _step(contact["first_name"]))


class TheGateStillBites(unittest.TestCase):
    """(a) The negative control. Without this the rest is a hole."""

    def test_a_sendable_contact_without_an_angle_fails(self):
        contact = _contact("no-angle-person")
        codes = _codes(_record([contact]), contact)
        self.assertIn("domains_contact_no_angle", codes)

    def test_a_second_sendable_contact_without_an_angle_fails_the_first(self):
        """Scope is wider than the recipient: another person who can be
        written to, and has no angle, still refuses the record's copy."""
        writing_to = _contact("angled-person", angle="finance")
        other = _contact("other-sendable-person")
        codes = _codes(_record([writing_to, other]), writing_to)
        self.assertIn("domains_contact_no_angle", codes)

    def test_the_recipient_is_in_scope_even_when_not_sendable(self):
        """A contact the record does not call sendable is still in scope when
        the step being checked is addressed to them."""
        contact = _contact("unverified-person", sendable=False, verified=False)
        codes = _codes(_record([contact]), contact)
        self.assertIn("domains_contact_no_angle", codes)


class TheGateIgnoresPeopleWhoCannotBeWrittenTo(unittest.TestCase):
    """(b) The correction itself."""

    def test_an_unsendable_contact_without_an_angle_does_not_refuse(self):
        writing_to = _contact("angled-person", angle="finance")
        stranger = _contact("unsendable-stranger", sendable=False,
                            verified=False)
        codes = _codes(_record([writing_to, stranger]), writing_to)
        self.assertNotIn("domains_contact_no_angle", codes)

    def test_the_canary_shape_passes(self):
        """The measured shape: one angled sendable contact and twenty-three
        unsendable ones with no angle."""
        writing_to = _contact("angled-person", angle="finance")
        crowd = [_contact(f"unsendable-{n}", sendable=False, verified=False)
                 for n in range(23)]
        codes = _codes(_record([writing_to] + crowd), writing_to)
        self.assertNotIn("domains_contact_no_angle", codes)

    def test_a_record_of_only_angled_sendable_contacts_passes(self):
        writing_to = _contact("angled-person", angle="finance")
        peer = _contact("other-angled-person", angle="operations")
        codes = _codes(_record([writing_to, peer]), writing_to)
        self.assertNotIn("domains_contact_no_angle", codes)


class ExclusionIsNotAWayToSkipTheGate(unittest.TestCase):
    """(c) A contact on the excluded list, still marked sendable, still counts."""

    def test_an_excluded_but_sendable_contact_without_an_angle_fails(self):
        writing_to = _contact("angled-person", angle="finance")
        set_aside = _contact("set-aside-person")
        record = _record([writing_to, set_aside], excluded=[dict(set_aside)])
        self.assertIn("domains_contact_no_angle", _codes(record, writing_to))

    def test_the_contact_level_flag_does_not_exempt_either(self):
        writing_to = _contact("angled-person", angle="finance")
        flagged = _contact("flagged-person", excluded=True)
        self.assertIn("domains_contact_no_angle",
                      _codes(_record([writing_to, flagged]), writing_to))


class TheScopeItself(unittest.TestCase):

    def test_send_scope_excludes_the_unsendable(self):
        writing_to = _contact("angled-person", angle="finance")
        stranger = _contact("unsendable-stranger", sendable=False,
                            verified=False)
        scope = lint.send_scope(_record([writing_to, stranger]), writing_to)
        self.assertEqual([c["key"] for c in scope], ["angled-person"])

    def test_a_stale_sendable_flag_keeps_a_contact_in_scope(self):
        """Conservative in both directions: the flag alone is enough to be
        asked about, so a hand-set record cannot smuggle anybody past."""
        writing_to = _contact("angled-person", angle="finance")
        stale = _contact("stale-flag-person", sendable=True, verified=False)
        scope = lint.send_scope(_record([writing_to, stale]), writing_to)
        self.assertIn("stale-flag-person", [c["key"] for c in scope])

    def test_scope_with_no_recipient_is_the_sendable_contacts(self):
        angled = _contact("angled-person", angle="finance")
        stranger = _contact("unsendable-stranger", sendable=False,
                            verified=False)
        scope = lint.send_scope(_record([angled, stranger]))
        self.assertEqual([c["key"] for c in scope], ["angled-person"])


class OtherLanesAreUnaffected(unittest.TestCase):

    def test_a_cold_record_is_not_asked_about_angles(self):
        contact = _contact("no-angle-person")
        record = _record([contact])
        record["lane"] = "cold"
        record["hook"] = "they published a resourcing post"
        self.assertNotIn("domains_contact_no_angle", _codes(record, contact))


if __name__ == "__main__":
    unittest.main()
