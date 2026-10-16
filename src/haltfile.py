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

#: The directory bit, by VALUE rather than by importing `stat`. TASK 0225
#: added `import stat` and
#: `test_the_stop_sending_brake_asks_nobody_for_permission` caught it on the
#: first run: the brake's dependency set is the filesystem and nothing else,
#: because every import is a thing that can be broken, or that can demand a
#: token, at the moment the operator needs the brake. Property 4 of this
#: module, enforced by test rather than by intention.
_FILE_TYPE_MASK = 0o170000
_DIRECTORY = 0o040000

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

    THE HOME RULE, added by TASK 0225. In one sentence: the brake's state is
    only determinable when the directory it lives in is itself a readable
    directory, and a home that cannot be confirmed makes the brake state
    UNKNOWN, which refuses - whatever the leaf's absence appears to say.

    WHY THAT RULE AND NOT "ABSENCE REFUSES". Absence of the leaf is the
    ONLY way the brake is ever released, so refusing on absence would build
    a brake that is always on - the same defect facing the other way. The
    thing that must not be confused with "the operator has not pulled the
    brake" is "I am not looking where the brake lives", and that is a
    question about the HOME, not about the leaf.

    WHAT THIS RULE DOES NOT CATCH, stated because a guard that is believed
    to cover more than it does is worse than none: a path whose home is
    right and whose LEAF is wrong - a sibling, a typo, a rename - is
    indistinguishable here from a brake that was never pulled, because both
    are "home readable, leaf absent". Nothing inside this function can tell
    those apart; only an assertion on the constant's identity can, and that
    lives in the test module as
    `test_the_shipped_constant_is_the_brake_and_not_a_sibling`. TASK 0225
    measured that plant surviving all 36 tests before that test existed.

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
    path = STOP_SENDING_PATH

    #: The home rule. An absolute path is required first, because
    #: `dirname` of a relative path resolves against the current working
    #: directory - the one thing this module's own docstring forbids the
    #: brake from depending on.
    if not os.path.isabs(path):
        raise OperatorStop(
            f"the brake path {path!r} is not absolute, so it would resolve "
            f"against whichever directory the process happens to be in: the "
            f"brake state is UNKNOWN and UNKNOWN refuses")
    home = os.path.dirname(path)
    try:
        home_stat = os.stat(home)
    except OSError as unreachable:
        raise OperatorStop(
            f"cannot read the brake's home {home}, so the state of the "
            f"brake at {path} is undetermined "
            f"({unreachable.strerror or type(unreachable).__name__}): the "
            f"brake state is UNKNOWN and UNKNOWN refuses. This is the home "
            f"rule, not an errno: a brake whose directory cannot be "
            f"confirmed is not a released brake") from unreachable
    if home_stat.st_mode & _FILE_TYPE_MASK != _DIRECTORY:
        raise OperatorStop(
            f"the brake's home {home} is not a directory, so the state "
            f"of the brake at {path} is UNKNOWN and UNKNOWN refuses")

    try:
        os.lstat(path)
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
