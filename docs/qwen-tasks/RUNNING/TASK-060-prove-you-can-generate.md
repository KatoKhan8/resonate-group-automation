# TASK-060 - Credential verification: prove YOU can generate

## WHY THIS TASK EXISTS

Until 2026-09-14 the Qwen worktrees had no `config/.env`, so the configured
model was unreachable and `py -3 -m src.generate --live` could not run here.
Credentials have now been placed in every worktree. **Nobody has verified
that a Qwen worker can actually use them.**

This task is the verification. It is deliberately small and touches no real
prospect.

## WHAT TO DO

1. Confirm the credentials are visible to the code, WITHOUT PRINTING ANY
   VALUE. `src.providers.load_env` and `key()` are the accessors. Report
   only names and AVAILABLE/MISSING.

2. Copy `work/queue.jsonl` to a scratch path OUTSIDE the repository and
   point the `QUEUE` environment variable at the copy. Never point `QUEUE`
   at the real file.

3. Pick ONE record in the scratch copy. Clear its stored cadence steps.

4. Run `py -3 -m src.generate --live --id <that record>`. This spends real
   model credits and is the point of the exercise.

5. Read what came back. For each generated step report:
       step key, word count, whether it names Productive,
       whether any gate refused it and which
   `store.log` entries carry the refusal reasons under `rejected`.

6. Run the quality gates against the result yourself:
   `lint.check_step`, `claims.check`, `claims.foreign_product`,
   and `generate._note_quality`.

7. Run `py -3 -m unittest tests.test_linkedin_note tests.test_generate`
   and report the real exit code. Never pipe a test run into a filter and
   read the filter's status.

8. Commit the REPORT to your branch. Do NOT commit the scratch queue, any
   generated prospect copy, or anything containing a real person's name.

## WHAT MUST BE IN THE RESULT BLOCK

    QWEN_MODEL_ACCESS      PASS or FAIL
    QWEN_PROVIDER_CONFIG   PASS or FAIL   (names only, never values)
    QWEN_TASK_EXECUTION    PASS or FAIL
    model calls spent
    steps generated / steps refused, with the refusal reasons

If any of the three is FAIL, say exactly what failed and stop. A FAIL
reported honestly is the correct outcome of a verification; a PASS that was
not earned is worse than useless.

## ABSOLUTE PROHIBITIONS

- **No provider WRITE. No send. No campaign mutation.** You now hold real
  EmailBison and HeyReach keys. Reads are permitted for this task only
  insofar as generation needs them; writes are not, ever.
- Do not contact a real prospect.
- Do not print a credential value anywhere: not in a commit, not in a task
  file, not in terminal output, not in a test name.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION.
