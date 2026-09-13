# TASK-009 - A person can enter a HeyReach campaign

## GOAL

Implement `AddLeadsToCampaign` on HeyReach, behind the sealed write door,
with the full test set below. **Build and prove the mechanism. Do NOT enable
it in production and do NOT call it against the live provider.** Claude
enables the route and runs the first real cohort.

## WHY IT MATTERS

There is no way to put a person into a HeyReach campaign today. `WRITE_ROUTES`
is seven routes and not one of them adds a lead; every `AddLeadsToCampaign`
spelling is deliberately absent AND asserted absent by the seal tests, beside
`Resume` and `StartCampaign`. That was a product decision on the record: a
campaign can be built and left in DRAFT, it cannot be started, and no person
can be put into one.

The operator has explicitly authorised crossing it, for verified Productive
leads into the Productive campaign, AFTER review and after every test below
passes. That authorisation is the reason this task exists and it is also its
boundary: it authorises a route, not a habit.

## CURRENT CONTEXT

`src/providerwrites.py` is the single door. `OPERATIONS` declares
`LINKEDIN_ADD_LEAD` as `("linkedin", True, ...)` - channel, **prospect-facing**,
and a reason it is unsupported: *"the URL is named in
heyreach.add_leads_endpoint but no successful response has ever been read;
adding a lead to a RUNNING campaign is prospect-facing because the sequence
acts on it immediately."*

`SUPPORTED` is `(LINKEDIN_PAUSE, EMAIL_PAUSE, EMAIL_STOP_LEAD,
EMAIL_CREATE_CAMPAIGN, EMAIL_SET_SEQUENCE)`. `LINKEDIN_ADD_LEAD` is not in it
and **you must not add it.** Claude does that, separately, after review.

`heyreach.add_leads_endpoint()` already names a URL. Nobody has read a
successful response from it. Establishing the real request shape - and
recording what was actually observed rather than what was hoped - is most of
this task.

### The cautionary precedent, and read it before you design anything

`bisonfactory._ensure_leads` calls `bison.create_lead` and
`bison.attach_leads` DIRECTLY. It does not go through
`providerwrites.perform`. So the one prospect-facing EmailBison operation has
no killswitch check, no action-ledger reservation and no write-door
classification - while `EMAIL_ADD_LEAD` is declared prospect-facing and is
not in `SUPPORTED` either. The factory gets away with it because
`_ensure_stopped` runs first and a stopped campaign sends nothing, but the
declared safety model and the code disagree. That is TASK-010.

**Do not copy that shape.** Every HeyReach lead write goes through
`providerwrites.perform` with a readback, or this task is not done.

## SCOPE

1. Establish the request contract from the adapter, the fixtures and the
   vendor's own documented shape. Where you cannot establish something
   without a live call, say so explicitly and leave it as a question for
   Claude - do not guess a field name and do not invent a response shape.
2. Implement the verb in `src/providers/heyreach.py`, added to
   `WRITE_ROUTES`. Expect the seal tests to fail; update them to assert the
   new set deliberately, and say in your result that you did and why.
3. Route it through `providerwrites.perform` with a real `readback` -
   `/campaign/GetLeadsFromCampaign` is already wired and is what proves
   membership. A 200 is not a verdict here any more than it is on the
   schedule route.
4. Leave `SUPPORTED` untouched.

## TESTS REQUIRED

Every one of these, against a fake transport, and each must be shown to fail
when the guard it covers is removed:

- **provider contract** - the request shape, and that a response which does
  not confirm membership is not read as success.
- **idempotency** - the same lead twice adds one membership; a re-run after a
  partial failure adds nothing new.
- **duplicate prevention** - a lead already in the campaign is not added
  again, established from provider membership rather than from local state.
- **tenant / workspace isolation** - a lead belonging to another client
  cannot enter this client's campaign; `organizationUnitId` is checked
  against the client's configured `org_unit`, and a mismatch REFUSES.
- **wrong campaign** - leads intended for campaign A never reach campaign B,
  including when both are staged in the same run.
- **restart / retry** - a crash between the request and the readback leaves a
  state the next run can classify: recovered, or refused as ambiguous. Never
  a silent second add. `UNKNOWN` is never retryable.
- **readback verification** - membership is read back and compared against
  exactly the leads asked for; a partial add is reported as partial.
- **killswitch** - a tripped killswitch refuses the write.

## FILES ALLOWED

`src/providers/heyreach.py`, `src/providerwrites.py` (the `OPERATIONS` entry
and its reason text only - NOT `SUPPORTED`), `tests/**`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`SUPPORTED` in `src/providerwrites.py`. `work/**`. `config/**`. Every other
`src/` file.

## PRODUCTION CONSTRAINTS

**ZERO live HeyReach calls.** Not one. The workspace holds 48 campaigns
belonging to the client and two of ours; a probe against any of them is a
real action against a real estate. Campaign 599020 and 594061 are ours and
are still off limits to you. There is no `config/.env` in your worktree, so
this is structural - if you find yourself needing a key, you have left your
lane.

## EXPECTED OUTPUT

The verb, the door wiring, the tests, and a written contract section stating
for each field: established from what, or UNKNOWN and what single live call
would settle it.

## DONE CONDITION

Claude can read your contract, enable `SUPPORTED` in one line, and run a
bounded real cohort knowing exactly which parts were proven offline and which
are being established for the first time on that call.

## RESULT

STATUS: TODO
COMMIT SHA:
TESTS:
FILES CHANGED:
FINDINGS:
RISKS:
RECOMMENDED CLAUDE ACTION:
