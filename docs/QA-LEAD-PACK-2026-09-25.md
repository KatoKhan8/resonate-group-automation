# QA Lead-Pack Check — `scripts/qa/check_lead_pack.py`

**TASK-294.** Lane F, the standing QA suite. Pre-push, subject: lead.

**Operator specification:** `docs/QA-LANE-F-CONTRACT-2026-09-25.md` §1, §9,
§10.

---

## The question this answers

Does every lead in this batch carry at least one research fact that is
provably about THAT company, with a source, a date and a snippet — and does
the copy's first line actually use one?

This is the check that decides whether a personalised email is personalised
or merely shaped like it.

---

## The defect this exists for

Measured 2026-09-24 (lane D): 50 of 71 job rows in the research pilot
belonged to a DIFFERENT company, because `companyName` is a text filter and
not an identity match. On five of the eight accounts that returned rows,
**every** row was somebody else's. A presence check — "this account has
research" — called those accounts covered.

The rendered set and the researched set were **disjoint**: 636 of 927
rendered rows matched a queue record, and ZERO carried a pack fact. 291
rendered rows (31%) matched no queue record at all.

---

## Four rules

| Rule | What it checks |
|------|----------------|
| `pack_present` | At least one admitted fact for this lead's account |
| `fact_has_source_date_snippet` | Each admitted fact carries all THREE: a snippet, a source URL, and a date |
| `opener_uses_a_pack_fact` | The first line of step 1 references a fact in the pack |
| `no_claim_outside_the_pack` | No company claim in any step traces to nothing |

`copylint.first_line` and `copylint.pack_text` answer the opener rule.
`copylint.untraceable` and `copylint.specifics_in` answer the traceability
rule. Both are imported, not reimplemented.

---

## One identity report (not a rule)

Per lead: **admitted / refused / unverifiable** counts, reported separately
and **never summed into "covered"**.

- `admitted` — the fact says whose it is and it is this account's
- `refused` — the fact says whose it is and it is somebody else's
- `unverifiable` — the fact does not say, so the question was never asked

**`unverifiable` is NOT a pass.** "We could not ask" and "we asked and the
answer was no" are different problems with different fixes, and folding them
together reports the second as the first.

---

## The three sets

Every lead is reported in exactly one of three sets, and the three sets must
add to the subject count:

1. **admitted** — carries at least one admitted pack fact
2. **only_unverifiable_or_refused** — carries research, but none admitted
3. **no_record** — matches no queue record at all

Lane D measured 31% in the last of those across the rendered rows. A join
that matches everything is a join that is not asking.

---

## The join key

Rendered rows are joined to queue records by **email address**: the
`email` field on the rendered row, matched against the `contacts[].email`
field on queue records. This is the same key the send path uses.

---

## The negative control

`--audit-pack-cache <path>` runs the identity test over a research-pack
cache. Against the quarantined pre-fix pilot cache
(`work/researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json`) it finds the 50
job rows of 71 that were a different company.

This is how a check that cannot fire is told apart from one that has nothing
to fire on. The function delegates to `scripts.packfact_check.audit_pack_cache`
— the same module lane D built — because two copies of an identity test is
how the two come to disagree about who a fact belongs to.

---

## Usage

```
py -3 scripts/qa/check_lead_pack.py \
    --phase pre_push \
    --workspaces <path to work/ copy> \
    --json work/qa/<run>/lead_pack.json
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | PASS — every subject checked, every rule clear |
| 1 | FAIL — at least one subject offends at least one rule |
| 2 | UNCONFIRMED — the check ran and could not establish the answer (including `subjects == 0`) |
| 3 | ERROR — the check could not run |

---

## What this does NOT do

- **It does not understand claims.** A sentence that is wrong in a way
  carrying no specific ("you must be struggling with scale") passes the
  traceability check and is a judgement call for a person.
- **It does not buy anything.** No Apify call, no provider write. It reads
  what the estate already holds.
- **It does not duplicate `identity_of`.** The send path and this check ask
  the same module (`src/packfacts.identity_of`), and two copies of an
  identity test is how the two come to disagree.

---

## Boundaries

- **READ ONLY.** No provider write, no Apify spend.
- **Does not edit** `src/packfacts.py`, `scripts/packfact_check.py`,
  `src/copylint.py`. Lane D owns them. Defects go in FINDINGS.
- **No prospect PII** in committed output. Email addresses are hashed.

---

## The acceptance bar

- The 128 are reported BY NAME, in three sets that must add to 128.
- `refused` and `unverifiable` appear as separate columns everywhere.
- `--audit-pack-cache` against the quarantined cache finds the 50-of-71.
- Source, date and snippet are asserted individually, with a count per
  missing element.
- `subjects == 0` exits 2 with a stated reason.
- One constructed failure per rule, shown firing.

---

## Files

| File | Purpose |
|------|---------|
| `scripts/qa/check_lead_pack.py` | The check script |
| `tests/test_a_pack_fact_must_belong_to_this_company.py` | 25 tests, all passing |
| `scripts/qa/__init__.py` | Registry entry for `lead_pack` |
