"""A HeyReach write cannot land on a list this estate did not create.

POOL 0240 implements the operator's decision of 2026-10-17: "Heyreach ne smije
raditi po tuđim listama." `scripts/batch_linkedin_push.py` builds
`existing_lists` by free-text name and selects by name at the former :584. In
a shared workspace, a name match can return a list a different tenant owns;
the last-wins rule on duplicate names (pilotcaps/0250, measured from bytes)
means the ordering authority is UNKNOWN. The only proof that a list is ours
is that a local contact carries its id from a prior run. The fix: the reuse
arm fires only when the selected list id is in that claimed set; anything
else falls through to CREATE.

Three tests:

* `test_a_list_found_by_name_that_no_local_record_claims_is_not_reused` -
  THE bar. Fixture: a stranger's list with our seat's name is the only row
  `heyreach.lists` returns. Local records carry no `linkedin_list_id`. After
  the fix, `create_list` MUST be called (safe outcome: our own list). Before
  the fix, `create_list` is NOT called and `create_campaign` lands on the
  stranger's id (bad outcome).

* `test_a_list_found_by_name_that_a_local_record_claims_is_reused` -
  the positive control. Fixture: our own list id IS claimed by a local
  contact. After the fix, the reuse arm fires and `create_list` is NOT
  called.

* `test_no_list_at_all_creates` - the baseline. No list with our name at
  the provider. CREATE fires. This is the pre-existing behaviour and the
  negative control for the new test above.

The mutation proof is the pair: the first test's fixture on the OLD code
would have the stranger's id flow into `create_campaign` and
`add_leads_to_list`. On the NEW code, it flows into `create_list` instead.
"""
import contextlib
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import batch_linkedin_push as push                                  # noqa: E402


# A seat the fake attestation will vouch for.
SEAT_ID = "7"
SEAT_NAME = f"RESONATE PRODUCTIVE LI B1 SEAT {SEAT_ID}"[:50]

# The stranger's list id. The fixture returns this under our name, to
# simulate the last-wins rule returning a tenant we do not own.
STRANGER_LIST_ID = "STRANGER-9999"

# Our own list id - the one a prior run wrote back onto a local contact.
CLAIMED_LIST_ID = "OURS-1234"

# The new id `create_list` returns on the CREATE arm.
NEW_LIST_ID = "NEWLY-CREATED-5678"

CAMPAIGN_ID = 24680


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------

def _campaign():
    return {"kind": "campaign",
            "campaign_id": "productive-email-batch1-proof-reuse",
            "client": "productive",
            "record_ids": ["reuse-1"]}


def _lead():
    return {"record_id": "reuse-1",
            "contact_key": "reuse-person",
            "profileUrl": "https://www.linkedin.com/in/reuse-person",
            "firstName": "Reuse",
            "lastName": "Person",
            "company": "Reuse Co",
            "position": "Tester"}


def _record_with_claimed_list():
    """A local record whose contact carries CLAIMED_LIST_ID as its list."""
    return {"id": "reuse-1",
            "domain": "reuse-co.test",
            "company": "Reuse Co",
            "contacts": [
                {"key": "reuse-person",
                 "name": "Reuse Person",
                 "first_name": "Reuse",
                 "last_name": "Person",
                 "linkedin": "https://www.linkedin.com/in/reuse-person",
                 "linkedin_list_id": CLAIMED_LIST_ID},
            ]}


def _record_without_claim():
    """A local record with no linkedin_list_id on its contact."""
    return {"id": "reuse-1",
            "domain": "reuse-co.test",
            "company": "Reuse Co",
            "contacts": [
                {"key": "reuse-person",
                 "name": "Reuse Person",
                 "first_name": "Reuse",
                 "last_name": "Person",
                 "linkedin": "https://www.linkedin.com/in/reuse-person"},
            ]}


def _fake_seat():
    return [{"id": SEAT_ID, "sender_id": "sender-7", "active": True}]


