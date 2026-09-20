"""An audit reported four providers unauthenticated. All four were configured.

2026-09-20. A hand-written diagnostic checked `CONTACTOUT_KEY`, `BLITZ_KEY`,
`APIFY_KEY` and `SLACK_BOT_TOKEN`, found them absent, and reported that the
primary enrichment provider was unauthenticated and that decision-maker
discovery - and therefore cohort expansion - was impossible.

The real names are `CONTACTOUT_TOKEN`, `BLITZ_API_KEY` and `APIFY_TOKEN`.
All were set. ContactOut had 36,679 credits and 117,419 searches remaining.

**The codebase was never wrong.** `src/config.py`, `src/providers/contactout.py`,
`src/web/api.py`, `src/web/security.py`, `tests/base.py` and `.env.example`
all say `CONTACTOUT_TOKEN`. The only wrong spelling anywhere was in the
throwaway script, which invented a plausible name instead of asking the
registry that every real consumer already reads.

These tests pin the two halves of the lesson:

  1. THE NAMES COME FROM `config.VARIABLES`, so a diagnostic cannot invent
     one. This is the structural fix - the previous failure was possible
     only because a human wrote a list.
  2. CONFIGURED IS NOT AUTHENTICATED, and the five states stay distinct.
     A transport failure is not a bad key.

No network: `check()` is stubbed. No credential value is ever asserted on.
"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from scripts import credential_health as ch  # noqa: E402
from src import config  # noqa: E402
from src.providers import contactout  # noqa: E402


class TheNameComesFromTheRegistry(unittest.TestCase):
    """The structural fix. A hand-written list is what produced the bug."""

    def test_contactout_is_registered_as_TOKEN_not_KEY(self):
        names = ch.credential_names()
        self.assertIn("CONTACTOUT_TOKEN", names)
        self.assertNotIn("CONTACTOUT_KEY", names)

    def test_the_adapter_reads_the_same_name_the_registry_declares(self):
        """The registry and the code that spends the credit must agree, or
        the registry is documentation rather than truth."""
        source = open(contactout.__file__, encoding="utf-8").read()
        self.assertIn('key("CONTACTOUT_TOKEN")', source)
        self.assertNotIn("CONTACTOUT_KEY", source)

    def test_no_module_anywhere_LOOKS_UP_the_wrong_name(self):
        """A regression over the whole tree, because the wrong name reads as
        plausible and would be believed again.

        USAGE, not mention. Three files name `CONTACTOUT_KEY` in prose - this
        test, and two docstrings explaining the mistake - and forbidding the
        string outright would delete the explanation that stops it recurring.
        What must never appear is a LOOKUP.
        """
        lookups = (
            'environ.get("CONTACTOUT_KEY")', "environ.get('CONTACTOUT_KEY')",
            'environ["CONTACTOUT_KEY"]', "environ['CONTACTOUT_KEY']",
            'key("CONTACTOUT_KEY")', "key('CONTACTOUT_KEY')",
            'getenv("CONTACTOUT_KEY")', "getenv('CONTACTOUT_KEY')",
        )
        offenders = []
        for folder in ("src", "scripts", "tests"):
            base = os.path.join(ROOT, folder)
            for here, _dirs, files in os.walk(base):
                if "__pycache__" in here:
                    continue
                for filename in files:
                    if not filename.endswith(".py"):
                        continue
                    path = os.path.join(here, filename)
                    if os.path.basename(path) == os.path.basename(__file__):
                        continue
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        text = fh.read()
                    if any(pattern in text for pattern in lookups):
                        offenders.append(os.path.relpath(path, ROOT))
        self.assertEqual([], offenders,
                         "these LOOK UP CONTACTOUT_KEY, which does not exist")

    def test_the_registry_is_the_source_and_not_a_literal_in_the_script(self):
        """If `credential_names` ever stops reading `config.VARIABLES`, the
        class of bug comes straight back."""
        source = open(ch.__file__, encoding="utf-8").read()
        self.assertIn("config.VARIABLES", source)

    def test_every_provider_credential_in_the_registry_is_reported(self):
        registry = {name for name, _c, group, _w in config.VARIABLES
                    if group == "providers"}
        self.assertEqual(registry, set(ch.credential_names()))


class ConfiguredIsNotAuthenticated(unittest.TestCase):
    """The other half. An environment variable proves nothing about whether
    the credential works, whose account it is, or whether it has quota."""

    def setUp(self):
        self._saved = os.environ.get("CONTACTOUT_TOKEN")
        self.addCleanup(self._restore)

    def _restore(self):
        if self._saved is None:
            os.environ.pop("CONTACTOUT_TOKEN", None)
        else:
            os.environ["CONTACTOUT_TOKEN"] = self._saved

    def test_an_unset_variable_is_NOT_CONFIGURED(self):
        os.environ.pop("CONTACTOUT_TOKEN", None)
        state, _ = ch.state_of("CONTACTOUT_TOKEN")
        self.assertEqual(ch.NOT_CONFIGURED, state)

    def test_a_blank_variable_is_NOT_CONFIGURED(self):
        os.environ["CONTACTOUT_TOKEN"] = "   "
        state, _ = ch.state_of("CONTACTOUT_TOKEN")
        self.assertEqual(ch.NOT_CONFIGURED, state)

    def test_set_but_unasked_is_UNVERIFIED_never_VERIFIED(self):
        """The exact overclaim that started this: presence read as proof."""
        os.environ["CONTACTOUT_TOKEN"] = "something"
        state, detail = ch.state_of("CONTACTOUT_TOKEN", verify=False)
        self.assertEqual(ch.UNVERIFIED, state)
        self.assertEqual(9, detail["length"])

    def test_a_provider_that_answers_ok_is_VERIFIED(self):
        os.environ["CONTACTOUT_TOKEN"] = "something"
        real = contactout.check
        contactout.check = lambda: {"ok": True, "status": 200, "note": "fine"}
        try:
            state, _ = ch.state_of("CONTACTOUT_TOKEN", verify=True)
        finally:
            contactout.check = real
        self.assertEqual(ch.VERIFIED, state)

    def test_a_rejected_credential_is_FAILED(self):
        os.environ["CONTACTOUT_TOKEN"] = "something"
        real = contactout.check
        contactout.check = lambda: {"ok": False, "status": 401,
                                    "note": "unauthorized"}
        try:
            state, _ = ch.state_of("CONTACTOUT_TOKEN", verify=True)
        finally:
            contactout.check = real
        self.assertEqual(ch.FAILED, state)

    def test_a_transport_failure_is_UNAVAILABLE_and_not_a_bad_key(self):
        """Treating these alike is how a provider outage gets diagnosed as a
        credential problem at two in the morning."""
        from src.providers import HttpTimeout
        os.environ["CONTACTOUT_TOKEN"] = "something"
        real = contactout.check

        def boom():
            raise HttpTimeout("timed out")

        contactout.check = boom
        try:
            state, detail = ch.state_of("CONTACTOUT_TOKEN", verify=True)
        finally:
            contactout.check = real
        self.assertEqual(ch.UNAVAILABLE, state)
        self.assertIn("HttpTimeout", detail["error"])

    def test_a_credential_no_adapter_claims_is_UNVERIFIED_not_VERIFIED(self):
        """Honest failure. A name nothing can check must not be reported as
        healthy just because it is set."""
        os.environ["CONTACTOUT_TOKEN"] = "something"
        real = ch.CHECKERS.pop("CONTACTOUT_TOKEN")
        try:
            state, detail = ch.state_of("CONTACTOUT_TOKEN", verify=True)
        finally:
            ch.CHECKERS["CONTACTOUT_TOKEN"] = real
        self.assertEqual(ch.UNVERIFIED, state)
        self.assertIn("cannot verify", detail["why"])

    def test_no_credential_VALUE_is_ever_returned(self):
        """Only the name, the length and what the provider said."""
        os.environ["CONTACTOUT_TOKEN"] = "super-secret-value"
        for verify in (False, True):
            _state, detail = ch.state_of("CONTACTOUT_TOKEN", verify=verify)
            self.assertNotIn("super-secret-value", repr(detail))


if __name__ == "__main__":
    unittest.main()
