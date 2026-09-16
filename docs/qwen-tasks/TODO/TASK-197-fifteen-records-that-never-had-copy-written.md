PRIORITY: P0
DEPENDS:

# TASK-197 - fifteen verified records nobody ever generated copy for

## WHERE THIS SITS

TASK-194 sorted the 41 records that are verified but not campaign-ready, and
the first bucket is the cheapest work in the whole system:

    15   no cadence at all - generation never ran
    23   cadence generated, ZERO approvals
     3   partial approvals with lint or claim failures

    step refusals:  289 draft_not_approved,  3 unsupported_claim,
                     3 awaiting_dependency,  2 lint_failed,  2 approval_stale
    permanent blocks: ZERO

These 15 records are verified. The person credits are spent, the addresses are
confirmed, and the reason they are not campaign-ready is that nobody ran the
generator on them. Items 2 and 3 in TASK-194's priority list need a human to
approve copy; this one does not need anything but a run.

Generation costs model tokens and nothing else. `--spend` with the generate
stage refuses unless a model is configured, and the main worktree has
`LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` set. Every worktree now has the
same credential file.

## THE QUESTION

1. **Name the 15**, hashed, and confirm each one is genuinely verified with a
   confirmed address and genuinely has no cadence. Two different things could
   look like "no cadence": generation never ran, or generation ran and produced
   nothing. Distinguish them before you run anything, because the second is a
   defect and re-running it will just fail again.
2. **Run generation on those 15 and only those 15.** Use `--id` if the runner
   takes it - TASK-181 established that `--limit` bounds the scan window rather
   than the work, so it is the wrong tool for "exactly these fifteen".
3. **Report what came out, per record and per step**: generated, and then the
   lint verdict and the claims verdict. TASK-167 found the email CONTROL passes
   both for all 17 of its contacts; generated copy has a worse record than
   that in this repository, and the two gates are what catch it.
4. **Then state what each record needs next.** A record whose steps generate
   and pass both gates needs approval, which is a human. A record whose steps
   fail claims needs different evidence. A record whose steps fail lint needs
   regeneration. Sort them.
5. **Measure the token cost** and project it across the 23 unapproved and the
   3 partial records, so the operator knows what finishing the whole Gap-3 set
   would cost in model spend.

## THE TRAP

Generation is the stage this repository has burned most often. `pushable` was
retired as a promotion criterion because copy that passed every automated gate
still failed a human read, and the operator's hand-written fallbacks beat
everything the model produced on both channels
(`docs/LEADS-ARE-BLOCKED-2026-09-14.md`). So generating copy for 15 records is
progress ONLY if the copy is honest, and the honest measure is the claims gate
against that record's own evidence, not the fact that text appeared.

**Do not set `approval.by` on anything.** 289 steps are held by
`draft_not_approved` and that number is not a backlog to clear - it is a human
reading that has not happened. Bulk-approving to raise a count is named in the
checkpoint as the most damaging action available here.

Second trap: do not regenerate the 23 records that already have cadence. They
are waiting on approval, not on copy, and regenerating resets what a human
would be approving and makes any stale approval staler.

## WHAT YOU MAY NOT DO

- No provider writes. No staging, no campaign, no leads, no sends.
- Do not set, clear or default `approval.by` for any step or record.
- Do not run generation on any record outside the 15.
- Do not touch the 23 with existing cadence or the 3 partials.
- Do not widen a lint rule or relax the claims gate to make a draft pass.
  Regenerate, or report the refusal.
- Never commit copy text containing a real company name, contact name, domain
  or email. Hash identifiers; if you quote generated copy, redact it.

## FILES ALLOWED

    docs/FIFTEEN-GENERATED-2026-09-16.md   (new)
    scripts/task197_*.py
    work/   (generation writes drafts onto the records - that is the task;
             check for another live writer first and say what you found)

## FILES FORBIDDEN

    src/   config/

## DELIVERABLE

The 15 named and confirmed, the never-ran versus produced-nothing split, the
generation run over exactly those records, per-record per-step lint and claims
verdicts, what each record needs next, and the measured token cost with its
projection across the remaining 26.
