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
    COMMIT: 3a3e959b
    CAMPAIGNS WALKED / UNREADABLE: live sweep not yet run (requires provider
      reads; script and tests complete). The script walks every campaign in
      campaigns.jsonl that has a heyreach_campaign_id or bison_campaign_id.
    PROVIDER ROWS READ: live sweep owed
    MATCHED / UNRECORDED / STATE_MISMATCH / NOT_OURS / UNKNOWN: live sweep owed
    EXHAUSTIVENESS IDENTITY PRINTED (yes/no, the line):
      yes - "Exhaustiveness: {sum} == {total}  OK"
      Pinned in test: test_exhaustiveness_identity_holds
    THE LEDGER-KEY FUNCTION YOU IMPORTED:
      push.push_id from src/push.py (line: "from src import ... push ...")
      Used in _possible_keys() via push.push_id(rec, contact_key, sk, ch)
      executionguard._key also imports this same function (line 1207)
    WOULD THIS HAVE CAUGHT ISSUE-025's 76 BLANKS:
      YES. The 91 foreign leads attached to campaigns 491-498 would have no
      queue record match (they are the client's leads from campaigns 327/328/
      352, created months earlier). Each would be classified UNRECORDED: the
      provider has leads the ledger never heard of. The forward reconciler
      returned "0 unsettled, 0 problems" because the ledger had no rows. The
      reverse sweep would have surfaced ~85-91 UNRECORDED rows.
    grep -rn reverse_reconcile scripts/ src/:
      scripts/reverse_reconcile.py:39:    py -3 scripts/reverse_reconcile.py
      scripts/reverse_reconcile.py:40:    py -3 scripts/reverse_reconcile.py --work-dir ...
      scripts/reverse_reconcile.py:607:   p = argparse.ArgumentParser(prog="reverse_reconcile", ...)
      Also imported by tests/test_reverse_reconciliation_is_exhaustive.py

    TESTS: 11/11 passing
      test_exhaustiveness_identity_holds                           OK
      test_injected_row_with_no_ledger_key_is_unrecorded           OK
      test_removing_classification_makes_injected_test_fail        OK
      test_provider_read_failure_produces_unknown                  OK
      test_exhaustiveness_still_holds_after_failure                OK
      test_each_row_gets_exactly_one_class                         OK
      test_failed_ledger_with_active_provider_is_mismatch          OK
      test_sent_ledger_with_active_provider_is_matched             OK
      test_imported_key_matches_stored_key                         OK
      test_zero_campaigns_reported                                 OK
      test_script_is_importable                                    OK

    FILES CHANGED:
      scripts/reverse_reconcile.py                                 (new)
      tests/test_reverse_reconciliation_is_exhaustive.py           (new)
      docs/REVERSE-RECONCILIATION-2026-09-25.md                    (new)

    FINDINGS:
      1. collision.campaign_bindings() only indexes by bison_campaign_id,
         not heyreach_campaign_id. The reverse reconciler works around this
         by using the campaign row directly as the binding evidence.
      2. The EmailBison lead reading pages GET /campaigns/{id}/leads directly
         (same approach as bison._paged) because bison.membership() returns
         lead IDs without emails, and the email is needed for queue matching.
      3. NOT_OURS requires positive evidence (provider campaign name
         contradicting our binding). A lead in a bound campaign with no queue
         match is UNKNOWN by default, promoted to UNRECORDED if the provider
         shows activity. This is the honest answer.

    RISKS:
      1. The live sweep has not been run. The script and tests are complete
         but unvalidated against real provider data.
      2. The EmailBison path uses bison.base(), bison.headers() and the
         leads endpoint directly. If the route shape changes, the pagination
         may break silently.
      3. HeyReach campaign_leads returns customUserFields: [] (confirmed live
         2026-08-26), so queue matching relies entirely on LinkedIn URL
         normalization via linkedin.key().

    RECOMMENDED CLAUDE ACTION:
      1. Run the live sweep from Claude's worktree against a copy of work/
      2. Review the UNRECORDED rows for evidence of unrecorded writes
      3. Consider whether collision.campaign_bindings() should also index
         by heyreach_campaign_id for consistency
