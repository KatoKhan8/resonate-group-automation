"""The history monitor never pulls a finance, payroll, HR, admin or
credential room.

Operator decision, 2026-09-22. The catalogue exists to answer questions about
outreach. Nothing it could learn in a payroll channel is worth having that
material sitting in `work/` at all, and "we only summarised it" is not a
defence once the raw history is on disk.

The load-bearing case is the LAST one: a room whose NAME is innocuous and
whose PURPOSE is not. A name-only rule reads `#leadership` with a purpose of
"comp planning and salary bands", which is exactly the room this exists for.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "slack_history",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "scripts", "slack_history.py"))
slack_history = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slack_history)


def channel(name, purpose="", topic=""):
    return {"id": "C1", "name": name,
            "purpose": {"value": purpose}, "topic": {"value": topic}}


class TestTheNamedRoomsAreRefused(unittest.TestCase):

    def test_each_named_category_is_excluded(self):
        for name in ("finance", "finance-ops", "payroll", "payroll-2026",
                     "hr", "hr-updates", "human-resources", "people-ops",
                     "admin", "admin-internal", "credentials", "secrets",
                     "billing", "invoicing", "salaries", "api-keys"):
            with self.subTest(name=name):
                self.assertTrue(slack_history.is_sensitive(channel(name)),
                                f"#{name} would have been pulled")

    def test_an_ordinary_room_is_not_excluded(self):
        """The rule has to leave the estate's actual channels alone."""
        for name in ("resonate-os", "replies-productive",
                     "resonate-notifications", "general", "engineering"):
            with self.subTest(name=name):
                self.assertFalse(slack_history.is_sensitive(channel(name)),
                                 f"#{name} was excluded and should not be")

    def test_a_short_term_does_not_swallow_an_unrelated_name(self):
        """`hr` must not match `#thread-watch` or `#chruby`."""
        for name in ("thread-watch", "chruby", "shredder"):
            with self.subTest(name=name):
                self.assertFalse(slack_history.is_sensitive(channel(name)))


class TestThePurposeIsReadToo(unittest.TestCase):
    """The case a name-only rule gets wrong."""

    def test_an_innocuous_name_with_a_sensitive_purpose_is_excluded(self):
        room = channel("leadership",
                       purpose="compensation planning and salary bands")
        self.assertTrue(slack_history.is_sensitive(room),
                        "a room whose purpose is comp planning was pulled")

    def test_a_sensitive_topic_is_excluded(self):
        room = channel("ops-sync", topic="rotating the vault credentials")
        self.assertTrue(slack_history.is_sensitive(room))


class TestItFailsClosed(unittest.TestCase):
    """An unreadable shape is excluded, never included by default."""

    def test_a_non_dict_is_sensitive(self):
        for value in (None, "", [], "finance"):
            with self.subTest(value=value):
                self.assertTrue(slack_history.is_sensitive(value))

    def test_a_channel_with_no_name_or_purpose_is_not_crashed_on(self):
        self.assertFalse(slack_history.is_sensitive({"id": "C2"}))


class TestTheListIsBilingual(unittest.TestCase):
    """An English-only rule read `#racuni` - invoices - straight past."""

    def test_croatian_finance_rooms_are_excluded(self):
        for name in ("racuni", "ra\u010duni", "fakture", "knjigovodstvo",
                     "place", "pla\u0107e", "porezi", "lozinke"):
            with self.subTest(name=name):
                self.assertTrue(slack_history.is_sensitive(channel(name)),
                                f"#{name} would have been pulled")

    def test_diacritics_are_folded_not_required(self):
        """`#ra\u010duni` and `#racuni` are the same room for this purpose."""
        self.assertTrue(slack_history.is_sensitive(channel("ra\u010duni")))
        self.assertTrue(slack_history.is_sensitive(channel("racuni")))

    def test_an_ordinary_croatian_room_is_not_excluded(self):
        for name in ("prodaja", "marketing-tim", "razvoj"):
            with self.subTest(name=name):
                self.assertFalse(slack_history.is_sensitive(channel(name)))


if __name__ == "__main__":
    unittest.main()
