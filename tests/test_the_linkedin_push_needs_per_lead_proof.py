"""A LinkedIn push cannot happen without the same per-lead proof the email
path requires. TASK 0030 (GLM-C), 2026-10-15.

`scripts/batch_linkedin_push.py` selects its push set in `enrolled_leads()`
by two facts only: the contact carries a LinkedIn URL and does not yet carry
`campaign_id_linkedin` (lines 117-121). The email path refuses a lead before
it is ever attached - suppression and DNC per lead, killswitch, a
campaign-scoped execution grant (`src/bisonfactory.py` `_ensure_leads`) -
and the sanctioned LinkedIn paths hold the same line:
`src/heyreachfactory.py` `ensure_leads` Gate 2 asks
`eligibility.must_not_contact` per lead (line 1225), and
`src/channels.py` `linkedin_verdict` is the canonical per-lead verdict for
this channel. None of them is consulted anywhere between the store and
`heyreach.add_leads_to_list` (script line 494).

GREEN SINCE TASK 0170 (GLM-C), 2026-10-15: `gated_enrolled_leads()` consults
`channels.linkedin_verdict` per contact, before any provider shape is built,
and returns every refusal with its reason. The two assertions that moved are
`test_an_unsubscribed_contact_is_not_enrolled` and
`test_a_contact_at_a_suppressed_account_is_not_enrolled` - born-red at 0030's
HEAD with `'unsub-will' unexpectedly found` / `'held-sup' unexpectedly
found`, green under the gate. The clean-contact control was green before and
after, so the gate admits what it should. The born-red and three-state
mutation record is in `docs/LINKEDIN-PUSH-GATE-ENUMERATION-2026-10-15.md`
and the GLM-C lane log.

The clean-contact control is load-bearing. A gate that refused everything
would pass the refusal assertions; only the pair says the gate is real.

The second class below holds the other half of 0170: nothing the verdict
refused may reach `heyreach.add_leads_to_list` by this path, and everything
it allowed must go through `liststaging.stage_lead`'s door. Its fixtures
are deliberately separate records under a separate campaign id, so a
byte-exact revert of the script alone reproduces the trio above with its
original failure text while this class errors honestly (the seam is gone).
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

from src import channels

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import batch_linkedin_push as push                               # noqa: E402


# The campaign prefix `enrolled_leads()` selects on.
CAMPAIGN = {"kind": "campaign",
            "campaign_id": "productive-email-batch1-proof",
            "client": "productive",
            "record_ids": ["proof-1", "proof-2"]}

CLEAN_AND_REFUSED = {
    "id": "proof-1",
    "domain": "proof-co.test",
    "company": "Proof Co",
    "contacts": [
        # Clean on every per-lead fact: not excluded, not unsubscribed,
        # not suppressed, not a duplicate, canonical profile URL.
        {"key": "clean-ok", "name": "Clean Ok",
         "linkedin": "https://www.linkedin.com/in/clean-ok"},
        # DNC: this person asked us to stop. `channels.linkedin_verdict`
        # refuses them UNSUBSCRIBED before any other channel question.
        {"key": "unsub-will", "name": "Unsub Will",
         "linkedin": "https://www.linkedin.com/in/unsub-will",
         "unsubscribed": True},
    ],
}

SUPPRESSED_ACCOUNT = {
    "id": "proof-2",
    "domain": "held-co.test",
    "company": "Held Co",
    # `_suppressed` reads a drop_reason beginning "suppress" as the account's
    # own suppression record, with no file involved - the fixture decides.
    "drop_reason": "suppressed: fixture",
    "contacts": [
        {"key": "held-sup", "name": "Held Sup",
         "linkedin": "https://www.linkedin.com/in/held-sup"},
    ],
}


# TASK 0170's second half - the transport seam. Deliberately SEPARATE
# records under a SEPARATE campaign id, so nothing here touches the trio's
# fixtures above and a byte-exact revert of the script alone reproduces the
# trio's original failure text unchanged. first_name/last_name are present
# because `validate_lead_row` refuses a nameless row - the provider answers
# 200 with `addedLeadsCount: 0` for one, and a silent drop is the one thing
# `liststaging` exists to prevent.
TRANSPORT_CAMPAIGN = {"kind": "campaign",
                      "campaign_id": "productive-email-batch1-proof2",
                      "client": "productive",
                      "record_ids": ["proof-3", "proof-4", "proof-5"]}

TRANSPORT_CLEAN = {
    "id": "proof-3",
    "domain": "door-co.test",
    "company": "Door Co",
    "contacts": [
        {"key": "door-clean", "name": "Door Clean",
         "first_name": "Door", "last_name": "Clean",
         "linkedin": "https://www.linkedin.com/in/door-clean"},
    ],
}

TRANSPORT_SUPPRESSED = {
    "id": "proof-4",
    "domain": "held-co.test",
    "company": "Held Co",
    "drop_reason": "suppressed: fixture",
    "contacts": [
        {"key": "door-sup", "name": "Door Sup",
         "first_name": "Door", "last_name": "Sup",
         "linkedin": "https://www.linkedin.com/in/door-sup"},
    ],
}

TRANSPORT_UNUSABLE = {
    "id": "proof-5",
    "domain": "url-co.test",
    "company": "Url Co",
    "contacts": [
        # A company page, not a profile. The VERDICT refuses it
        # (`linkedin_url_not_canonical`); the door would NOT -
        # `liststaging.canonical_profile_url` mangles "company/..." into an
        # /in/ URL rather than refusing it - so this test's red under gate
        # removal is the gate's, not the door's.
        {"key": "door-bad-url", "name": "Door Bad",
         "first_name": "Door", "last_name": "Bad",
         "linkedin": "https://www.linkedin.com/company/door-co"},
    ],
}


class ARefusedLeadIsNeverEnrolled(unittest.TestCase):
    """The per-lead proof the email path requires, asked of the push set."""

    def enrolled(self):
        with mock.patch("src.campaigns.load", return_value=[CAMPAIGN]), \
             mock.patch("src.store.load",
                        return_value=[CLEAN_AND_REFUSED,
                                      SUPPRESSED_ACCOUNT]):
            return push.enrolled_leads()

    def test_an_unsubscribed_contact_is_not_enrolled(self):
        """A person who asked us to stop is not pushed on the second channel
        either. The email path refuses this lead per lead
        (`bisonfactory._ensure_leads` suppression; `heyreachfactory` Gate 2);
        the push set must not carry them to `add_leads_to_list`."""
        keys = [lead["contact_key"] for lead in self.enrolled()]
        self.assertNotIn("unsub-will", keys)

    def test_a_contact_at_a_suppressed_account_is_not_enrolled(self):
        """Suppression is an account fact that closes every channel at once,
        the same fact `channels.linkedin_verdict` reads before any LinkedIn
        question of its own."""
        keys = [lead["contact_key"] for lead in self.enrolled()]
        self.assertNotIn("held-sup", keys)

    def test_a_clean_contact_is_still_enrolled(self):
        """The gate must not be so tight that it refuses everything. A
        contact clean on every per-lead fact still reaches the push set."""
        keys = [lead["contact_key"] for lead in self.enrolled()]
        self.assertIn("clean-ok", keys)


class ARefusedLeadCannotReachTheTransport(unittest.TestCase):
    """TASK 0170's second half: the refusal holds at the write itself.

    The class above proves a refused lead is not in the push set; this one
    proves it cannot reach `heyreach.add_leads_to_list` by this path, and
    that a clean lead still arrives through `liststaging.stage_lead`'s
    door - so the door is wired, not just the list shorter. The seam is
    patched (`mock.patch.object(push.heyreach, ...)`) exactly as 0030's
    tests patched theirs; no provider or network call is made.
    """

    def setUp(self):
        from src import store
        # `stage_lead` routes its write through `providerwrites.perform`,
        # which reads and writes ledger state through the store - and the
        # store works through ENVIRONMENT VARIABLES (`store.use_directory`
        # sets QUEUE and clears STATE_OVERRIDES), the isolation
        # tests/test_list_staging.py documents for the same reason: without
        # it these tests trip the guard that refuses a test writing real
        # client state.
        self._store_tmp = tempfile.mkdtemp(prefix="rga-li-push-proof-")
        self._env_prev = {k: os.environ.get(k)
                          for k in ("QUEUE",) + tuple(store.STATE_OVERRIDES)}
        store.use_directory(os.path.join(self._store_tmp, "work"))

    def tearDown(self):
        for key, value in self._env_prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def run_the_push_offline(self):
        """Gate, then door, offline. Returns (sent_urls, named_refusals).

        The two phases run under DIFFERENT patches on purpose: the gate
        reads record state from the store, the door must NOT see the
        patched store - `perform` keeps its own ledger state in the
        isolated directory, and overlaying the record fixtures onto it
        would be a fixture fighting the mechanism it is trying to observe.
        """
        sent = []

        def fake_add(list_id, rows):
            sent.extend(row["linkedin_url"] for row in rows)
            return {"addedLeadsCount": len(rows)}

        def members_reader(list_id, offset=0, limit=100):
            # Echo what has been sent: the readback runs after the
            # transport, so a staged lead is found present.
            return ([{"profile_url": url} for url in sent], len(sent))

        def unbound_list_reader(list_id):
            return {"id": list_id, "campaignIds": []}

        with mock.patch("src.campaigns.load",
                        return_value=[TRANSPORT_CAMPAIGN]), \
             mock.patch("src.store.load",
                        return_value=[TRANSPORT_CLEAN,
                                      TRANSPORT_SUPPRESSED,
                                      TRANSPORT_UNUSABLE]):
            leads, refusals = push.gated_enrolled_leads()
        with mock.patch.object(push.heyreach, "add_leads_to_list", fake_add):
            push.stage_rows_to_list(
                940797, leads,
                list_reader=unbound_list_reader,
                members_reader=members_reader)
        return sent, refusals

    def test_a_suppressed_contact_cannot_reach_add_leads_to_list(self):
        """THE bar: suppression is an account fact that must close this
        path at the write, not just at the list. Remove the gate and the
        suppressed row rides straight through the door to the transport -
        this is the test that turns red."""
        sent, refusals = self.run_the_push_offline()
        self.assertNotIn("https://www.linkedin.com/in/door-sup", sent)
        named = {(r["contact_key"], r["reason"]) for r in refusals}
        self.assertIn(("door-sup", channels.SUPPRESSED), named)

    def test_an_unusable_profile_url_cannot_reach_add_leads_to_list(self):
        """THE bar: a company page is not a person, and a connection
        request to one is not a smaller mistake than a request to nobody.
        Only the verdict refuses it here - the door's own canonicaliser
        mangles `company/...` into an `/in/` URL rather than refusing - so
        this red under gate removal is the gate's, not the door's."""
        sent, refusals = self.run_the_push_offline()
        self.assertNotIn("https://www.linkedin.com/company/door-co", sent)
        named = {(r["contact_key"], r["reason"]) for r in refusals}
        self.assertIn(("door-bad-url", channels.PROFILE_UNUSABLE), named)

    def test_a_clean_lead_still_goes_through_the_door(self):
        """The control: the door is wired, not just the list shorter. A
        clean lead reaches the transport seam by exactly this path, and the
        two refusals above are the only ones named."""
        sent, refusals = self.run_the_push_offline()
        self.assertIn("https://www.linkedin.com/in/door-clean", sent)
        self.assertEqual(sorted(r["contact_key"] for r in refusals),
                         ["door-bad-url", "door-sup"])


if __name__ == "__main__":
    unittest.main()
