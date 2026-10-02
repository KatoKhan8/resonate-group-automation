# TASK-959 — the merge gate cannot read a branch bigger than its prompt budget

## Why

Every merge needs a GLM verdict, and NEEDS_CLAUDE does not pass. Measured on
2026-10-02, on TASK-940's own branch:

- `glm.complete` accepts a prompt up to `MAX_PROMPT_CHARS` = **60,000**
  characters and refuses above it rather than truncating — deliberately, because
  a silently shortened prompt produces a confident answer to a question nobody
  asked.
- Every attempt is clamped to `GLM_TIMEOUT` = **180 s**:
  `timeout=min(int(timeout or GLM_TIMEOUT), GLM_TIMEOUT)` at
  `src/providers/glm.py:320`. So `scripts/glm_verify_branch.py --timeout 600` is
  **inert**: the flag cannot raise the ceiling it names. One 57,445-character
  call died with `GlmTimeout`; the identical call on retry answered in time, so
  180 s is **marginal** at that size, not a law about it.
- Independently of the timeout, the verifier's own budget leaves part of a large
  patch unseen and says so: **30,596 of 79,833 characters** on that branch,
  including the tail of `main()`. Its banner then tells the reviewer, correctly,
  that NEEDS_CLAUDE is the right answer if the unseen part could matter.

So a branch can be correct, carry its own tests, pass its acceptance, show zero
new failing names against the reference — and still be unmergeable, because the
gate cannot see it. **Most of the current queue is that size**:
`task-one-os-authority` is 5,032 insertions across 21 files,
`task-942-token-budget` 1,266 across 28, `task-word-contract-enforced` 1,118
across 13.

Two bounds for one question is the defect this repository already names in
`lint` vs the writer contract, and in the suite lock's `--lock-wait` that
carried its own copy of a timeout.

## The measurement this task starts with

**What prompt size does a 180 s attempt actually answer?** Nobody knows; two
data points exist (24,984 chars → 37 s; 57,445 chars → timed out once, answered
once). Measure it: three or more sizes, real calls, latency recorded, with the
model and `max_tokens` held fixed, and write it to
`docs/GLM-PROMPT-BUDGET-2026-10-03.md` as a table of size against seconds.

Then, and only then, the two bounds can be made to agree — by deriving the
accepted prompt size from what the ceiling can answer, or by raising the ceiling
to what the accepted size needs. Either way **one of the two numbers must be
derived from the other**, never written twice.

## The part that is NOT this task's to decide

Even with the bounds reconciled, a 200,000-character patch does not fit. The
remedy is a design change — review a branch in SEVERAL calls (per file, or code
then prose) and combine the verdicts, with a rule for what a split verdict
means. **That is an operator decision, because it changes what a PASS means**,
and it is written up for them rather than implemented here. Until it is taken,
a large branch's gate is: suite name-set diff clean, acceptance executed, and
Claude review recorded — with the GLM verdict recorded as NEEDS_CLAUDE and the
reason named as the gate's limit rather than the branch's fault.

## Acceptance

```
python -c "import os,re,sys; p='docs/GLM-PROMPT-BUDGET-2026-10-03.md'; assert os.path.isfile(p), 'no measurement document: '+p; t=open(p,encoding='utf-8').read(); rows=re.findall(r'^\|\s*([0-9][0-9,]{3,})\s*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|', t, re.M); assert len(rows)>=3, 'fewer than three measured sizes: '+repr(rows); sizes=sorted(int(r[0].replace(',','')) for r in rows); assert sizes[-1]>=40000, 'the largest size measured is '+str(sizes[-1])+', which does not reach the sizes that actually time out'; print('OK',len(rows),'sizes measured, largest',sizes[-1])"
```

```
python -c "import sys,os,tempfile; sys.path.insert(0,'.'); os.environ['SPEND_LEDGER']=os.path.join(tempfile.mkdtemp(),'l.jsonl'); from src.providers import glm; seen=[]; glm.request=lambda m,u,h,b,t: (seen.append(t), (200, {'choices':[{'message':{'content':'ok'}}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}))[1]; glm.complete('probe', timeout=600, ledger_client='TASK-959'); assert seen==[600], 'the requested timeout was clamped to '+str(seen); print('OK the requested timeout reaches the transport:', seen[0])"
```

### NEGATIVE CONTROL

Both commands fail TODAY, which is the point. Measured before being written
down, both of them:

- command 1 → `AssertionError: no measurement document:
  docs/GLM-PROMPT-BUDGET-2026-10-03.md`;
- command 2 → `AssertionError: the requested timeout was clamped to [180]`.

Command 2 asserts the EFFECT and makes no paid call: it replaces the transport
seam (`glm.request`) with a stub that records the timeout it is handed and
returns a minimal valid response, so the clamp is observed rather than read out
of the source. **An earlier version of this command read the source text and
PASSED today, which is how it was caught** — the needle contained a space and
the haystack had had its spaces stripped, so it could never match. A validator
that agrees with you is worse than none.

Two conditions on running it: `SPEND_LEDGER` is pointed at a temporary file in
the command itself, so the probe cannot write a row into the production ledger;
and it must run where `config/.env` resolves, because `_send` calls `headers()`
before the stub is reached — from a worktree the same command dies with
`MissingKey: no ZAI_API_KEY in config/.env`, which is TASK-960's trap, not this
one's finding.

Command 1 can also fail after the work: if somebody writes the document with
two sizes, or stops measuring below 40,000 — the size region where the timeout
actually bites.

## Files

`src/providers/glm.py` (the two bounds), `scripts/glm_verify_branch.py` (the
flag's default must be READ from the adapter, never copied — the suite lock's
`--lock-wait` already carries that lesson), and the new measurement document.

## Not in scope

The multi-call review design. The spend ledger (TASK-960). Any change to what a
PASS means.
