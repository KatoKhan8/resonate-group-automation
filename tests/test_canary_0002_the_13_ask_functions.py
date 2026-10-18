#!/usr/bin/env python3
"""canary/0002. The 13 ask functions, proven on synthetic records.

audit/0001 measured the thirteen rows of the canary preflight that read a
queue record as 0 lane-closable / 13 operator / 0 provider-read: every one
carried `ask: None` and answered UNKNOWN in every world, including the one
where its own input held the exclusion. "The code is lane-buildable, the
sight is not." canary/0002 built the code. THIS FILE is the proof that each
function returns the right verdict, and it is the whole proof the brief
asked for:

    THREE CONTROLS PER ROW, ON SYNTHETIC RECORDS:

      satisfies  the field/block present and clean  -> PASS
      violates   the field/block carrying the exclusion -> EXCLUDED
      absent     the field/block missing entirely   -> UNKNOWN, NEVER PASS

    That third arm is the one that matters. A missing authority must never
    read as clearance, and every absent-arm test pins both halves:
    `assertEqual(UNKNOWN)` AND `assertNotEqual(PASS)`.

    PLUS, BECAUSE A GREEN CELL PROVES NOTHING UNTIL THE INSTRUMENT HAS
    SHOWN IT CAN PRINT THE OTHER ANSWER:

      test_every_row_degrades_to_unknown_when_its_ask_is_reverted_to_none
          the exact defect audit/0001 measured - `ask: None` back in the
          slot - must turn every satisfies world UNKNOWN again, for the
          gate's own reason ("no form that can be evaluated"), 13/13.
      test_every_satisfies_world_reddens_when_the_ask_excludes_everybody
          the subtler break - an ask that refuses everybody passes the
          absent arms - must turn every satisfies world EXCLUDED, 13/13.

THE WORLDS ARE PLANTED, NEVER THE PRODUCTION ESTATE. `preflight.
_planted_state` writes the eight authority files into a temp dir (its own
docstring: the records go in through the real writers), this file overwrites
the planted queue with synthetic JSONL rows, re-resolves the state, sets the
QUEUE env so `store.load`/`clientapproval.path` follow the plant, sets
CLIENTS_DIR to a synthetic client, and evaluates under `preflight.
_pointed(paths)`. No production `work/`, no main checkout, no network, no
provider call. Every address is a reserved domain (.test/.invalid), asserted
on this module's own bytes at the end.

WHAT IS HONESTLY NOT PROVEN HERE, named rather than hidden:

  * WRITER-ADDED ABSENCE. `events`, `suppression`, `review` and `paused`
    are created by their writers, and no production writer writes
    `unsubscribed: False` or `open: False` back. Rows 5-9 therefore PASS
    here on synthetic blocks a production writer would never produce, and
    real records no policy path ever touched will read UNKNOWN on those
    rows - never clear, never excluded. The one production negative is
    inbound's restore, which may write `paused: None` (row 8's satisfies
    arm is exactly that value).
  * ROW 10 IS ASYMMETRIC, BY ITS DECIDERS' OWN ANSWERS. Absent
    verification evidence is EXCLUDED, not UNKNOWN: `verification.decide
    ([])` answers unknown/not-sendable and CLAUDE.md makes that a hard
    rule. Absent MX block is UNKNOWN: `mx.allows_email` answers
    (True, "no MX check has been run") for it, a fail-open the ask wraps
    into Undecided - one-directional, it can never manufacture a PASS.
    Both halves are pinned below.
  * ROW 13 SELF-POLICES. The client-approval register is not among the
    eight declared authorities, so evaluate()'s five-state gate never sees
    it; the ask enforces ABSENT/UNREADABLE/EMPTY/POPULATED itself. The
    SPEC HAZARD audit/0001 named - load() answering [] for a missing file
    and is_suppressed reading [] as "not suppressed" - is the absent arm.
  * THESE ARE VERDICTS, NOT CLEARANCE. Clearance is the operator's
    judgement over the whole table and is not this file's to claim.

Run (module alone; NO full-suite lock is taken or needed):

    py -3 -B -m unittest tests.test_canary_0002_the_13_ask_functions -v
"""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import (clientapproval, clients, events, lint, preflight,  # noqa: E402
                 store, verification)

