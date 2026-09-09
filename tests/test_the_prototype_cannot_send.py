"""The prototype had a live send path, and the product's claim did not know.

`src/push.py` raises `LiveSendNotEnabled`. `LIVE-READINESS.md` classifies both
sending rows as BLOCKING and says "there is no code path to either provider".
`RELEASE-CANDIDATE.md` rests its "Live Productive pilot - NO-GO" on the same
sentence.

`prototype/bin/push.py` was one. `--live` did a real `requests.post` to
`campaign/AddLeadsToCampaignV2` and to EmailBison's `campaigns/<id>/leads`,
with no eligibility decision, no approval fingerprint, no killswitch, no pilot
cap, no account fatigue, no sequence check and no suppression - and then
rewrote `work/queue.jsonl` with its own serialisation rather than through
`src/store.py`, so the tenancy validation and the evidence guard never saw it.

It needed an API key in the environment and a flag. Nothing imported it, which
is exactly why nobody looked: the audits that established "nothing can send"
read `src/`.

These tests assert behaviour - they load the module and call it - rather than
searching its source for `requests`, because a test that greps for a word
passes the moment somebody spells it differently.
"""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTOTYPE = os.path.join(ROOT, "prototype", "bin", "push.py")


def load():
    """Load the script by path. It is not a package and never was."""
    spec = importlib.util.spec_from_file_location("prototype_push", PROTOTYPE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheFileIsStillThere(unittest.TestCase):
    def test_it_loads(self):
        """If it is deleted, delete this file too - do not weaken it."""
        self.assertTrue(os.path.exists(PROTOTYPE))
        self.assertTrue(hasattr(load(), "refuse_live"))


class EveryLivePathRefuses(unittest.TestCase):
    def setUp(self):
        self.push = load()

    def test_the_linkedin_path_refuses_before_it_imports_a_transport(self):
        with self.assertRaises(SystemExit) as caught:
            self.push.push_heyreach(campaign_id=1, sender_account=1, live=True)
        self.assertIn("cannot send", str(caught.exception))

    def test_the_queue_rewrite_refuses(self):
        """The second hazard: it wrote the queue without src/store.py."""
        with self.assertRaises(SystemExit) as caught:
            self.push.mark_pushed({"any-record"})
        self.assertIn("cannot send", str(caught.exception))

    def test_the_refusal_names_the_guarded_path(self):
        with self.assertRaises(SystemExit) as caught:
            self.push.refuse_live()
        self.assertIn("src/push.py", str(caught.exception))

    def test_a_dry_run_is_still_allowed(self):
        """The refusal is about sending, not about the script existing.

        `push_heyreach(live=False)` returns before the refusal, so the
        prototype can still show what it would have done - which is the only
        thing it was ever safe for.
        """
        rows = getattr(self.push, "rows")
        self.push.rows = lambda path=None: []
        self.addCleanup(setattr, self.push, "rows", rows)
        self.assertEqual(self.push.push_heyreach(1, 1, live=False), set())


class NoTransportIsReachedFirst(unittest.TestCase):
    """The refusal must land before any network object is constructed.

    Asserted by breaking the import: if `requests` were reached, these would
    raise ImportError or AttributeError rather than SystemExit, and the test
    would fail for a different reason than it passes for.
    """

    def setUp(self):
        self.push = load()

    def test_the_linkedin_path_never_reaches_requests(self):
        import sys
        planted = sys.modules.get("requests")
        sys.modules["requests"] = None          # any use raises TypeError
        self.addCleanup(lambda: sys.modules.pop("requests", None)
                        if planted is None else
                        sys.modules.__setitem__("requests", planted))
        with self.assertRaises(SystemExit):
            self.push.push_heyreach(campaign_id=1, sender_account=1, live=True)


if __name__ == "__main__":
    unittest.main()
