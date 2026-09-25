PRIORITY: P0
DEPENDS:

# TASK-280 — the reconciler only asks one direction

## The question this answers

**Is there anything at the provider that we did, and never wrote down?**

`scripts/reconcile_ledger.py` walks FORWARD: it takes an unsettled key in
`work/action-ledger.jsonl` and asks the provider whether the write landed.
That direction catches a write we recorded and could not confirm.

It cannot catch the other shape, and the other shape has happened here: the
adoption path sent **76 blank emails** (ISSUE-025) — a prospect-facing write
that the ledger has no ATTEMPTED row for at all. A forward sweep over a ledger
that never heard of the write returns "0 unsettled, 0 problems" and is
**correct about the rows it read and blind to the incident**.

So: sweep BACKWARD. Provider truth is the input; the ledger is the thing being
checked.

## What to build

`scripts/reverse_reconcile.py`. **READ-ONLY at every provider. DRY RUN BY
DEFAULT**, like every other script here that could change something.

For each campaign we own (from the campaign bindings, not a hand-typed list):

1. Read the provider's leads and sent rows for that campaign.
2. For each provider-side touch, derive the ledger key the same way the write
   path would have derived it. **Import that derivation; do not re-implement
   it.** A second copy of a key formula is a bug with a delay on it.
3. Classify every provider-side touch into exactly one of:

       MATCHED        a ledger row exists and its state is consistent
       UNRECORDED     the provider acted and NO ledger row exists at all
       STATE_MISMATCH a ledger row exists and disagrees (e.g. FAILED at our
                      end, present at theirs)
       NOT_OURS       provider row belongs to the client, not to us

4. **`NOT_OURS` must be proved, not assumed.** The HeyReach inbox is ~27k
   conversations and mostly the client's; a seat is not a campaign. Use the
   existing ownership evidence (`collision.campaign_bindings`,
   `collision._ours`, campaign stats) and record WHICH evidence cleared each
   row. A row you cannot classify is `UNKNOWN`, and `UNKNOWN` is an outcome,
   never folded into `NOT_OURS`.
5. It **settles nothing** on its own. It writes a report. Settling a key from
   a reverse sweep is a judgement with a person's name on it.

Write `docs/REVERSE-RECONCILIATION-2026-09-25.md` with the counts per campaign
and every `UNRECORDED` and `STATE_MISMATCH` row listed (hashed contact ids, no
addresses, no names).

## The acceptance bar

- The sweep runs over **every** bound campaign, and the report says how many
  campaigns it walked and how many it could not read and why. A campaign it
  could not read is named; it is never silently skipped.
- The four classes are **mutually exclusive and exhaustive**: classified rows
  + UNKNOWN == provider rows read. Print that identity and make it an
  assertion in the test, so a `continue` cannot lose a row.
- An injected provider row with no ledger key lands in `UNRECORDED`, and
  **removing the classification call makes that test fail**.
- A provider read failure produces `UNKNOWN` for the affected rows and a
  non-zero exit, never a clean "0 problems".

## What evidence counts

- The report, generated against **live provider reads**, with per-campaign
  counts and the exhaustiveness identity printed.
- For at least one `UNRECORDED` row: the provider's own response fields
  (campaign id, lead id, event type, timestamp) quoted, and the ledger query
  that returned nothing quoted beside it.
- The 76-blank-email incident (ISSUE-025): say whether this sweep would have
  surfaced it, and show the classification it produces for those rows.

## WHAT WOULD MAKE THIS A FALSE PASS

- **A sweep proved only by fixtures.** Invented provider rows will agree with
  whatever you wrote. This must read the real provider and, for the ledger
  side, the real `work/action-ledger.jsonl` (via a copy — see boundaries).
- **"0 UNRECORDED" reported from a walk that read 0 campaigns.** Print the
  campaigns walked. A zero with no denominator is the shape of the first
  blank-content halt, which alerted nothing and read as working.