# ---------------------------------------------------------------------------
# A single harness that runs `main()` with a chosen record fixture and
# returns what each adapter write was called with, so each test can assert
# on a specific outcome without re-stating the patch tree.
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _no_writes_context(_reason=None):
    """A stand-in for `providers.allow_writes` that does nothing."""
    yield


def _run_main_with(record, lists_returned):
    """Run push.main() against a fixed fixture.

    Returns a dict with:
        exit_code:     the int main() returned
        create_list_calls:   list of (name,) args
        create_campaign_calls: list of (name, list_id, seats) args
        set_sequence_calls: list of (campaign_id, graph) args
        add_lead_calls: list of (list_id, leads) args that reached the
                        transport seam via liststaging
    """
    create_list_calls = []
    create_campaign_calls = []
    set_sequence_calls = []
    add_lead_calls = []

    def fake_create_list(name):
        create_list_calls.append((name,))
        return {"id": NEW_LIST_ID}

    def fake_create_campaign(name, list_id, seats):
        create_campaign_calls.append((name, list_id, seats))
        return {"id": CAMPAIGN_ID}

    def fake_set_sequence(campaign_id, graph):
        set_sequence_calls.append((campaign_id, graph))
        return {}

    def fake_add_leads_to_list(list_id, leads):
        add_lead_calls.append((list_id, leads))
        return {"addedLeadsCount": len(leads)}

    def fake_lists():
        return lists_returned

    # The transport seam for liststaging is the lambda inside the script
    # that calls heyreach.add_leads_to_list. Patching heyreach's function
    # captures it regardless of how liststaging dispatches.
    tmp = tempfile.mkdtemp(prefix="rga-li-reuse-proof-")
    from src import store
    store.use_directory(os.path.join(tmp, "work"))
    # Ensure the report's `work/` target exists under the temp tree.
    os.makedirs(os.path.join(tmp, "work"), exist_ok=True)

    try:
        with mock.patch.object(push, "load_env", lambda: None), \
             mock.patch.object(push.clients, "load",
                               lambda _c: {"linkedin_connection_requests_per_seat_day": 10}), \
             mock.patch.object(push, "attested_seats", _fake_seat), \
             mock.patch.object(push, "gated_enrolled_leads",
                               lambda: ([_lead()], [])), \
             mock.patch.object(push, "verify_leads",
                               lambda leads, **_: (leads, [])), \
             mock.patch.object(push, "standard_graph", lambda: {"steps": []}), \
             mock.patch.object(push, "HALT", ""), \
             mock.patch.object(push, "ROOT", tmp), \
             mock.patch.object(push.haltfile, "require_released", lambda: None), \
             mock.patch.object(push.providers, "allow_writes", _no_writes_context), \
             mock.patch.object(push.heyreach, "lists", fake_lists), \
             mock.patch.object(push.heyreach, "create_list", fake_create_list), \
             mock.patch.object(push.heyreach, "create_campaign",
                               fake_create_campaign), \
             mock.patch.object(push.heyreach, "set_sequence",
                               fake_set_sequence), \
             mock.patch.object(push.heyreach, "add_leads_to_list",
                               fake_add_leads_to_list), \
             mock.patch.object(push.liststaging, "stage_lead",
                               lambda list_id, lead, transport, **_: transport({"listId": list_id})), \
             mock.patch("time.sleep", lambda _s: None), \
             mock.patch("src.campaigns.load", lambda: [_campaign()]), \
             mock.patch("src.store.load", lambda: [record]):
            exit_code = push.main(["--live", "--veto-waived", "fixture"])
    finally:
        # Restore any env the store module may have cached; mkdtemp cleanup
        # is best-effort and the OS reaps it.
        pass

    return {"exit_code": exit_code,
            "create_list_calls": create_list_calls,
            "create_campaign_calls": create_campaign_calls,
            "set_sequence_calls": set_sequence_calls,
            "add_lead_calls": add_lead_calls}


