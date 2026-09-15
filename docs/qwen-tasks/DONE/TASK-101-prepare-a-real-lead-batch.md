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

**COMMIT SHA:** dae0de3

**TESTS:** Analysis script `scripts/task101_lead_batch.py` reads the snapshot and runs the full pipeline. No unit tests were written because this is an analysis task, not a code change. The script is the verification - run it and the numbers match the report.

**FILES CHANGED:**
- `docs/TASK-101-LEAD-BATCH-REPORT.md` - tracked report with funnel counts and every drop reason
- `scripts/task101_lead_batch.py` - analysis script that produces the batch and report
- `work/task101_batch.json` - the batch file (gitignored, operational artefact)

**FINDINGS:**

1. **The cohort is 70 on paper but 46 in practice.** TASK-096 identified economic_buyer as the largest cohort at 70 contacts with email. After the full pipeline, 46 survive all gates. The drop-off is 24 contacts (34.3%).

2. **The binding constraint is verification, not cohort size.** 19 of 70 contacts (27.1%) dropped at the exclusion step, ALL because `contact.sendable` is False. Their verification states: 8 unknown (never verified), 6 accept_all_uncleared (catch-all domain not cleared by Reoon), 4 no verification data, 1 held (verifiers disagree). Zero were blocked by engagement history, suppression, DNC, bounce, or meeting.

3. **Zero cross-campaign duplicates.** All 70 contacts have `campaign_ids = []`. None are already in any of the 83 campaigns. The dedupe stage dropped zero.

4. **Zero personalisation failures.** All 51 sendable contacts have 100% coverage on every required merge field. No fallbacks were needed.

5. **Zero greeting defects.** All 51 leads passed greeting proof across all their email steps (~230 bodies checked). No "undefined", "null", missing names, or cohort-name-as-person-name.

6. **Five contacts dropped at quality gates because generation never reached them.** Three have no cadence at all, two have LinkedIn-only cadences. This is a generation gap, not a quality failure of existing copy.

7. **The batch of 46 is below the 50-lead target.** To reach 50, the operator would need to: (a) spend verification credits on the 19 dropped contacts (estimated 19 credits), and/or (b) generate cadences for the 5 contacts that lack them.

**RISKS:**

- The batch is 46, not 50. The task says "do not pad it to reach 50" and the batch is honest at 46.
- `heyreach.add_lead` is NOT in `providerwrites.SUPPORTED`. Enabling it is an operator decision. The batch is ready but the write path is not open.
- The 19 verification failures are recoverable with credits but that is a cost decision, not an engineering one.

**RECOMMENDED CLAUDE ACTION:**

1. Review the report at `docs/TASK-101-LEAD-BATCH-REPORT.md`.
2. Decide whether to spend verification credits on the 19 dropped contacts to grow the batch toward 50+.
3. Decide whether to enable `heyreach.add_lead` in `providerwrites.SUPPORTED` to allow the write.
4. Generate cadences for the 5 contacts that lack them if the batch is to be expanded.
