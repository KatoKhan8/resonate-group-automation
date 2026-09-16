# Why 484 and 485 were archived

## ROOT CAUSE

**EmailBison archives a campaign that has no sending account attached.**
Hypothesis C. Not an operator action, and not anything this repository did.

## EVIDENCE

Every campaign in this workspace, read from the provider:

    id    status      senders         leads   created -> updated
    451   completed   [3948]              1   09-13 08:37 -> 09-14 16:30
    481   paused      [2736, 2737]       23   09-13 20:11 -> 09-13 22:17
    484   ARCHIVED    []                  0   09-16 08:14 -> 09-16 08:20
    485   ARCHIVED    []                 10   09-16 08:20 -> 09-16 08:30

Four for four. Every campaign with a sender survives; both campaigns with
none were archived, about six and ten minutes after creation. The
`updated_at` on each archived campaign is the archive transition, and both
fall in that window rather than at any moment this session wrote to them.

**Ruled out, with reasons:**

  A. We archived them explicitly. There is NO archive route and no campaign
     DELETE route in `bison.WRITE_ROUTES`. The twelve routes are create,
     update, sequence-steps, attach-leads, pause, resume,
     stop-future-emails, schedule, attach-sender-emails, /leads,
     /leads/{id}, /custom-variables.
  B. One of our calls archives implicitly. 481 received the same calls -
     create, update via set_limits, sequence-steps, attach-leads, pause -
     and survived. The ONLY call 484 and 485 never received is
     attach-sender-emails. The difference is the ABSENCE of a call, not the
     presence of one.
  D. A creation / set_sequence / lead-write side effect. Same refutation:
     481 went through all three and is still paused.
  E. `scripts/provider_truth.py` ran twice in the window. It POSTs only to
     HeyReach `/campaign/GetAll` and reads HeyReach sequences. It does not
     touch EmailBison.

`archived` is already documented in `bison.py` as observed on this instance,
and it is in none of the classification tuples - not STARTED_STATES, not
STARTING_STATES, not FAILED_STATES, not NOT_STARTED_STATES. So it falls
through every branch that reads a status, which is why the activation
preflight printed it and still said PASS.

**Confidence.** Correlational across four campaigns and consistent with every
other fact. Not proven causally: nobody has watched a senderless campaign
survive the window with a sender attached, which is what the fix tests.

## WHY IT HAPPENED HERE, AND IT IS OUR ORDERING

`bisonfactory.stage` runs `_ensure_senders` BEFORE `_ensure_leads`, and
`_ensure_senders` is a no-op when the campaign row names none:

    "no senders staged: the campaign names none, and choosing an inbox would
     be choosing who a prospect hears from"

That refusal is right - picking an inbox is the operator's call - but it
leaves the campaign incomplete at the provider for as long as it takes
somebody to choose. On this provider that window is minutes, and the
provider closes it by archiving.

## SAFE FIX

Name the sender on the campaign ROW before staging, so `_ensure_senders`
attaches it during `stage()` rather than skipping. The operator authorized
sender 2736 for this cohort on 2026-09-16, so the choice is already made and
the fix is to apply it earlier in the same run.

No gate changes. No new permission. The same two authorized verbs.

## CAN 485 BE RESTORED?

Not by anything wired. There is no unarchive route in `WRITE_ROUTES`. The
only candidate is `/campaigns/{id}/update`, which `set_limits` already
PATCHes with `{name, max_emails_per_day, max_new_leads_per_day}` and no
status field - so sending a status through it is untested, and 485 holds the
canonical approved production state. Not experimenting on it.

If the EmailBison UI offers restore/unarchive, that is the cheapest path and
it preserves the verified state.

## CURRENT 485 PROVIDER STATE

    status              archived
    leads               10
    sequence steps      3
    daily cap           20
    sent                0
    senders             []
    approval fingerprints  30/30 matching, 0 stale
