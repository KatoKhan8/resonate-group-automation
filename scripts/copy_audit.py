#!/usr/bin/env python3
"""Re-check every step of every lead on a list of campaigns against gates 1-3.

    py scripts/copy_audit.py --snapshots work/review/raw \
        --packs work/researchpack-*.jsonl --out work/review

READS ONLY, and reads only FILES: it works from the snapshots
`scripts/copy_snapshot.py` wrote, so the audit can be re-run and its own
bugs fixed without touching a client's provider again.

WHAT IT IS FOR. On 2026-09-25 campaigns 503/504/505 sent 64 emails carrying
the wrong company's pitch signed with the wrong person's name. 491-498 are
LIVE and were built by earlier work, and "older" is not "checked" - so every
lead on both sets is re-checked here against the same three gates, and the
table says which sub-check each lead failed rather than only that it failed.

THE SUB-COLUMNS ARE THE POINT. "775 leads fail gate 2" is true and nearly
useless if every one of them fails only because no lead in the estate
carries a template id yet. The breakdown separates
  - the STRUCTURAL failure (nothing records provenance), from
  - the SUBSTANTIVE ones (the copy names our company, the signature is not
    the mailbox owner's, the quoted line is a navigation bar, the body is
    empty),
because they have different fixes and only the second set describes what a
prospect actually received.
"""
import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import clients, copyprovenance, reviewfile  # noqa: E402

#: The two sets the operator named. 491-498 are LIVE; 503-505 are the
#: campaigns that sent the sixty-four.
LIVE = ("491", "492", "493", "494", "495", "496", "497", "498")
INCIDENT = ("503", "504", "505")

#: How a gate-2 reason is classified for the table. Ordered: the first
#: match wins, so a step that is both unstamped and refused counts once in
#: each column it genuinely names.
GATE2_BUCKETS = (
    ("no_template_id", "no template id"),
    ("refused_term", "refused term"),
    ("wrong_signature", "and the mailbox belongs to"),
    ("uncomparable_signature", "mailbox owner is not known"),
    ("blank_body", "NO COPY AT THE PROVIDER"),
    ("unresolved_merge", "unresolved merge field"),
)

GATE3_BUCKETS = (
    ("no_fact_recorded", "names no pack fact"),
    ("no_span", "no quoted span"),
    ("not_in_snippet", "does not appear in the fact"),
    ("truncated", "no terminal punctuation"),
    ("no_finite_verb", "no finite verb"),
    ("imperative", "opens on the verb"),
    ("no_subject", "no subject before the verb"),
    ("nav_text", "navigation text"),
    ("nav_run", "capitalised words in a row"),
    ("too_short", "under 6 words"),
    ("title_case", "Title Case throughout"),
    ("language_switcher", "language switcher"),
    ("no_source_url", "carries no source url"),
)


def _bucket(reasons, buckets):
    hit = set()
    for reason in reasons or ():
        for name, needle in buckets:
            if needle in reason:
                hit.add(name)
    return hit


def audit_campaign(cid, snapshot, packs, config, client):
    rows = reviewfile.rows(snapshot, packs=packs, config=config, client=client)
    counts = collections.Counter()
    signature_pairs = []
    for row in rows:
        counts["leads"] += 1
        if not row["gate2_ok"]:
            counts["gate2_fail"] += 1
        if not row["gate3_ok"]:
            counts["gate3_fail"] += 1
        if not row["gate2_ok"] and not row["gate3_ok"]:
            counts["both_fail"] += 1
        if row["verdict"] == "HOLD":
            counts["hold"] += 1
        for name in _bucket(row["gate2_reasons"], GATE2_BUCKETS):
            counts["g2:" + name] += 1
        for name in _bucket(row["gate3_reasons"], GATE3_BUCKETS):
            counts["g3:" + name] += 1
        for step in row["steps"]:
            counts["steps"] += 1
            if step.get("signature"):
                signature_pairs.append((step["signature"], row["sender_name"]))
    # WHAT ALREADY LEFT THE BUILDING.
    #
    # `sent_at`, NOT `status == "sent"`. A row the provider handed to a
    # mailbox and which then bounced reads `status: bounced`, and counting
    # status would report 62 attempted deliveries on 503-505 where the
    # operator counted 64 - the two bounced rows were attempted, reached a
    # real address and are part of the incident. An audit that says 62 to an
    # operator holding 64 is an audit nobody trusts again.
    for queue_row in snapshot.get("queue") or []:
        counts["queue:" + str(queue_row.get("status") or "?")] += 1
        if queue_row.get("sent_at"):
            counts["attempted"] += 1
    constants = copyprovenance.constant_signatures(signature_pairs)
    return rows, counts, constants


