PRIORITY: P3
DEPENDS: TASK-092

# TASK-110 - sequence QA across the whole generated estate

## WHAT THIS IS

TASK-092 counts six specific copy defects. This one asks a different question
of the same material: **does each SEQUENCE work as one conversation?**

A sequence can have six individually clean messages and still be broken - six
messages that each pass lint, and together ask one question six times.

## WHAT TO CHECK, PER SEQUENCE

1. **Progression.** Does each rung do a DIFFERENT job, or do several collapse
   into one discovery question? The ladder specifies six different jobs.
   `ogpartner-dk/jacob-faertz` is the sequence that got it right - six rungs,
   six jobs, product named once at rung 4, easy out at rung 6.
2. **Does it read as one person writing?** Tone drift between steps, a step
   that reintroduces the sender as if for the first time, a step that assumes
   context an earlier step never gave.
3. **Is there an easy out?** A final rung that lets somebody decline without
   awkwardness.
4. **Does a later step acknowledge that earlier steps went unanswered**, or
   does it pretend to be a first contact?
5. **Conceptual duplication** - not the string-level duplicate TASK-092
   counts, but two steps making the same ASK in different words.

## WHAT NOT TO DO

- Do not regenerate. Read what is stored. Regeneration costs 560 steps and 83
  human approvals and is the operator's call.
- Do not fix. This is a measurement; a fix in the same change makes the
  before-number unverifiable.
- Hash identifiers in the report.

## DELIVERABLE

`docs/SEQUENCE-QA-2026-09-15.md`: a per-sequence verdict, the rate of each
defect with its denominator, and the three worst and three best sequences
with identifiers hashed. Name which defects are universal (a prompt problem)
and which are rare (a per-record problem) - that distinction decides the fix.

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

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 6463b5d

**TESTS:** PII check passed — no unhashed record IDs, contact names, or
domains in the report. `scripts/task110_sequence_qa.py` runs clean against
the snapshot.

**FILES CHANGED:**
- `docs/SEQUENCE-QA-2026-09-15.md` — the deliverable
- `scripts/task110_sequence_qa.py` — the analysis script
- `.qwen/tmp/task110_full_output.txt` — full per-sequence text dump

**FINDINGS:**

Snapshot: `work/queue.snapshot.jsonl`, 2026-09-14T21:52:15Z, 300 records,
81 sequences across 68 records with a cadence.

Per-defect rates (denominator: 81 sequences):

| Defect | Rate | Universal or per-record |
|---|---|---|
| Progression collapse (same ask, different words) | 39/81 (48.1%) | Universal (prompt) |
| Re-introduction in later steps | 38/81 (46.9%) | Universal (prompt) |
| Silence never acknowledged (step 3+) | 56/81 (69.1%) | Universal (prompt) |
| Company description repeated in emails | 32/51 (62.7%) | Universal (prompt) |
| Missing easy out | 23/81 (28.4%) | Per-record |
| High text similarity between steps | 21/81 (25.9%) | Per-record |
| Product name absent | 16/81 (19.8%) | Per-record |

**Critical operational finding:** All 6 approved sequences carry defects.
Every one lacks an easy out and every one omits the product name. Five of
six have question collapse. The approved sequences are the worst in the
estate (avg 2.0 defects vs 0.1-0.4 for other states). They predate the
ladder fix of 2026-09-14.

Only 11/60 sequences (18.3%) follow the full correct ladder shape. The
reference sequence (`ogpartner-dk/jacob-faertz`, hashed as `seq-b580268f93`)
is one of them.

Cross-channel overlap (em1 vs li2) is 0% — emails and LinkedIn messages
are saying different things. This is the one thing that works.

**RISKS:**
- The approved sequences cannot be sent in their current state without
  the recipient experiencing the same question 3-5 times and no product
  name. This is the before-number; regeneration is the operator's call.
- The universal defects (prompt problems) affect ALL sequences, including
  the 18 that are zero-defect on the per-record checks. A prompt fix would
  move all four universal defects simultaneously.

**RECOMMENDED CLAUDE ACTION:**
1. The approved sequences need regeneration before sending. The report
   provides the before-number for each defect.
2. The four universal defects are prompt problems — passing prior-step
   summaries, suppressing the company description after em1, and adding
   silence-acknowledgement instructions to rungs 3+ would move all four.
3. The per-record defects (easy out, product name) are already specified
   by the ladder; the model sometimes fails to follow. Tightening the
   prompt language may help but regeneration is the direct fix.
