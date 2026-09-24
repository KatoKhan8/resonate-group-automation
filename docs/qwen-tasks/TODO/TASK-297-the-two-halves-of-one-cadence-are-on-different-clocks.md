PRIORITY: P1
DEPENDS:

# TASK-297 — the two halves of one cadence are on different clocks

## DISPATCH NOTE

Lane F, the standing QA suite. **The per-campaign HeyReach check:
`scripts/qa/check_campaign_heyreach.py`.**

**NOT in the minimum subset for today's 128** — they are an EMAIL push onto
EmailBison 502/503. This check gates the **825 enrollment across 33 seats at
25/seat/day**, which is the next thing after it, and it must exist before that
happens. P1, claim it today.

**READ `docs/QA-LANE-F-CONTRACT-2026-09-25.md` FIRST.**

`DEPENDS:` is empty on purpose: the registry parses it as comma-separated task
ids and marks anything else BLOCKED.

## The question this answers

**Is this LinkedIn campaign running, on the right seat, with the fields and
the window and the headroom to actually send — and is this lead free to be
enrolled in it?**

And the one underneath it: **do the email half and the LinkedIn half of the
same cadence agree about when they may speak?** They do not. ISSUE-045,
measured 2026-09-24: every one of the 15 EmailBison campaigns is
**09:00-17:00 Mon-Fri in its own timezone**; HeyReach is **07:00-23:00 seven
days**. A cross-channel cadence whose two halves run on different clocks will
land its LinkedIn touch at 07:30 on a Sunday and its email touch nine working
hours later on Monday, and nothing in this system currently says so.

### The six rules, operator's words

    campaign_in_progress_on_the_right_seat
                              status IN_PROGRESS, and the LinkedIn account it
                              is attached to is the seat we intended
    custom_fields_match_the_pushed_variables
                              the sequence's merge variables and the fields
                              we are pushing are the same set
    schedule_07_to_23_seat_local_seven_days
                              and seat-LOCAL, not UTC
    seat_under_its_daily_cap  the seat has headroom today
    lead_not_in_another_linkedin_campaign
                              at HeyReach, in any campaign, ours or the
                              client's
    connection_note_under_280_characters

## What to build

`scripts/qa/check_campaign_heyreach.py` plus its tests.

**The read surface that already exists. Use it; do not re-implement it:**

    heyreach.campaign_read(id)        heyreach.campaign_status(id)
    heyreach.campaign_cannot_send(id) heyreach.campaign_stats(id)
    heyreach.campaign_leads(id)       heyreach.campaign_sequence(id)
    heyreach.connection_notes(seq)    heyreach.note_is_placeholder(note)
    heyreach.note_matches(seq, approved)
    heyreach.sequence_hazards(seq, supplied_fields)
    heyreach.supplied_field_names(rows, linkedin_account_id)
    heyreach.campaigns_for_lead(profile_url=…, linkedin_id=…)
    heyreach.lead_state(row)          heyreach.li_accounts()
    heyreach.check_tenant(id, org_unit)
    heyreachfactory.custom_fields_for / merge_variable_of / merge_sequence_copy
    seatledger                        for the per-seat daily cap

**The four rules that need care, and why:**

1. **A seat is not a campaign, and the inbox is mostly the client's.** ~27,000
   conversations. `heyreach.campaigns_for_lead` will return the client's
   campaigns alongside ours. **Ask `campaign_stats` before calling anything
   ours**, and say which evidence decided ours vs theirs for every row.
   `heyreach.check_tenant(id, org_unit)` exists; use it.
2. **`schedule_07_to_23_seat_local_seven_days` is a TIMEZONE question, not a
   number-comparison question.** The seat's local timezone is the one that
   matters; comparing `07:00` from the provider against `07:00` in the config
   in UTC will pass a campaign that starts at 02:00 for its seat. Read the
   seat's timezone and state it. **A guessed timezone is worse than a missing
   one** — CLAUDE.md. And report, per campaign, the **overlap in hours between
   this LinkedIn window and the email window of the campaign carrying the same
   cadence**. That number is the finding; today it is small.
3. **`custom_fields_match_the_pushed_variables` is a SET DIFF, both
   directions.** `heyreach.sequence_hazards(sequence, supplied_fields)`
   already answers a version of this. A merge variable the sequence names and
   the push does not supply renders as a gap in somebody's LinkedIn message; a
   field supplied and never named is wasted. Both are reported, by name.
4. **`connection_note_under_280_characters` must count the RENDERED note, not
   the template.** A 240-character template with a `{company}` in it can
   render past 280. `note_is_placeholder` exists because a note that is still
   a placeholder has never been approved; a placeholder that is under 280 is
   not a pass.

**The LinkedIn write path is fail-closed and stays that way.**
`LINKEDIN_ADD_LEAD` is CONDITIONAL and refuses unless a provider read at the
moment of the write proves the destination cannot send: *"Only DRAFT proves
that. PAUSED does not. FINISHED does not."* This check does not write, does
not weaken that gate, and does not propose weakening it.

Write `docs/QA-CAMPAIGN-HEYREACH-2026-09-25.md`.

## The acceptance bar

- **Run against all 33 live HeyReach campaigns**, not a sample. Report every
  campaign id with its verdict, ordered by provider id numerically.
- **The window overlap with the email half is reported in hours, per
  cadence**, with both windows quoted as their providers returned them and
  both timezones named. "They differ" is not a result; the number is.
- **`custom_fields_match_the_pushed_variables` reports the set diff both
  directions, by name, per campaign.**
