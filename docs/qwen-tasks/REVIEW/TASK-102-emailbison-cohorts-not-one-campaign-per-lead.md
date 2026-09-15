PRIORITY: P1
DEPENDS: 

# TASK-102 - the same cohort philosophy for EmailBison

## THE POLICY

`docs/PRODUCTION-SCALE-POLICY.md` section 7. Coherent cohorts, not one
campaign per lead. Supported variables only. Correct signatures. Meaningful
variants. Conversational sequences with same-thread follow-ups.

## THE PROVIDER FACTS THAT CONSTRAIN THE DESIGN

**There is NO `first_name` and NO `company` merge variable at EmailBison.**
The whole body travels as `body_N`. `headline`, `industry` and `location` are
the three fields that can travel. So the greeting CANNOT be delegated to the
provider, and a broken greeting goes straight to a person - which is why the
pre-write greeting guard exists and why it runs before the write.

`THREAD_REPLY_PATTERNS['email_five']` is (F, T, F, T, F), carried ladder ->
factory -> payload -> readback, and the follow-up rung TELLS THE MODEL it is
continuing a thread rather than only flipping a flag.

**The alternating structure is a BET, not evidence.** The estate has NO
CONTROL GROUP: every campaign with sends uses `thread_reply=True` at step 2,
and campaign 481 - the only one with False there - has zero sends. Say so
wherever the design rests on it.

**"Short follow-up" is NOT supported.** Same-thread follow-ups that got
replies average 857 characters against 571 for new threads - LONGER. That
measurement is survivorship-biased (taken only on emails that got replies) so
it supports neither "be short" nor "be long", and the addendum now asserts no
length in either direction. A test pins that. Do not reintroduce a length
instruction.

## WHAT TO PRODUCE

1. What cohorts does the EMAIL side support? 94% of the 92 contacts have an
   email; that is the ceiling. Apply the same evidence standard as TASK-096.
2. A cohort-shaped campaign design: the hypothesis, the 5-step sequence with
   its thread_reply pattern, the variables used (from the three that exist),
   the variants per position, and the signature.
3. What campaign 481 already holds - it is paused with 23 leads, 5 provider
   steps and 0 sent - and whether it is the right vehicle or should be left
   alone.

## WHAT NOT TO DO

- No writes. 481 stays paused; 451 is completed and stays completed.
- Do not design a sequence using a merge variable EmailBison does not expose.
  Check the three before using anything.
- Do not create one campaign per lead. That is the whole point.

## DELIVERABLE

`docs/EMAILBISON-COHORT-DESIGN-2026-09-15.md` with the cohort counts, the
sequence design, and an explicit list of which design choices rest on evidence
and which rest on the bet.

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

**STATUS:** DONE

**COMMIT SHA:** 8792acc

**TESTS:** No code changes — this is a design and analysis document. The
existing test suite was not run because no source code was modified. All
claims are derived from `work/queue.snapshot.jsonl` (stamped
2026-09-14T21:52:15Z from master 0ac5e60, 300 records) and from the
provider truth documents and source code already in the repository.

**FILES CHANGED:**
- `docs/EMAILBISON-COHORT-DESIGN-2026-09-15.md` — the deliverable

**FINDINGS:**

1. **The email ceiling is 56 sendable contacts.** 87 of 92 contacts have
   email (94.6%), but only 56 are sendable (reoon valid, sendable=True).
   The remaining 31 are either unverified (22) or accept_all/unsafe (9).

2. **{HEADLINE} is not available.** Zero of 87 email contacts carry a
   headline in any field. This is a LinkedIn profile field that EmailBison
   resolves from its own data, but our records do not have it and we do not
   populate it as a custom variable. It may not be used in any sequence
   design.

3. **{INDUSTRY} is 100% covered** from `company_facts.industry` — 6 distinct
   values, dominated by Advertising Services (29/56 sendable), Marketing &
   Advertising (14), and Marketing Services (10). It needs to be added to
   `LEAD_VARIABLES` in `bison.py` and populated at staging time.

4. **{LOCATION} is 100% covered in principle** from `company_facts.offices`,
   but the data is full street addresses (74 distinct values), not the
   city/metro format EmailBison's {LOCATION} expects. An extraction function
   would be needed. Not written.

5. **The estate supports one cohort of 56, not split by industry.** No
   single industry reaches 25. The only viable design is all 56 as one
   cohort with industry variation expressed through the merge variable in
   the copy.

6. **Campaign 481 should be left alone.** It is paused with 23 leads and
   an all-new-thread pattern (F,F,F,F,F) — the only such campaign in the
   estate. Its value is as a structural reference, not as a vehicle for the
   new design. A new campaign with the full 56-lead pool and the
   (F,T,F,T,F) pattern is cleaner.

7. **The signal field is null for all 300 records.** No signal-based cohort
   grouping is possible. The only grouping fields with coverage are
   industry (100%), angle (95%), persona (100%), and title (100%, too fine
   for cohort keys).

8. **29 of 87 email contacts already have a `bison_lead_id`** from previous
   staging in campaigns 352 or earlier. Deduplication is needed before they
   can join a new campaign.

9. **Five variants per position with 56 contacts gives ~11 exposures per
   variant per step** — below the evaluator's 30-exposure minimum. The
   experiment framework will report `insufficient_data` for every cell
   unless traffic is much larger or the minimum is lowered. This is a
   design constraint, not a defect.

10. **PROVEN LEARNINGS is empty.** Nothing survives the sample-size
    objection. The estate has 56 sendable email contacts, zero control
    groups, and no reproduced reply rate.

**RISKS:**
- The cohort design rests on the snapshot, which is from 2026-09-14. If
  records have been added, dropped, or enriched since then, the counts
  will differ. The snapshot stamp is quoted so the measurement is
  reproducible.
- The `industry` custom variable is not yet in `LEAD_VARIABLES`. The
  campaign cannot run until it is added and the staging pipeline populates
  it.
- The {LOCATION} extraction function does not exist. If location-based
  personalisation is wanted, it needs to be built.
- The design is for one cohort of 56. If the estate grows to 100+, the
  design should be revisited — at that point splitting by industry or
  angle becomes viable and the single-cohort assumption stops being forced
  by small numbers.

**RECOMMENDED CLAUDE ACTION:**
1. Accept the cohort design as the basis for campaign construction.
2. Add `industry` to `LEAD_VARIABLES` in `src/providers/bison.py` and wire
   the staging pipeline to populate it from `company_facts.industry`.
3. Leave campaign 481 paused. It is the all-new-thread reference arm.
4. The generation pipeline needs to produce 25 messages (5 variants × 5
   steps) for the cohort. The ladder and thread-reply pattern are already
   in `cadencelibrary.py`.
5. Do not activate until a human has read the sequence. The human read is
   the gate.
