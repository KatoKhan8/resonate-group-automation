#!/usr/bin/env python3
"""A cached client policy cannot outlive the config it was computed from.

Found 2026-10-15 by `suppression/0110` and reproduced here with different
instruments (glm-b, TASK 0160): `lint._POLICY_CACHE` was keyed on the client
name alone. `clients_dir()` reads `CLIENTS_DIR` from the environment on
every call, dozens of test modules point it at a fixture directory, and the
suite runs in ONE process - so a policy computed while a redirect was
active, or a `None` cached because the redirect hid the client's file, was
still being served after `tests/envisolation.py` had handed the environment
back. A green control failed only inside a full run, which made a 232-name
reference read as 233. The one-line fix on suppression's branch clears the
cache in that one module's setUp; this module pins the property the cache
itself must hold, so no module has to remember.

The production shape of the same defect is a process that cached a client's
verification roles before the operator edited the YAML. Productive moved
primary to Deliverable on 2026-09-21; a watcher that had already cached the
old roles would keep refusing what the client's own policy cleared - the
804-of-1,308 refusal `src/eligibility.py` documents - until a restart.

THE FIX THIS MODULE PINS is the one `operatorexclusion._CACHE` already uses
for the exclusion register: a cached value is served only while the file it
was computed from still has the same resolved path, mtime and size, and a
missing file is never cached at all. One `os.stat` per lookup keeps the
cache's own reason for existing intact - `check` runs once per step per
contact.

WHAT THIS IS NOT. No policy changes and no lint rule moves: every lookup
returns exactly what a fresh `clients.load` would have returned, `None`
still means the conservative default, and a record with no client still
gets it. The only behaviour that changes is the cache no longer answering
for a config it did not read.
"""
import os
import shutil
import tempfile
import unittest

from src import clients, eligibility, lint, verification

#: A slug no real `config/clients/` entry will ever carry, so the rewrite
#: tests cannot be satisfied by somebody else's file.
FICTIONAL = "poisonme"

#: The `verification:` block is the only part `policy_for` reads; the rest
#: is the minimum `clients.load` accepts. The two variants differ in length
#: as well as content, so a rewrite changes the file's identity even if the
#: filesystem clock has not ticked between them.
CONFIG = """name: Poisonme
domain: poisonme.test
booking_link: https://poisonme.test/book/
verification:
  primary: {primary}
  secondary: reoon
  catch_all: reoon
"""

VERIFICATION_REASONS = {eligibility.HELD_VERIFICATION_UNKNOWN,
                        eligibility.HELD_INSUFFICIENT_CONFIRMATIONS,
                        eligibility.BLOCKED_NOT_SENDABLE}


def _contact(key="someone", email="someone@example.test"):
    """Verified by the pair the record's client actually requires."""
    return {"key": key, "name": "Someone Example", "email": email,
            "title": "Chief Financial Officer", "persona": "economic_buyer",
            "angle": "finance",
            "verification": {"state": "verified", "evidence": [
                {"provider": name, "status": "valid", "email": email}
                for name in ("deliverable", "reoon")]}}


def _record(contact, client="productive"):
    step = {"channel": "email",
            "subject": "margin visibility while projects are active",
            "body": ("Someone, I work with Marketing teams on margin "
                     "visibility while projects are active, and I do not know "
                     "how Example Agency handles it\n\nIs that roughly how it "
                     "works at Example Agency today, or have you already put "
                     "something in place for it?")}
    return {"id": "poison-test", "client": client, "lane": "domains",
            "company": "Example Agency", "domain": "example.test",
            "state": "ready", "contacts": [contact], "excluded": [],
            "cadence": {contact["key"]: {"em1": step}}}


class ThePremise(unittest.TestCase):
    """If these change, the rest of the file is about nothing."""

    def test_the_real_config_and_the_default_disagree_on_the_primary(self):
        self.assertEqual(
            verification.policy_for(clients.load("productive"))["primary"],
            "deliverable")
        self.assertEqual(verification.DEFAULT_POLICY["primary"], "contactout")


class _ForgetClientPolicies:
    """Every class here starts and ends with the cache empty."""

    def setUp(self):
        super().setUp()
        lint.forget_policies()
        self.addCleanup(lint.forget_policies)

    @staticmethod
    def _policy(client):
        return lint.policy_for_record({"client": client})


class _RedirectedClientDir(_ForgetClientPolicies):
    """`CLIENTS_DIR` pointed at a private directory, handed back after.

    What a fixture-building test module does to the environment, and what
    `tests/envisolation.py` restores between modules - which it says, in its
    own docstring, is everything it can do: a cached module left behind is
    not covered. These tests are that sentence with the cache's owner
    present.
    """

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="policy-cache-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.saved = os.environ.get("CLIENTS_DIR")
        os.environ["CLIENTS_DIR"] = self.tmp
        self.addCleanup(self._restore_dir)

    def _restore_dir(self):
        if self.saved is None:
            os.environ.pop("CLIENTS_DIR", None)
        else:
            os.environ["CLIENTS_DIR"] = self.saved

    def _write(self, directory, client, primary):
        with open(os.path.join(directory, f"{client}.yaml"), "w",
                  encoding="utf-8") as f:
            f.write(CONFIG.format(primary=primary))


