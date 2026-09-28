PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-553 — the P.S. must reach the rendered email and the projection

**Operator decision, Zvonimir, 2026-09-28: rendering the P.S. in the email a
person receives is a CANARY REQUIREMENT.**

## The state, retracted and confirmed

P0-B first reported the P.S. renders. **It retracted that**, and an independent
review confirmed the retraction and found it **understated**:

    src/bisonfactory.py    contains ZERO `ps` references
    src/render.py          reads `subject` / `body` only
    approval.fingerprint   does NOT cover `ps` - identical fingerprint with
                           and without it
    _certified_copy        its `forbidden` set omits `ps`

So the P.S. reaches the stored step and **no prospect-facing surface, no
operator-facing surface, and no client export.** Gating is fixed; rendering
does not exist.

**The fingerprint gap is the dangerous one: approved copy and the same copy
with a different P.S. hash identically, so an approval does not cover it.**

## Acceptance — proven END TO END, not per-function
1. The P.S. appears in the **rendered email body** a person would receive.
2. The P.S. appears in the **EmailBison projection** — the payload the provider
   is actually handed.
3. **`approval.fingerprint` changes when the P.S. changes.** Negative control:
   two drafts differing only in the P.S. must produce **different** fingerprints.
4. `_certified_copy`'s `forbidden` set covers `ps`.
5. **A required P.S. that is missing BLOCKS** — it must never vanish silently.
   Negative control: a step with no P.S. is refused, naming the step.
6. Mutation: drop the P.S. from the projection; acceptance 2 must go red.

## Files
`src/bisonfactory.py`, `src/render.py`, `src/sequenceplan.py`, `src/approve.py`
as needed, plus your own tests. **Do NOT touch `src/generate.py`** (TASK-550)
or `src/claims.py` (TASK-551).

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
