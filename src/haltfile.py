"""The brake the operator can pull alone: a zero-byte file at one path.

    C:\\Users\\Zvonimir\\Desktop\\resonate-ops\\STOP-SENDING

`pilotcaps/0160` returned criterion 9 NOT MET: "a kill switch the owner can
operate alone is named and tested." This module is that switch. One
question, asked immediately before every provider transport that is not
itself a brake: does this file exist?

WHY AN ABSOLUTE PATH OUTSIDE EVERY CHECKOUT. There is more than one clone -
`qwc` has its own `work/` and `qwen/0100` found it empty while the real
20,449-row ledger lived in a different tree. A brake whose path is relative
to whichever checkout is running is a brake the operator can create in the
wrong tree and believe he pulled. The path is a constant, resolved from
neither `__file__` nor the current working directory.

WHY A FILE AND NOT A BUTTON. It must work when the thing it is stopping is
broken. A file needs a keyboard. A button needs the web app, a browser and
a session - all of which can be the thing that is wrong.

THE FOUR PROPERTIES (the task fails without all four):

1. Checked immediately before the transport call, inside the same function.
   In `providerwrites._perform` it sits between the last permission
   question and `try: transport(payload)`; every provider write site that
   does not route through `perform` carries the same check on the line
   before its verb. A brake checked at the top of a loop or a cycle has a
   hole as long as the cycle.
2. Fail-closed on unreadable. `FileNotFoundError` is the ONLY outcome that
   allows a send: permissions, I/O error, anything else refuses. Today's
   defect family is "unreadable became go"; this does not join it.
3. No bypass: no path reaches a transport without passing this check,
   proven by call graph against the 58-write-path denominator and enforced
   by test.
4. It asks nobody for permission. No gate, no role, no token, no grant in
   front of this check - a brake that asks for permission is not a brake,
   and the halt it replaces was broken precisely because it demanded a
   GateToken nothing could supply at that moment. That is also why this
   module imports ONLY `os`: importing any gate-bearing module would put
   that module between the operator and the brake.

WHAT THIS FILE DOES NOT STOP. Mail already queued at EmailBison. The render
is a snapshot - the whole lesson of the 76 blank emails is that a queued row
goes out with the words it was queued with, whatever happens to this file
afterwards. The provider-side pause is a separate layer and stays the
operator's. Deleting the file releases the brake; it never un-sends.
"""
import os

#: The one path, outside every checkout, never derived from `__file__` or
#: the working directory. Read at call time from the module (not captured at
#: import) so a test can point it at a temp path; no test of this repository
#: ever creates the real file.
STOP_SENDING_PATH = r"C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING"

#: The four verbs that are THEMSELVES brakes, exempt from this one. Pausing
#: and stopping a lead can only ever mean somebody receives LESS - the same
#: argument `providerwrites.REPEATABLE` is built on, and these values are
#: exactly that set's members, pinned there by test. Pulling STOP-SENDING
#: must never disable another brake: the 481 blank-content watch re-applies
#: `bison.pause` every 180 seconds through `perform`, and it must keep doing
#: so with the file present.
BRAKE_OPERATIONS = frozenset({
    "heyreach.pause",
    "heyreach.stop_lead",
    "bison.pause",
    "bison.stop_lead",
})


class OperatorStop(RuntimeError):
    """The operator's own brake fired. The transport was not reached.

    A sibling of `providerwrites.WriteRefused`, deliberately NOT a subclass:
    a stop pulled by the owner is not one of the machine's refusals, and
    letting it be caught by a handler written for `WriteRefused` (or for the
    provider's own errors) is how an operator's stop gets reworded into
    something it is not. Callers catch it by name.
    """


def require_released():
    """Return None, or raise OperatorStop. The whole brake.

    `FileNotFoundError` for the LEAF is the only "go". Any other outcome of
    reading the path refuses: an unreadable brake is an UNKNOWN brake, and
    UNKNOWN never becomes go. `os.lstat` rather than `os.path.exists` for
    exactly that reason - `exists` answers False for a path it could not
    read, which is the "unreadable became go" defect in one function. A
    DIRECTORY at the path also stops the send: `lstat` succeeds, so the
    path is not absent, and the conservative reading of "something is
    there" is that the operator put it there.

    THE WINDOWS SPLIT, measured 2026-10-15: `lstat` of a path whose parent
    is a FILE raises FileNotFoundError carrying winerror 3
    (ERROR_PATH_NOT_FOUND) on Windows - the same exception Python gives a
    genuinely missing leaf (winerror 2). POSIX hands the parent-is-a-file
    case to NotADirectoryError, an OSError, which already refuses below.
    Treating every Windows FileNotFoundError as "absent" would re-open the
    exact hole this module exists to close, one errno mapping wide: a
    brake path it cannot resolve is a brake state it cannot determine, so
    winerror 3 is UNKNOWN and refuses.
    """
    try:
        os.lstat(STOP_SENDING_PATH)
    except FileNotFoundError as missing:
        if getattr(missing, "winerror", None) == 3:
            raise OperatorStop(
                f"cannot read {STOP_SENDING_PATH} "
                f"({missing.strerror or type(missing).__name__}): a "
                f"component of the path is missing or not a directory, so "
                f"the brake state is UNKNOWN and UNKNOWN refuses. "
                f"Fail-closed by design; restore the path, or delete the "
                f"file, to release the brake") from missing
        return None
    except OSError as unreadable:
        raise OperatorStop(
            f"cannot read {STOP_SENDING_PATH} "
            f"({unreadable.strerror or type(unreadable).__name__}): the "
            f"brake state is UNKNOWN and UNKNOWN refuses. Fail-closed by "
            f"design; restore read access to the path, or delete the file, "
            f"to release the brake") from unreadable
    raise OperatorStop(
        f"STOP-SENDING is present at {STOP_SENDING_PATH}: the operator has "
        f"pulled the brake and no transport was reached. Delete the file to "
        f"release it")