# ------------------------------------------------------- the synthetic world
#
# Reserved domains only (.test). None of these identifiers collides with the
# filler the plant itself writes (filler-control.invalid /
# filler-control@other.invalid / campaigns 999001-2), so no control excludes
# by accident against the planted authorities.

KEY = "c-0002"
NAME = "Control Person"
EMAIL = "control-person@control-account.test"
DOMAIN = "control-account.test"
COMPANY = "Control Account"
CLIENT = "control-client"
CLIENT_DOMAIN = "control-client.test"
AT = "2026-10-18T00:00:00+00:00"

HISTORY_KEY = "h-0001"
HISTORY_NAME = "History Person"
HISTORY_EMAIL = "history-person@control-account.test"

INSIDER_EMAIL = "insider@control-client.test"

#: The 13 rows this file proves, in table order.
THE_THIRTEEN = (
    "client_suppressed_drop",
    "client_own_domain",
    "record_state",
    "contact_flags",
    "contact_reply_event",
    "account_suppressed",
    "account_review_open",
    "account_paused",
    "account_reply_log",
    "mx_and_verification",
    "hygiene_workspace_history",
    "hygiene_account_history",
    "client_approval_register",
)


def _entry(**over):
    entry = {"key": KEY, "name": NAME, "email": EMAIL}
    entry.update(over)
    return entry


def _record(**over):
    """A skeleton-shaped synthetic record. `store.load` does not validate
    rows, but the skeleton mirrors `store.new_record` anyway: the fields
    store.REQUIRED names are present unless an absent-arm deletes one."""
    rec = {"id": "r-0002", "client": CLIENT, "domain": DOMAIN,
           "company": COMPANY, "state": "sourced", "drop_reason": None,
           "contacts": [_entry()]}
    rec.update(over)
    return rec


def _without(rec, *keys):
    """The same record with fields DELETED, not set to None. An absent arm
    means the key is not in the dict - `rec.get()` answering None and the
    key missing are different worlds, and the asks must tell them apart."""
    out = dict(rec)
    for key in keys:
        out.pop(key, None)
    return out


def _event(kind, contact=KEY, at=AT, **over):
    entry = {"type": kind, "contact": contact, "at": at}
    entry.update(over)
    return entry


def _evidence_valid(email=EMAIL):
    """Two independent confirmations bound to the exact address, which is
    what `verification.evidence_for` demands and what the default policy
    (primary contactout + secondary deliverable, 2 required) clears."""
    return {"evidence": [
        {"provider": "contactout", "status": verification.S_VALID,
         "email": email, "at": AT},
        {"provider": "deliverable", "status": verification.S_VALID,
         "email": email, "at": AT},
    ]}


def _mx_allowed():
    """A stored MX block `fresh_decision` re-derives as allowed: a google
    host (MAILBOX_HOSTS, category NORMAL), and the stored verdict/status
    are ignored by design - only hostnames are evidence."""
    return {"mx_records": ["gmail-smtp-in.l.google.com"],
            "status": "known_allowed", "email_domain": DOMAIN}


def _mx_no_mx():
    return {"mx_records": [], "status": "no_mx", "email_domain": DOMAIN}


def _approval_row(state, domain=DOMAIN, client=CLIENT):
    """A register row of the exact shape `clientapproval.record` writes:
    kind/client/domain/state/who/source/at, `who` and `source` required."""
    return {"kind": clientapproval.DECISION, "client": client,
            "domain": domain, "state": state, "who": "operator-control",
            "source": "canary/0002 control plant", "at": AT}


# ------------------------------------------------------------------ harness

