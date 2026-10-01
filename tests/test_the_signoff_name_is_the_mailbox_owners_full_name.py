"""The sign-off name must be the mailbox owner's FULL name, in the real config.

WHAT WAS MEASURED, 2026-10-01. `src/sendersignature.py` states the contract in
its own module docstring: the signature is two lines, "the mailbox owner's full
name, then ``Productive``", and "the ``name`` field is the owner's full name".
`config/clients/productive.yaml` carried `sender.name: Ivan` - a first name. So
the rendered sign-off said `Ivan` while the sending mailbox's provider From
display name, read live from EmailBison the same day, said `Ivan Mamic`.

WHY NO EXISTING TEST CAUGHT IT. `tests/test_task906_signature_composed_into_copy.py`
exercises `compose` with the fixture `{"name": "Anna Kowalski"}` - a full name
that no config supplies. Every link in the chain held for an invented sender and
none of them was ever asked about the sender that actually sends. That is the
shape of a green test that cannot fail: the fixture is the thing under test.

So this file asserts against the LOADED CLIENT CONFIG, not a fixture.

WHY IT COSTS NOTHING TO FIX NOW. `approval.sender_fingerprint` covers the sender
identity, so moving `sender.name` invalidates approvals that recorded it.
Measured across `work/queue.jsonl` at the time of the change: 3005 approval
stamps, and **every one of them carries no `sender_fingerprint` at all**, which
`approval.is_sender_current` already treats as STALE for every client. Nothing
currently valid is invalidated, and no canary copy exists yet. The same change
made after generation would invalidate the package the operator approved.

WHAT THIS DOES NOT CLAIM. It does not prove the sign-off equals the provider's
From display name, because the local mailbox roster (`work/senders.jsonl`,
account `eb-2778`) carries NO name field - there is nothing local to compare to.
That gap is named here rather than papered over: the equality was established by
a live provider read recorded in `docs/R2-SIGNATURE-MEASUREMENT-2026-10-01.md`,
and until the roster carries the provider display name a test cannot assert it
offline.
"""
import unittest

from src import clients, sendersignature


def signoff_name(config):
    """The first line of the composed signature, or '' when there is none."""
    sig = sendersignature.compose(clients.sender_identity(config))
    return sig.splitlines()[0] if sig else ""


def is_full_name(name):
    """A full name is at least two whitespace-separated parts.

    Deliberately structural rather than a list of expected names: the
    assertion must keep working for a second client whose sender we have
    never seen, and it must fail for any first-name-only value.
    """
    return len([part for part in (name or "").split() if part]) >= 2


class SignoffNameIsTheOwnersFullName(unittest.TestCase):

    def test_the_real_productive_config_signs_off_with_a_full_name(self):
        """POSITIVE CONTROL on production data, not on a fixture."""
        config = clients.load("productive")
        name = signoff_name(config)
        self.assertTrue(
            is_full_name(name),
            "config/clients/productive.yaml sender.name must be the mailbox "
            "owner's FULL name per src/sendersignature.py's contract; the "
            "composed sign-off line was %r" % name)

    def test_a_first_name_only_config_is_caught(self):
        """NEGATIVE CONTROL: the assertion above is capable of failing.

        Without this, a `is_full_name` that returned True unconditionally
        would leave the positive control green and prove nothing.
        """
        first_name_only = {"sender": {"mode": "client_rep", "name": "Ivan",
                                      "role": "founder",
                                      "company": "Productive"}}
        self.assertFalse(is_full_name(signoff_name(first_name_only)))

    def test_a_missing_sender_name_produces_no_signature_at_all(self):
        """The existing contract, restated so this file cannot pass vacuously.

        `compose` returns '' with no name - a signature without a name is not
        a signature - so the full-name assertion must also reject the empty
        case rather than treating absence as acceptable.
        """
        self.assertEqual(signoff_name({"sender": {"mode": "client_rep"}}), "")
        self.assertFalse(is_full_name(""))

    def test_the_company_line_is_still_the_fixed_word(self):
        """Guard the other half of the two-line contract while we are here."""
        config = clients.load("productive")
        sig = sendersignature.compose(clients.sender_identity(config))
        self.assertEqual(sig.splitlines()[1], "Productive")


if __name__ == "__main__":
    unittest.main()
