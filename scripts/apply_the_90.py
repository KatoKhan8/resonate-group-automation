#!/usr/bin/env python3
"""Put the 2026-10-12 proposal's do-not-contact list on `agency-dnc.jsonl`,
reversibly, and prove both directions by NAME-SET rather than by count.

TASK 0020, suppression lane, 2026-10-15. THIS SCRIPT WRITES NOTHING WITHOUT
`--apply`, AND THE DEFAULT IS A DRY RUN.

## Why this file exists at all, instead of `agencydnc.add(...)` x 90

Every handoff since 2026-10-12 has recorded the apply step as
"`agencydnc.add(...)` x 90". **That command cannot be run**, and it is not a
question of permission - it is not executable against the artefacts that
exist. Measured 2026-10-15:

    agencydnc.add("email", "<64-hex digest>")
    ValueError: not a usable identifier

`add(kind, value)` takes the PLAINTEXT identifier and computes the digest
itself, by design - `fingerprint()` is the only thing that ever sees an
address. The proposal
(`work/review/SUPPRESSION-PROPOSAL-2026-10-12.json`) deliberately stores
`sha256` digests and no plaintext, and so does the classification derived
from it. There is no address anywhere on disk to hand to `add`, and
recovering one needs a provider read.

So the row is written with the digest we already hold. That is sound because
the digest is the whole key: `load()` indexes by `fingerprint` and nothing
else, and `lookup()` hashes the candidate it is given and asks the index.
The stored `kind` is not part of the key - it is not stored at all. A row
appended with a correct email digest is therefore indistinguishable, to every
reader, from one `add()` wrote.

That the proposal's digests ARE `agencydnc.fingerprint` digests is a
measurement and not an assumption: 4 of the 94 were found already on
`work/agency-dnc.jsonl`, a file only `add()` has ever written, by exact
intersection of 256-bit digests. Those 4 are the four this script will not
write, and they are the proof its arithmetic is right.

## The one thing this script refuses hardest

**A digest already on the list is a refusal of the whole run.** Not a skip.
If a target were already present for an independent reason, the reversal
below would delete somebody who asked to be removed before this task
existed - which is the worst outcome available here, worse than not applying
at all. The 90 were measured absent on 2026-10-14 against a 15-row file; that
is a statement about a file that can change, so it is re-measured here and
`--apply` stops if it no longer holds.

## Reversal

Append-only is a durability property, not a reversal strategy: `agencydnc`
has no remover, by design. Reversal rewrites the file keeping every physical
row whose fingerprint is not in this run's manifest.

**It is NOT a byte-restore from the backup**, and that distinction is the
whole reason the manifest exists. Between apply and reversal somebody may
legitimately add a row - the web layer and
`scripts/record_self_send_exclusions.py` both can - and restoring bytes would
silently destroy it. The backup is taken, and is used only as the authority
for the before name-set that the reversal is proved against.

    py -3 scripts/apply_the_90.py --set the-90
    py -3 scripts/apply_the_90.py --set the-90 --apply --backup work/dnc-backup
    py -3 scripts/apply_the_90.py --revert work/dnc-backup/REVERSAL-<stamp>.json
    py -3 scripts/apply_the_90.py --revert <manifest> --apply
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import agencydnc, store                              # noqa: E402

CLASSIFIED = os.path.join("work", "suppression-measure",
                          "the-94-classified.json")

# The two sets anybody could mean by "the 90", and they are not the same
# people. Required rather than defaulted, because the difference is 8 real
# human beings and an operator should have to name which.
#
#   the-90  every person not already on the list - the proposal's own
#           `to_add: 90`. Includes 5 this lane's independent classifier
#           declined to decide and 3 it put on hold.
#   the-82  only those the independent pass called `suppressed` on an
#           explicit opt-out phrase. The 3 already-on-list suppressed
#           people are not here because they are already on the list.
SETS = ("the-90", "the-82")

# A reason category is derived from the rule that classified the person, and
# never guessed. `agencydnc.REASONS` is a closed vocabulary and picking the
# wrong member of it mislabels why somebody is suppressed forever.
#
# `wrong-target` and `needs-review` are deliberately absent: the first may be
# about mis-targeting rather than about the person, and the second is the
# bucket whose whole meaning is "the rules decline to decide". Including
# either needs `--reason-undecided`, typed by a person.
HOLD_REASON = {
    "gdpr-erasure": agencydnc.LEGAL,
    "company-closed": agencydnc.INTERNAL,
}

HEX = set("0123456789abcdef")


def _sha256(path):
    if not os.path.exists(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _physical_rows(path):
    """Lines carrying at least one row. Counted separately from `load()`.

    `load()` returns a dict keyed by fingerprint, so it CANNOT see a
    duplicate physical row - two identical appends collapse to one entry and
    the name-set looks untouched. The reversal has to remove bytes, so it
    needs the physical count as well as the set.
    """
    if not os.path.exists(path):
        return 0
    rows = 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                rows += len(agencydnc._rows_in(line)[0])
    return rows


def _refuse(message):
    print(f"REFUSED: {message}")
    raise SystemExit(2)


def _targets(which, classified, reason_undecided):
    """The people this run would write, each with a derived reason.

    Refuses rather than guessing anywhere the classification does not settle
    the reason, and refuses on a count that does not match the set's name -
    a set called `the-90` that holds 89 people is a different set.
    """
    if not os.path.exists(classified):
        _refuse(f"{classified} does not exist. It is gitignored, so it is "
                f"present only in the tree that produced it. Without it "
                f"there is no list to apply and nothing here may be guessed.")
    with open(classified, encoding="utf-8") as handle:
        doc = json.load(handle)
    people = doc.get("people") or []
    if not people:
        _refuse(f"{classified} names no people")

    out = []
    undecided = []
    for person in people:
        if person.get("already_on_dnc"):
            continue                       # the 4; already suppressed
        bucket = person.get("bucket")
        if which == "the-82" and bucket != "suppressed":
            continue
        digest = (person.get("fingerprint") or "").strip().lower()
        if len(digest) != 64 or set(digest) - HEX:
            _refuse(f"fingerprint is not a sha256 digest: {digest!r}")
        if bucket == "suppressed":
            reason = agencydnc.REQUESTED
            why = "explicit opt-out phrase in their own words"
        else:
            rules = person.get("my_rule_hold") or []
            derived = [HOLD_REASON[r] for r in rules if r in HOLD_REASON]
            if derived:
                reason, why = derived[0], rules[0]
            else:
                undecided.append((digest, bucket, rules))
                continue
        out.append({"fingerprint": digest, "reason": reason, "bucket": bucket,
                    "why": why, "domain": person.get("domain"),
                    "first_asked": person.get("first_asked")})

    if undecided:
        if not reason_undecided:
            print(f"\n{len(undecided)} people have no reason this script will "
                  f"derive, so they are NOT included:")
            for digest, bucket, rules in undecided:
                print(f"  {digest[:16]}  bucket={bucket:<13} "
                      f"rules={rules or '[]'}")
            print("  Include them only by typing a category: "
                  "--reason-undecided requested|legal|complaint|internal\n")
        else:
            for digest, bucket, rules in undecided:
                out.append({"fingerprint": digest,
                            "reason": reason_undecided, "bucket": bucket,
                            "why": f"operator-supplied: {reason_undecided}",
                            "domain": None, "first_asked": None})

    expected = int(which.split("-")[1])
    if len(out) != expected:
        _refuse(f"--set {which} resolved to {len(out)} people, not "
                f"{expected}. Nothing is written on a count that does not "
                f"match the set it is named after. "
                f"{'Pass --reason-undecided to include the undecided.' if undecided else ''}")
    # Deterministic order, so two runs of the same set produce the same bytes
    # and a diff between them is a real difference.
    out.sort(key=lambda r: r["fingerprint"])
    return out


def _refuse_wrong_tree(path):
    """The file must already exist, or this is the wrong checkout.

    `agencydnc.path()` resolves against `store.queue_path()`, which resolves
    against THIS TREE's ROOT. `work/` is gitignored, so every worktree has
    its own and a run from one resolves to a path that does not exist:

        wt-suppression-2026-10-14\\work\\agency-dnc.jsonl   <- not read by anything
        resonate-group-automation\\work\\agency-dnc.jsonl   <- the real list

    Left unguarded that is the worst failure this script could have, because
    it does not look like a failure. The dry run would report
    `before fingerprints=0`, no target would collide with an empty index, the
    apply would create a fresh 90-row file, the read-back would prove the
    name-set perfectly, and nothing in production would have changed. A
    silent no-op reporting APPLIED AND PROVEN.

    Same root cause as the suite lock in CLAUDE.md, and refused the same way:
    fail closed rather than resolve it cleverly. Pass `AGENCY_DNC` to point
    somewhere deliberately - a rehearsal, or a test.
    """
    if os.path.exists(path) or os.environ.get("AGENCY_DNC"):
        return
    _refuse(
        f"{path} does not exist.\n"
        f"  `work/` is per-worktree and gitignored, so this is almost "
        f"certainly the wrong checkout rather than an empty list.\n"
        f"  Run this from the MAIN checkout, or set AGENCY_DNC explicitly "
        f"for a rehearsal.\n"
        f"  Creating the file here would apply 90 suppressions that nothing "
        f"in production reads, and prove them.")


def apply_set(which, classified, reason_undecided, backup_dir, do_apply):
    path = agencydnc.path()
    _refuse_wrong_tree(path)
    targets = _targets(which, classified, reason_undecided)

    print(f"file          {path}")
    print(f"set           {which}  ({len(targets)} people)")
    before_index = agencydnc.load(path)
    before_set = set(before_index)
    before_rows = _physical_rows(path)
    before_sha = _sha256(path)
    damaged = agencydnc.damaged_lines(path)
    print(f"before        fingerprints={len(before_set)} "
          f"physical_rows={before_rows} damaged_lines="
          f"{damaged or 'NONE'} sha256={(before_sha or '-')[:16]}")

    if damaged:
        _refuse(f"lines {damaged} cannot be fully read. A do-not-contact "
                f"list whose current roster is uncertain is not a list this "
                f"run may rewrite - the reversal could not prove itself "
                f"complete against it.")

    collisions = sorted(t["fingerprint"] for t in targets
                        if t["fingerprint"] in before_set)
    if collisions:
        _refuse(f"{len(collisions)} target(s) are ALREADY on the list: "
                f"{[c[:16] for c in collisions]}. The whole run stops. A "
                f"reversal of this manifest would delete a row that was "
                f"here before this task, and an unsuppressed person is a "
                f"worse outcome than an unapplied list.")

    by_reason = {}
    for target in targets:
        by_reason[target["reason"]] = by_reason.get(target["reason"], 0) + 1
    print(f"reasons       {by_reason}")
    print(f"after         fingerprints={len(before_set) + len(targets)} "
          f"physical_rows={before_rows + len(targets)}  (predicted)")

    if not do_apply:
        print("\nDRY RUN. Nothing written. Re-run with "
              "--apply --backup <dir> to write.")
        return 0

    if not backup_dir:
        _refuse("--apply needs --backup <dir>. The backup is the authority "
                "for the before name-set the reversal is proved against.")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ")
    copy = os.path.join(backup_dir, f"agency-dnc.{stamp}.jsonl")
    if before_sha is not None:
        shutil.copy2(path, copy)
        if _sha256(copy) != before_sha:
            _refuse("the backup copy does not hash to the original. "
                    "Nothing written.")
    manifest_path = os.path.join(backup_dir, f"REVERSAL-{stamp}.json")
    manifest = {
        "task": "TASK 0020 suppression, the 90",
        "set": which,
        "at": store.now(),
        "file": path,
        "backup": copy if before_sha is not None else None,
        "before": {"sha256": before_sha, "physical_rows": before_rows,
                   "fingerprints": sorted(before_set)},
        "added": [t["fingerprint"] for t in targets],
        "reasons": {t["fingerprint"]: t["reason"] for t in targets},
    }
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    print(f"backup        {copy if before_sha is not None else '(no file yet)'}")
    print(f"manifest      {manifest_path}")

    # The write. Mirrors `agencydnc.add`: inside the production barrier, heal
    # a previous tear before appending, one row per line, flushed and fsynced
    # because a do-not-contact row is not worth buffering.
    store.refuse_production_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    written_at = store.now()
    with open(path, "a", encoding="utf-8") as handle:
        if handle.tell() > 0:
            with open(path, "rb") as reader:
                reader.seek(-1, os.SEEK_END)
                if reader.read(1) != b"\n":
                    handle.write("\n")
        for target in targets:
            handle.write(json.dumps({"fingerprint": target["fingerprint"],
                                     "reason": target["reason"],
                                     "at": written_at},
                                    sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())

    return _prove(path, before_set, {t["fingerprint"] for t in targets},
                  before_rows, len(targets), manifest_path)


def _prove(path, before_set, added, before_rows, added_n, manifest_path):
    """Read the file back off disk and compare NAME-SETS, both directions."""
    after_index = agencydnc.load(path)
    after_set = set(after_index)
    after_rows = _physical_rows(path)
    damaged = agencydnc.damaged_lines(path)
    gained = after_set - before_set
    lost = before_set - after_set
    print("\n--- read back off disk ---")
    print(f"NEW   (in after, not before) {len(gained)}")
    print(f"GONE  (in before, not after) {len(lost)}")
    print(f"physical_rows {before_rows} -> {after_rows} "
          f"(expected {before_rows + added_n})")
    print(f"damaged_lines {damaged or 'NONE'}")
    ok = True
    if gained != added:
        ok = False
        print(f"MISMATCH: NEW is not exactly the target set. "
              f"missing={sorted(added - gained)[:4]} "
              f"unexpected={sorted(gained - added)[:4]}")
    if lost:
        ok = False
        print(f"MISMATCH: {len(lost)} fingerprint(s) LOST: "
              f"{[x[:16] for x in sorted(lost)][:4]}")
    if after_rows != before_rows + added_n:
        ok = False
        print("MISMATCH: physical row count is not before + added")
    if damaged:
        ok = False
        print("MISMATCH: the file now has lines that cannot be fully read")
    print("VERDICT " + ("APPLIED AND PROVEN BY NAME-SET" if ok
                        else "NOT PROVEN - reverse it:"))
    if not ok:
        print(f"  py -3 scripts/apply_the_90.py --revert {manifest_path} "
              f"--apply")
    return 0 if ok else 1


def revert(manifest_path, do_apply):
    """Remove exactly this manifest's fingerprints and prove the before-set."""
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    path = agencydnc.path()
    _refuse_wrong_tree(path)
    if os.path.abspath(manifest["file"]) != os.path.abspath(path):
        _refuse(f"this manifest was written against {manifest['file']} and "
                f"this tree resolves to {path}. A reversal must rewrite the "
                f"same file the apply wrote.")
    added = set(manifest["added"])
    before_set = set(manifest["before"]["fingerprints"])
    print(f"file          {path}")
    print(f"manifest      {manifest_path}  set={manifest['set']} "
          f"added={len(added)}")

    damaged = agencydnc.damaged_lines(path)
    if damaged:
        _refuse(f"lines {damaged} cannot be fully read; a reversal cannot "
                f"prove itself complete against an unreadable roster.")

    kept, removed, foreign = [], 0, []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                kept.append(line.rstrip("\n"))
                continue
            rows, _bad = agencydnc._rows_in(stripped)
            for row in rows:
                digest = row.get("fingerprint")
                if digest in added:
                    removed += 1
                    continue
                if digest not in before_set:
                    # Somebody was added between apply and reversal. It is
                    # KEPT, and named - this is exactly the row a byte
                    # restore from the backup would have destroyed.
                    foreign.append(digest)
                kept.append(json.dumps(row, sort_keys=True))
    print(f"would remove  {removed} physical row(s) of {len(added)} "
          f"fingerprint(s)")
    print(f"would keep    {len(kept)} row(s)")
    if foreign:
        print(f"ARRIVED AFTER THE APPLY, kept: {len(foreign)} "
              f"{[f[:16] for f in foreign][:6]}")
    if not do_apply:
        print("\nDRY RUN. Nothing written. Re-run with --apply.")
        return 0

    store.refuse_production_write(path)
    tmp = f"{path}.{os.getpid()}.revert.tmp"
    # NO `newline=`, deliberately, so this writes the same bytes `add` does.
    # `agencydnc.add` opens in text mode without it, so on Windows the real
    # `work/agency-dnc.jsonl` is CRLF - measured 2026-10-15. Writing "\n"
    # here reads back identically (`load` strips) but changes every line of
    # the file, which destroys the one cheap check on a reversal: that a
    # clean undo is byte-identical to the pre-apply backup.
    with open(tmp, "w", encoding="utf-8") as handle:
        for line in kept:
            handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)

    after_set = set(agencydnc.load(path))
    expected = before_set | set(foreign)
    still_there = sorted(after_set & added)
    lost = sorted(expected - after_set)
    unexpected = sorted(after_set - expected)
    print("\n--- read back off disk ---")
    print(f"fingerprints  {len(after_set)}")
    print(f"still present from the manifest {len(still_there)}")
    print(f"GONE that should be here        {len(lost)}")
    print(f"HERE that should not be         {len(unexpected)}")
    print(f"damaged_lines {agencydnc.damaged_lines(path) or 'NONE'}")
    ok = not still_there and not lost and not unexpected
    # The name-set is the proof. The byte comparison is the cheap corroboration
    # and is only expected to match when nothing arrived in between.
    backup = manifest.get("backup")
    if backup and os.path.exists(backup):
        same = _sha256(path) == manifest["before"]["sha256"]
        print(f"bytes vs backup {'IDENTICAL' if same else 'differ'}"
              + ("" if same or not foreign else
                 f" - expected, {len(foreign)} row(s) arrived after the apply"))
    print("VERDICT " + ("REVERSED AND PROVEN BY NAME-SET" if ok
                        else "REVERSAL NOT PROVEN - the byte backup is "
                             f"{backup}"))
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", dest="which", choices=SETS,
                        help="which list to apply; required unless --revert")
    parser.add_argument("--classified", default=CLASSIFIED)
    parser.add_argument("--reason-undecided", choices=agencydnc.REASONS,
                        help="category for people no rule classified; "
                             "typed by a person or they are left out")
    parser.add_argument("--backup", help="directory for the byte backup and "
                                         "the reversal manifest")
    parser.add_argument("--revert", metavar="MANIFEST",
                        help="undo the apply this manifest describes")
    parser.add_argument("--apply", action="store_true",
                        help="actually write; the default is a dry run")
    args = parser.parse_args(argv)

    if args.revert:
        return revert(args.revert, args.apply)
    if not args.which:
        parser.error("--set is required (or --revert MANIFEST)")
    return apply_set(args.which, args.classified, args.reason_undecided,
                     args.backup, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
