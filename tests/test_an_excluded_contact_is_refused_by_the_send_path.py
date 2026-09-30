#!/usr/bin/env python3
"""A person on the record's `excluded` list never reaches the send path.

THE DEFECT, MEASURED 2026-09-30 ON THE LIVE QUEUE.

One contact stood in BOTH `rec["contacts"]`, carrying `sendable: True`, AND in
`rec["excluded"]` with the reason "verification pair does not satisfy this
client's policy". `eligibility._selected` returned None for her - not blocked -
because it asked `contact["excluded"]`, a FLAG on the contact, while the
exclusion itself lives in `rec["excluded"]`, a LIST of contact dicts written by
`personas.set_aside`. Two representations of one fact; the send path read the
one nobody writes.

She was stopped a gate later, by verification. That is luck and not a guard:
the verification gate was itself asking the wrong client's policy, and
correcting it - which is the commit after this one - would have made an
excluded person eligible. So the order matters and is asserted here directly:
exclusion is decided BEFORE and INDEPENDENTLY OF verification.

No real person appears in this file. The keys and addresses are synthetic.
"""
import unittest

from src import eligibility


def _contact(key="set-aside-person", email="set.aside@example.test"):
    return {
        "key": key,
        "name": "Set Aside Person",
        "first_name": "Set",
        "email": email,
        "title": "Chief Financial Officer",
        "persona": "economic_buyer",
        "angle": "finance",
        "sendable": True,
        "primary": True,
        "verification": {
            "state": "verified",
            "sendable": True,
            "evidence": [{"provider": name, "status": "valid", "email": email,
                          "at": "2026-09-30T12:00:00+00:00"}
                         for name in ("deliverable", "reoon")],
        },
    }


def _record(contact, excluded=()):
    return {
        "id": "example-test",
        "client": "productive",
        "lane": "domains",
        "company": "Example Agency",
        "domain": "example.test",
        "state": "ready",
        "contacts": [contact],
        "excluded": list(excluded),
        "cadence": {contact["key"]: {"em1": {
            "channel": "email",
            "subject": "utilisation and capacity across live projects",
            "body": ("Set, I work with Marketing teams on utilisation and "
                     "capacity across live projects, and I do not know how "
                     "Example Agency handles it\n\nIs that roughly how it "
                     "works at Example Agency today, or have you already put "
                     "something in place for it?"),
        }}},
    }


class TheExcludedListIsRead(unittest.TestCase):

    def test_a_contact_named_on_the_excluded_list_is_not_selected(self):
        contact = _contact()
        record = _record(contact, excluded=[dict(contact)])
        self.assertEqual(eligibility._selected(record, contact),
                         eligibility.BLOCKED_NOT_SELECTED)

    def test_the_same_person_under_a_rebuilt_key_is_still_excluded(self):
        """Re-enrichment can rebuild a contact under a different key. The
        address is the same person, so the address is matched too."""
        contact = _contact(key="set-aside-person-2")
        stale = _contact(key="set-aside-person")
        record = _record(contact, excluded=[stale])
        self.assertEqual(eligibility._selected(record, contact),
                         eligibility.BLOCKED_NOT_SELECTED)

    def test_a_contact_absent_from_the_list_is_selected(self):
        """The control. Without it this file would pass with a rule that
        refuses everyone."""
        contact = _contact()
        other = _contact(key="somebody-else", email="somebody@example.test")
        record = _record(contact, excluded=[other])
        self.assertIsNone(eligibility._selected(record, contact))

    def test_an_empty_excluded_list_selects(self):
        contact = _contact()
        self.assertIsNone(eligibility._selected(_record(contact), contact))

    def test_the_contact_level_flag_still_refuses(self):
        """The check that already existed is not replaced by the new one."""
        contact = _contact()
        contact["excluded"] = True
        self.assertIsNone(_record(contact).get("excluded") or None)
        self.assertEqual(eligibility._selected(_record(contact), contact),
                         eligibility.BLOCKED_NOT_SELECTED)


class ExclusionOutranksVerification(unittest.TestCase):
    """The ordering the next commit makes load-bearing."""

    def test_an_excluded_contact_is_refused_though_verification_would_clear(self):
        contact = _contact()
        record = _record(contact, excluded=[dict(contact)])
        verdict = eligibility.decide(record, contact, "em1",
                                     step=record["cadence"][contact["key"]]["em1"])
        self.assertEqual(verdict["verdict"], eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_NOT_SELECTED, verdict["reasons"])

    def test_the_refusal_does_not_depend_on_the_verification_answer(self):
        """Strip the evidence entirely: the reason must not change to a
        verification one. An excluded person is excluded for being excluded."""
        contact = _contact()
        contact["verification"] = {"state": "unknown", "sendable": False,
                                   "evidence": []}
        record = _record(contact, excluded=[dict(contact)])
        verdict = eligibility.decide(record, contact, "em1",
                                     step=record["cadence"][contact["key"]]["em1"])
        self.assertEqual(verdict["verdict"], eligibility.BLOCKED)
        self.assertIn(eligibility.BLOCKED_NOT_SELECTED, verdict["reasons"])


if __name__ == "__main__":
    unittest.main()