def redaction_selftest(snapshots_dir, campaigns):
    """Prove no recipient from these campaigns appears in anything git tracks.

    THE FILTER IS TESTED AGAINST EVERY VALUE, AFTER THE FILES ARE WRITTEN.
    `reviewfile.refuse_outside_work` runs before the first byte and is unit
    tested, but that only proves the function refuses - it does not prove
    nothing leaked by another route: a name pasted into a doc, an address in
    a commit message, a fixture built by copying a real row.

    So this takes the ACTUAL addresses and domains of the 1,465 real people
    in these campaigns and searches every file `git ls-files` reports, which
    is by definition the set that gets pushed. Reporting zero hits is only
    worth something because the search covers each value individually rather
    than a sample: a redaction checked on one address and skipped on the
    rest is how an IPv4 leaked once already.
    """
    import subprocess

    # OUR OWN INFRASTRUCTURE IS NOT A RECIPIENT, and leaving it in makes the
    # test cry wolf on its first run: `resonategroup.co` matched 14 committed
    # documents because the operator seeded his own address as a lead on
    # campaign 491, and every sending domain in the pool would match the
    # sender inventory. A self-test that reports a leak in BUILD-SPEC.md is
    # a self-test nobody reads twice.
    # `resonate.co` is `src/testidentity.py`'s own domain - the seeded test
    # identity, which is deliberately in the estate and deliberately in the
    # code that has to exclude it from every count.
    ours = {"resonategroup.co", "resonate.co"}
    snapshots = {}
    for cid in campaigns:
        path = os.path.join(snapshots_dir, "bison-%s.json" % cid)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            snapshots[cid] = json.load(f)
        for row in snapshots[cid].get("sender_pool") or []:
            address = str((row or {}).get("email") or "")
            if "@" in address:
                ours.add(address.split("@", 1)[1].lower())

    # ADDRESSES AND DOMAINS ONLY. Company names were in this set for one run
    # and produced `BUILD-SPEC.md carries 'first person'` - a real company
    # called First Person and an ordinary English phrase. A needle that
    # matches prose cannot distinguish a leak from a sentence, and the
    # identifying data is the address anyway.
    needles = set()
    for snapshot in snapshots.values():
        for lead in snapshot.get("leads") or []:
            email = str(lead.get("email") or "").strip().lower()
            if not email or "@" not in email:
                continue
            domain = email.split("@", 1)[1]
            if domain in ours:
                continue
            needles.add(email)
            needles.add(domain)
    tracked = subprocess.run(["git", "ls-files"], capture_output=True,
                             text=True, cwd=reviewfile.root())
    files = [f for f in tracked.stdout.splitlines() if f.strip()]
    hits = []
    for name in files:
        full = os.path.join(reviewfile.root(), name)
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                body = f.read().lower()
        except (OSError, IsADirectoryError):
            continue
        for needle in needles:
            if needle in body:
                hits.append((name, needle))
    print()
    print("REDACTION SELF-TEST")
    print("   %d distinct recipient values from %d campaigns"
          % (len(needles), len(campaigns)))
    print("   %d git-tracked files searched, each against every value"
          % len(files))
    if hits:
        print("   LEAK - %d hit(s):" % len(hits))
        for name, needle in hits[:20]:
            print("      %s carries %r" % (name, needle))
    else:
        print("   0 hits. No recipient of these campaigns appears in "
              "anything git tracks.")
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshots", default=os.path.join("work", "review", "raw"))
    ap.add_argument("--packs", nargs="*", default=())
    ap.add_argument("--out", default=os.path.join("work", "review"))
    ap.add_argument("--client", default="productive")
    ap.add_argument("--campaigns", nargs="*", default=list(LIVE + INCIDENT))
    a = ap.parse_args(argv)

    pack_files = []
    for pattern in a.packs:
        pack_files += sorted(glob.glob(pattern)) or [pattern]
    packs = reviewfile.load_packs(pack_files)
    config = clients.load(a.client)

    table, totals, all_constants = [], collections.Counter(), {}
    detail = {}
    for cid in a.campaigns:
        path = os.path.join(a.snapshots, "bison-%s.json" % cid)
        if not os.path.exists(path):
            print("MISSING SNAPSHOT %s - not audited, and NOT counted clean"
                  % path)
            continue
        with open(path, encoding="utf-8") as f:
            snapshot = json.load(f)
        rows, counts, constants = audit_campaign(cid, snapshot, packs, config,
                                                 a.client)
        table.append((cid, snapshot.get("campaign", {}).get("status"), counts))
        detail[cid] = {"counts": dict(counts), "constant_signatures": constants}
        if constants:
            all_constants[cid] = constants
        group = "LIVE" if cid in LIVE else "INCIDENT"
        for key, value in counts.items():
            totals[key] += value
            totals["%s:%s" % (group, key)] += value

    print()
    print("RETROACTIVE COPY AUDIT - gates 2 and 3, per campaign, "
          "read back from the provider")
    print()
    head = ("camp", "status", "leads", "steps", "G2 fail", "G3 fail",
            "both", "attempted", "bounced")
    print("%-6s %-11s %6s %6s %8s %8s %6s %10s %8s" % head)
    print("-" * 74)
    for cid, status, counts in table:
        print("%-6s %-11s %6d %6d %8d %8d %6d %10d %8d"
              % (cid, str(status)[:11], counts["leads"], counts["steps"],
                 counts["gate2_fail"], counts["gate3_fail"],
                 counts["both_fail"], counts["attempted"],
                 counts["queue:bounced"]))
    print("-" * 74)

    def band(name, keys, buckets):
        print()
        print(name)
        for key, _needle in buckets:
            live = totals["LIVE:%s:%s" % (keys, key)]
            inc = totals["INCIDENT:%s:%s" % (keys, key)]
            if not (live or inc):
                continue
            print("   %-24s 491-498 %6d    503-505 %6d" % (key, live, inc))

    band("GATE 2 - copy provenance, why each lead failed", "g2", GATE2_BUCKETS)
    band("GATE 3 - pack fact, why each lead failed", "g3", GATE3_BUCKETS)

    print()
    print("TOTALS")
    for group in ("LIVE", "INCIDENT"):
        print("   %-9s leads %5d   gate2 fail %5d   gate3 fail %5d   "
              "both %5d   attempted deliveries %5d"
              % (group, totals["%s:leads" % group],
                 totals["%s:gate2_fail" % group],
                 totals["%s:gate3_fail" % group],
                 totals["%s:both_fail" % group],
                 totals["%s:attempted" % group]))
    if all_constants:
        print()
        print("CONSTANT SIGNATURES - one literal name across several mailbox "
              "owners")
        for cid, constants in sorted(all_constants.items()):
            for signature, owners in sorted(constants.items()):
                print("   %s  %-12r signed out of %d different owners' "
                      "mailboxes: %s"
                      % (cid, signature, len(owners), ", ".join(owners[:6])))

    out = os.path.abspath(a.out)
    reviewfile.refuse_outside_work(out)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "copy-audit-2026-09-25.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"campaigns": detail, "totals": dict(totals)}, f, indent=1)
    print()
    print("detail ->", path)
    leaks = redaction_selftest(a.snapshots, a.campaigns)
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
