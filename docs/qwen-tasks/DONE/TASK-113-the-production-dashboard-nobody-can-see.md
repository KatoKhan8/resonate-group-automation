PRIORITY: P4
DEPENDS: 

# TASK-113 - one place that says what production is doing

## THE POLICY

`docs/PRODUCTION-SCALE-POLICY.md` and the durable-state policy in `CLAUDE.md`:
a fresh session on a different computer must be able to read the repository
and say what happened and what to do next.

Several pieces exist already and are generated rather than hand-written:

    docs/state/LEDGER.json            tasks, branches, worktrees
    docs/state/QUEUE-MANIFEST.json    sanitised queue shape
    docs/state/PROVIDER-CAMPAIGNS.json  HeyReach campaign truth
    docs/state/SENDER-CAPACITY.json   sender estate
    docs/state/CHECKPOINT-latest.md   the human-readable checkpoint

**They do not yet answer the production questions in one place.**

## WHAT TO BUILD

A generated `docs/state/PRODUCTION-DASHBOARD.json` plus a readable
`docs/state/PRODUCTION-DASHBOARD.md`, answering:

    LEADS        total qualified, unassigned qualified, by signal, by cohort,
                 by campaign, live, queued
    HEYREACH     campaigns, live, draft, senders, utilisation, throughput
    EMAILBISON   campaigns, live, senders, throughput
    EXPERIMENTS  running, completed, winner candidate, inconclusive, failed
    LEARNING     new findings, confidence, sample size, and whether each has
                 been promoted into generation policy

## THE RULE THAT DECIDES WHETHER THIS IS ANY GOOD

**Existence is not function.** The recurring defect in this repository is a
value computed correctly that nothing downstream reads - an evaluator reported
INSUFFICIENT_DATA forever because nothing wrote the field it read.

So: every field must be sourced from something that actually exists. **A field
you cannot source must say ABSENT and why - never 0.** A zero and a missing
writer are indistinguishable, and this dashboard would be the single most
dangerous place in the repository to confuse them.

## WHAT NOT TO DO

- Do not invent a number to fill a field.
- Do not put PII in it. Counts and hashes only; `work/` stays gitignored.
- Do not hand-maintain it. Generated, or it drifts and is believed.

## DELIVERABLE

The generator, both outputs, and a list of every field that came back ABSENT
with what would have to exist to populate it. That list is the roadmap.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from the outside.** If you
  measure zero of something, prove you read the right field first. Industry
  and headcount were reported at 0% three separate times by a reader looking
  at `sizing`, which is null everywhere, instead of `company_facts`.
- Say what you SAMPLED. `per_page` is accepted and IGNORED on every EmailBison
  route - you get 15 rows whatever you ask for - and offset pagination is
  refused past ~500 pages. A number without its page budget is not
  reproducible.
- Never use `meta.total` as a sent count. Campaign 274 reports 30,411
  scheduled rows and zero of its first 100 pages are sent. Count rows WHERE
  `sent_at` IS PRESENT.
- **Do not quote 8.49%** - unreproduced. **Do not quote any open rate** -
  `open_tracking` is False estate-wide, which is an ABSENT MEASUREMENT and not
  a zero. **Do not count an UNKNOWN as negative** - 53.4% of unknowns are
  correctly unknown.
- INTERESTED may NOT carry a learning claim: 0.44 precision on the old pattern
  set, and the new set is UNMEASURED, which is not the same as good.
  MEETING_INTENT (1.00) and OBJECTION (1.00) may, with recall stated.
- Never weaken, widen or disable a gate, a lint rule or a sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- No unhashed PII in any tracked file or commit message - no real names,
  domains, emails, profile URLs or reply text. A seat holder is a real person
  too; Claude leaked one yesterday and the guard caught it.
- Separate OBSERVATIONS (with n), HYPOTHESES, and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection. TASK-059
  left it empty and was right to.

---

## RESULT BLOCK

**STATUS**: COMPLETE

**COMMIT SHA**: e54de4b

**TESTS**: 24/24 pass in tests/test_production_dashboard.py. Pre-existing
fixture_hygiene failures (TASK-120, APPROVAL-REVOCATION-EVIDENCE) are
unrelated to this change.

**FILES CHANGED**:
- `scripts/production_dashboard.py` - the generator (695 lines)
- `tests/test_production_dashboard.py` - 24 tests covering every section
- `docs/state/PRODUCTION-DASHBOARD.json` - machine-readable output
- `docs/state/PRODUCTION-DASHBOARD.md` - human-readable output
- Task file moved TODO → RUNNING

**FINDINGS**:

The generator reads from six existing state files and the queue snapshot.
It does NOT call any provider. It produces 20 ABSENT fields, each with a
reason saying what would have to exist to populate it.

The ABSENT fields cluster into four groups:

1. **EmailBison has no machine-readable state** (5 fields). The provider
   truth is in markdown only. A `scripts/bison_provider_truth.py` that
   writes `docs/state/BISON-CAMPAIGNS.json` would populate all five.

2. **No experiment has data** (4 fields). The evaluator in src/variants.py
   is wired and tested, but no campaign has started sending. These will
   populate automatically once leads flow.

3. **No structured learning registry** (5 fields). Findings are in task
   result blocks and docs but not in a machine-readable store. A
   `docs/state/LEARNINGS.json` would populate these.

4. **Structural absences** (6 fields). No campaign has started (so
   utilisation and throughput are unmeasured, not zero), no record has
   reached live state, and sample sizes were never recorded for the
   documented findings.

**THE CALLER CHAIN**: The generator is a standalone script consumed by
being run (`py -3 scripts/production_dashboard.py`). It is not imported
by src/ modules. Its consumers are: any fresh session that reads
`docs/state/PRODUCTION-DASHBOARD.json` or
`docs/state/PRODUCTION-DASHBOARD.md` to answer "what is production doing."

**RISKS**:
- The queue snapshot is from 2026-09-14T21:52:15Z. If the queue changes,
  the dashboard must be regenerated to reflect it.
- The LEDGER.json is from 2026-09-15T07:34:08Z. Task counts may be stale.

**RECOMMENDED CLAUDE ACTION**:
1. Review and integrate.
2. Consider adding `py -3 scripts/production_dashboard.py` to the
   durable_state.py regeneration chain so the dashboard refreshes
   automatically with the other state files.
3. The EmailBison gap is the largest single group of ABSENT fields. A
   `scripts/bison_provider_truth.py` that writes `docs/state/BISON-CAMPAIGNS.json`
   would close 5 of 20 gaps.