class _Harness(unittest.TestCase):
    """A planted authority tree, a synthetic queue, and one cell reader."""

    def setUp(self):
        from src import operatorexclusion

        self.tmp = tempfile.mkdtemp(prefix="rga-c0002-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(operatorexclusion.forget)
        operatorexclusion.forget()
        lint.forget_policies()
        self.addCleanup(lint.forget_policies)

        # One synthetic client config, in a planted CLIENTS_DIR - never the
        # real config/clients/. READ BACK, not "it parsed": clients.py's
        # YAML parser silently drops malformed keys, against its own
        # docstring, so a config that failed to carry `domain` would turn
        # row 2's arms into a test of nothing.
        clients_dir = os.path.join(self.tmp, "clients")
        os.makedirs(clients_dir)
        with open(os.path.join(clients_dir, CLIENT + ".yaml"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("name: %s\ndomain: %s\n" % (CLIENT, CLIENT_DOMAIN))
        self._env("CLIENTS_DIR", clients_dir)
        config = clients.load(CLIENT)
        self.assertEqual(CLIENT_DOMAIN, config.get("domain"),
                         "the planted client config did not survive the "
                         "YAML parser - every client-domain arm below would "
                         "be a test of nothing")

    def _env(self, name, value):
        saved = os.environ.get(name)
        os.environ[name] = value

        def restore():
            if saved is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = saved
        self.addCleanup(restore)

    def plant(self, records, register_rows=None):
        """(state, paths, readback rows).

        `_planted_state` writes the eight authorities through their real
        writers; the queue is then OVERWRITTEN with this test's synthetic
        rows (LF JSONL, the store's own format) and the state re-resolved,
        exactly the discipline the TASK-0250 module uses. The QUEUE env
        follows the plant so the asks' own readers - `store.load()` inside
        `hygiene.index()`, `clientapproval.path()` beside the queue - read
        the planted world and never this checkout's work/.
        """
        state, paths = preflight._planted_state(self.tmp)
        with open(paths["queue"], "w", encoding="utf-8", newline="\n") as h:
            for rec in records:
                h.write(json.dumps(rec, sort_keys=True) + "\n")
        if register_rows is not None:
            register = os.path.join(os.path.dirname(paths["queue"]),
                                    "client-approval.jsonl")
            with open(register, "w", encoding="utf-8", newline="\n") as h:
                for row in register_rows:
                    h.write(json.dumps(row, sort_keys=True) + "\n")
        self._env("QUEUE", paths["queue"])
        state = preflight._planted_state(self.tmp, paths=paths)[0]
        return state, paths, store.read_jsonl(paths["queue"])

    def world(self, records, register_rows=None):
        """(state, paths, contact) with the contact bound to the LAST
        planted record - the candidate. History records, where an arm needs
        one, go first."""
        state, paths, rows = self.plant(records, register_rows=register_rows)
        return state, paths, self.contact(rows[-1])

    def contact(self, rec, **over):
        contact = {"key": KEY, "name": NAME, "email": EMAIL,
                   "domain": DOMAIN, "company": COMPANY, "record": rec}
        contact.update(over)
        return contact

    def cell(self, state, paths, contact, rule, channel="email"):
        """One rule's cell, through the instrument's own evaluate() - the
        whole chain (authority gate, needs_record floor, ask), not the ask
        called beside it. A control that proved only the function would
        prove the function can read a dict, which nobody doubted."""
        self.assertEqual(preflight.PRESENT_POPULATED, state["queue"]["state"],
                         "the planted queue is not POPULATED, so the gate "
                         "would answer UNKNOWN before any ask ran and every "
                         "arm below would be a test of the gate")
        with preflight._pointed(paths):
            row = preflight.evaluate(contact, state=state, channel=channel)
        return row["cells"][rule]

    def assert_pass(self, cell):
        self.assertEqual(preflight.PASS, cell["cell"])
        self.assertFalse(cell.get("not_applicable"),
                         "a not_applicable PASS is the channel answering, "
                         "not the ask - this control would prove nothing")

    def assert_excluded(self, cell, *whys):
        self.assertEqual(preflight.EXCLUDED, cell["cell"])
        for text in whys:
            self.assertIn(text, cell["why"])

    def assert_unknown_never_pass(self, cell, *whys):
        """THE THIRD ARM, and the one that matters: both halves pinned."""
        self.assertEqual(preflight.UNKNOWN, cell["cell"])
        self.assertNotEqual(preflight.PASS, cell["cell"])
        for text in whys:
            self.assertIn(text, cell["why"])


# ------------------------------------------------- the satisfies worlds once
#
# One source of truth per row: the satisfies arm test AND both mutation
# proofs build the SAME world, so a mutation proof can never quietly mutate
# a different world than the one the arm proved.

SATISFIES = {
    "client_suppressed_drop":
        lambda h: h.world([_record()]),
    "client_own_domain":
        lambda h: h.world([_record()]),
    "record_state":
        lambda h: h.world([_record()]),
    "contact_flags":
        lambda h: h.world([_record()]),
    "contact_reply_event":
        lambda h: h.world([_record(events=[])]),
    "account_suppressed":
        # SYNTHETIC-ONLY ARM, and the report says so: no production writer
        # writes `unsubscribed: False` back - the block's only writer writes
        # True. A present-and-false block is what a synthetic plant can
        # build and a real unworked record cannot, which is exactly why the
        # absent arm beside it is UNKNOWN and never PASS.
        lambda h: h.world([_record(suppression={"unsubscribed": False})]),
    "account_review_open":
        lambda h: h.world([_record(review={"open": False})]),
    "account_paused":
        # `paused: None` is the ONE production negative: inbound's restore
        # may write it. pause_state returns rec["paused"] as-is, so None
        # falls through to "not paused", and the floor sees the field.
        lambda h: h.world([_record(paused=None)]),
    "account_reply_log":
        lambda h: h.world([_record(events=[])]),
    "mx_and_verification":
        lambda h: h.world([_record(contacts=[_entry(
            verification=_evidence_valid(), mx=_mx_allowed())])]),
    "hygiene_workspace_history":
        lambda h: h.world([_record()]),
    "hygiene_account_history":
        lambda h: h.world([_record()]),
    "client_approval_register":
        lambda h: h.world([_record()],
                          register_rows=[
                              _approval_row(clientapproval.APPROVED)]),
}

assert tuple(SATISFIES) == THE_THIRTEEN or set(SATISFIES) == set(THE_THIRTEEN)


# --------------------------------------------------------------- the 13 rows

class Row01ClientSuppressedDrop(_Harness):
    """eligibility._suppressed, the drop_reason branch (row 1 of 13)."""

    RULE = "client_suppressed_drop"

    def test_satisfies_a_record_with_no_drop_reason_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_a_suppress_drop_reason_is_excluded(self):
        state, paths, rows = self.plant(
            [_record(drop_reason="suppressed: client removal 2026-10-18")])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "drop_reason", "suppress")

    def test_absent_the_field_is_unknown_and_never_pass(self):
        state, paths, rows = self.plant([_without(_record(), "drop_reason")])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "drop_reason")


class Row02ClientOwnDomain(_Harness):
    """eligibility._client_own_domain, email channel (row 2 of 13)."""

    RULE = "client_own_domain"

    def test_satisfies_an_address_not_at_the_client_domain_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_the_clients_own_staff_address_is_excluded(self):
        rec = _record(contacts=[_entry(email=INSIDER_EMAIL)])
        state, paths, rows = self.plant([rec])
        contact = self.contact(rows[0], email=INSIDER_EMAIL)
        cell = self.cell(state, paths, contact, self.RULE)
        self.assert_excluded(cell, INSIDER_EMAIL, CLIENT_DOMAIN,
                             "_client_own_domain")

    def test_absent_the_record_names_no_client_so_the_domain_is_unknown(
            self):
        state, paths, rows = self.plant([_without(_record(), "client")])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "no client")

    def test_an_unreadable_client_config_is_unknown_not_the_fail_open(self):
        """eligibility._client_own_domain returns None - a PASS - when
        clients.load raises. The ask loads the config itself and refuses to
        inherit that fail-open: unreadable is UNKNOWN, and the wrap is
        one-directional (it can never turn an UNKNOWN into a PASS)."""
        state, paths, contact = SATISFIES[self.RULE](self)
        self._env("CLIENTS_DIR", os.path.join(self.tmp, "no-clients-here"))
        cell = self.cell(state, paths, contact, self.RULE)
        self.assert_unknown_never_pass(cell, "fail-open")


