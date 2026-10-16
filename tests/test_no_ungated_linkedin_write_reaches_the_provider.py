#!/usr/bin/env python3
"""With provider writes unauthorised, a LinkedIn write may not reach the verb.

TASK 0076. The mutating surface of `src/providers/heyreach.py` was derived by
execution, not by inheriting a number: twelve public functions can write
(eleven POST routes - activate_campaign shares StartCampaign with
start_campaign - plus the read-first legs of add_senders, create_campaign,
remove_senders and set_sequence), and a thirteenth, set_schedule, is sealed
in the adapter because a schedule write can never be read back.

Every one of them funnels through `providers.request` into `_transport`, and
the real transport's FIRST line is `refuse_unauthorized_write` - the door.
These tests pin the invariant at the socket seam: `urllib.request.urlopen`
is replaced by a recorder, so a red row means a LinkedIn write ACTUALLY
REACHED the provider's verb on the wire while writes were unauthorised.

The control observes the guard it tests: with `allow_writes` engaged the
same call DOES reach the recorder, so the recorder is on the true path and
the door is the only thing that stopped the twelve.

What this file cannot see, said plainly: a function that called urllib
directly instead of `providers.request` would bypass the door and these
rows with it. The twelve measured verbs all go through `request`; the first
ungated verb is by definition one that skips it.

No network: the recorder replaces urlopen for the whole module, authorised
or not; nothing opens a socket. HEYREACH_KEY is a dummy string, never a
real credential and never printed.
"""
import json
import os
import sys
import unittest
import urllib.request

from src import providers
from src.providers import ProviderError, ProviderWriteRefused, heyreach
from src.reviewapproval import NotApproved

DUMMY_KEY = "0076-test-dummy-never-a-real-credential"

# A permissive body. The read-first verbs must parse their read leg so they
# can walk on to the write leg, where the door is the thing under test.
BODY = json.dumps({
    "success": True, "isValid": True, "isSuccess": True, "ok": True,
    "data": {"id": 1, "campaignId": 1, "listId": 1, "memberId": 1,
             "items": [], "status": "DRAFT", "success": True},
    "items": [], "results": [], "rows": [], "list": [],
    "id": 1, "campaignId": 1, "listId": 1, "memberId": 1, "status": "DRAFT",
})

ROW = {"linkedin_url": "https://www.linkedin.com/in/example-0076",
       "email": None, "first_name": "Example", "last_name": "Person",
       "company": "Example Ltd"}

SCHEDULE = {"dailyStartTime": "09:00", "dailyEndTime": "17:00",
            "timeZoneId": "UTC", "days": ["MON", "TUE"]}


