PRIORITY: P0
DEPENDS:

# TASK-296 — eleven campaigns legitimately hold three steps

## DISPATCH NOTE

Lane F, the standing QA suite. **The per-campaign EmailBison check:
`scripts/qa/check_campaign_bison.py`.** In the minimum subset for **today's
128**, which go onto new four-step campaigns **502 and 503** (501 is consumed
by the stop-test campaign).

**READ `docs/QA-LANE-F-CONTRACT-2026-09-25.md` FIRST.**

`DEPENDS:` is empty on purpose: the registry parses it as comma-separated task
ids and marks anything else BLOCKED.

## The question this answers

**Is the campaign these leads are about to be attached to actually built — at
the provider, right now — to send what we think it will send?**

Every readback this project has trusted and then found wrong was of this
shape: `active`, `in_sequence` and `scheduled` were each read as a send;
campaign 485 was left at **0 steps** because a final `wait_in_days` of 0 made
`set_sequence` raise; 76 blank emails went out of a campaign that looked fine.

### The eight rules, operator's words

    campaign_exists          by ID at the provider, not by name — ISSUE-036
    step_count_matches       the provider sequence step count equals THIS
                             campaign's own stored `cadence_steps`
    templates_use_only_carried_variables
                             every step template references only variables the
                             lead actually carries
    sender_attached_and_connected
                             at least one sender, and its status is Connected
    schedule_and_limits_set  a sending window and daily limits, both read back
    no_settled_blank_rows    zero settled blank rows in the queue
    not_paused               the campaign is not paused
    id_matches_our_registry  the provider id equals the one in
                             `work/campaigns.jsonl`

## What to build

`scripts/qa/check_campaign_bison.py` plus its tests.

**The read surface that already exists. Use it; do not re-implement it:**

    bison.campaign(id)            bison.sequence_steps(id)
    bison.schedule(id)            bison.sending_schedule(id, day)
    bison.campaign_senders(id)    bison.sender_emails(expect_workspace=…)
    bison.scheduled_emails(id)    bison.campaign_lead_ids(id)
    bison.campaign_lead_count(id) bison.variables_of(lead)
    bison.custom_variables()      bison.LEAD_VARIABLES
    campaigns.load() / campaigns.require(id, rows)
    emptyrender.scan(rows) / classify_row / summarise
    bisonfactory._sequence_steps(configured, cadence_steps)

**The five rules that need care, and why:**

1. **`campaign_exists` is a read BY ID.** ISSUE-036:
   `find_campaigns_by_name` cannot find a campaign this system just created.
   A name lookup that comes back empty is not evidence the campaign is
   missing. Use `bison.campaign(id)`.
2. **`step_count_matches` compares against THAT CAMPAIGN'S OWN stored
   `cadence_steps`, never a global constant.** Option A is chosen: new
   campaigns get four steps, **485-500 stay three-step**, no stored
   `cadence_steps` row is rewritten. **Eleven rows legitimately hold three
   while new ones hold four.** A check comparing to 4 refuses eleven correct
   campaigns; a check comparing to `copylint.STEPS_EXPECTED` (which is **5**)
   refuses all of them. Read the row, then read the provider, then diff.
   And diff the **keys as SETS, both directions** — not the counts. `len == len`
   compares equal while the sets differ, which is how a half-applied change
   reads as complete.
3. **`templates_use_only_carried_variables` is the one that catches a blank
   before it renders.** Extract the `{VARIABLE}` names from every step
   template the provider returned, and diff against the variables the leads
   for this campaign actually carry (`bison.variables_of` on real leads, and
   `bison.custom_variables()` for what the workspace has defined at all).
   **Both directions**: a template naming a variable no lead carries sends a
   gap; a lead carrying a variable no template names is wasted render and is
   how `body_4` came to exist while nothing read it. Note the step→variable
   mapping is positional and **the step key is not the variable number** —
   em4 reads `{BODY_3}`, em5 reads `{BODY_4}` (TASK-295 has the table).
4. **`sender_attached_and_connected` needs the sender's STATUS, not its
   presence.** `bison.fetch_events` carries an `EMAIL_ACCOUNT_DISCONNECTED`
   event that currently normalises to `unknown` with no alert on it — a sender
   mailbox that stopped working, attached and useless. Attached is not
   Connected. Also check the workspace: `expect_workspace` exists on
   `sender_emails` because `workspace_id` is accepted and discarded by every
   list route on this API, so a caller can believe it scoped a read and be
   holding another client's estate.
5. **`no_settled_blank_rows` is why 496/497/498 still hold 63 stopped leads.**
   All three carry settled blank rows from the incident (11/9/4) and
   re-pushing to them is refused — ISSUE-035. Read the queue with
   `bison.scheduled_emails(id)` and classify with `emptyrender.scan`. A
   campaign with zero scheduled rows at all is **not** a campaign with zero
   blanks: it is VACUOUS and must be reported as such.

**Order campaigns by PROVIDER ID, numerically.** `created_at` is null on the
campaigns that actually send, so any report sorted by it silently drops or
reorders the live ones.

Write `docs/QA-CAMPAIGN-BISON-2026-09-25.md`.

## The acceptance bar

- **Run against all live EmailBison campaigns, not only 502 and 503** — the
  estate is 10 active, 1 archived (495), 1 new empty (500), and the check's
  value on day one is the set of campaigns that fail it. Report every campaign
  id with its verdict; a check run on two campaigns cannot be said to have
  been run.