class Row03RecordState(_Harness):
    """eligibility._record_state (row 3 of 13)."""

    RULE = "record_state"

    def test_satisfies_a_sourced_record_with_no_drop_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_a_dropped_record_is_excluded(self):
        state, paths, rows = self.plant([_record(state="dropped")])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "_record_state", "dropped")

    def test_absent_the_state_field_is_unknown_and_never_pass(self):
        state, paths, rows = self.plant([_without(_record(), "state")])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "state")


class Row04ContactFlags(_Harness):
    """eligibility._replied, the FLAG branch (row 4 of 13)."""

    RULE = "contact_flags"

    def test_satisfies_an_entry_with_no_flags_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_an_unsubscribed_flag_on_the_entry_is_excluded(self):
        rec = _record(contacts=[_entry(unsubscribed=True)])
        state, paths, rows = self.plant([rec])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "stop flag", "blocked:unsubscribed")

    def test_violates_a_stopped_flag_on_the_entry_is_excluded(self):
        rec = _record(contacts=[_entry(stopped=True)])
        state, paths, rows = self.plant([rec])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "blocked:contact_stopped")

    def test_absent_the_contact_list_is_unknown_and_never_pass(self):
        state, paths, rows = self.plant([_without(_record(), "contacts")])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "contacts")

    def test_a_person_not_on_the_record_is_unknown_not_a_borrowed_block(
            self):
        """eligibility._identity answers blocked:contact_not_on_record for a
        contact missing from the record - but NO row of this table declares
        that question, so this row answers UNKNOWN rather than borrowing
        another decider's exclusion."""
        other = _record(contacts=[_entry(key="somebody-else",
                                         email="other-person@example.test")])
        state, paths, rows = self.plant([other])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "contact_not_on_record")


