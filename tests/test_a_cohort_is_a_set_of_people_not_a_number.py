#!/usr/bin/env python3
"""A count is not a cohort, and 43 of the wrong people is still 43.

The 2026-10-01 canary shortlist lived in one text file outside the repository and
no committed script reproduced it, so the number could not be re-measured after a
rule changed. Measured before `scripts/canary_cohort.py` was written: NO
conjunction of up to four of fifteen plausible record and contact predicates
reproduces those 43 members. `sendable` covers all 43 and selects 873.
`sendable AND mx AND not_dropped` selects 872.

AND THE NEAR MISS IS THE REASON THIS FILE EXISTS. `bison_lead_id AND
has_research` selects EXACTLY 43 rows, and 52 of them are the wrong people - a
symmetric difference larger than the cohort. A session comparing sizes would have
called that a successful reproduction. So the script reports a DIGEST OF THE
MEMBER SET and these tests pin the property that makes a digest worth having:
same people, same digest; same count, different people, different digest.

The other property asserted here is that nothing prints a prospect. The script's
whole reason for taking its input from a path outside the repository is that the
shortlist flags its own contact keys as PII, because they are derived from
people's names - so a digest over the set, and never a member list, is the only
thing that may be printed or committed.
"""
import io
import unittest
from contextlib import redirect_stdout

from scripts import canary_cohort
from tests.base import QueueTest


class ADigestIdentifiesThePeopleNotTheCount(unittest.TestCase):

    def test_the_same_set_in_any_order_digests_the_same(self):
        pairs = [("b-com", "two"), ("a-com", "one"), ("c-com", "three")]
        self.assertEqual(canary_cohort.digest(pairs),
                         canary_cohort.digest(list(reversed(pairs))))
        self.assertEqual(canary_cohort.digest(pairs),
                         canary_cohort.digest(set(pairs)))

    def test_the_same_count_with_different_members_digests_differently(self):
        """THE MEASURED NEAR MISS, as a property.

        Two cohorts of equal size and no member in common must not compare
        equal by anything this script prints.
        """
        a = [("a-com", "one"), ("b-com", "two"), ("c-com", "three")]
        b = [("x-com", "nine"), ("y-com", "ten"), ("z-com", "eleven")]
        self.assertEqual(len(a), len(b))
        self.assertNotEqual(canary_cohort.digest(a), canary_cohort.digest(b))

    def test_one_member_changing_changes_the_digest(self):
        a = [("a-com", "one"), ("b-com", "two")]
        b = [("a-com", "one"), ("b-com", "three")]
        self.assertNotEqual(canary_cohort.digest(a), canary_cohort.digest(b))

    def test_the_digest_is_one_way_and_carries_no_member(self):
        """It is printed and committed, so it must not be a lookup table."""
        pairs = [("kestrelwharf-test", "dana-whitfield")]
        out = canary_cohort.digest(pairs)
        self.assertNotIn("dana", out)
        self.assertNotIn("kestrelwharf", out)
        self.assertEqual(16, len(out))
        self.assertTrue(all(ch in "0123456789abcdef" for ch in out))