- **`step_count_matches` reports the stored `cadence_steps` and the provider's
  step keys side by side, per campaign, as SETS diffed both directions.**
  Expect eleven campaigns at three steps and the new ones at four, and say so
  explicitly — that is the correct answer under Option A, not a failure.
- **`templates_use_only_carried_variables` reports the two-direction variable
  diff per campaign**, named. Counts alone are rejected.
- **A campaign with zero scheduled rows is VACUOUS for the blank rule**, not
  PASS, and the result says which campaigns those were.
- **The offending ids are campaign ids and, for the blank rule, the offending
  queue row ids.** A person must be able to open them at the provider.
- One constructed failure per rule, shown firing — including a campaign whose
  provider step count is right and whose step KEYS are wrong, which the count
  comparison passes and the set diff catches.
- **`subjects == 0` exits 2 with a stated reason.**
- Suite baseline **by name**, both directions, against `HEAD~1`.

## What evidence counts

- The provider's own named response fields, quoted: the schedule object's
  `days`, `start`, `end`, `timezone`; the sender's status string; the sequence
  steps as returned; the campaign's paused/active field as returned. **Print
  the object's keys.** `None` from a `.get()` is not evidence of emptiness —
  a session reported five empty steps and refused a campaign because it asked
  for `subject`/`body` on an object whose keys are
  `email_subject`/`email_body`.
- `work/campaigns.jsonl` rows read from a **named copy of production's
  `work/`**, with mtime and row count.
- The per-campaign table, ordered by provider id numerically.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Comparing step COUNTS instead of step KEY SETS.** `3 == 3` compares equal
  while the keys are `em1, em2, em3` on one side and `em1, em2, em4` on the
  other. Diff the sets, both directions, print the names.
- **A global expected step count.** Eleven campaigns hold three and are
  correct. This is the whole point of Option A and a check that does not know
  it will refuse the estate.
- **`find_campaigns_by_name` returning empty read as "the campaign does not
  exist".** ISSUE-036 says it cannot find a campaign this system just created.
- **Attached read as Connected.** A disconnected mailbox is attached.
- **Zero scheduled rows read as zero blanks.** That is the ISSUE-041 shape: a
  check that passes because the thing it checks is absent. 496/497/498 have
  real blanks; a campaign with an empty queue has no evidence either way.
- **Believing a paused campaign is safe to push to.** It is a finding, not a
  detail: the campaigns land stopped by design and going live is a separate
  operator decision, so "not paused" must be checked against the intent
  recorded for THAT campaign, and the check must say which intent it used.
- **Sorting the report by `created_at`.** It is null on the campaigns that
  send. Sort by provider id, numerically.
- **A workspace-blind read.** `workspace_id` is accepted and discarded by
  every list route; `GET /users` via `bison.bound_workspace()` is the only
  route that states which workspace the credential is bound to. Assert it
  before believing any list.
- **Fixtures.** ~30 tests here were green against three Apify actor ids that
  answer 404 because the cassette and the code agreed with each other. Read
  the provider.
- **Any provider write.** No `set_sequence`, no `set_schedule`, no
  `set_limits`, no `pause`, no `resume`. If the check finds a campaign
  misconfigured, that is a TASK, not a fix.

## Boundaries

- **READS ONLY at EmailBison.** `src/providerwrites.py` `SUPPORTED` is not
  consulted by anything in `scripts/qa/`.
- **Do not edit `src/bisonfactory.py`** (lane D), `src/cadence.py`,
  `config/clients/productive.yaml`, `scripts/batch1_build.py` (lane B), or
  `src/providers/*` (nobody's, in this lane).
- Do not edit `scripts/*_watch_loop.py` or anything under `work/` except
  `work/qa/`.
- Production `work/` is not yours; `--workspaces` a named copy.

## Files

    ALLOWED    scripts/qa/check_campaign_bison.py,
               tests/test_step_counts_agree_while_the_keys_do_not.py,
               docs/QA-CAMPAIGN-BISON-2026-09-25.md
    FORBIDDEN  src/bisonfactory.py, src/cadence.py, src/emptyrender.py,
               config/clients/productive.yaml, scripts/batch1_build.py,
               src/providers/*, scripts/*_watch_loop.py,
               work/* except work/qa/, config/.env

## Result block

    STATUS:
    BRANCH:
    COMMIT SHA:
    TESTS:
    FILES CHANGED:
    CAMPAIGNS CHECKED (every live id, ordered by provider id numerically):
    PER-CAMPAIGN TABLE: rule verdicts, offenders:
    STORED cadence_steps vs PROVIDER STEP KEYS, SET DIFF BOTH DIRECTIONS:
    THE ELEVEN THREE-STEP CAMPAIGNS, NAMED, AND WHY THAT IS CORRECT:
    TEMPLATE VARIABLES vs LEAD VARIABLES, BOTH DIRECTIONS, PER CAMPAIGN:
    SENDER STATUS PER CAMPAIGN (attached count / Connected count):
    SCHEDULE AS THE PROVIDER RETURNED IT, PER CAMPAIGN:
    SCHEDULED ROWS / SETTLED BLANKS PER CAMPAIGN (and which were VACUOUS):
    bound_workspace() ASSERTED?:
    THE CONSTRUCTED FAILURES AND THEIR MESSAGES:
    WORKSPACES COPY USED (path, mtime, rows):
    SUITE BASELINE vs HEAD~1 — new/gone BY NAME, both directions:
    FINDINGS:
    RISKS:
    RECOMMENDED CLAUDE ACTION:
