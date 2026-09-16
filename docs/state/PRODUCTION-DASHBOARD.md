# Production Dashboard

Generated: 2026-09-16T05:38:06+00:00
Source: work/queue.jsonl (Claude worktree)  550 records  mtime 2026-09-16T05:23:26Z
Previous snapshot: 2026-09-14T21:52:15Z from master 0ac5e60 300 records (STALE - superseded by 550-record ingest)

> A zero and a missing writer are indistinguishable from the
> outside. Fields marked **ABSENT** have no data source, not
> a zero value.

## LEADS

- **Total records**: 550
- **Total contacts**: 277
- **Sendable contacts**: 68
- **Verified contacts**: 68
- **Records with cadence**: 68
- **Live records**: 0

**By record state**:
  - queued: 315
  - dropped: 126
  - verified: 65
  - held: 32
  - drafted: 12
**By persona**: ABSENT - persona_plan is empty for all 550 records in current state
**By angle**: ABSENT - messaging.angle is 'unknown' for all 550 records in current state

- **Cohorts defined**: 1 (batch: productive-pilot-2026-09-07 for 50 string-batch records; 500 records have dict-batch)
- **Cohorts above 50 leads**: ABSENT - batch field is a dict for 500 of 550 records; cohort derivation needs re-run
- **Campaigns with leads**: ABSENT - no campaign has started; both HeyReach and EmailBison Resonate campaigns have 0 leads attached

## HEYREACH

- **Total campaigns in account**: 83
- **Resonate campaigns**: 1
- **Resonate live**: 0
- **Resonate draft**: 1
- **LinkedIn accounts available**: 41

- **Senders total**: 41
- **Healthy senders**: 33
- **Daily connection capacity**: 1054
- **Daily message capacity**: 1143
- **Healthy with no active campaign**: 0

- **Utilisation**: ABSENT - no Resonate campaign has started sending; utilisation is not 0%, it is unmeasured. The 12 IN_PROGRESS campaigns in the account are the client's own, not Resonate's.
- **Throughput**: ABSENT - no Resonate campaign has started sending; throughput is unmeasured

- **Account status totals**: `{"DRAFT": 8, "PAUSED": 32, "FINISHED": 31, "IN_PROGRESS": 12}`

### Resonate Campaign Details

- **RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1** (id=599020)
  - Status: DRAFT, Classification: DRAFT
  - Leads: 0, Senders: 1
  - Sequence nodes: 24
  - Started: ABSENT (never started)

## EMAILBISON

- **Campaigns total**: ABSENT - no BISON-CAMPAIGNS.json exists; provider truth is in docs/BISON-PROVIDER-TRUTH-2026-09-14.md (markdown only)
- **Resonate campaigns**: ABSENT - no machine-readable EmailBison state; TASK-069 and TASK-071 mapped the API but no generator script writes a JSON state file
- **Live campaigns**: ABSENT - no EmailBison state file to read
- **Senders**: ABSENT - no EmailBison state file to read
- **Throughput**: ABSENT - no EmailBison state file to read; the provider truth doc reports campaign 481 paused with 0 sent and campaign 451 completed with 1 sent, but these are not in a machine-readable state file

## EXPERIMENTS

- **Copy experiment infrastructure**: EXISTS AND WIRED
- **Experiments with data**: ABSENT - no campaign has started sending; the evaluator in src/variants.py has never received exposure data. INSUFFICIENT_DATA is not the verdict - the experiment has not started.
- **Running**: 0
- **Completed**: 0
- **Winner candidates**: ABSENT - no experiment has reached evaluation
- **Cadence experiment infrastructure**: EXISTS BUT UNUSED
- **Cadence is fixed**: True
- **Cadence steps**: 7
- **Variant wiring**: EXISTS AND WIRED - variants.apply_to_step has a caller
- **Exposure tracking**: EXISTS AND WIRED - variants.journey_of, results_from
- **Statistical discipline**: EXISTS AND WIRED - Wilson bounds, sample floor

## LEARNING