class TheCriteriaAreCodeAndReRunnable(QueueTest):

    def rec(self, rid, contacts, **over):
        row = {"id": rid, "domain": f"{rid}.test", "contacts": contacts}
        row.update(over)
        return row

    #: A MODULE-LEVEL SENTINEL, because `email or <default>` treats the EMPTY
    #: STRING as absent and substitutes the default - so the "no address" case
    #: silently became a valid one and the first run of this file reported a
    #: contact selected that should have been excluded. The bug was in the
    #: fixture, which is the second time that exact shape has appeared in this
    #: work: a falsy value is not a missing one.
    UNSET = object()

    def contact(self, key, sendable=True, mx=True, email=UNSET, **over):
        row = {"key": key,
               "email": (f"{key}@example.test" if email is self.UNSET
                         else email),
               "sendable": sendable, "mx": {"status": "ok"} if mx else None}
        row.update(over)
        return row

    def test_each_clause_excludes_and_is_counted(self):
        """Every exclusion is a named reason, never a silent drop."""
        recs = {
            "ok-com": self.rec("ok-com", [self.contact("yes")]),
            "dropped-com": self.rec("dropped-com", [self.contact("a")],
                                    drop_reason="not icp"),
            "noaddr-com": self.rec("noaddr-com", [self.contact("b", email="")]),
            "unsendable-com": self.rec("unsendable-com",
                                       [self.contact("c", sendable=False)]),
            "nomx-com": self.rec("nomx-com", [self.contact("d", mx=False)]),
            "flagged-com": self.rec("flagged-com",
                                    [self.contact("e", excluded=True)]),
            "setaside-com": self.rec(
                "setaside-com", [self.contact("f", email="f@setaside.test")],
                excluded=[{"email": "f@setaside.test"}]),
        }
        chosen, why = canary_cohort.derive(recs)
        self.assertEqual({("ok-com", "yes")}, chosen)
        self.assertEqual(1, why["record dropped"])
        self.assertEqual(1, why["no address"])
        self.assertEqual(1, why["not sendable"])
        self.assertEqual(1, why["no MX verdict"])
        self.assertEqual(1, why["contact flagged excluded"])
        self.assertEqual(1, why["set aside on the record"])

    def test_it_is_a_pure_function_of_the_store(self):
        """Two runs over identical input select identically. No clock, no order."""
        recs = {"a-com": self.rec("a-com", [self.contact("one"),
                                            self.contact("two")]),
                "b-com": self.rec("b-com", [self.contact("three")])}
        first, _ = canary_cohort.derive(recs)
        second, _ = canary_cohort.derive(dict(reversed(list(recs.items()))))
        self.assertEqual(first, second)
        self.assertEqual(canary_cohort.digest(first),
                         canary_cohort.digest(second))

    def test_a_set_aside_contact_is_matched_on_address_not_only_on_key(self):
        """`personas.set_aside` stores whole contact dicts, and a re-enriched
        contact can be rebuilt under a different key while remaining the same
        person - which `eligibility._is_set_aside` exists for."""
        recs = {"x-com": self.rec(
            "x-com", [self.contact("rebuilt-key", email="same@x.test")],
            excluded=[{"key": "old-key", "email": "SAME@X.test"}])}
        chosen, why = canary_cohort.derive(recs)
        self.assertEqual(set(), chosen)
        self.assertEqual(1, why["set aside on the record"])


class NothingPrintsAProspect(QueueTest):

    def test_pinning_a_file_prints_no_address_name_or_key(self):
        """The reason the input stays outside the repository in the first place."""
        import os
        import tempfile

        pinned = ("\n  1  kestrelwharf-test  key=dana-whitfield "
                  "persona=champion campaign=FRESH\n"
                  "  2  brightpath-test  key=alex-morgan "
                  "persona=economic_buyer campaign=491/approved\n")
        handle, path = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                out.write(pinned)
            found = canary_cohort.pinned(path)
            self.assertEqual(2, len(found))
            self.assertEqual(("kestrelwharf-test", "dana-whitfield"), found[1])
            captured = io.StringIO()
            with redirect_stdout(captured):
                canary_cohort.main(["--pin", path])
            printed = captured.getvalue()
            for secret in ("dana-whitfield", "alex-morgan", "dana", "alex",
                           "@", "kestrelwharf-test", "brightpath-test"):
                self.assertNotIn(secret, printed,
                                 f"{secret!r} reached stdout; a cohort report "
                                 f"may carry counts and a digest and nothing "
                                 f"that identifies a person")
            self.assertIn(canary_cohort.digest(set(found.values())), printed)
        finally:
            os.unlink(path)

    def test_both_pinned_layouts_resolve_to_the_same_members(self):
        """The shortlist exists in two shapes; a digest must not depend on which."""
        rows = canary_cohort.PINNED_ROW.match(
            "  7  aimediagroup-com  key=rick-held persona=economic_buyer")
        addr = canary_cohort.PINNED_ROW_ADDR.match(
            "  7  aimediagroup-com  rick-held  <somebody@aimediagroup.test>  CFO")
        self.assertIsNotNone(rows)
        self.assertIsNotNone(addr)
        self.assertEqual((rows.group(2), rows.group(3)),
                         (addr.group(2), addr.group(3)))
