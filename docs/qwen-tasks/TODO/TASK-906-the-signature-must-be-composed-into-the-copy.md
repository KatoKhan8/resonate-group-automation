PRIORITY: P1
SIZE: M
DEPENDS: TASK-905

# TASK-906 — compose the signature into the rendered mail and the projection

**Operator decision "A", Zvonimir, 2026-09-28.** Start only after TASK-560 has
landed — it touches the same rendering path.

## The state, measured
Signatures now EXIST on all 222 productive inboxes — the operator added them.
**That did not unblock criterion 2**, because:

    `email_signature` appears exactly ONCE in all of src/ - inside a docstring
    `src/sendersignature.py` has ZERO production callers
    0 of 99 queued messages carry their mailbox's signature - including all
      37 already sent, so the provider does not append one either

Chain status: owner 159/225 pass, identity 145, **signature present 145**,
**rendered 0 of 225**, **projection 0 of 225**.

## The rule
**We compose the signature into our rendered copy and the EmailBison
projection, read from the canonical per-mailbox source**, so it is visible and
verifiable **before** anything is sent. No provider signature configuration;
no provider writes.

**Content for the canary, exactly:** two lines — the mailbox owner's full name,
then `Productive`. **No title, no phone, no link.** The single-link rule stands:
the only link permitted anywhere is `https://productive.io/get-started/`.

## Acceptance
1. Chain proven per sender: **owner → identity → signature → rendered email →
   projection**, all five links.
2. **If the provider ever appends its own signature, our check must detect the
   duplicate and BLOCK.** Negative control: a body already carrying the
   signature block is refused, not double-signed.
3. **Negative controls (all must FAIL):** wrong pairing; missing; empty;
   another Productive sender's signature; present in the rendered copy but
   absent from the projection.
4. **Un-skip `TASK-341`'s three signature tests, or replace them with tests
   that actually run.** They are currently skipped and have never executed.
5. Criterion 2 passes **only** when all five links are proven. Otherwise report
   BLOCKED naming the failed link.
6. Mutation: break the sender→signature mapping; the verifier must catch it.

## Files
The signature / sender-identity modules, `src/sendersignature.py`, the
rendering path shared with TASK-560, plus your own tests. **The rendering path is serialised 553 -> 555 -> 556 -> 554. Do not start until TASK-905 has landed.**

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