class TheReuseArmRequiresOwnership(unittest.TestCase):
    """THE bar. A list found by name but not claimed locally is not reused.

    The operator's decision of 2026-10-17: "Heyreach ne smije raditi po
    tuđim listama." The last-wins rule in the dict comprehension that
    builds `existing_lists` means the ordering of `heyreach.lists()`
    decides which duplicate-named row survives. That ordering is UNKNOWN
    (the provider's paginated `/list/GetAll`), so the fix must be correct
    without knowing it - the only proof a list is ours is a local contact
    carrying its id.
    """

    def test_a_list_found_by_name_that_no_local_record_claims_is_not_reused(
            self):
        """Stranger's list under our name, no local claim -> CREATE.

        This is the mutation the brief requires. On the OLD code (no
        claimed_list_ids check), `existing_lists.get(name)` returns
        STRANGER_LIST_ID, the reuse arm fires, and `create_campaign`
        receives STRANGER_LIST_ID - a write landing on a list this estate
        did not create. On the NEW code, `STRANGER_LIST_ID not in
        claimed_list_ids`, the CREATE arm fires, `heyreach.create_list`
        is called, and `create_campaign` receives NEW_LIST_ID.

        Asserts the safe outcome, which the OLD code cannot produce.
        """
        lists_returned = [{"name": SEAT_NAME, "id": STRANGER_LIST_ID}]
        result = _run_main_with(_record_without_claim(), lists_returned)

        # THE bar: CREATE must have fired, not REUSE.
        self.assertEqual(
            len(result["create_list_calls"]), 1,
            "a list named like ours but unclaimed locally MUST trigger "
            "CREATE; got create_list calls: %r" % (
                result["create_list_calls"],))

        # And the downstream writes must land on OUR new id, not the
        # stranger's.
        for _name, list_id, _seats in result["create_campaign_calls"]:
            self.assertNotEqual(
                list_id, STRANGER_LIST_ID,
                "create_campaign received the STRANGER's list id - the "
                "fix is not in effect")
            self.assertEqual(
                list_id, NEW_LIST_ID,
                "create_campaign received the NEW list id from our own "
                "CREATE arm")

        for list_id, _leads in result["add_lead_calls"]:
            self.assertNotEqual(
                list_id, STRANGER_LIST_ID,
                "add_leads_to_list received the STRANGER's list id - a "
                "write reached a list this estate did not create")

    def test_a_list_found_by_name_that_a_local_record_claims_is_reused(
            self):
        """Our own list, claimed by a local contact -> REUSE.

        The positive control. If the fix were so tight that it always
        CREATEd, a legitimate reuse (the second run of the push, when
        contacts already carry the id we wrote back) would create a
        duplicate list and leave the client's estate carrying two per
        seat forever - the exact outcome the original REUSE comment
        warned about.
        """
        lists_returned = [{"name": SEAT_NAME, "id": CLAIMED_LIST_ID}]
        result = _run_main_with(_record_with_claimed_list(), lists_returned)

        self.assertEqual(
            result["create_list_calls"], [],
            "a list named like ours AND claimed by a local contact MUST "
            "reuse; create_list was called: %r" % (
                result["create_list_calls"],))

        for _name, list_id, _seats in result["create_campaign_calls"]:
            self.assertEqual(
                list_id, CLAIMED_LIST_ID,
                "create_campaign received the claimed list id via REUSE")

    def test_no_list_at_all_creates(self):
        """No list with our name anywhere -> CREATE.

        The negative control. This was the pre-existing behaviour and is
        unchanged by the fix; if it ever breaks, the CREATE path itself
        is broken and neither of the two assertions above can be trusted.
        """
        lists_returned = []
        result = _run_main_with(_record_without_claim(), lists_returned)

        self.assertEqual(
            len(result["create_list_calls"]), 1,
            "no list at the provider -> CREATE; got %r" % (
                result["create_list_calls"],))
        for _name, list_id, _seats in result["create_campaign_calls"]:
            self.assertEqual(
                list_id, NEW_LIST_ID,
                "create_campaign received the NEW list id from CREATE")


if __name__ == "__main__":
    unittest.main()
