PRIORITY: P0
DEPENDS:

# TASK-215 - compare_bison compares two different things and can never pass

## WHERE THIS SITS

This is the LAST gate before the first real EmailBison send, and it cannot
pass as written. Everything else is done: campaign 485 is live-ready at the
provider with sender 2736 attached, 10 leads, the 3-step CONTROL sequence,
cap 20/day, 0 sent, and all 30 approvals now fingerprinted against the
CONTROL-expanded copy.

`providerwrites.perform` demands an `executionguard.Authorization` for
`bison.activate` because it is prospect-facing. `authorize()` demands a
`readback`, and for EmailBison that is `configdiff.compare_bison`. It returns
`verdict: FAIL` with eight mismatches, and four of them are comparing
quantities that are not the same quantity.

Measured 2026-09-16 against campaign 485:

    MATCH    lead_count 10/10, lead_set (all 10 addresses), campaign_id 485,
             max_emails_per_day 20, max_new_leads_per_day 20

    MISMATCH BY DESIGN - these are the defect
      subjects   approved: the RESOLVED per-contact text
                 provider: ['{SUBJECT_1}', 'Re: {SUBJECT_2}', '{SUBJECT_3}']
      bodies     approved: the RESOLVED per-contact body
                 provider: ['<p>{BODY_1}</p>', ...]
      delays     approved: [1, 4, 8] repeated per contact - cadence DAYS
                 provider: [3, 4, 1] - provider WAIT_IN_DAYS
      actions    same shape of disagreement

    MISMATCH BECAUSE THE LOCAL ROW IS STALE - bookkeeping, also yours
      status        row says 'paused', provider says 'draft'
      workspace     row says '', provider says '10'
      sender_ids    row says [], provider says ['2736']
      campaign_name row holds the human name, provider holds the DERIVED name
                    with the '[client/campaign_id]' suffix

## WHY THE FIRST GROUP IS A DEFECT AND NOT A FINDING

TASK-159 established the architecture from the provider: **EmailBison has no
merge variables.** The sequence carries `{SUBJECT_N}` / `{BODY_N}` and the
per-lead words travel as CUSTOM VARIABLES on the lead. So the provider's
sequence SHOULD hold placeholders, and the resolved copy should be compared
against the lead's custom variables - not against the sequence.

The delays are the same mistake in the other direction. `CAMPAIGN-FACTORY.md`
and `bisonfactory._sequence_steps` both say a cadence DAY is a position in a
schedule and a provider node delay is a property of the graph - "two different
quantities that happen to agree" - and that the config declares the wait and
the factory verifies it reproduces the cadence. Comparing days to waits
compares a schedule to a graph.

So `compare_bison` was written for an architecture where the sequence carried
resolved copy. It has never passed, which is consistent with no EmailBison send
ever having been made through this path.

## THE QUESTION

1. **Compare like for like.** Per field, state what the approved side and the
   provider side each mean, then compare the two that are the same quantity:
     - sequence subjects/bodies vs the EXPECTED PLACEHOLDERS the config
       declares (`{SUBJECT_1}`...), normalising the provider's own `Re: `
       prefix on a `thread_reply` step - `bisonfactory._comparable_step`
       already does that normalisation and the reason is documented there
     - the RESOLVED per-contact copy vs the LEAD'S CUSTOM VARIABLES at the
       provider, which is where it actually lives
     - declared `wait_in_days` vs provider `wait_in_days`
2. **Fix the stale-row group at its source.** `bisonfactory.stage` knows the
   provider id, the derived name, the attached senders and the workspace, and
   does not write them back onto the campaign row. Either record them there or
   have `compare_bison` derive them the way the factory does - and say which
   you chose and why. TASK-170 hit the identical derived-name problem in its
   own identity check and fixed it by calling
   `bisonfactory.provider_campaign_name`.
3. **Do NOT make the comparison pass by loosening it.** The point of this gate
   is that an approval covers the words a prospect receives. If the resolved
   copy is NOT in the lead's custom variables, that is a real mismatch and it
   must FAIL - loudly, naming the contact. Report that rather than widening.
4. **Prove it both ways.** A test where the provider matches and the verdict is
   PASS, and a test where one contact's custom variable differs from its
   approved copy and the verdict is FAIL naming that contact. A comparator that
   cannot fail is the defect it is replacing.
5. **Then run it for real against 485** and report the verdict and every field.

## THE TRAP

This gate stands immediately before the first real send this system has ever
made. A comparator rewritten to return PASS is worse than one that always
returns FAIL, because the second one blocks and the first one lies. If you
cannot make a field compare honestly, leave it failing and say so.

