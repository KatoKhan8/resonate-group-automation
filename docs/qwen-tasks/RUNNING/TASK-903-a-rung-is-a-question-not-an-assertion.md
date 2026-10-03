PRIORITY: P0
SIZE: M
DEPENDS: 

# TASK-903 — rungs ask a question, they do not assert the prospect's situation

**Operator decision, Zvonimir, 2026-09-28. Read this reasoning before coding:**

> The ladder design is wrong, not the research. **No company publishes its
> margin or resourcing**, so rungs that ASSERT the prospect's margin/resource
> situation can never be licensed.

Measured: of 93 accounts with an admitted pack, **0 can license rungs 1 and 3
of Offer A**. 18 packs contain the words; none clears the gate.

## The rule

**The rung TOPIC stays** (rung 1 margin visibility; rung 3 resource decisions
that move margin). **The COPY expresses it as a question to the prospect, or as
what Productive does — never as a statement about the prospect's situation.**

    RIGHT  "How do you see a project's margin before it closes?"
    RIGHT  "Productive shows margin while the work is still running."
    WRONG  "Your margin is invisible until the project closes."

**A question or a Productive-capability statement needs no prospect evidence.
An assertion about the prospect still does.**

## Scope
1. Implement in the **generator prompts** and the **step objectives**.
2. **`sequencegate` must still check the rung TOPIC is covered** — the ladder
   keeps all its power; only the permitted grammatical form changes.
3. **The claims gate must still refuse any assertion about the prospect without
   licensed evidence.** Do not relax it to make rungs pass.
4. **Check Offer B's rungs for the same flaw and apply the same rule.**

## Acceptance
1. For Offer A rungs 1 and 3 and every Offer B rung with the same shape: a
   question form and a capability form both **pass** the claims gate with a
   pack containing no margin/resource fact.
2. **NEGATIVE CONTROL:** the assertion form of the same rung is still
   **REFUSED** on that pack. The corridor must close for assertions and only
   for assertions.
3. **`sequencegate` still refuses a step that does not pursue its rung's
   topic** — prove with a step that covers the wrong rung.
4. Mutation: revert one rung's objective to its assertion form; control 2 must
   go red.

## Files
`config/clients/productive-offers.yaml` (step objectives) and
**`src/copystages.py`** (prompt text). **Do NOT touch `src/generate.py`** —
TASK-901 owns it. If you believe you must, stop and say so.

## RULES THAT OUTRANK FINISHING — every brief here

- **NEVER WIDEN A GATE TO MAKE A DRAFT PASS.** If a gate refuses correct copy,
  fix what it CONSULTS, never what it PERMITS.
- **A test count is never a PASS.** Name the real path exercised, the negative
  control, and the killed mutation.
- **EVERY new check needs a NEGATIVE control** — an input that must be REFUSED
  — and a **NEAR-MISS** control, not only an obvious one. The B1 defect below
  exists precisely because every control used a pack containing the literal
  word.
- **MUTATION CHECK IS MANDATORY.** Break your own fix in source, prove the
  intended test goes red for the intended reason, confirm no other guard fired
  first, restore the source and verify **byte-identical by sha256**.
  These files are **CRLF**: a `\n`-anchored regex matches zero times and your
  mutation becomes a silent no-op that looks like a surviving test.
- **PROVIDER WRITES = 0.** `sending.live` is false, the freeze stands, nothing
  is sent to anybody.
- Production `work/` is READ-ONLY. Verify `work/queue.jsonl` and
  `work/campaigns.jsonl` unchanged **by sha256 from a fresh process** — mtime
  is the wrong instrument, 23 loops write that checkout.
- **Write suite logs OUTSIDE the repository.** A log inside the tree became
  part of `test_fixture_hygiene`'s corpus and nearly committed real prospect
  domains. And interrupting a suite leaves one temp dir per test — 94,867 of
  them broke every later run. **A suite with no `Ran N tests` line is an
  absent measurement, not a failure**: sweep `%TEMP%` and re-run.
- Suite baseline is `docs/state/SUITE-BASELINE-2026-09-26.txt`, 128 named
  failures, compared **AS SETS, NEVER COUNTS**. It is known stale on master
  (TASK-549): four of its entries fail on master with no branch at all.
- Commit and push to your own branch; **verify the remote with `git rev-parse`**.
  Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** (VERIFIED / UNPROVEN /
  UNKNOWN) and your exact branch head SHA. GLM verifies against that SHA.
