#!/usr/bin/env python3
"""The exact words awaiting approval, for the contacts nothing else blocks.

    py -3 scripts/near_miss_approval_packet.py

READ-ONLY. No provider write, no state mutation, no approval field touched.
It renders what is already there and writes one file.

WHY THIS EXISTS. The cohort screen says READY_NOW = 0 on both channels, and
not because the estate is empty: every contact carrying approved copy is either
already live or sits on an account collision refuses, and every contact on a
clean account has no approval. The two sets do not overlap. Seventeen contacts
- twelve LinkedIn, five email - pass every gate except approval. Nothing else
converts anybody: generating the missing `li4` copy unblocks zero, because all
nine copy-blocked contacts are already on STOP or HOLD accounts.

So one approval pass is the whole bottleneck, and the only thing standing
between it and the operator is the reading. This makes the reading cheap.

IT READS LIVE STATE, NOT THE SNAPSHOT. `scripts/task200_approval_packet.py`
builds from `work/queue.snapshot.jsonl`, which is stale and has already
produced wrong numbers twice. A packet is a document somebody approves words
from; building it from a stale file is how an operator approves a sentence that
no longer exists.

IT WRITES TO work/, WHICH IS GITIGNORED, AND THAT IS DELIBERATE. An approval
packet must carry the copy a prospect will actually receive, naming the real
company - hashing it would defeat the purpose, because nobody can approve a
message they cannot read. The PII guard refused an earlier packet on its first
commit, correctly, and the answer was to move the artefact rather than weaken
the guard or hash the copy into uselessness.

WHAT IT DOES NOT DO. It does not approve anything. `approve.approve_step` is
the action a person takes, and the whole point of the accountability gate added
today - 84 stamps in this estate read `by: "claude"` - is that this process
does not get to sign its own work.
"""
import argparse
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from src import claims, clients, lint, store                     # noqa: E402
from src.providers import load_env                               # noqa: E402

import next_ready_cohort as cohort                               # noqa: E402

# THE SCREEN IS RUN, NOT REIMPLEMENTED. `next_ready_cohort` already asks every
# gate in the order the guard asks them, and a packet built on a second opinion
# of who is near-miss would be a packet about different people than the screen
# reports. It exposes `--json`; this consumes it.
OUTPUT = os.path.join(ROOT, "work", "approval",
                      "NEAR-MISS-PACKET-2026-09-17.md")


def verdicts(text, rec, contact, config):
    """Lint and claims, beside the words, so the read is one pass."""
    out = []
    try:
        problems = lint.check(text, config=config) or []
        out.append("lint: clean" if not problems
                   else "lint: " + ", ".join(sorted(str(p) for p in problems)))
    except Exception as exc:
        out.append(f"lint: UNKNOWN ({type(exc).__name__})")
    try:
        verdict = claims.check(text, rec, contact, config=config)
        out.append(f"claims: {verdict}")
    except Exception as exc:
        out.append(f"claims: UNKNOWN ({type(exc).__name__})")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)

    load_env(os.path.join(ROOT, "config", ".env"))
    config = clients.load("productive")
    recs = store.load()

    campaigns_by_id = {c["campaign_id"]: c
                       for c in store.read_jsonl(store.campaigns_path())}
    screen = cohort.Screen(recs, config)
    rows = []
    for channel in ("linkedin", "email"):
        for row in cohort.run(channel, recs, config, campaigns_by_id, screen):
            row["class"] = cohort.classify(row)
            if row["class"] == "NEAR_MISS":
                rows.append((channel, row))

    if not rows:
        print("No near-miss contacts. Nothing to approve, nothing written.")
        return 0

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    by_record = {rec["id"]: rec for rec in recs}

    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write("# Near-miss approval packet\n\n")
        fh.write(f"Generated {stamp} from LIVE state.\n\n")
        fh.write(f"**{len(rows)} contacts pass every gate except approval.** "
                 f"Approving them is the only action that converts anybody "
                 f"today: generating the missing copy unblocks zero, and "
                 f"re-reading the failed collision probes unblocks zero.\n\n")
        fh.write("Each step below is the copy a prospect would receive, with "
                 "the lint and claims verdicts beside it. Nothing here is "
                 "approved by generating this file.\n\n---\n\n")

        for channel, row in rows:
            rec = by_record.get(row.get("record_id"))
            if rec is None:
                continue
            contact = next((c for c in rec.get("contacts") or []
                            if c.get("key") == row.get("contact_key")), None)
            if contact is None:
                continue
            fh.write(f"## {channel} - {rec.get('company') or rec['id']} - "
                     f"{contact.get('name') or contact.get('key')}\n\n")
            fh.write(f"- record `{rec['id']}` contact `{contact.get('key')}`\n")
            fh.write(f"- title: {contact.get('title') or 'UNKNOWN'}\n")
            fh.write(f"- held by: {row.get('why')}\n\n")
            try:
                steps, missing = cohort.render(rec, contact, channel, None,
                                               config)
            except Exception as exc:
                fh.write(f"  COPY WOULD NOT RENDER: {type(exc).__name__}\n\n")
                continue
            if missing:
                fh.write(f"  missing steps: {sorted(missing)}\n\n")
            for key in sorted(steps):
                step = steps[key] or {}
                fh.write(f"### {key}\n\n")
                subject = step.get("subject")
                if subject:
                    fh.write(f"**Subject:** {subject}\n\n")
                text = step.get("body") or step.get("note") or ""
                fh.write("```\n" + str(text).strip() + "\n```\n\n")
                for line in verdicts(text, rec, contact, config):
                    fh.write(f"- {line}\n")
                fh.write("\n")
            fh.write("---\n\n")

    print(f"{len(rows)} near-miss contacts written to")
    print(f"  {OUTPUT}")
    print("\nNothing was approved. `approve.approve_step` is the action a "
          "person takes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