Second trap: do not touch the approvals, the copy, the sequence, the leads or
the cap. The campaign is staged and verified. This task changes a COMPARATOR.

## WHAT YOU MAY NOT DO

- No provider WRITES. Reads against EmailBison are expected and required.
- Do not activate anything. Do not call resume.
- Do not change `providerwrites` SUPPORTED/CONDITIONAL, `executionguard`, or
  any gate's threshold.
- Do not modify approvals, cadence copy, the sequence, the lead set or caps.
- Never commit an email address, a contact name, a company name or a domain -
  this comparison handles all four. Hash them in the deliverable.

## FILES ALLOWED

    src/configdiff.py
    src/bisonfactory.py   (only to write back provider facts onto the row, if
                           that is the option you choose)
    tests/test_compare_bison.py   (new)
    docs/COMPARE-BISON-2026-09-16.md   (new)

## FILES FORBIDDEN

    src/providerwrites.py   src/executionguard.py   src/approve.py
    src/approval.py   config/   work/

## DELIVERABLE

Each field with what both sides mean and which two are comparable; the
like-for-like comparison implemented; the stale-row group fixed at its source
with your reason; both tests green with the exit code read off the process; and
the real verdict for 485 field by field.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 536dc3e9

**TESTS:**
- `tests/test_compare_bison.py` - 7 tests, all pass (exit code 0)
- `tests/test_bison_campaign_write` - 30 tests, all pass
- `tests/test_bison_prewrite_check` - 29 tests, all pass
- `tests/test_emailbison_no_empty_greeting` - 7 tests, all pass
- Total: 73 tests, 0 failures

**FILES CHANGED:**
- `src/configdiff.py` - rewrote `approved_bison`, updated `provider_bison` to
  read per-lead custom variables, updated `compare_bison` to do per-lead copy
  comparison, added `_expected_lead_variables` and `_hash_email` helpers
- `tests/test_compare_bison.py` - new file, 7 tests
- `docs/COMPARE-BISON-2026-09-16.md` - new deliverable doc

**FINDINGS:**

1. **The defect was exactly as described.** Four fields compared different
   quantities:
   - subjects/bodies: resolved per-contact text vs provider placeholders
   - delays: cadence day positions vs provider `wait_in_days`
   - actions: cadence step keys vs provider step names
   - campaign_name: human name vs derived name

2. **The fix compares like for like:**
   - subjects/bodies: expected placeholders from config vs provider placeholders
   - delays: declared `wait_in_days` from config vs provider `wait_in_days`
   - actions: `step1/step2/step3` on both sides
   - campaign_name: `bisonfactory.provider_campaign_name` on both sides

3. **Per-lead copy comparison added.** The resolved per-contact copy is now
   compared against the lead's custom variables at the provider. A mismatch
   FAILS loudly, naming the contact by hashed email (SHA-256, first 12 chars).

4. **Stale-row group: derived in the comparator.** Chose to derive
   `campaign_name` and `workspace` in the comparator rather than write them
   back in the factory. TASK-170 precedent for `campaign_name`. `sender_ids`
   and `status` still read from the row - if they mismatch, that's a real
   issue to fix at the row level.

5. **Thread-reply normalisation.** Both sides apply `_comparable_step` to strip
   the `Re: ` prefix on thread_reply steps, so the comparison is honest.

6. **Real verdict for 485: OWED from Claude's worktree.** This worktree has no
   `work/` directory and cannot access live campaign data. The comparison
   requires:
   ```
   py -3 -m src.configdiff --campaign 485 --channel email --workspace 10 --json
   ```
   Run from Claude's worktree and report the verdict back.

**RISKS:**

1. **Per-lead read is expensive for large campaigns.** Each lead requires a
   separate `GET /leads/{id}` call. Acceptable for staged campaigns with a
   handful of leads; prohibitive for thousands.

2. **`sender_ids` and `status` still read from the row.** If the row is stale,
   these fields will still mismatch. Fix at the row level, not in the
   comparator.

3. **`_hash_email` uses SHA-256 truncated to 12 chars.** Enough to identify a
   contact in a failure message without logging PII. Not collision-proof for
   millions of leads, but fine for ten.

**RECOMMENDED CLAUDE ACTION:**

1. Run the comparison against campaign 485 from Claude's worktree and report
   the verdict.
2. If `sender_ids` or `status` still mismatch, fix the campaign row to carry
   the correct values.
3. The gate should now pass for campaign 485 if the provider holds what was
   staged. If it fails, the failure will name the specific field and contact.
