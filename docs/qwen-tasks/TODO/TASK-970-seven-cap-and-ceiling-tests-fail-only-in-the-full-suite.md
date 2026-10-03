# TASK-970 — seven cap and ceiling tests fail only inside the full suite

Measured 2026-10-03 on `task-942-token-budget`'s gate run. **These are safety
tests — the daily volume cap and the five-account-a-day ceiling — so a verdict
about them is worth more care than a re-run and a shrug.**

## What was measured

`task-942-token-budget` @ `b82304ab`, full run, 2,099.7s, one `Ran` line, 14,695
results: **238 failing names against the reference's 231. Seven NEW, none
gone.**

    test_no_write_happens_without_every_gate.TheCapCountsDurableRowsNotAPlanDict
        test_a_second_action_the_same_day_is_refused_by_the_cap
        test_one_tenants_actions_do_not_consume_anothers_ceiling
        test_the_ledger_count_is_what_the_cap_reads
    test_the_sixth_account_of_the_day_is_not_opened.TheGateRefusesTheSixthAccount
        test_a_contact_at_an_already_open_account_authorizes_at_the_ceiling
        test_the_ledger_is_the_authority_not_the_callers_plan
        test_the_refusal_carries_the_reason_the_ceiling_gives
        test_the_sixth_account_of_the_day_is_refused

## Four things that were checked before calling it anything

1. **Both modules pass ALONE on the branch** — 32 tests, OK. And they pass
   alone on master too, so the isolated behaviour is identical on both sides.
2. **Master's own full run does not carry these names.** The reference
   (`reference-231-master-cd8e00bc.log`, measured in a neutrally-named tree)
   has 231 names and none of these seven.
3. **The branch's only change to shared test infrastructure is benign.** The
   whole `tests/base.py` diff is one line: `complete()` on a test double gains
   `max_tokens=None`. It cannot reach a cap or a ceiling.
4. **The "new module perturbs the order" hypothesis is NOT confirmed.** The
   branch adds a 693-line test file, which changes discovery order; running
   that module and then the ceiling module in ONE process gives 70 tests, OK.
   So whatever the interaction is, it is not that pair.

## What that leaves

Seven names, from two modules about the same subject — **a durable-row ledger
being the authority for a cap** — that fail only under the full suite, on one
side of a merge. Two readings, and this task exists to settle which:

- **order or state dependence across the whole suite.** Those tests assert
  things like "the ledger count is what the cap reads" and "the ledger is the
  authority, not the caller's plan". If any earlier test in a 14,695-test run
  leaves a durable row where they can see it, the count they read is not the
  count they wrote. That would be a defect IN THEM — a safety test that depends
  on what ran before it is a safety test that can read green for the wrong
  reason — and the branch would merely have perturbed the order.
- **a real effect of this branch** that only manifests at full-suite scale.

The project's recorded remedy for the first reading is ONE re-run, and that is
running. **The outcome decides the task:**

- if the seven vanish → they are order-dependent, and THIS TASK is to make them
  independent (build their own ledger, assert on what they wrote) rather than to
  re-run the suite whenever they appear;
- if the seven recur → the branch does not merge and the cause is in it, and
  this task becomes the hunt for it, starting with what the branch deleted
  (3,008 lines across 46 files).

## Acceptance

```
python -c "import subprocess,sys,os; mods=['tests.test_no_write_happens_without_every_gate','tests.test_the_sixth_account_of_the_day_is_not_opened']; r=subprocess.run([sys.executable,'-m','unittest']+mods,capture_output=True,text=True,encoding='utf-8',errors='replace',env=dict(os.environ,PYTHONIOENCODING='utf-8')); assert r.returncode==0, 'the two modules do not even pass together: '+ (r.stderr or '')[-400:]; print('OK both modules pass together')"
```

```
python -c "import re,sys; log=sys.argv[1] if len(sys.argv)>1 else 'scripts/suite_run.log'; t=open(log,encoding='utf-8',errors='replace').read(); names=[n for n in ('test_the_sixth_account_of_the_day_is_refused','test_the_ledger_count_is_what_the_cap_reads') if re.search(r'^(FAIL|ERROR): '+n, t, re.M)]; assert not names, 'the cap/ceiling names are failing in this full run: '+str(names); print('OK neither cap/ceiling name fails in', log)"
```

### NEGATIVE CONTROL

Command 1 passes today — it is the isolation control, and it is the half that
proves the modules are not simply broken. Command 2 is the one that can fail: it
reads a FULL-SUITE log and refuses if either name appears, so pointing it at
`resonate-ops/logs/942-run1-7new-b82304ab.log` — the run that produced this task
— must FAIL, and pointing it at the master reference must pass. **Run it against
both; a command that only ever sees good logs proves nothing.**

## Files

`tests/test_no_write_happens_without_every_gate.py`,
`tests/test_the_sixth_account_of_the_day_is_not_opened.py`, and whatever shared
state they turn out to read.

## Not in scope

`task-942-token-budget` itself until the re-run decides. The run-1 log is kept
at `resonate-ops/logs/942-run1-7new-b82304ab.log` so the comparison survives the
worktree.