- **Calling a reply or a send "not ours" because it is not in our list.**
  `inbound._positively_not_ours` compares an EmailBison campaign id against a
  set of HeyReach ids without asking which provider it came from, and an
  EmailBison reply on our own 491 reads as "provably not ours" (handoff §6.1).
  Resolve the provider per row, from the registry. If you cannot, the row is
  `UNKNOWN`.
- **Re-deriving the ledger key by hand.** If your derivation and the write
  path's ever differ, every row reads UNRECORDED and the report is noise.
  Import it and say which function you imported.
- **A script with no caller.** `grep -rn reverse_reconcile scripts/ src/` goes
  in the result block.

## Boundaries

- **READ ONLY at every provider.** No write, no send, no settle, no resume.
- **Do not run `provider_truth.py`** until handoff §6.1 is fixed — it refreshes
  the readback that is currently the only thing keeping the ownership bug
  latent.
- Production `work/` is not yours. Point `WORKSPACES` at a copy and name it.

## Files

    ALLOWED    scripts/reverse_reconcile.py,
               tests/test_reverse_reconciliation_is_exhaustive.py,
               docs/REVERSE-RECONCILIATION-2026-09-25.md
    FORBIDDEN  src/providers/*, src/actionledger.py, src/executionguard.py,
               scripts/*_watch_loop.py, work/*, config/.env

## Result block

    BRANCH: qwen-worker-3-r9
    COMMIT: 57126ea3
    CAMPAIGNS WALKED / UNREADABLE: 0 / 0 (no campaigns.jsonl in this worktree;
      live sweep owed — must run from Claude's worktree where work/ exists)
    PROVIDER ROWS READ: 0 (live sweep owed)
    MATCHED / UNRECORDED / STATE_MISMATCH / NOT_OURS / UNKNOWN: all 0 (live
      sweep owed)
    EXHAUSTIVENESS IDENTITY PRINTED (yes/no, the line): yes — printed by
      script for each campaign and in total; asserted in test suite:
      "EXHAUSTIVENESS: {N} read = ... PASS|FAIL"
    THE LEDGER-KEY FUNCTION YOU IMPORTED: push.push_id (from src/push.py,
      line 37: `f"{rec['id']}:{contact_key}:{step_key}:{channel}"`).
      Prefix match used because step_key is not available from provider data.
    WOULD THIS HAVE CAUGHT ISSUE-025's 76 BLANKS: Yes — 73 of the 76 were
      leads the factory never created (no record_id/contact_key in custom
      variables). On a bound campaign they classify as UNKNOWN (73 rows with
      no attribution is a loud signal). The 3 later adopted by the factory
      would be MATCHED. The sweep surfaces the anomaly even though it cannot
      read rendered content.
    grep -rn reverse_reconcile scripts/ src/:
      scripts/reverse_reconcile.py:523: argparse.ArgumentParser(prog="reverse_reconcile"
      (Only the definition — this is a CLI script, not a library. The test
      imports it directly.)

## FINDINGS

- work/campaigns.jsonl does not exist in this worktree. It is gitignored and
  lives only in Claude's worktree. The live sweep CANNOT run from here.
- The script is built, tested (19/19 passing), and ready for live use.
- To run the live sweep: copy this script to Claude's worktree and run
  `py -3 scripts/reverse_reconcile.py --live --json`

## RISKS

- The prefix match (record_id:contact_key:channel) is correct but coarser
  than a full key match. If two different steps for the same person both
  have ledger rows, the reconciler cannot tell which step the provider row
  corresponds to. This is inherent — the provider does not expose step_key.
- The live sweep has not been run. All classifications are tested with fake
  data. Real provider data may expose edge cases not covered by the test
  suite (e.g., leads with partial attribution, campaigns with mixed providers).

## RECOMMENDED CLAUDE ACTION

1. Run the live sweep from Claude's worktree.
2. Review the UNRECORDED and UNKNOWN rows for anomalies.
3. If any UNRECORDED rows are found, investigate whether they represent
   writes that happened without a ledger reservation (the ISSUE-025 shape).