class APoisonedCache(_ForgetClientPolicies, unittest.TestCase):
    """The measured poison, seeded the way `suppression/0110` seeded it."""

    def _poison(self, client):
        # Reaching into the private dict is the point: the poison IS a dict
        # entry, and no public API creates one on demand. The redirect tests
        # below grow the same entry through the public front door.
        lint._POLICY_CACHE[client] = None

    def test_a_none_entry_does_not_survive_the_real_config(self):
        self._poison("productive")
        self.assertEqual((self._policy("productive") or {}).get("primary"),
                         "deliverable",
                         "a poisoned cache served the default policy for a "
                         "client whose own config is readable")

    def test_the_control_still_passes_verification(self):
        """The control `suppression/0110` watched flip, asserted at the gate
        that flipped: a contact the client's own policy clears must not be
        held for verification unknown because a cache said None."""
        self._poison("productive")
        contact = _contact()
        record = _record(contact)
        verdict = eligibility.decide(
            record, contact, "em1", config=clients.load("productive"),
            step=record["cadence"][contact["key"]]["em1"])
        reasons = set(verdict["reasons"])
        self.assertFalse(reasons & VERIFICATION_REASONS,
                         f"refused on verification: {sorted(reasons)}")


class AHiddenConfig(_RedirectedClientDir, unittest.TestCase):
    """The exact measured mechanism, grown through the public front door."""

    def test_a_hidden_config_does_not_poison_the_next_lookup(self):
        """No file under the redirect, the environment handed back, and the
        client's own policy must answer - not the `None` the redirect
        produced."""
        self.assertIsNone(self._policy("productive"))
        self._restore_dir()
        self.assertEqual((self._policy("productive") or {}).get("primary"),
                         "deliverable")


class AFixtureConfig(_RedirectedClientDir, unittest.TestCase):
    """The redirect is not ignored either: while it points elsewhere, the
    fixture file IS the client's config."""

    def test_a_fixture_governs_only_while_the_redirect_is_active(self):
        self._write(self.tmp, "productive", "contactout")
        self.assertEqual((self._policy("productive") or {}).get("primary"),
                         "contactout")
        self._restore_dir()
        self.assertEqual((self._policy("productive") or {}).get("primary"),
                         "deliverable",
                         "the fixture's policy outlived the redirect that "
                         "made it true")

    def test_the_resolved_path_is_part_of_the_files_identity(self):
        """Two directories can hold the same-sized file with the same forced
        mtime and different words in it. A cache that compared only mtime
        and size would keep serving the first directory's policy about the
        second one, which is the redirect case again one directory along."""
        other = tempfile.mkdtemp(prefix="policy-cache-other-")
        self.addCleanup(shutil.rmtree, other, True)
        self._write(self.tmp, FICTIONAL, "contactout")
        self._write(other, FICTIONAL, "deliverable")
        here = os.path.join(self.tmp, f"{FICTIONAL}.yaml")
        there = os.path.join(other, f"{FICTIONAL}.yaml")
        # "contactout" and "deliverable" differ in length, and a path-blind
        # stamp compares exactly mtime and size. Pad the shorter file with a
        # YAML comment so the two agree in the two things that stamp can see
        # and differ in everything it cannot.
        gap = os.path.getsize(there) - os.path.getsize(here)
        with open(here if gap > 0 else there, "ab") as f:
            f.write(b"#" * abs(gap))
        self.assertEqual(os.path.getsize(here), os.path.getsize(there))
        stamp = (2000000000, 2000000000)
        os.utime(here, stamp)
        os.utime(there, stamp)
        self.assertEqual((self._policy(FICTIONAL) or {}).get("primary"),
                         "contactout")
        os.environ["CLIENTS_DIR"] = other
        self.assertEqual((self._policy(FICTIONAL) or {}).get("primary"),
                         "deliverable",
                         "a same-size, same-mtime file in another directory "
                         "was not noticed")


class ARewrittenConfig(_RedirectedClientDir, unittest.TestCase):
    """The production shape: the file changes under a live process."""

    def test_the_new_file_governs(self):
        self._write(self.tmp, FICTIONAL, "contactout")
        self.assertEqual((self._policy(FICTIONAL) or {}).get("primary"),
                         "contactout")
        self._write(self.tmp, FICTIONAL, "deliverable")
        self.assertEqual((self._policy(FICTIONAL) or {}).get("primary"),
                         "deliverable",
                         "the cache kept answering for a config that was "
                         "rewritten under it")

    def test_an_unchanged_config_is_still_served_from_the_cache(self):
        """The cache's own reason for existing, pinned so the fix cannot
        become "stop caching": a second lookup of an unchanged file does
        not read it again. `check` runs once per step per contact."""
        self._write(self.tmp, FICTIONAL, "deliverable")
        self.assertIsNotNone(self._policy(FICTIONAL))
        reads = []
        real_load = clients.load

        def counting_load(*args, **kwargs):
            reads.append(args)
            return real_load(*args, **kwargs)

        clients.load = counting_load
        self.addCleanup(setattr, clients, "load", real_load)
        again = self._policy(FICTIONAL)
        self.assertEqual((again or {}).get("primary"), "deliverable")
        self.assertEqual(reads, [], "an unchanged config was re-read")


if __name__ == "__main__":
    unittest.main()
