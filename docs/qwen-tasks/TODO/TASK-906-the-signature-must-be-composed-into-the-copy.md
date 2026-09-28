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

### ACCEPTANCE COMMANDS — run these exactly and paste the real output

**These must stay in THIS section.** GLM's extractor enters at the first
`## Acceptance` heading and stops at the next `## `, so commands in a later
section are invisible — that cost three `NEEDS_CLAUDE` verdicts on
TASK-560/907. Only lines beginning `py -3`, `python`, `grep` or `scripts/` are
picked up.

    py -3 -m unittest tests.test_render_preview
    py -3 -m unittest tests.test_task560_ps_reaches_the_person
    py -3 -m unittest tests.test_task907_ps_producer_hop
    py -3 -m unittest tests.test_task904_opt_out
    py -3 -m unittest tests.test_the_research_pack_has_one_shape
    py -3 -m unittest tests.test_approve
    py -3 -m unittest tests.test_generate
    py -3 scripts/runtime_approval_hash_probe.py --mode project

All must be green; `tests.test_render_preview` must be **29 tests, 0
failures**.

### THE BYTE-IDENTICAL ASSERTION — this is the one that matters

Per the CONSTRAINT section at the end of this file, **consolidate the two
existing `_append_ps` copies into one shared appender before adding a third**,
then compose the signature through that single path. Then prove the two
surfaces cannot drift, pasting output:

    py -3 -c "import sys; from scripts.render_preview import _fixture_rec_email as F, _fixture_config_email as C, _build_email_plan as B; from src import optout as O; p=B(C(),[F()]); bad=[(i,v['name'],v['value'].count(O.OPT_OUT_LINE)) for i,L in enumerate(p['leads']) for v in L['variables'] if v['name'].startswith('body_') and v['value'].count(O.OPT_OUT_LINE)!=1]; sys.exit('WRONG opt-out count: %r' % (bad,)) if bad else print('OK: exactly one opt-out line in every body on every lead')"
    py -3 -c "import sys; from scripts.render_preview import _fixture_rec_email as F, _fixture_config_email as C, _build_email_plan as B; p=B(C(),[F()]); b=[v['value'] for v in p['leads'][0]['variables'] if v['name']=='body_1']; sys.exit('em1 P.S. count=%r' % [x.count('P.S.') for x in b]) if [x for x in b if x.count('P.S.')!=1] else print('OK: em1 carries exactly one P.S.')"

**Both RUN BY CLAUDE on master and proven in both directions** — they exit 0 as
written and exit 1 when the required count is changed. **Read the exit code off
the process, never through a pipe**: `| tail` masks it and reports 0 for a
failing command.

**They count rather than using `in`, and that matters here more than anywhere.**
GLM found the printing version weak: `line in body` is true for one occurrence
**or three**, so it blessed the duplicate state TASK-904 refuses. **You are
adding a third piece of trailing content to the same bodies** — if your
signature composition double-appends the P.S. or the opt-out, an `in` check
would call it green. Add the same exactly-once assertion for the signature.

The P.S. (TASK-560/907) and the opt-out (TASK-904) are already on master, and
adding a signature must drop neither and duplicate neither.

**The real acceptance is a test you write asserting the rendered body and the
EmailBison projection are BYTE-IDENTICAL for the same step, with P.S., opt-out
and signature all present.** Not "both contain the signature" — identical.
`assertEqual` on the two strings.

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

---

# CONSTRAINT ADDED — 2026-09-28, Claude (merge authority)

**There must be exactly ONE appender for prospect-facing trailing content. Do
not add a third.**

TASK-560 shipped `_append_ps` **twice** — `src/bisonfactory.py:1639` and
`src/render.py:61` — with byte-identical logic. That was allowed through
because the two copies do not diverge today, but **you append a signature to
those same two surfaces**, and a third and fourth copy would let "the body a
person receives" and "the body in the projection" drift apart — the exact
invariant this whole chain exists to guarantee.

**Before adding an appender, consolidate the two that exist into one shared
function and call it from both surfaces.** That consolidation is explicitly in
scope for this task and is not scope creep. Then compose the signature through
the same single path.

**Acceptance addition:** a test that asserts the rendered body and the
EmailBison projection are **byte-identical** for the same step, with P.S. and
signature both present. Not "both contain the signature" — identical.