class Row05ContactReplyEvent(_Harness):
    """eligibility._replied, the EVENT branch (row 5 of 13)."""

    RULE = "contact_reply_event"

    def test_satisfies_a_present_empty_event_log_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_a_reply_event_against_the_key_is_excluded(self):
        rec = _record(events=[_event(events.REPLY_RECEIVED, channel="email")])
        state, paths, rows = self.plant([rec])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "reply event")

    def test_absent_the_event_log_is_unknown_and_never_pass(self):
        """TASK-0250's doctrine one row over: `events` is writer-added, so
        an absent list is not 'no reply recorded' but 'no event writer ever
        ran for this record'."""
        state, paths, rows = self.plant([_record()])   # no events key at all
        self.assertNotIn("events", rows[0])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "events")


class Row06AccountSuppressed(_Harness):
    """eligibility._paused, the account-suppression branch (row 6 of 13)."""

    RULE = "account_suppressed"

    def test_satisfies_a_present_false_suppression_block_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_a_company_unsubscribe_is_excluded(self):
        rec = _record(suppression={"unsubscribed": True, "at": AT,
                                   "reason": "client removal",
                                   "by": "operator-control"})
        state, paths, rows = self.plant([rec])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "suppression", "unsubscribed")

    def test_absent_the_block_is_unknown_and_never_pass(self):
        state, paths, rows = self.plant([_record()])
        self.assertNotIn("suppression", rows[0])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "suppression")


class Row07AccountReviewOpen(_Harness):
    """eligibility._paused, the open-review branch (row 7 of 13)."""

    RULE = "account_review_open"

    def test_satisfies_a_present_closed_review_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_an_open_review_is_excluded(self):
        rec = _record(review={"open": True, "since": AT,
                              "reason": "control review",
                              "by": "operator-control"})
        state, paths, rows = self.plant([rec])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "review", "open")

    def test_absent_the_block_is_unknown_and_never_pass(self):
        state, paths, rows = self.plant([_record()])
        self.assertNotIn("review", rows[0])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "review")


class Row08AccountPaused(_Harness):
    """eligibility._paused via cadence.pause_state (row 8 of 13)."""

    RULE = "account_paused"

    def test_satisfies_paused_none_the_production_negative_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_a_policy_hold_on_the_account_is_excluded(self):
        rec = _record(paused={"reason": "positive_reply_hold",
                              "since": AT, "outcome": "positive",
                              "channel": "email", "by": HISTORY_KEY})
        state, paths, rows = self.plant([rec])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "paused by the reply policy",
                             "positive_reply_hold")

    def test_violates_a_booked_meeting_excludes_with_no_paused_field_at_all(
            self):
        """FAIL BEFORE THE FLOOR, proven: a MEETING_MARKED event pauses the
        company through pause_state with no `paused` field ever written. An
        exclusion found on a partial record is still an exclusion - the
        evaluate() asymmetry, inside the ask. Had the floor been asked
        first, this world would have read UNKNOWN."""
        rec = _record(events=[_event(events.MEETING_MARKED)])
        state, paths, rows = self.plant([rec])
        self.assertNotIn("paused", rows[0])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "paused by the reply policy",
                             events.MEETING_MARKED)

    def test_absent_the_field_and_every_writer_is_unknown_never_pass(self):
        state, paths, rows = self.plant([_record()])
        self.assertNotIn("paused", rows[0])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "paused")


