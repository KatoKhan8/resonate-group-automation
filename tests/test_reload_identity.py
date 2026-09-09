"""No test may leave a stale exception class behind it.

`importlib.reload` re-executes a module into the *same* namespace. The module
object survives; the classes defined in it do not. So reloading
`src.providers` mints a new `ProviderError` while every module that did
`from .providers import ProviderError` at import time keeps holding the old
one. `except` is `isinstance`, and `isinstance` says no.

Nothing crashes when that happens, which is the whole problem. The handler is
simply skipped, the log line it would have written is never written, and the
exception leaves by a route nobody designed. `src/enrich.py` has four such
handlers on the spend path. One of them stopped recording that a ContactOut
call had timed out, so a record that had been charged for a call carried no
trace that the call was ever made - found only because an unrelated fix made
that handler reachable for synthetic records.

Two tests used to reload production modules in-process to ask an import-time
question. They now ask it in a subprocess, and this file holds the line: a
sentinel that fails if anything has mutated the registry again, and a
subprocess proof that the hazard is real rather than theoretical.
"""
import importlib
import subprocess
import sys
import unittest

# Every module that binds the class at *module* scope, and so can go stale.
# `src.verification` deliberately imports it inside the function that catches
# it, so it always resolves the current class - the other way to be correct
# here, and the reason it is absent.
CATCHERS = ("src.enrich", "src.generate", "src.mapping", "src.poller",
            "src.research", "src.validate")


class AProcessNoTestHasCorrupted(unittest.TestCase):
    """Named to sort first, and it reloads nothing.

    An earlier draft put this assertion beside tests that restore the registry
    in `tearDown`, where the restoring healed the process before the sentinel
    could ever look - a sentinel that cannot fire, which is worse than none.
    """

    def test_no_catcher_is_holding_a_stale_provider_error(self):
        providers = importlib.import_module("src.providers")
        for name in CATCHERS:
            module = importlib.import_module(name)
            self.assertIs(
                module.ProviderError, providers.ProviderError,
                "%s holds a different ProviderError than src.providers "
                "exposes, so its `except ProviderError` handlers are dead "
                "for the rest of this process. Something reloaded a "
                "production module in-process; ask import-time questions in "
                "a subprocess instead." % name)

    def test_the_provider_submodules_agree_too(self):
        providers = importlib.import_module("src.providers")
        for name in ("contactout", "aiark", "reoon", "bison", "heyreach",
                     "deliverable", "apify"):
            module = importlib.import_module("src.providers." + name)
            self.assertIs(module.ProviderError, providers.ProviderError, name)


class TheHazardIsReal(unittest.TestCase):
    """Proved out of process, because proving it in process is the defect."""

    def run_python(self, script):
        done = subprocess.run([sys.executable, "-c", script],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def test_reloading_the_package_orphans_a_catcher(self):
        """If this ever reports `catches`, the binding has changed and this
        file has nothing left to protect."""
        self.assertEqual(self.run_python(
            "import importlib, sys\n"
            "import src.enrich as e\n"
            "importlib.reload(importlib.import_module('src.providers'))\n"
            "p = sys.modules['src.providers']\n"
            "print('catches' if isinstance(p.ProviderError('x'), "
            "e.ProviderError) else 'orphaned')\n"), "orphaned")

    def test_a_cold_import_needs_no_credentials(self):
        """What the two rewritten tests actually wanted to know."""
        self.assertEqual(self.run_python(
            "import src.enrich, src.providers.contactout\n"
            "print('imported')\n"), "imported")


if __name__ == "__main__":
    unittest.main()
