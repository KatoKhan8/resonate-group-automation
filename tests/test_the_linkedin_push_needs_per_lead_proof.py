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

THE TASK FORBIDS WIRING THE GATE IN, so this test is RED on the branch that
carries it, by design. It states the required behaviour - a lead the per-lead
proof refuses is never enrolled, while a clean lead still is - and it was
mutation-proved: with `enrolled_leads()` temporarily wired to
`channels.linkedin_verdict` in a scratch mutation, both halves pass; see
`docs/LINKEDIN-PUSH-GATE-ENUMERATION-2026-10-15.md` for the proof record.

The clean-contact control is load-bearing. A gate that refused everything
would pass the refusal assertions; only the pair says the gate is real.
"""
import os
import sys
import unittest
from unittest import mock

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


if __name__ == "__main__":
    unittest.main()