class Row09AccountReplyLog(_Harness):
    """suppression.decide step 2 via account.replies (row 9 of 13)."""

    RULE = "account_reply_log"

    def test_satisfies_a_present_empty_event_log_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_an_unflagged_reply_in_the_log_is_excluded(self):
        """REPLY_CLASSIFIED is in account.replies' type set but NOT in
        events.is_reply - so this world excludes on row 9 while row 5, the
        event branch of _replied, reads 'asked, did not fire'. The branch
        split between the two rows, asserted rather than claimed."""
        rec = _record(events=[_event(events.REPLY_CLASSIFIED,
                                     classification="positive")])
        state, paths, rows = self.plant([rec])
        contact = self.contact(rows[0])
        cell = self.cell(state, paths, contact, self.RULE)
        self.assert_excluded(cell, "reply event(s)", "suppression.decide")
        row5 = self.cell(state, paths, contact, "contact_reply_event")
        self.assert_pass(row5)

    def test_absent_the_event_log_is_unknown_and_never_pass(self):
        state, paths, rows = self.plant([_record()])
        self.assertNotIn("events", rows[0])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "events")


class Row10MxAndVerification(_Harness):
    """channels.email_verdict via mx.allows_email and the client's
    verification policy, email channel (row 10 of 13). ASYMMETRIC BY ITS
    DECIDERS' OWN ANSWERS - both halves pinned."""

    RULE = "mx_and_verification"

    def test_satisfies_verified_and_mx_allowed_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_no_verification_evidence_is_excluded_not_unknown(
            self):
        """THE DECIDER'S OWN ANSWER, cited beside the cell: decide([]) is
        unknown/not-sendable - 'no verification evidence' - and CLAUDE.md
        makes that a hard rule. An unverified address is a VIOLATED row,
        not an unanswered one; this is the one absent field among the
        thirteen that excludes, and it excludes because the send path
        itself refuses."""
        self.assertFalse(verification.decide([])["sendable"])
        rec = _record(contacts=[_entry(mx=_mx_allowed())])
        state, paths, rows = self.plant([rec])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "verification policy",
                             "no verification evidence")
        self.assertNotEqual(preflight.UNKNOWN, cell["cell"])

    def test_violates_a_dead_mx_channel_is_excluded(self):
        """The MX leg, with the verification leg satisfied first so the
        exclusion can only come from the channel: an empty host list the
        decider re-derives as NO_MX."""
        rec = _record(contacts=[_entry(verification=_evidence_valid(),
                                       mx=_mx_no_mx())])
        state, paths, rows = self.plant([rec])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "MX policy")

    def test_absent_the_mx_block_is_unknown_wrapping_the_fail_open(self):
        """mx.allows_email answers (True, 'no MX check has been run') for a
        contact with no stored block. A check nobody ran is not clearance:
        the ask wraps that one fail-open into UNKNOWN - the only such wrap
        among the thirteen, and one-directional."""
        rec = _record(contacts=[_entry(verification=_evidence_valid())])
        state, paths, rows = self.plant([rec])
        self.assertNotIn("mx", rows[0]["contacts"][0])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "mx",
                                       "no MX check has been run")

    def test_absent_the_contact_list_is_unknown_and_never_pass(self):
        state, paths, rows = self.plant([_without(_record(), "contacts")])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "contacts")


class Row11HygieneWorkspaceHistory(_Harness):
    """hygiene.check step 2 via hygiene.index (row 11 of 13)."""

    RULE = "hygiene_workspace_history"

    def test_satisfies_an_unworked_identity_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_a_confirmed_touch_on_the_same_address_excludes(self):
        """The same strong identity (email) in a SECOND record with a
        PUSH_MARKED event: hygiene._from_contact reads one confirmed touch
        as PREVIOUSLY_CONTACTED, and worst() orders it over the candidate's
        own FRESH row."""
        history = _record(
            id="r-0001",
            contacts=[{"key": HISTORY_KEY, "name": NAME, "email": EMAIL}],
            events=[_event(events.PUSH_MARKED, contact=HISTORY_KEY)])
        state, paths, rows = self.plant([history, _record()])
        cell = self.cell(state, paths, self.contact(rows[-1]), self.RULE)
        self.assert_excluded(cell, "worked this person before",
                             "contacted 1 time(s)")

    def test_absent_a_strong_identifier_is_unknown_and_never_pass(self):
        """No email, no LinkedIn profile, no provider id: 'could not be
        matched' is not 'no history exists'. Identity is proved, never
        guessed - a name and a company are never identity."""
        state, paths, rows = self.plant([_record()])
        cell = self.cell(state, paths,
                         self.contact(rows[0], email=""), self.RULE)
        self.assert_unknown_never_pass(cell, "strong identifier")


