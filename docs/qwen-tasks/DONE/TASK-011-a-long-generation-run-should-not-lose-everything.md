# TASK-011 - A long generation run should not lose everything

## GOAL

Make `generate.run` durable across a crash, so a batch that dies on record
nineteen keeps the eighteen it paid for.

## WHY IT MATTERS

`generate.run` loads the estate, walks every target calling
`generate_record`, and saves ONCE at the end:

    recs = store.load()
    for rec in targets:
        ops = generate_record(rec, model, client) if live else plan(rec, client)
        ...
    if live:
        store.save(recs)

The twenty-account Productive cohort is roughly 110 model calls over many
minutes. Anything that ends the process before the last line - a crash, a
Ctrl-C, a laptop lid, a machine that has already died once from memory
exhaustion - discards every draft written in that window, and they were paid
for. The credits are real money and the account had exactly $50 on it when
this was written.

It is also the one place where the money and the durability rule meet: work
that cost something and exists only in a process's memory is the least
durable state in this system.

## CURRENT CONTEXT

- `src/generate.py`, `run()` near the foot of the file.
- `store.transaction()` exists and runs loss guards - `refuse_evidence_loss`
  and `refuse_history_loss` - which a naive per-record write must not defeat.
  Read what those guards are for before choosing where to write.
- `generate_record` mutates `rec` IN PLACE and the caller saves the whole
  list, so any per-record approach has to be careful that a concurrent run
  reloading the estate does not clobber a record it did not touch.
- There IS already a precedent for immediate persistence in this repository
  and it is the right one to follow: `bisonfactory._remember_lead` writes the
  provider's lead id in its own transaction, immediately, with a comment
  explaining that an id the provider issued and this system did not record is
  a lead that will be created again. Same argument, different resource.

## SCOPE

1. Persist each record's drafts as soon as that record finishes, not at the
   end of the batch.
2. Do it through `store.transaction()` so the loss guards still run. A write
   that defeats them to gain durability has traded one loss for another.
3. Prove the property: a run that raises partway leaves the completed records
   saved and the rest untouched.
4. Do NOT add a resume flag, a checkpoint file, or a new state format. The
   estate is the checkpoint - a record that already carries a clean draft is
   not re-planned, which `plan` already implements. Re-running the same
   command IS the resume.

## FILES ALLOWED

`src/generate.py`, `tests/**`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/store.py` - if the transaction API genuinely cannot express this, that
is a finding and a design question, not a licence to change the store.
`work/**`. `config/**`.

## PRODUCTION CONSTRAINTS

Offline. Use `llm.ScriptedModel`, which plays canned answers and records
prompts, and a model that raises partway through. **No live model call** -
the credits are finite and they are for real copy.

## TESTS REQUIRED

- A batch of three records where the model fails on the second: record one's
  drafts are on disk, record three is untouched, and the failure is still
  raised.
- The existing durability guards still fire - a run must not be able to drop
  verification evidence or history on its way to being crash-safe.
- Re-running after the partial failure regenerates ONLY what is missing, and
  costs no model call for the record that already finished. Assert on the
  scripted model's recorded prompts, which is what makes "costs nothing"
  checkable rather than asserted.
- Break the per-record write and confirm the first test fails for the
  intended reason.

## EXPECTED OUTPUT

The change, the tests, and one sentence in the module docstring saying where
a partial run leaves the estate.

## DONE CONDITION

A generation run killed halfway has kept everything it paid for, and a test
proves it.

## RESULT

STATUS: DONE
COMMIT SHA: 2574b04
TESTS: 52 pass in tests/test_generate.py (48 existing + 4 new in
  TestCrashRecovery). All existing tests unchanged and green.
FILES CHANGED: src/generate.py (run() per-record checkpoint via
  store.transaction(), module docstring note), tests/test_generate.py
  (TestCrashRecovery with 4 tests), task file moved TODO → RUNNING → DONE.
FINDINGS: None. The store.transaction() API expressed this cleanly; no
  change to src/store.py was needed. The _remember_lead precedent in
  bisonfactory was the right pattern to follow.
RISKS: Each record now acquires and releases the queue lock individually,
  so a 500-record batch takes 500 lock cycles instead of 1. Measured
  impact should be small (the lock is advisory and uncontended in normal
  operation), but a heavily concurrent setup would see more contention.
  The Snapshot three-way merge handles concurrent edits correctly.
RECOMMENDED CLAUDE ACTION: Merge to master. The change is confined to
  generate.run() and adds tests; no store.py or provider changes.