- **Structured learning registry**: ABSENT - no learning registry exists; findings are in task result blocks and documentation but not in a machine-readable store
- **Proven learnings (with sample size)**: ABSENT - no finding survives a sample-size objection with a recorded n; TASK-059 left PROVEN LEARNINGS empty and was right to

### Documented Findings

| Finding | Value | Promoted | Note |
|---------|-------|----------|------|
| interested_pattern_precision | 0.44 | No | INTERESTED may NOT carry a learning claim at 0.44 precision |
| meeting_intent_precision | 1.0 | Yes | MEETING_INTENT (1.00) may carry a learning claim, with recall stated |
| objection_precision | 1.0 | Yes | OBJECTION (1.00) may carry a learning claim, with recall stated |
| open_tracking | False | Yes | open_tracking is False estate-wide; any open rate is ABSENT MEASUREMENT, not a zero. Do not quote any open rate. |
| unknowns_are_not_negative | 53.4% of unknowns are correctly unknown | Yes | Do not count an UNKNOWN as negative |

## OPERATIONS

- **Master HEAD**: e6cdfde
- **Master pushed**: True
- **Total tasks**: 113
- **Task stages**: `{"TODO": 17, "REVIEW": 8, "DONE": 88}`
- **Branches with unpushed work**: 3
- **Dirty worktrees**: 8
- **Active worktrees**: 9

## ABSENT FIELDS - THE ROADMAP

These fields have no data source. Each entry says what
would have to exist to populate it.

| Path | What would populate it |
|------|------------------------|
| `LEADS.campaigns_with_leads` | no campaign has started; both HeyReach and EmailBison Resonate campaigns have 0 leads attached |
| `LEADS.queued_records` | no record has reached a live/sending state; the lead block holds |
| `HEYREACH.utilisation` | no Resonate campaign has started sending; utilisation is not 0%, it is unmeasured. The 12 IN_PROGRESS campaigns in the account are the client's own, not Resonate's. |
| `HEYREACH.throughput` | no Resonate campaign has started sending; throughput is unmeasured |
| `HEYREACH.resonate_campaign_details[0].started_at` | never started |
| `EMAILBISON.campaigns_total` | no BISON-CAMPAIGNS.json exists; provider truth is in docs/BISON-PROVIDER-TRUTH-2026-09-14.md (markdown only) |
| `EMAILBISON.resonate_campaigns` | no machine-readable EmailBison state; TASK-069 and TASK-071 mapped the API but no generator script writes a JSON state file |
| `EMAILBISON.live_campaigns` | no EmailBison state file to read |
| `EMAILBISON.senders` | no EmailBison state file to read |
| `EMAILBISON.throughput` | no EmailBison state file to read; the provider truth doc reports campaign 481 paused with 0 sent and campaign 451 completed with 1 sent, but these are not in a machine-readable state file |
| `EXPERIMENTS.experiments_with_data` | no campaign has started sending; the evaluator in src/variants.py has never received exposure data. INSUFFICIENT_DATA is not the verdict - the experiment has not started. |
| `EXPERIMENTS.winner_candidates` | no experiment has reached evaluation |
| `EXPERIMENTS.inconclusive` | no experiment has reached evaluation |
| `EXPERIMENTS.failed` | no experiment has reached evaluation |
| `LEARNING.structured_learning_registry` | no learning registry exists; findings are in task result blocks and documentation but not in a machine-readable store |
| `LEARNING.documented_findings.interested_pattern_precision.sample_size` | exact n not recorded in a machine-readable file |
| `LEARNING.documented_findings.meeting_intent_precision.sample_size` | exact n not recorded in a machine-readable file |
| `LEARNING.documented_findings.objection_precision.sample_size` | exact n not recorded in a machine-readable file |
| `LEARNING.documented_findings.unknowns_are_not_negative.sample_size` | exact n not recorded in a machine-readable file |
| `LEARNING.proven_learnings_with_sample_size` | no finding survives a sample-size objection with a recorded n; TASK-059 left PROVEN LEARNINGS empty and was right to |
