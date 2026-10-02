# TASK-966 — the operator's exemplars, which this machine cannot reach

Operator's order, 2026-10-02 night:

1. **16 em1 emails from the Resonate campaign of 02-10**, anonymized (recipient
   names and domains replaced), into `prompts/exemplars/em1-operator.md` with an
   anatomy of five blocks;
2. **the Volteum cadence** — 5 steps, days 0 / 3 / 7 / 12 / 18 — into
   `prompts/exemplars/cadence-operator.md`, anonymized, with a table of the role
   each step plays.

The writer sees both in `WRITER_SYSTEM` as examples of **structure, not
content**.

## THIS IS BLOCKED ON CONTENT, AND THE MEASUREMENT SAYS SO

**The 16 em1 bodies are not reachable from this machine.** The EmailBison
adapter's committed endpoints are `/replies`, `/events`, `/campaigns`,
`/campaigns/{id}/sequence-steps`, leads and senders. There is **no endpoint for
the body of a SENT message**, so sixteen individual sends cannot be read. What
can be read is the campaign SEQUENCE — and that is a template, not sixteen
emails.

**Volteum is not in this workspace.** All 40 campaigns were listed and none is
named Volteum; the reader is sound, because the same call printed real campaign
names beside the empty hit. So that cadence lives somewhere this machine cannot
see — another workspace, another tool, or the operator's own notes.

**What IS available, and it is worth knowing before anybody re-asks:** the five
internal Resonate campaigns each carry exactly ONE order-1 step with a body,
read tonight through `bison.sequence_steps` (a read; internal campaigns are a
read-only learning asset by standing rule). Their lengths:

| campaign | em1 words |
|---|---|
| 274 | 261 |
| 327 | 281 |
| 328 | 279 |
| 418 | 246 |
| 352 | 72 |

Those are operator-written em1s and they are **2× the 90–140 contract the same
operator set tonight**, with the fifth below it. If they are the structural
exemplars, the contract and the exemplars disagree by a factor of two — recorded
in TASK-964 as a question for the operator, not resolved here.

## What this task needs to become unblocked

One of:

- **the 16 bodies supplied** — pasted, or dropped into a file whose path is
  named, already anonymized or with permission to anonymize them here;
- **or a provider read for sent messages**, which is a new endpoint in
  `src/providers/bison.py` and its own task, with the usual contract: a trimmed
  dict, never a raw payload;
- **or a decision that the five sequence templates above are the exemplars**, in
  which case the anatomy is derived from five rather than sixteen and this task
  says so in the file.

And for the cadence: the Volteum steps themselves, in any form.

**Nothing is written into `prompts/exemplars/` until the content exists.** A
placeholder exemplar is worse than none: `WRITER_SYSTEM` is read by the model on
every generation, and an invented example of "structure" teaches the structure
of the invention. The two files are therefore NOT created empty and NOT wired
in — that is the whole point of this task sitting in BLOCKED rather than TODO.

## The anatomy, which can be written now and is the only part that can

The five blocks the operator named for em1, kept here so the shape survives even
if the examples take a week:

1. the OFFER — what is being given before anything is asked;
2. the GIVE — the smaller tangible piece that makes block 1 concrete (**this is
   the block that cannot be written until the client answers which Productive
   offer gives before it asks, the equivalent of "a free map of 100 accounts"**);
3. the PROOF — a named client and a number, licensed as an evidence row;
4. the ASK — one question, and it is the CTA;
5. the EXIT — an explicit way to say no.

## Acceptance

```
python -c "import os,sys; p='prompts/exemplars/em1-operator.md'; assert os.path.isfile(p), 'no exemplar file: '+p; t=open(p,encoding='utf-8').read(); import re; blocks=re.findall(r'^#{2,3}\s*\d\.', t, re.M); assert len(blocks)>=5, 'the five-block anatomy is not there: '+str(blocks); n=len(re.findall(r'^---$', t, re.M)); assert n>=16, 'fewer than 16 exemplars separated: '+str(n); print('OK', len(blocks), 'blocks,', n, 'separators')"
```

```
python -c "import os,re,sys; p='prompts/exemplars/em1-operator.md'; t=open(p,encoding='utf-8').read(); bad=re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', t); assert not bad, 'a real address survived anonymisation: '+str(bad[:3]); assert not re.search(r'\b(ltd|limited|gmbh|inc)\b', t, re.I) or 'EXAMPLE' in t.upper(), 'a real company suffix with no anonymisation marker'; print('OK anonymised: no addresses')"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import copyprompts; s=copyprompts.WRITER_SYSTEM if hasattr(copyprompts,'WRITER_SYSTEM') else ''; assert 'structure' in s.lower() and 'not content' in s.lower().replace('  ',' '), 'the writer is shown exemplars without being told they are structure and not content'; print('OK the instruction is explicit')"
```

### NEGATIVE CONTROL

Command 1 fails today with `no exemplar file` and will keep failing until the
content exists — which is the honest state of this task. Its `>=16` check is
what stops it being satisfied by one example and a promise.

Command 2 is the anonymisation gate and it must run BEFORE anything is
committed: these are real emails to real people. Its control is that it fails on
any address-shaped string, and it was written against the measured fact that the
project has twice committed PII into generated artefacts.

Command 3 fails today because the instruction does not exist. It is the one that
keeps "structure, not content" from being a comment in a task file rather than a
line the model actually reads.

## Files

`prompts/exemplars/em1-operator.md`, `prompts/exemplars/cadence-operator.md`,
and the `WRITER_SYSTEM` wiring in `src/copyprompts.py`.

## Not in scope

The role ladder, the lint rules and the contract: TASK-964. The client question
about which offer gives before it asks is recorded in both.
