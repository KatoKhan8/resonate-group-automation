# QA Lead Pack Check — 2026-09-25

**TASK-294.** The researched set and the rendered set are disjoint.

## What this check answers

**Does every lead in a batch carry at least one research fact that is
provably about THAT company, with a source, a date and a snippet — and does
the copy's first line actually use one?**

This is the check that decides whether a personalised email is personalised
or merely shaped like it.

## The four rules

| Rule | What it checks |
|------|---------------|
| `pack_present` | At least one **admitted** fact for this lead's account |
| `fact_has_source_date_snippet` | Each admitted fact carries all THREE: source URL, date, snippet |
| `opener_uses_a_pack_fact` | The first line of step 1 references a fact in the pack |
| `no_claim_outside_the_pack` | No company claim in any step traces to nothing |

And one report that is not a rule but is the reason the task exists:

| Report | What it shows |
|--------|--------------|
| `identity` | Per lead: admitted / refused / unverifiable counts, separately, never summed |

## Identity, not presence

`src.packfacts.identity_of` is the one test. Three answers:

- **admitted** — the fact says whose it is and it is this account's
- **refused** — the fact says whose it is and it is somebody else's
- **unverifiable** — the fact does not say, so the question was never asked

**`unverifiable` is NOT a pass.** A fact that does not say whose it is has
not been shown to be this account's. "We could not ask" and "we asked and
the answer was no" are different problems with different fixes, and folding
them together reports the second as the first.

### The 50-of-71 precedent

50 of 71 job rows in the research pilot belonged to a DIFFERENT company,
because `companyName` is a text filter and not an identity match. On five
of eight accounts that returned rows, every row was somebody else's. A
presence check — "this account has research" — called those accounts
covered. `identity_of` refuses them.

## The join

The check joins rendered rows to queue records by **email address**. Lane D
measured 291 of 927 rendered rows matching no queue record at all (31%). A
join that matches everything is a join that is not asking.

The three sets the check reports:

1. **admitted** — carries at least one admitted pack fact
2. **only_unverifiable_or_refused** — matched a record but no admitted fact
3. **no_record** — matched no queue record at all

These three sets must add to the rendered row count.

## The result shape

Conforms to the QA suite contract (`docs/QA-LANE-F-CONTRACT-2026-09-25.md`):

```json
{
  "check": "lead_pack",
  "phase": "pre_push",
  "verdict": "PASS | FAIL | VACUOUS | ERROR",
  "subjects": 128,
  "clean": 121,
  "rules": {
    "pack_present": "...",
    "fact_has_source_date_snippet": "...",
    "opener_uses_a_pack_fact": "...",
    "no_claim_outside_the_pack": "..."
  },
  "counts": { ... },
  "offenders": { ... },
  "unverifiable": { ... },
  "identity_totals": {"admitted": N, "refused": N, "unverifiable": N},
  "per_lead_identity": [{"lead": "...", "domain": "...", "admitted": N, ...}],
  "source_date_snippet": {"missing_source": N, "missing_date": N, "missing_snippet": N},
  "three_sets": {"admitted": [...], "only_unverifiable_or_refused": [...], "no_record": [...]},
  "join": {"key": "email", "matched": N, "unmatched": N},
  "evidence": {"files_read": [{"path": "...", "mtime": "...", "rows": N}]},
  "vacuum_reason": "..."
}
```

Arithmetic: `clean + |union(offenders)| == subjects`.

`subjects == 0` → `VACUOUS`, exit 2, with `vacuum_reason` stated.

## How to run

```bash
py -3 scripts/qa/check_lead_pack.py \
    --phase pre_push \
    --batch batch-2-2026-09-25 \
    --workspaces <path-to-work-copy> \
    --json work/qa/<run>/lead_pack.json
```

## What this check does NOT do

- **No provider write.** No Apify call. No EmailBison call. No HeyReach call.
- **No identity reimplementation.** `identity_of` is imported from
  `src.packfacts`. Two copies would disagree.
- **No editing of lane D's files.** `src/packfacts.py`, `scripts/packfact_check.py`,
  `src/copylint.py` are read-only. Defects go in FINDINGS as proposed tasks.
- **No reporting lane D's 93% as coverage on the 128.** That is across all
  394 researched records. Different denominator, different question.

## Constructed failures demonstrated

| Rule | Constructed failure | Message |
|------|-------------------|---------|
| `pack_present` | Lead with no research | lead in `offenders["pack_present"]` |
| `fact_has_source_date_snippet` | Fact with `source_url` deleted after identity admitted it | lead in offenders, `missing_source: 1` |
| `fact_has_source_date_snippet` | Fact with empty `published_at` | lead in offenders, `missing_date: 1` |
| `opener_uses_a_pack_fact` | Generic opener "I wanted to reach out about your growth." | lead in offenders |
| `no_claim_outside_the_pack` | "You raised $50M in Series C funding." not in pack | lead in offenders |
| 50-of-71 shape | Fact with `companyWebsite: "https://acme-solutions.com"` for domain `acme.com` | `identity_of` → REFUSED; lead in `pack_present` offenders |
| `subjects == 0` | No rendered row matches a queue record | verdict VACUOUS, `vacuum_reason` stated |

## Production run evidence owed

This worktree has no `work/queue.jsonl` or `work/stage/s7-copy.jsonl`.
The production run against the 128 requires:

1. A named copy of production's `work/` directory
2. Running `py -3 scripts/qa/check_lead_pack.py --workspaces <copy>` from
   Claude's worktree
3. Pasting the output into the result block

The negative control (`--audit-pack-cache`) requires the quarantined
pre-fix pilot cache, which is also not present in this worktree.

## Tests

30 tests in `tests/test_a_pack_fact_must_belong_to_this_company.py`:

- `IdentityOfTests` (5) — the one test, three answers
- `PackForTests` (3) — pack assembly
- `TheFiftyOfSeventyOneShape` (2) — the constructed identity failure
- `PackPresentRule` (3) — rule 1 both ways
- `FactHasSourceDateSnippet` (3) — rule 2, each missing element
- `OpenerUsesAPackFact` (3) — rule 3 both ways
- `NoClaimOutsideThePack` (2) — rule 4 both ways
- `IdentityColumnsReportedSeparately` (2) — verdicts never summed
- `ThreeSetsAddToRendered` (1) — partition arithmetic
- `SubjectsZeroIsVacuous` (2) — exit 2 with reason
- `ArithmeticCloses` (1) — clean + offending == subjects
- `JoinKeyReported` (1) — key and counts both directions
- `RulesKeysConsistent` (1) — every key in counts exists in rules
- `NoProviderCalls` (1) — no provider import in source