def standard_sequence():
    """The real writable sequence, built exactly as the push script builds it.

    Returns None when the client's stored graph is not on the machine; the
    set_sequence row then skips rather than test a hand-made shape.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "config", "linkedin",
                        "productive-standard.json")
    if not os.path.exists(path):            # the file is the client's, not
        return None                         # ours to require
    with open(path, encoding="utf-8") as handle:
        graph = json.load(handle)["graph"]
    scripts = os.path.join(root, "scripts")
    sys.path.insert(0, scripts)
    try:
        import batch_linkedin_push as push
        return heyreach.sequence_for_write(push.drop_bison_handoff(graph))
    finally:
        sys.path.remove(scripts)


class RecordedResponse:

    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return BODY.encode("utf-8")


class AtTheSocket(unittest.TestCase):
    """The recorder replaces urlopen; a write seen here reached the verb."""

    def setUp(self):
        self.wire = []
        self._real_urlopen = urllib.request.urlopen
        urllib.request.urlopen = self._recorder
        self._env = os.environ.copy()
        os.environ["HEYREACH_KEY"] = DUMMY_KEY
        os.environ.pop(providers.WRITES_ENV, None)   # keep the door armed

    def tearDown(self):
        urllib.request.urlopen = self._real_urlopen
        os.environ.clear()
        os.environ.update(self._env)

    def _recorder(self, req, timeout=None):
        self.wire.append((req.get_method(), req.full_url))
        return RecordedResponse()

    def writes_on_the_wire(self):
        # The door's own notion of a write: a write method that is not a
        # POST the module declared as a read (GetAll/GetById are POSTs).
        # Evaluated here, in context, against the same registry the door
        # reads - the registry is populated when heyreach imports.
        return [entry for entry in self.wire
                if entry[0] in providers.WRITE_METHODS
                and not providers.is_declared_read(entry[0], entry[1])]

    def assert_refused_before_the_wire(self, exc_type, call):
        with self.assertRaises(exc_type):
            call()
        self.assertEqual(self.writes_on_the_wire(), [],
                         "a LinkedIn write reached the provider verb")


class TheTwelveMutatingVerbs(AtTheSocket):

    def test_add_leads_to_campaign_is_refused_before_the_wire(self):
        self.assert_refused_before_the_wire(
            ProviderWriteRefused,
            lambda: heyreach.add_leads_to_campaign(123, [ROW], 456))

    def test_add_leads_to_list_is_refused_before_the_wire(self):
        self.assert_refused_before_the_wire(
            ProviderWriteRefused,
            lambda: heyreach.add_leads_to_list(1, [ROW]))

    def test_add_senders_is_refused_before_the_wire(self):
        self.assert_refused_before_the_wire(
            ProviderWriteRefused,
            lambda: heyreach.add_senders(1, [2]))

    def test_create_campaign_is_refused_before_the_wire(self):
        self.assert_refused_before_the_wire(
            ProviderWriteRefused,
            lambda: heyreach.create_campaign("0076-test", 1, [2]))

    def test_create_list_is_refused_before_the_wire(self):
        self.assert_refused_before_the_wire(
            ProviderWriteRefused,
            lambda: heyreach.create_list("0076-test-list"))

    def test_pause_campaign_is_refused_before_the_wire(self):
        self.assert_refused_before_the_wire(
            ProviderWriteRefused,
            lambda: heyreach.pause_campaign(1))

    def test_remove_senders_is_refused_before_the_wire(self):
        self.assert_refused_before_the_wire(
            ProviderWriteRefused,
            lambda: heyreach.remove_senders(1, [2]))

    def test_resume_campaign_is_refused_before_the_wire(self):
        self.assert_refused_before_the_wire(
            ProviderWriteRefused,
            lambda: heyreach.resume_campaign(1))

    def test_set_sequence_is_refused_before_the_wire(self):
        sequence = standard_sequence()
        if sequence is None:
            self.skipTest("no stored standard graph on this machine")
        self.assert_refused_before_the_wire(
            ProviderWriteRefused,
            lambda: heyreach.set_sequence(1, sequence))

    def test_start_campaign_is_refused_before_the_wire(self):
        self.assert_refused_before_the_wire(
            ProviderWriteRefused,
            lambda: heyreach.start_campaign(1))

    def test_stop_lead_in_campaign_is_refused_before_the_wire(self):
        self.assert_refused_before_the_wire(
            ProviderWriteRefused,
            lambda: heyreach.stop_lead_in_campaign(
                1, 2, ROW["linkedin_url"]))

    def test_activate_campaign_is_refused_before_the_wire(self):
        """Approval is checked in the adapter, before the door; the door's
        cover of the shared StartCampaign route is start_campaign's row."""
        self.assert_refused_before_the_wire(
            NotApproved,
            lambda: heyreach.activate_campaign("605732"))

    def test_set_schedule_is_sealed_in_the_adapter(self):
        """The thirteenth public writer: refuses in the adapter because a
        schedule write can never be read back, so it never even reads."""
        self.assert_refused_before_the_wire(
            ProviderError,
            lambda: heyreach.set_schedule(1, SCHEDULE))
        self.assertEqual(self.wire, [])   # not even a read leg


class TheSurfaceIsPinned(unittest.TestCase):

    def test_the_twelve_still_exist_and_are_callable(self):
        for name in ("add_leads_to_campaign", "add_leads_to_list",
                     "add_senders", "activate_campaign", "create_campaign",
                     "create_list", "pause_campaign", "remove_senders",
                     "resume_campaign", "set_sequence", "start_campaign",
                     "stop_lead_in_campaign", "set_schedule"):
            self.assertTrue(callable(getattr(heyreach, name, None)), name)


class TheControlSeesTheGuardItTests(AtTheSocket):
    """Without this, the twelve green rows could mean a recorder that
    nothing ever reaches rather than a door that nothing got past."""

    def test_an_authorised_pause_does_reach_the_wire(self):
        with providers.allow_writes(
                "0076 control: prove the recorder sees a write"):
            heyreach.pause_campaign(1)
        writes = self.writes_on_the_wire()
        self.assertEqual(len(writes), 1)
        self.assertTrue(writes[0][1].split("?")[0].endswith("/campaign/Pause"),
                        writes[0])


if __name__ == "__main__":
    unittest.main()
