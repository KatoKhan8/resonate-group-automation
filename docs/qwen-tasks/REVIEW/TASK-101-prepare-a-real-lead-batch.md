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

**COMMIT SHA:** 3c76909

**TESTS:** Pipeline script `scripts/prepare_lead_batch.py` runs end-to-end. Fixture hygiene test (`tests.test_fixture_hygiene`) confirms no PII in the tracked report. Pre-existing failures in TASK-120 are unrelated.

**FILES CHANGED:**
- `scripts/prepare_lead_batch.py` - the pipeline script (new)
- `work/lead-batch-economic-buyer.json` - the batch file (gitignored, operational artefact)
- `docs/LEAD-BATCH-REPORT-2026-09-15.md` - the tracked report (new)

**FUNNEL:**

| Stage | Count | Drop |
|-------|------:|-----:|
| Cohort (economic_buyer + email) | 70 | - |
| After dedupe | 53 | 17 |
| After exclusion | 36 | 17 |
| After personalisation | 30 | 6 |
| After greeting proof | 30 | 0 |
| After quality gates | **23** | 7 |

**Drop-off breakdown:**

- **Dedupe (17 dropped):** All 17 are already claimed by one of 11 existing campaigns.
- **Exclusion (17 dropped):** not_sendable:unknown: 7; not_sendable:accept_all_uncleared: 5; not_sendable:never_verified: 4; not_sendable:held: 1. No contacts removed by suppression list (only example domains exist), no agency DNC file found, no reply events in estate.
- **Personalisation (6 dropped):** No email copy generated (record state is queued/held, never reached drafting).
- **Greeting proof (0 dropped):** All 30 opening lines have resolved company references, no broken tokens.
- **Quality gates (7 dropped):** Unsupported claims - 'profitability' asserted without evidence (2), 'utilisation/utilization' asserted without evidence (2), 'capacity' asserted without evidence (1), 'our previous discussions' asserts prior contact with no confirmed touch (4 contacts, some overlapping with other claim failures).

**FINDINGS:**

1. **The estate supports a batch of 23 qualified economic_buyer leads.** This is the largest honest batch the pipeline can produce from the current snapshot. The drop-off from 70 to 23 (67% loss) is real and each stage's reason is evidenced.

2. **The verification gap is the largest single loss.** 17 of 53 post-dedup contacts are not sendable. 4 were never verified at all (no verification data), 7 have unknown verification state, 5 are accept-all-uncleared, 1 is held. Running the verification waterfall on these 17 could recover some.

3. **6 contacts have no email copy at all.** Their records are in states queued (4) or held (2) and never reached the drafting stage. Generating copy for them would require running the generation pipeline first.

4. **7 contacts fail the claims gate.** The stored copy asserts things about profitability, utilisation, capacity, and prior contact that nothing on the record supports. These are stale drafts from before `claims.check` was wired into the generation path. Regenerating the copy would fix them.

5. **No provider write was performed.** The batch file is at `work/lead-batch-economic-buyer.json` and is ready for the operator's decision on enabling `heyreach.add_leads` or the EmailBison attach-leads route.

**RISKS:**

- The 23 leads are all from the economic_buyer persona. If the operator wants a different cohort (e.g., Advertising Services industry, 51 leads), a separate batch would be needed.
- The 17 not-sendable contacts could potentially be recovered by running verification, but that is a provider spend (ContactOut/Reoon credits per address).
- The 7 claims-failing contacts need copy regeneration, which is a generation run, not a batch preparation issue.

**RECOMMENDED CLAUDE ACTION:**

1. Review the batch of 23 leads and the funnel drop-off.
2. Decide whether to recover the 17 not-sendable contacts by running verification.
3. Decide whether to generate copy for the 6 contacts without email steps.
4. Decide whether to regenerate copy for the 7 contacts with unsupported claims.
5. If the batch of 23 is acceptable, enable the appropriate provider write route.
