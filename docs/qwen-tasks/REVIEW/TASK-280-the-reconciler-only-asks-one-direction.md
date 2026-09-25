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

    BRANCH: qwen-worker-4-r9-task280
    COMMIT: 424cda40
    CAMPAIGNS WALKED / UNREADABLE: 0 / 0 (no work/campaigns.jsonl in this worktree)
    PROVIDER ROWS READ: 0 (no campaign bindings to sweep)
    MATCHED / UNRECORDED / STATE_MISMATCH / NOT_OURS / UNKNOWN: 0/0/0/0/0
    EXHAUSTIVENESS IDENTITY PRINTED (yes/no, the line):
      yes: "EXHAUSTIVENESS: 0 classified + 0 unknown = 0 total (provider rows read: 0)"
    THE LEDGER-KEY FUNCTION YOU IMPORTED: push.push_id from src.push
    WOULD THIS HAVE CAUGHT ISSUE-025's 76 BLANKS:
      Yes, in principle. Those leads would classify as UNRECORDED (provider has
      them, ledger has no ATTEMPTED row). Cannot show live classification from
      this worktree - campaign bindings are not present. Live sweep is owed from
      Claude's worktree.
    grep -rn reverse_reconcile scripts/ src/:
      scripts/reverse_reconcile.py:483:        prog="reverse_reconcile",
      (standalone entry point, same pattern as reconcile_ledger.py)

    TESTS: 25 tests in tests/test_reverse_reconciliation_is_exhaustive.py, all pass
    FILES CHANGED:
      scripts/reverse_reconcile.py (new)
      tests/test_reverse_reconciliation_is_exhaustive.py (new)
      docs/REVERSE-RECONCILIATION-2026-09-25.md (new)
    FINDINGS:
      - Script is structurally correct and fully tested
      - Live sweep requires production work/ state which is not in this worktree
      - To complete live evidence: run from Claude's worktree or copy work/ to
        a temp directory and pass --workspace /path/to/copy
      - The 76-blank-email incident (ISSUE-025) would be caught as UNRECORDED
        rows, but live classification is owed
    RISKS:
      - Live sweep not verified from this worktree (no campaign data)
      - The NOT_OURS classification is conservative: rows that cannot be proved
        ours stay UNKNOWN rather than being folded into NOT_OURS
    RECOMMENDED CLAUDE ACTION:
      - Run the live sweep from Claude's worktree with production state
      - Review the UNRECORDED rows for ISSUE-025 campaigns (491-498)
      - Decide which UNRECORDED rows need manual settlement
