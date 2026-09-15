PRIORITY: P1
DEPENDS: TASK-096

# TASK-101 - prepare a real lead batch, up to the point of the write

## WHERE THIS STOPS

At the batch file. **It does not write to any provider.** `heyreach.add_leads`
is not in `providerwrites.SUPPORTED` and enabling it is an operator decision.
This task produces the thing that would be written, plus the evidence that it
is safe to write, so the operator's decision is a yes/no on a real artefact
rather than on a promise.

## INPUT

The cohort TASK-096 identifies. If TASK-096 concluded that no cohort of 50
exists on this estate - which is plausible, there are 92 contacts on
not-dropped records - then take the LARGEST honest cohort it found and
prepare that, stating its size. **Do not pad it to reach 50.**

## THE PIPELINE, AND EVERY STEP MUST BE EVIDENCED

    DEDUPE            against every other campaign in the estate. A prospect
                      already in one of 83 campaigns must not enter another.
    EXCLUSION CHECK   suppression list, DNC, bounced addresses, positive-reply
                      protection, engagement state. `ENGAGEMENT-HYGIENE.md`.
    PERSONALISATION   every merge variable the sequence uses must RESOLVE for
                      every lead, or the lead carries a safe fallback, or the
                      lead is excluded. There is no fourth option. HeyReach
                      has 8 per-variable fallbacks configured on 599020.
    GREETING PROOF    render the actual greeting for every lead and check for
                      "Hey ,", "Hi undefined,", "Hi null," and a cohort name
                      where a person belongs.
    QUALITY GATES     lint, claims, the structural diversity check.

Report the count surviving each stage. **The drop-off between stages is the
most useful number in this task** - if 60 leads become 11 at the exclusion
step, that changes the plan entirely.

## WHAT NOT TO DO

- **No provider write of any kind.**
- Do not exclude a lead silently. Every drop carries a reason - "never delete
  a queue record, drop it with a reason" is a standing rule here.
- Do not fabricate a personalisation value to keep a lead in the batch. An
  invented fact is what `claims.check` exists to refuse.
- Hash every identifier in the report. The batch FILE itself may hold real
  data - it is an operational artefact under `work/`, which is gitignored -
  but the REPORT is tracked and must not.

## DELIVERABLE

The batch under `work/` (gitignored), a tracked report with the funnel counts
and every drop reason, and an explicit statement of what the operator would be
authorising if they enabled the write.

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

**COMMIT SHA:** beb6095

**TESTS:** `tests.test_fixture_hygiene` - 11/11 pass (PII guard green). Two independent workers ran the pipeline. Both confirmed 70 -> 70 -> 51 -> 51 -> 51 up to greeting proof. The quality-gates stage diverged: worker 1 (this result) checked generated copy for banned phrases and claims (26 survive); worker 2 checked structural properties only (51 survive). Worker 1's result is the correct one - the task asks for lint and claims, which require reading the actual copy.

**FILES CHANGED:**
- `scripts/prepare_lead_batch.py` - the pipeline script (new, two versions merged)
- `docs/LEAD-BATCH-REPORT-101.md` - tracked report with funnel counts and every drop reason (new)
- `work/batch-TASK-101.jsonl` and `work/task101_batch.json` - batch files (gitignored)
- `docs/qwen-tasks/RUNNING/TASK-101-prepare-a-real-lead-batch.md` - task moved from TODO

**FUNNEL:**

| Stage | Count | Drop |
|-------|------:|-----:|
| cohort_selected (economic_buyer, email) | 70 | - |
| after_dedupe | 70 | 0 |
| after_exclusion | 51 | -19 |
| after_personalisation | 51 | 0 |
| after_greeting_proof | 51 | 0 |
| after_quality_gates | 26 | -25 |

**Final batch: 26 leads.**

**FINDINGS:**

1. **The biggest drop is at exclusion (19 of 70, 27%).** All 19 are unverified emails: 12 unknown state, 6 accept_all_uncleared, 1 held. None are sendable. These contacts have not been through the verification waterfall, or the waterfall returned an inconclusive result. They CANNOT receive outreach without spending verification credits first.

2. **The second biggest drop is at quality gates (25 of 51, 49%).** 23 have banned phrases in generated copy (overwhelmingly 'just checking in' in step li5). 2 have unsupported claims in em5 ('our previous discussions' when no prior contact is recorded). These are REAL failures in existing generated copy that need regeneration through the normal pipeline.

3. **5 leads were fixed by punctuation normalisation** (curly apostrophes in LinkedIn notes). This is the same preprocessing `src/lint.py` applies before checking. They pass lint after normalisation.

4. **3 leads have no cadence data at all.** They pass quality gates (nothing to fail) but need copy generation before they can receive outreach.

5. **Zero duplicates found.** The 70 economic buyers are all distinct people by email and LinkedIn URL.

6. **Zero greeting failures.** All 51 verified leads render correct greetings.

7. **No structural diversity warnings** on the final 26. Industry spread: Advertising Services 15, Marketing & Advertising 6, Marketing Services 4, Business Consulting and Services 1. Angle spread: founder 15, operations 7, None 3, economic_buyer 1.

8. **16 of 26 have at least one approved step.** The remaining 10 have generated copy that passes lint but has not been through the approval workflow.

**OBSERVATIONS (with n):**
- n=70: The economic_buyer cohort is the largest honest cohort (TASK-096).
- n=19: Verification is the first gate that matters. 27% of the cohort has no verified email.
- n=25: Banned phrases in generated copy are the second gate. 49% of verified leads have them.
- n=23: 'just checking in' in step li5 is the dominant banned phrase. It appears in the LinkedIn close step.
- n=5: Punctuation normalisation fixes 5 leads that would otherwise fail lint.
- n=26: The final batch is 37% of the original cohort.

**HYPOTHESES:**
- The 'just checking in' in li5 comes from a template or generation pattern that used this phrase as a default LinkedIn close. Regenerating li5 for the 23 affected leads would recover most of them.
- The 19 unverified contacts could be recovered by running them through the verification waterfall (spending credits). Whether that is worth it depends on the credit cost vs. the value of recovering 19 leads.

**PROVEN LEARNINGS:**
- (none that survive a sample-size objection on a single estate of 92 contacts)

**RISKS:**
- The batch file under `work/` holds real PII (names, emails, domains). It is gitignored and is an operational artefact. The tracked report hashes all identifiers.
- The 26 leads have NOT been written to any provider. No HeyReach campaign has been populated. The operator decision to enable `heyreach.add_leads` is still owed.

**RECOMMENDED CLAUDE ACTION:**
1. Regenerate copy for the 25 leads that failed quality gates (fix 'just checking in' in li5, fix claims in em5).
2. Generate copy for the 3 leads with no cadence data.
3. Run verification on the 19 unverified contacts if credit budget allows.
4. After regeneration, re-run the pipeline to get an updated batch count.
5. Decide whether to enable `heyreach.add_leads` for the final batch.
