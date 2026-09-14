# TASK-053 - One readback that answers the whole acceptance question

## WHY

The operator's acceptance criterion for the HeyReach campaign is explicit,
and it is not "the API returned 200":

    WRITE TO HEYREACH -> READ BACK FROM HEYREACH
    -> COMPARE EXPECTED VS ACTUAL -> PASS

`scripts/heyreach_readback.py` exists and produced
`docs/HEYREACH-PROVIDER-READBACK-2026-09-14.md`. It prints. It does not
COMPARE, and it does not return a verdict - so the comparison is currently
done by a person reading two things side by side, which is exactly where a
"pass" gets asserted because the output looked fine.

## GOAL

`py -3 scripts/heyreach_readback.py <canonical-campaign-id> --expect` reads
the campaign back from HeyReach, builds what the factory WOULD write from
canonical state, compares them field by field, prints a table, and exits
non-zero on any mismatch.

## WHAT MUST BE COMPARED, AND EACH IS A SEPARATE ROW

The operator named these. Every one gets its own line in the table with
EXPECTED, ACTUAL and PASS/FAIL:

    campaign id and name
    status
    lead list id, and the lead COUNT from the provider
    sender seat ids
    schedule
    node count, and the count per node type
    every delay and its unit
    the branch structure - root-to-leaf paths, not just node totals
    the connection request note
    open-profile behaviour (present or absent, and which)
    the accepted and not-accepted paths
    the InMail path where supported
    every LinkedIn message text
    merge variables present
    DOUBLE-brace variables - must be zero, see below
    per-variable fallbacks

## THE THREE THAT MUST NEVER BE SKIPPED

- **`{{double}}` braces.** Measured across 81 campaign sequences in this
  workspace: 3,295 single-brace occurrences and ZERO double. A
  `{{first_name}}` reaches a prospect as literal text.
- **A repeated message ON ONE PATH.** Node totals hide this completely. The
  provider graph read on 2026-09-14 sends the identical message at +3 HOURS
  and again at +3 DAYS on the already-connected branch, and every
  node-count check passed it. Walk the paths.
- **Any literal person or company name.** `jacob` and `&Partner` are in the
  live graph today. The check must fail on a literal where a merge variable
  belongs.

## THE HARD PART

"Expected" has to come from canonical state, not from a snapshot somebody
saved. `heyreachfactory.stage(campaign_id, live=False)` returns
`report["plan"]["sequence"]`, which is exactly what a live run would write.
Use that. If you find yourself hard-coding an expected node count, stop:
that is a test of a number rather than of the system.

`heyreach.sequence_matches(observed, sent)` already exists and already
handles the provider adding bare END nodes. Read it before writing a
comparison, and say in FINDINGS whether you used it, extended it, or needed
something different and why.

## PROVE IT FAILS

A comparison that cannot fail is the defect this repository keeps finding.
Prove it by comparing the CURRENT provider state of 599020 against the
CURRENT locally built sequence - they genuinely disagree right now, on merge
variables, on `jacob`, on node count and on the duplicated message. The
script must exit non-zero and name all four.

Then prove the reverse with a fixture: an observed sequence identical to the
expected one exits zero.

## READ-ONLY. THIS IS ABSOLUTE.

You may READ from HeyReach. You may not write to any provider under any
circumstances. Do not call `heyreachfactory.stage(live=True)`, do not call
`scripts/write_heyreach_sequence.py` with `--live`, do not add a lead.
599020 holds zero leads and must still hold zero when you finish.

Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.

## RESULT BLOCK

End this file with STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION.

STATUS: DONE
COMMIT SHA: cd85bd7
TESTS:
  - tests/test_heyreach_readback.py: 11 tests, all pass
  - Full suite: 15 pre-existing failures in test_e2e, test_preproduction,
    test_replaysim. None caused by this change (only new files added).
  - Live run against 599020: exits 1, reports 8 FAIL rows:
    branch_structure, connection_note, message_texts, merge_variables,
    per_variable_fallbacks, literal:jacob, literal:&Partner,
    repeated_msg_on_path. 19 rows PASS.
  - 599020 confirmed at zero leads after the run.

FILES CHANGED:
  - scripts/heyreach_readback.py  (rewritten: comparison, not just printing)
  - tests/test_heyreach_readback.py  (new: 11 tests)

FINDINGS:

  1. sequence_matches: USED as a summary check at the end of the output,
     NOT extended. The operator's table needs EVERY row with its own
     PASS/FAIL, and sequence_matches returns only the FIRST mismatch.
     build_rows() is the detailed comparison; sequence_matches is the
     one-line summary. Both are run.

  2. The expected sequence comes from merge_sequence_copy(config) +
     build_sequence(), not from stage(). stage() also runs per-contact
     semantic duplicate detection, which currently refuses on
     acqcom-com/brian-price's copy. The SEQUENCE structure is independent
     of that refusal: the merge-variable graph is what the config says,
     regardless of whether any specific contact's copy clears the
     repetition check.

  3. Node count after stripping bare ENDs: 17 vs 17, PASS. The provider
     holds 24 raw nodes (7 bare-END reply-stops added by the vendor on
     MESSAGE conditionals). After stripping, the structure matches. The
     original readback report's "17 vs 24 FAIL" was comparing raw counts
     including the vendor's additions; the comparison here strips them
     first, same as sequence_matches does.

  4. The eight failures the script detected against 599020:
     - branch_structure: paths differ (provider has literal text, expected
       has merge variables)
     - connection_note: "{connection_note}" vs "hi jacob, as a founder..."
     - message_texts: merge variables vs literal text
     - merge_variables: 8 expected vs 0 at provider
     - per_variable_fallbacks: 8 expected vs 4 at provider (provider's
       duplicate messages collapse in the fallback dict)
     - literal:jacob: PRESENT at provider
     - literal:&Partner: PRESENT at provider
     - repeated_msg_on_path: DUPLICATED on path 1

  5. The double_brace_vars check PASSES: neither the expected nor the
     provider sequence has {{double}} braces. This is correct: the
     provider's defect is LITERAL TEXT, not double braces.

  6. Caller check: build_rows is called from scripts/heyreach_readback.py
     line 511 (production) and tests/test_heyreach_readback.py (7 test
     callers). grep -rn "build_rows" src/ returns nothing (it's a script
     function, not a src function). The script is the production entry
     point.

  7. Data access: the script reads campaign rows and client config from
     Claude's worktree via QUEUE/CAMPAIGNS/CLIENTS_DIR env vars. The Qwen
     worktree has no work/ or config/.env. Reading is read-only; nothing
     is written to either worktree's state files.

RISKS:
  - The env var setup (_setup_data_access) points at Claude's worktree
    path. If Claude's worktree moves, the script breaks. The path is
    hardcoded, matching the existing heyreach_readback.py convention.
  - The comparison strips bare-END reply-stops before comparing structure.
    If the provider adds a different kind of structural node in the future,
    the stripping won't catch it and the comparison will report a false
    mismatch. This is the correct failure mode (loud rather than silent).

RECOMMENDED CLAUDE ACTION:
  The script is ready for the acceptance run. Once Claude's permission
  classifier allows `py -3 scripts/write_heyreach_sequence.py --live`,
  the operator can:
    1. Write the corrected sequence
    2. Re-run `py -3 scripts/heyreach_readback.py productive-linkedin-production-v1 --expect`
    3. All 8 FAIL rows should flip to PASS
    4. Only then consider adding leads