class Row12HygieneAccountHistory(_Harness):
    """hygiene.check step 3 via _from_account (row 12 of 13)."""

    RULE = "hygiene_account_history"

    def test_satisfies_an_unworked_company_passes(self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_a_colleague_touched_at_the_domain_excludes(self):
        """A DIFFERENT person (so identity does not match and the step-2
        exclusion does not apply) at the SAME domain, with a confirmed
        touch: Sarah has never appeared before; Acme has been contacted.
        Sarah is not fresh - the case the hygiene module was asked for."""
        history = _record(
            id="r-0001",
            contacts=[{"key": HISTORY_KEY, "name": HISTORY_NAME,
                       "email": HISTORY_EMAIL}],
            events=[_event(events.PUSH_MARKED, contact=HISTORY_KEY)])
        state, paths, rows = self.plant([history, _record()])
        cell = self.cell(state, paths, self.contact(rows[-1]), self.RULE)
        self.assert_excluded(cell, "worked this company before",
                             "has been contacted before")

    def test_absent_a_domain_is_unknown_and_never_pass(self):
        state, paths, rows = self.plant([_record()])
        cell = self.cell(state, paths,
                         self.contact(rows[0], domain=""), self.RULE)
        self.assert_unknown_never_pass(cell, "domain")


class Row13ClientApprovalRegister(_Harness):
    """hygiene.check step 0 via clientapproval.is_suppressed (row 13 of 13).
    The register is NOT one of the eight declared authorities, so the ask
    self-polices ABSENT / UNREADABLE / EMPTY / POPULATED."""

    RULE = "client_approval_register"

    def test_satisfies_an_approved_domain_in_a_populated_register_passes(
            self):
        state, paths, contact = SATISFIES[self.RULE](self)
        self.assert_pass(self.cell(state, paths, contact, self.RULE))

    def test_violates_a_client_suppression_row_is_excluded(self):
        state, paths, rows = self.plant(
            [_record()],
            register_rows=[_approval_row(clientapproval.SUPPRESSED)])
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_excluded(cell, "approval register carries",
                             clientapproval.SUPPRESSED, "operator-control")

    def test_absent_the_register_file_is_unknown_never_a_manufactured_pass(
            self):
        """THE SPEC HAZARD audit/0001 named: clientapproval.load() answers
        [] for a missing file and is_suppressed reads [] as 'not
        suppressed' - a PASS manufactured by an absent authority. The ask
        stats the file before anything reads it."""
        state, paths, rows = self.plant([_record()])
        register = os.path.join(os.path.dirname(paths["queue"]),
                                "client-approval.jsonl")
        self.assertFalse(os.path.exists(register),
                         "the control must observe the ABSENT register - if "
                         "a plant left the file behind, this arm proved "
                         "nothing")
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "ABSENT")

    def test_a_present_but_empty_register_is_unknown_too(self):
        """PRESENT_EMPTY is not an answer for any rule whose question is
        'is this in here' - this module's own TASK-0190 doctrine, applied
        to a file the five-state gate cannot see. A suppression is born
        from a snapshot DIFF; a register that never held a row is a client
        who was never asked."""
        state, paths, rows = self.plant([_record()], register_rows=[])
        register = os.path.join(os.path.dirname(paths["queue"]),
                                "client-approval.jsonl")
        self.assertTrue(os.path.exists(register))
        self.assertEqual([], store.read_jsonl(register))
        cell = self.cell(state, paths, self.contact(rows[0]), self.RULE)
        self.assert_unknown_never_pass(cell, "EMPTY")


# --------------------------------------- the instrument's own other answers

