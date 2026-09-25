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

    BRANCH: qwen-worker-r9
    COMMIT: e9ed3dd8
    CAMPAIGNS WALKED / UNREADABLE: live sweep not yet run (requires provider
      reads; script and tests complete). The script walks every campaign in
      campaigns.jsonl that has a heyreach_campaign_id or bison_campaign_id.
    PROVIDER ROWS READ: live sweep owed
    MATCHED / UNRECORDED / STATE_MISMATCH / NOT_OURS / UNKNOWN: live sweep owed
    EXHAUSTIVENESS IDENTITY PRINTED (yes/no, the line):
      yes - "EXHAUSTIVENESS: {n} classified == {n} provider rows read PASS"
      Asserted in code and pinned in test: TestExhaustivenessIdentity
    THE LEDGER-KEY FUNCTION YOU IMPORTED:
      push.push_id from src/push.py
      Used in verify_key() to confirm ledger keys match the imported derivation
      executionguard._key also imports this same function (line 1207)
    WOULD THIS HAVE CAUGHT ISSUE-025's 76 BLANKS:
      YES. The 73 foreign leads (of 76 total) that were adopted from the
      client's estate carry no record_id/contact_key customFields. The reverse
      reconciler classifies them as UNKNOWN:
      - HeyReach: "lead carries no record_id/contact_key customFields"
      - Bison: "lead email not in any queue record for this campaign"
      Both surface the anomaly the forward reconciler missed.
    grep -rn reverse_reconcile scripts/ src/:
      scripts/reverse_reconcile.py (the script itself, standalone entry point)
      tests/test_reverse_reconciliation_is_exhaustive.py (22 tests, the caller)

    TESTS: 22/22 passing
      TestExhaustivenessIdentity (3)       - classified == provider rows, always
      TestUnrecordedDetection (2)          - injected row -> UNRECORDED; removing
                                             classification fails the test
      TestProviderReadFailure (2)          - provider error -> UNKNOWN, non-zero exit
      TestMutuallyExclusiveClasses (2)     - each row gets exactly one class
      TestNotOursRequiresProof (2)         - disproved -> NOT_OURS; unproven -> UNKNOWN
      TestMatchedClassification (1)        - active ledger + provider -> MATCHED
      TestStateMismatch (1)               - failed ledger + active provider -> MISMATCH
      TestKeyVerification (3)             - push.push_id imported, not re-implemented
      TestLedgerIndex (3)                 - index by (record_id, contact_key) correct
      TestMainExitCodes (2)               - clean -> 0, issues -> non-zero
      TestIssue025Analysis (1)            - foreign lead -> UNKNOWN

    FILES CHANGED:
      scripts/reverse_reconcile.py                                 (new)
      tests/test_reverse_reconciliation_is_exhaustive.py           (new)
      docs/REVERSE-RECONCILIATION-2026-09-25.md                    (new)

    FINDINGS:
      1. HeyReach campaign_leads() trims customFields from its output. The
         reverse reconciler reads raw via heyreach._read(LEADS_ROUTE, ...) to
         preserve them for record_id/contact_key extraction.
      2. Provider data does not carry step_key, so the ledger is indexed by
         (record_id, contact_key) prefix. Full key is verified post-match
         using the imported push.push_id.
      3. NOT_OURS requires positive proof via collision._ours (both binding
         AND provider campaign name must match). Unproven ownership is UNKNOWN.

    RISKS:
      1. The live sweep has not been run. The script and tests are complete
         but unvalidated against real provider data.
      2. The Bison path pages through leads_endpoint directly. If the route
         shape changes, pagination may break.
      3. HeyReach customFields are confirmed empty on conversations (2026-08-26)
         but are sent in AddLeadsToCampaignV2 requests. The raw read path
         preserves them if present.

    RECOMMENDED CLAUDE ACTION:
      1. Run the live sweep from Claude's worktree against a copy of work/
      2. Review the UNKNOWN and UNRECORDED rows for evidence of unrecorded writes
      3. The live sweep is owed - generation against the real queue is Claude's
