"""A fixture that blows up does not disable the rest of the run.

`ProviderTest.setUp` replaces `urllib.request.urlopen` with a tripwire so that
anything bypassing the transport seam dies loudly. It restored it in
`tearDown` - which `unittest` does not call when a `setUp` raises.

Forty-two classes extend `ProviderTest`. One subclass whose `setUp` failed
after `super().setUp()` therefore left the tripwire installed for the whole
process, and it was self-perpetuating: the next `ProviderTest.setUp` captured
`_forbidden` as "the original" and its `tearDown` restored that.

Two consumers open URLs directly - `tests/test_slack_route.py` posts with
`urllib.request.urlopen`, and `src/web/oidc.py` resolves it at call time for
discovery and token fetches. So a single fixture error produced 15 + 48 = 63
failures in modules that had nothing to do with it, and buried the one real
error under sixty-three phantoms.

Registering each restore with `addCleanup` where the state is captured fixes
it: cleanups run whether or not `setUp` completes, and unwind only what was
actually reached. The measure of the fix is not that the suite went green - it
is that on the broken tree the reproduction went from 63 failures and 4 errors
to 4 errors. The real failures stayed visible.
"""
import os
import unittest
import urllib.request

from src import providers
from tests.base import ProviderTest


def run_exploding():
    """Run one ProviderTest whose fixture fails after `super().setUp()`.

    Defined inside the function on purpose: a module-level TestCase subclass
    is collected by the loader, and this one is meant to fail.
    """

    class Exploding(ProviderTest):
        def setUp(self):
            super().setUp()
            raise RuntimeError("a fixture blew up after super().setUp()")

        def runTest(self):
            self.fail("setUp should have raised")

    result = unittest.TestResult()
    Exploding().run(result)
    return result


class AFailingSetupCleansUp(unittest.TestCase):

    def test_the_fixture_really_does_fail(self):
        """Anchors every assertion below: if it stopped raising they would
        all pass while proving nothing."""
        self.assertEqual(len(run_exploding().errors), 1)

    def test_the_network_tripwire_is_restored(self):
        """The one that cost 63 failures.

        Asserted against a sentinel rather than against whatever `urlopen`
        happened to be. Capturing it first is what makes this test useless:
        once a leak has occurred, the captured value IS the tripwire, the
        assertion holds, and the test passes while the defect is live.
        """
        def sentinel(*a, **kw):
            raise AssertionError("the sentinel was called")

        real = urllib.request.urlopen
        urllib.request.urlopen = sentinel
        try:
            run_exploding()
            self.assertIs(urllib.request.urlopen, sentinel,
                          "the failing setUp left its tripwire installed")
        finally:
            urllib.request.urlopen = real

    def test_two_failures_do_not_compound(self):
        """The self-perpetuating half: a second failing setUp must not
        capture the first one's tripwire as the original."""
        def sentinel(*a, **kw):
            raise AssertionError("the sentinel was called")

        real = urllib.request.urlopen
        urllib.request.urlopen = sentinel
        try:
            run_exploding()
            run_exploding()
            self.assertIs(urllib.request.urlopen, sentinel)
        finally:
            urllib.request.urlopen = real

    def test_the_transport_seam_is_restored(self):
        before = providers.transport() if hasattr(providers, "transport") else None
        run_exploding()
        if before is not None:
            self.assertIs(providers.transport(), before)

    def test_the_env_file_pointer_is_restored(self):
        before = providers.ENV_FILE
        run_exploding()
        self.assertEqual(providers.ENV_FILE, before)

    def test_a_popped_credential_comes_back_absent_not_blank(self):
        """`setUp` pops the real keys. Restoring one as "" would read as a
        configured-but-empty credential, which is a different thing."""
        os.environ.pop("CONTACTOUT_TOKEN", None)
        run_exploding()
        self.assertNotIn("CONTACTOUT_TOKEN", os.environ)

    def test_a_present_credential_comes_back_with_its_value(self):
        os.environ["CONTACTOUT_TOKEN"] = "a-real-looking-value"
        try:
            run_exploding()
            self.assertEqual(os.environ.get("CONTACTOUT_TOKEN"),
                             "a-real-looking-value")
        finally:
            os.environ.pop("CONTACTOUT_TOKEN", None)

    def test_the_store_override_is_restored(self):
        before = os.environ.get("QUEUE")
        run_exploding()
        self.assertEqual(os.environ.get("QUEUE"), before)




if __name__ == "__main__":
    unittest.main()
