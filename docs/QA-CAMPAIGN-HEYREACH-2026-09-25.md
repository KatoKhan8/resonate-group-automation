# QA Campaign HeyReach — 2026-09-25

**TASK-297.** The per-campaign HeyReach check: `scripts/qa/check_campaign_heyreach.py`.

## What it answers

**Is this LinkedIn campaign running, on the right seat, with the fields and
the window and the headroom to actually send — and is this lead free to be
enrolled in it?**

## The six rules

| Rule | What it checks |
|------|---------------|
| `campaign_in_progress_on_the_right_seat` | Status is `IN_PROGRESS`, and the LinkedIn account it is attached to is the seat we intended |
| `custom_fields_match_the_pushed_variables` | The sequence's merge variables and the fields we are pushing are the same set, diffed both directions by name |
| `schedule_07_to_23_seat_local_seven_days` | The sending window is 07:00-23:00 seat-local, seven days; plus the overlap in hours with the email half of the same cadence |
| `seat_under_its_daily_cap` | The seat has headroom today (ours < 40 on an exclusive seat) |
| `lead_not_in_another_linkedin_campaign` | The lead is not in another LinkedIn campaign at HeyReach, in any campaign, ours or the client's |
| `connection_note_under_280_characters` | The RENDERED connection note is under 280 characters; placeholders reported separately from over-length ones |

## Design decisions

### A seat is not a campaign

~27,000 conversations at HeyReach. `campaigns_for_lead` returns the client's
campaigns alongside ours. The check uses `_is_our_campaign` to decide
ownership based on campaign name markers ("resonate", "productive", "abm",
"cohort", "canary"), and reports the evidence for every attribution.

A collision report always says WHICH campaign and WHOSE it is:

    lead abc123... also in campaign 555001 (Sales Pipeline Q3),
    status=FINISHED, lead_status=Finished, whose=CLIENT'S,
    evidence=name='Sales Pipeline Q3'

### A guessed timezone is worse than a missing one

The seat's timezone is read from the `li_accounts()` response. If it is
absent, the schedule rule reports `UNCONFIRMED` with the reason "seat
timezone not readable". No fallback, no guess.

### The overlap is the finding

ISSUE-045: every one of the 15 EmailBison campaigns is 09:00-17:00 Mon-Fri
in its own timezone; HeyReach is 07:00-23:00 seven days. The overlap between
these two windows is computed per cadence and reported in hours per week:

    LinkedIn: 07:00-23:00 seven days (seat-local)
    Email:    09:00-17:00 Mon-Fri
    Overlap:  40 hours/week (8h × 5 weekdays)

### The rendered note, not the template

A 240-character template with `{COMPANY}` in it can render past 280 when the
company name is long enough. The check renders each note template with the
longest known value for each variable (extracted from the campaign's leads)
and measures the result.

A placeholder note (HeyReach's default "Hey, would love to connect!") that is
under 280 is NOT a pass — it was never approved. Placeholders are reported
separately from over-length ones.

### VACUOUS is not PASS

A campaign with zero leads is `VACUOUS` for the lead rules, not `PASS`. The
result names which rules are vacuous and why.

ISSUE-041: zero contacts in `work/queue.jsonl` carry `heyreach_lead_id`. Any
rule gated on that field will report "nothing to check" on 100% of subjects
and read as a clean pass. The check reports the key-presence count and
reports `VACUOUS` when the subject set is empty.

### No schedule read API

HeyReach has no API to read a campaign's schedule back. `set_schedule` is
deliberately not implemented in this codebase because the write can never be
verified. The schedule rule therefore reports `UNCONFIRMED` with the overlap
computation, and documents that the actual schedule at the provider cannot be
read.

## The read surface used

    heyreach.campaign_read(id)          campaign status and seat assignment
    heyreach.campaigns(offset, limit)   enumerate all campaigns
    heyreach.campaign_sequence(id)      the node graph, for merge variables
                                        and connection notes
    heyreach.campaign_leads(id)         enumerate leads for collision check
    heyreach.campaigns_for_lead(        is this person in another campaign?
        profile_url=...)
    heyreach.connection_notes(seq)      every connection-request note
    heyreach.note_is_placeholder(note)  vendor default detection
    heyreach.supplied_field_names(rows) what the push supplies
    heyreach.li_accounts(offset, limit) seat inventory with timezone
    seatledger.daily(seat_id, day)      per-seat daily cap verdict

## Exit codes

    0   PASS         every campaign checked, every rule clear
    1   FAIL         at least one campaign offends at least one rule
    2   UNCONFIRMED  a provider read failed, or the subject set was VACUOUS
    3   ERROR        the check itself broke

## Tests

24 tests across two modules:

    tests/test_a_note_that_fits_as_a_template_and_not_rendered.py
        - template under 280, rendered over 280 (the constructed failure)
        - render_note substitutes known variables
        - render_note leaves unknown variables in place
        - longest_rendered_length picks the worst
        - placeholder detection
        - placeholder under 280 is still a placeholder
        - extract_longest_field_values finds the worst
        - window overlap computation (4 tests)

    tests/test_a_seat_is_not_a_campaign.py
        - our campaign detected by name (4 patterns)
        - client campaign not detected as ours
        - None row is not ours
        - collision reports whose campaign with evidence
        - missing timezone returns None
        - empty timezone returns None
        - present timezone is returned
        - zero leads is VACUOUS, not PASS
        - vacuous result carries reason
        - error result carries reason

## Boundaries respected

- **READS ONLY at HeyReach.** No `add_leads_to_campaign`, no `set_sequence`,
  no `set_schedule`, no `pause`, no `start`, no `stop_lead_in_campaign`.
- **Does not edit** `src/heyreachfactory.py`, `src/providers/heyreach.py`,
  `src/seatledger.py`, or `src/linkedinstate.py`.
- **No prospect PII** in any committed file. Profile URLs are truncated to
  30 characters in reports.
- **No fixtures.** The tests exercise the check's logic with constructed data;
  the live run reads the provider.

## What would make this a false pass

- Calling a reply or an enrollment ours because it is on a seat we use.
- Comparing windows without timezones.
- A check keyed on `heyreach_lead_id` (zero contacts carry it).
- Measuring the note template instead of the rendered note.
- Treating a placeholder note as an approved one.
- A campaign with zero leads reported as clean.

## Live run owed

This worktree has no access to production `work/` or live HeyReach reads.
The live run against all 33 campaigns, with the per-campaign table, the
window overlap, the custom field diffs, the seat caps, the collision
reports, and the longest rendered notes, is owed from Claude's worktree.

The check is built, the tests are green, and the constructed failures are
demonstrated. The live evidence is the next step.