class TheInstrumentCanPrintTheOtherAnswer(_Harness):
    """A green cell proves nothing until the instrument has been shown able
    to print the other one. Both directions, on all thirteen rows, each in
    the SAME satisfies world its arm test proved."""

    def test_every_row_degrades_to_unknown_when_its_ask_is_reverted_to_none(
            self):
        """THE DEFECT audit/0001 MEASURED, put back on purpose: `ask: None`
        in the slot. Every satisfies world must read UNKNOWN again, for the
        gate's own reason - never PASS, never EXCLUDED. 13/13 or the count
        is named."""
        degraded = []
        for rule in THE_THIRTEEN:
            with self.subTest(rule=rule):
                weakened = tuple(
                    dict(r, ask=None) if r["name"] == rule else r
                    for r in preflight.RULES)
                state, paths, contact = SATISFIES[rule](self)
                with mock.patch.object(preflight, "RULES", weakened):
                    cell = self.cell(state, paths, contact, rule)
                self.assertEqual(preflight.UNKNOWN, cell["cell"])
                self.assertIn("no form that can be evaluated", cell["why"])
                degraded.append(rule)
        self.assertEqual(list(THE_THIRTEEN), degraded)

    def test_every_satisfies_world_reddens_when_the_ask_excludes_everybody(
            self):
        """The subtler break: an ask that refuses everybody would pass every
        absent arm and every violates arm green. In each satisfies world -
        the one proven PASS above - it must turn the cell EXCLUDED. 13/13
        or the count is named."""

        def _refuse_everybody(ctx):
            return "control mutation: this ask refuses everybody"

        reddened = []
        for rule in THE_THIRTEEN:
            with self.subTest(rule=rule):
                hostile = tuple(
                    dict(r, ask=_refuse_everybody) if r["name"] == rule
                    else r
                    for r in preflight.RULES)
                state, paths, contact = SATISFIES[rule](self)
                with mock.patch.object(preflight, "RULES", hostile):
                    cell = self.cell(state, paths, contact, rule)
                self.assertEqual(preflight.EXCLUDED, cell["cell"])
                self.assertIn("refuses everybody", cell["why"])
                reddened.append(rule)
        self.assertEqual(list(THE_THIRTEEN), reddened)


class TheWiringIsMeasuredNotClaimed(_Harness):
    """Existence is not function: the slots themselves, pinned."""

    def test_all_13_slots_point_at_their_own_named_function(self):
        by_name = {r["name"]: r for r in preflight.RULES}
        for rule in THE_THIRTEEN:
            with self.subTest(rule=rule):
                fn = by_name[rule]["ask"]
                self.assertIs(getattr(preflight, "_ask_" + rule), fn)
                self.assertEqual("_ask_" + rule, fn.__name__)

    def test_the_remaining_ask_none_rows_are_exactly_the_provider_rows(
            self):
        """Nobody may re-open a slot by accident: after canary/0002 the
        ONLY rows without an evaluable form are the four that declare a
        provider read, and the wrapper's own count line renders 0 no-form
        rules on both channels."""
        none_rows = [r for r in preflight.RULES if r.get("ask") is None]
        self.assertEqual(4, len(none_rows))
        for rule in none_rows:
            with self.subTest(rule=rule["name"]):
                self.assertTrue(rule.get("needs_provider_read"))
        no_form = [r["name"] for r in preflight.RULES
                   if r.get("ask") is None
                   and not r.get("needs_provider_read")]
        self.assertEqual([], no_form)


class NoRealAddressIsInThisFile(unittest.TestCase):
    """Reserved domains only, asserted on this module's own bytes - the
    TASK-0250 module's discipline, kept."""

    def test_every_address_literal_is_a_reserved_domain(self):
        path = os.path.abspath(__file__)
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8")
        found = re.findall(r"[\w.+-]+@[\w.-]+", text)
        self.assertTrue(found, "the scan found no address at all, so it "
                               "proved nothing - the builders above must "
                               "carry literals for it to read")
        for address in found:
            domain = address.rsplit("@", 1)[-1].rstrip(".\"',;:")
            self.assertTrue(
                domain.endswith(".test") or domain.endswith(".invalid"),
                "%s is not a reserved domain" % address)


if __name__ == "__main__":
    unittest.main(verbosity=2)