- **`lead_not_in_another_linkedin_campaign` reports, per offending lead, WHICH
  campaign and whose it is**, with the evidence that decided ours vs the
  client's. A bare "in another campaign" cannot be acted on.
- **Notes are measured RENDERED**, with the longest rendered note per campaign
  and its character count, and placeholders reported separately from
  over-length ones.
- **A campaign with zero leads is VACUOUS for the lead rules**, not PASS, and
  the result names which.
- One constructed failure per rule, shown firing — including a note that is
  under 280 as a template and over 280 rendered.
- **`subjects == 0` exits 2 with a stated reason.**
- Suite baseline **by name**, both directions, against `HEAD~1`.

## What evidence counts

- HeyReach's own named response fields, quoted: `leadCampaignStatus`, the
  campaign status string, the schedule object, the seat's account row. Not a
  paraphrase.
- `campaign_stats` output for every campaign a lead was found in, as the
  evidence for ours-vs-client.
- The seat ledger rows for the cap, and the day they were taken.
- `work/queue.jsonl` from a **named copy of production's `work/`**, mtime and
  row count.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Calling a reply or an enrollment ours because it is on a seat we use.** A
  seat is not a campaign. 27k conversations, and of 103 notification posts in
  72 hours, **99 were the client's own traffic and 2 were ours** — two real
  unmatched replies invisible in the noise for three days.
- **Comparing windows without timezones.** `07:00 == 07:00` in two different
  zones is a pass for a campaign that speaks at 02:00 local.
- **A check keyed on `heyreach_lead_id`.** ISSUE-041: **ZERO contacts in
  `work/queue.jsonl` carry it.** Any rule gated on that field will report
  "nothing to check" on 100% of subjects and read as a clean pass. If your
  rule keys on it, report the key-presence count first, and report VACUOUS.
  This is the single most likely false pass in this task.
- **Measuring the note template instead of the rendered note.**
- **Treating a placeholder note as an approved one** because it fits.
- **Counting `IN_PROGRESS` as "can send".** `campaign_cannot_send(id)` exists
  and answers the stricter question; the LinkedIn write gate already refuses
  on anything but DRAFT for a different reason, and the distinction is real:
  613744 is `IN_PROGRESS` and the operator's own test lead on it reads
  `leadCampaignStatus: "Finished"`. A stop against a finished lead returns
  "already settled" — **a pass by construction**, which is the shape of the
  first blank-content halt, which alerted and halted nothing and read as
  working.
- **A campaign with zero leads reported as clean.**
- **Fixtures.** Read the provider.
- **Any provider write.** No `add_leads_to_campaign`, no `set_sequence`, no
  `set_schedule`, no `pause`, no `start`, no `stop_lead_in_campaign`.

## Boundaries

- **READS ONLY at HeyReach.** In particular: do not call
  `heyreach.stop_lead_in_campaign`, whose own docstring says it has **NEVER
  BEEN LIVE-VALIDATED** — validating it is a separate, authorised measurement
  and not this task's to run.
- **Do not edit `src/heyreachfactory.py`, `src/providers/heyreach.py`,
  `src/seatledger.py`, or `src/linkedinstate.py`.** Defects go in FINDINGS.
- Do not edit `scripts/*_watch_loop.py` or anything under `work/` except
  `work/qa/`.
- No prospect PII, no profile URLs and no note text in any committed file.
  Ids and excerpts go under `work/qa/<run>/`; counts go in the doc.
- Production `work/` is not yours; `--workspaces` a named copy.

## Files

    ALLOWED    scripts/qa/check_campaign_heyreach.py,
               tests/test_a_note_that_fits_as_a_template_and_not_rendered.py,
               tests/test_a_seat_is_not_a_campaign.py,
               docs/QA-CAMPAIGN-HEYREACH-2026-09-25.md
    FORBIDDEN  src/heyreachfactory.py, src/providers/*, src/seatledger.py,
               src/linkedinstate.py, src/inbound.py, src/leadstop.py,
               scripts/*_watch_loop.py, work/* except work/qa/, config/.env

## Result block

    STATUS:
    BRANCH:
    COMMIT SHA:
    TESTS:
    FILES CHANGED:
    CAMPAIGNS CHECKED (all 33, ordered by provider id numerically):
    PER-CAMPAIGN TABLE: rule verdicts, offenders:
    STATUS AND SEAT PER CAMPAIGN, AS THE PROVIDER RETURNED THEM:
    WINDOW OVERLAP WITH THE EMAIL HALF, IN HOURS, PER CADENCE:
    BOTH WINDOWS AND BOTH TIMEZONES, QUOTED:
    CUSTOM FIELDS vs PUSHED VARIABLES, SET DIFF BOTH DIRECTIONS, PER CAMPAIGN:
    SEAT CAPS AND HEADROOM TODAY, PER SEAT:
    LEADS IN ANOTHER LINKEDIN CAMPAIGN: which campaign, whose, and the evidence:
    LONGEST RENDERED NOTE PER CAMPAIGN (chars) / PLACEHOLDERS, SEPARATELY:
    KEY-PRESENCE: how many subjects carried heyreach_lead_id (expect 0):
    THE CONSTRUCTED FAILURES AND THEIR MESSAGES:
    WORKSPACES COPY USED (path, mtime, rows):
    SUITE BASELINE vs HEAD~1 — new/gone BY NAME, both directions:
    FINDINGS:
    RISKS:
    RECOMMENDED CLAUDE ACTION:
