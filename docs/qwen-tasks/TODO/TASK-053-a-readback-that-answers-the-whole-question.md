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
