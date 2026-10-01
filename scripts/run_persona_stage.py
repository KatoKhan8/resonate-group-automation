#!/usr/bin/env python3
"""Run the persona stage on named records. DRY RUN unless --apply is given.

    py -3 scripts/run_persona_stage.py bigfish-co-uk thirstcraft-com
    py -3 scripts/run_persona_stage.py bigfish-co-uk thirstcraft-com --apply

WHY THIS EXISTS. `personas.select` is the stage that writes `persona` and
`angle` onto a record's contacts, and NOTHING in `scripts/` calls it - the only
caller of `select_domains` in the entire repository is `personas.select` itself
(`src/personas.py:376`), and `src/generate.py` never calls either. So a record
can reach `state: verified` with `stages: {}` and every contact carrying
`angle: None`, and then generation fails lint with `domains_contact_no_angle`
on every step because the angle was never written - not because any angle
resolution is broken.

That is exactly the state the 2026-10-01 canary records were in. Measured on
`bigfish-co-uk` at master `0724e820`, read-only, before this script existed:

    qualification.persona_plan.strategy        operations_led
    qualification.persona_plan.persona_priority  [operations, delivery,
                                                  resource_management, finance,
                                                  founder]
    personas.family_of(rowan-matthews)         ('operations', 0)
    personas.default_angle(cfg, champion, 'operations')   'operations'
    personas.select_domains(copy of rec)       rowan-matthews -> angle 'operations'
    stored contact angle                       None
    stages                                     {}

So the angle resolves on master with no code change. `default_angle` returns
None for `champion` only when it is called WITHOUT a routing family, and the
real path passes one from the record's own persona plan.

WHAT IT CHANGES, AND WHAT IT DOES NOT. `personas.select` applies ICP, readmits
contacts whose exclusion reason stopped being true, applies the per-persona cap,
writes `persona` and `angle`, marks one `primary`, and moves non-personas into
`excluded` via `set_aside`, which keeps each excluded contact WHOLE - address,
profile and verification evidence included - so a corrected persona list can
restore them. It writes no provider call of any kind and touches no cadence,
approval or copy.

THE WRITE IS A STORE WRITE. It runs inside `store.transaction()`, so the lock is
held across read-modify-write and `refuse_evidence_loss` / `refuse_history_loss`
run on the way out. Only one process may hold that lock; do not run this while
another writer is working.

DRY RUN IS THE DEFAULT and prints the before/after per contact without opening a
transaction at all, because the honest order is to read the diff first.
"""
import argparse
import copy
import sys

sys.path.insert(0, __file__.rsplit("scripts", 1)[0])

from src import clients, personas, store                            # noqa: E402


def shape(contacts):
    """The fields this stage decides, per contact, in a stable order."""
    return [{"key": c.get("key"), "persona": c.get("persona"),
             "angle": c.get("angle"), "primary": bool(c.get("primary")),
             "sendable": bool(c.get("sendable")), "title": c.get("title")}
            for c in sorted(contacts or [], key=lambda c: c.get("key") or "")]


def report(rec_id, before, after, excluded_before, excluded_after):
    print("== %s" % rec_id)
    keys = {e["key"] for e in before} | {e["key"] for e in after}
    b = {e["key"]: e for e in before}
    a = {e["key"]: e for e in after}
    for key in sorted(keys):
        was, now = b.get(key), a.get(key)
        if was == now:
            continue
        if now is None:
            print("   %-24s KEPT -> EXCLUDED  (%s)" % (key, (was or {}).get("title")))
            continue
        if was is None:
            print("   %-24s EXCLUDED -> KEPT   (%s)" % (key, now.get("title")))
            continue
        print("   %-24s persona %r -> %r | angle %r -> %r | primary %s -> %s"
              % (key, was.get("persona"), now.get("persona"),
                 was.get("angle"), now.get("angle"),
                 was.get("primary"), now.get("primary")))
    print("   excluded: %d -> %d" % (excluded_before, excluded_after))
    if before == after and excluded_before == excluded_after:
        print("   NO CHANGE")


def run(ids, apply_changes):
    config_cache = {}
    if not apply_changes:
        changed = 0
        for rec in store.load():
            if rec.get("id") not in ids:
                continue
            client = rec.get("client")
            if client not in config_cache:
                config_cache[client] = clients.load(client)
            working = copy.deepcopy(rec)
            before = shape(rec.get("contacts"))
            excluded_before = len(rec.get("excluded") or [])
            personas.select(working, config_cache[client])
            after = shape(working.get("contacts"))
            report(rec["id"], before, after, excluded_before,
                   len(working.get("excluded") or []))
            if before != after:
                changed += 1
        print("\nDRY RUN. %d of %d named records would change. "
              "Nothing was written." % (changed, len(ids)))
        return 0

    seen = set()
    with store.transaction() as recs:
        for rec in recs:
            if rec.get("id") not in ids:
                continue
            seen.add(rec["id"])
            client = rec.get("client")
            if client not in config_cache:
                config_cache[client] = clients.load(client)
            before = shape(rec.get("contacts"))
            excluded_before = len(rec.get("excluded") or [])
            personas.select(rec, config_cache[client])
            after = shape(rec.get("contacts"))
            report(rec["id"], before, after, excluded_before,
                   len(rec.get("excluded") or []))
    missing = sorted(ids - seen)
    if missing:
        print("\nNOT FOUND, nothing written for: %s" % ", ".join(missing))
    print("\nAPPLIED to %d record(s)." % len(seen))
    return 0 if not missing else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="+", help="record ids, e.g. bigfish-co-uk")
    parser.add_argument("--apply", action="store_true",
                        help="open a store transaction and write. Default is a "
                             "dry run that writes nothing.")
    args = parser.parse_args(argv)
    return run(set(args.ids), args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
