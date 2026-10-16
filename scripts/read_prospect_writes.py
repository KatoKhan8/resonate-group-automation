"""Print every provider write that touched one prospect, in order.

TASK 0230, section 3. The write ledger (`src/providerwrites._ledger`)
records every attempt through the door, and until now nothing read it back
per prospect. The first time a canary prospect replies with something
unexpected, the question is "what did they receive, and when" - and this
command is what gets run to answer it.

    py -3 scripts/read_prospect_writes.py --email jane.doe@example.com

Read-only. Opens the queue and the ledger for reading and writes nothing.

HOW A ROW IS ATTRIBUTED. Since TASK 0230 section 2, a row written for a
prospect carries `key` in the push_id shape `rec:contact:step:channel`, so
one row is attributed to one prospect by prefix match - no other file is
consulted. The email is resolved to (record, contact) through the record
store, which is the only authority for which person an address is.

FAIL-CLOSED, NOT CLEAN-LOOKING. Every way this command can know less than
the whole story is a non-zero exit with the gap named in the output:

  - the email matches no record, or the store cannot be read: UNKNOWN, not
    zero - "no record holds this address" is not the statement "nothing
    was ever sent to them";
  - the ledger file is missing: it cannot account for any window, all of
    them, including everything before the file existed;
  - a line that will not parse is named by line number, never skipped;
  - a row from before the step change - prospect-facing, no `key` - is an
    UNACCOUNTABLE WINDOW: it may be this prospect's and the ledger cannot
    say, so the attributable list prints with a banner saying it is NOT
    every write that touched them;
  - a timestamp that goes backwards means an append-only file was edited
    or merged, and "in order" stops being a claim this file supports.

A staging row (a pause, a resume: campaign-scoped, no authorization, no
prospect) is not attributed to anyone and is not a gap - it is simply not
this person's write.

Exit codes: 0 the account is complete; 2 it is partial or unknowable, with
the reason printed. Never a clean list on a partial answer.
"""
import argparse
import datetime
import io
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import providerwrites, store  # noqa: E402


def _normalise(address):
    """One comparison shape for both sides, or the raw string if the
    normaliser declines the address - an exact match on the raw string is
    still a match, only a looser one."""
    from src import verification
    folded = verification.normalise_address(address)
    return folded if folded else str(address or "").strip().lower()


def _resolve(email):
    """Every (record id, contact key) whose contact holds this email.

    Reads the store only. An address two records share is not an error -
    both are returned and both are attributed - because the ledger's rows
    name their own record and the truth is 'both', not 'pick one'.
    """
    try:
        recs = list(store.load())
    except Exception as e:  # unreadable store is a refusal, not emptiness
        raise _CannotAccount(
            f"the record store is unreadable ({store.queue_path()}: "
            f"{type(e).__name__}: {e}) - the email cannot be resolved and no "
            f"account of writes can be given")
    wanted = _normalise(email)
    matches = []
    for rec in recs:
        for contact in (rec.get("contacts") or []):
            if _normalise(contact.get("email") or "") == wanted:
                matches.append((str(rec.get("id")),
                                str(contact.get("key"))))
    return matches


class _CannotAccount(Exception):
    """The command cannot know the answer, in whole or in part."""


def _facing(operation):
    """True/False for prospect-facing, or None when this code no longer
    knows the verb - which is itself a gap the caller must name."""
    try:
        _channel, facing, _why = providerwrites.describe(operation)
    except providerwrites.WriteUnsupported:
        return None
    return bool(facing)


def main(argv=None, _out=None):
    out = _out or sys.stdout
    parser = argparse.ArgumentParser(
        description="Every provider write that touched one email, in order.")
    parser.add_argument("--email", required=True,
                        help="the prospect's email address")
    parser.add_argument("--ledger", default=None,
                        help="ledger path (default: the provider-writes "
                             "ledger beside the queue)")
    args = parser.parse_args(argv)

    try:
        matches = _resolve(args.email)
    except _CannotAccount as e:
        print(f"email: {args.email}", file=out)
        print(f"CANNOT ACCOUNT: {e}", file=out)
        return 2
    if not matches:
        print(f"email: {args.email}", file=out)
        print(
            f"CANNOT ACCOUNT: no record in {store.queue_path()} holds "
            f"{args.email!r}. This is UNKNOWN, not zero - it is not the "
            f"statement that no write touched them", file=out)
        return 2

    path = os.path.abspath(
        args.ledger or providerwrites.ledger_path())
    if not os.path.exists(path):
        print(f"email: {args.email}", file=out)
        print(
            f"CANNOT ACCOUNT: there is no provider-write ledger at {path}. "
            f"A missing ledger cannot account for any window, all of them, "
            f"including everything before the file existed", file=out)
        return 2

    prefixes = tuple(f"{rid}:{ckey}:" for rid, ckey in matches)
    gaps = []          # (line number, description) - the unaccountable
    attributed_rows = []
    staging_rows = 0
    last_at = None
    with io.open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                gaps.append((lineno, "unreadable line - a hole in the "
                                     "audit trail, named rather than "
                                     "skipped"))
                continue
            operation = str(row.get("operation"))
            key = str(row.get("key") or "")
            at = str(row.get("at") or "")
            if key and key.startswith(prefixes):
                attributed_rows.append((lineno, row))
            elif _facing(operation) is None:
                gaps.append((lineno, f"operation {operation!r} is not "
                                     f"declared by this code - the row "
                                     f"cannot even be classified as "
                                     f"prospect-facing or not"))
            elif _facing(operation) is True and key in ("", "UNKNOWN"):
                # A prospect-facing row that names no contact: written
                # before the step change, or by a write that held no
                # authorization. Either way the ledger cannot say whose
                # prospect it touched - which is exactly a window it
                # cannot account for.
                gaps.append((lineno, f"prospect-facing {operation} at {at} "
                                     f"carries no contact key and cannot "
                                     f"be attributed to any prospect"))
            else:
                staging_rows += 1
            if at:
                if last_at is not None and at < last_at:
                    gaps.append((lineno, f"timestamp goes backwards "
                                         f"({last_at} -> {at}): an "
                                         f"append-only ledger was edited "
                                         f"or merged, and 'in order' is "
                                         f"not a claim this file supports"))
                last_at = at if last_at is None else max(last_at, at)

    print(f"email: {args.email}", file=out)
    for rid, ckey in matches:
        print(f"record: {rid} (contact {ckey})", file=out)
    print(f"ledger: {path}", file=out)
    print(file=out)
    for lineno, row in attributed_rows:
        print(f"{row.get('at', 'UNKNOWN')}  {row.get('operation', 'UNKNOWN')}"
              f"  {row.get('outcome', 'UNKNOWN')}  "
              f"campaign {row.get('campaign', 'UNKNOWN')}  "
              f"step {row.get('step', 'UNKNOWN')}  "
              f"by {row.get('by', 'UNKNOWN')}", file=out)
    print(file=out)
    if staging_rows:
        print(f"({staging_rows} staging write(s) - campaign-scoped, no "
              f"prospect - are not this person's writes)", file=out)
    if gaps:
        print("account: INCOMPLETE", file=out)
        for lineno, why in gaps:
            print(f"  line {lineno}: {why}", file=out)
        print("The list above is every write this ledger can attribute; "
              "it is NOT every write that touched them.", file=out)
        return 2
    print(f"account: complete - {len(attributed_rows)} write(s) "
          f"attributable to {args.email}, in order", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
