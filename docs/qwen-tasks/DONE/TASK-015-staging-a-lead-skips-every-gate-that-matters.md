# TASK-015 - Staging a lead skips every gate that matters

## GOAL

Make `bisonfactory` refuse to stage a contact that `executionguard` would
refuse, so the collision, suppression, reply-stop and fatigue gates apply to
the act of putting a real person into a real provider campaign.

## WHY IT MATTERS - THIS ONE ALREADY HAPPENED

On 2026-09-13 nineteen Productive contacts were staged into EmailBison
campaign 481. The provider refused five of them. Of the fourteen that
attached, **nine were already in the client's own campaigns**:

    142476  bounced             in the client's campaign 327
    199963  in_sequence         in campaign 352 - being emailed RIGHT NOW
    144582  stopped             in 352, and sequence_finished in 327
    173033  sequence_finished   in 352
    + five more sequence_finished across 327 and 352

Nothing in this system objected. The provider's own refusal caught five; the
other nine went in. They were stopped by hand afterwards and campaign 481 was
paused throughout, so nobody was mailed - but the only thing standing between
those people and a second cold sequence was a provider quirk.

`PLAYBOOK.md` calls cold-sequencing a live customer the single most expensive
mistake in the motion. One of those nine is `stopped` in the client's live
campaign, which is the state a reply or an unsubscribe leaves behind.

## THE DEFECT, EXACTLY

`executionguard.authorize()` is the gate. It consults, in order: tenancy,
approval, campaign approval, readback, then a JIT re-read of eligibility,
suppression, lint, claims, fatigue AND collision - `check_address`,
`check_linkedin_profile`, `check_account`, `account_policy` - then caps,
sender health, stoppability, the ledger and the killswitch.

`grep -c collision src/bisonfactory.py` returns **0**.

`bisonfactory._ensure_leads` calls `bison.create_lead` and
`bison.attach_leads` directly. It never obtains an `Authorization`, so none
of those gates runs. `docs/CAMPAIGN-FACTORY.md` says the opposite in writing:
*"the only operations that need a full Authorization are `add_lead` and
`activate`."*

TASK-010 fixed part of this - `_ensure_leads` now consults
`killswitch.workspace_state` and re-reads provider status before attaching -
and that was the right first move. It is not the whole hole. The killswitch
answers "may this tenant act at all". It does not answer "is this particular
person already mid-sequence in the client's own campaign".

## WHY `eligibility.decide` DID NOT CATCH IT EITHER

Measured: `eligibility.decide(rec, contact, "em1", ...)` returned **eligible,
reasons=[]** for `1gslab-com/claudia-papa`, the contact whose lead is
`stopped` in campaign 352.

It is not broken. Collision state is not something `eligibility` can know
from the record - it has to be FETCHED from the provider and passed in.
`executionguard` takes an `estate` argument for exactly this, and
`nextaction.next_best_action` passes one. The staging path fetches no estate
and passes none, so the question is never asked.

That is the shape of this defect: not a gate that failed, a gate that was
never reached.

## SCOPE

1. Decide where the estate is fetched. `collision.check_account(domain,
   expect_workspace=estate)` and `collision.leads_for_domain` are the
   existing readers - use them rather than writing a second provider walk.
   Note that this costs provider reads per domain, so where it happens and
   how it is cached is a real design question; state your answer.
2. Make `_ensure_leads` refuse a contact that collision says STOP, and
   report which contact and why - the same shape as the missing-copy refusal
   already there, which names the contact and the step.
3. Decide, and write down, whether staging should require a full
   `executionguard.Authorization` or a narrower check. Arguments both ways:
   - FOR: `CAMPAIGN-FACTORY.md` already says it should, and the gates are
     one object for a reason.
   - AGAINST: `Authorization` is per-ACTION with a 60-second TTL and a
     ledger reservation, and staging twenty leads is not twenty actions. A
     token minted for a batch re-opens the window `revalidate()` exists to
     close.
   Whichever you choose, say why the other was rejected.
4. Reconcile `docs/CAMPAIGN-FACTORY.md` with what is true afterwards.

## FILES ALLOWED

`src/bisonfactory.py`, `src/collision.py` (reads only - do not change its
verdicts), `tests/**`, `docs/CAMPAIGN-FACTORY.md`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/executionguard.py` - if the guard needs changing, that is a finding and
a design conversation. `work/**`. `config/**`.

## PRODUCTION CONSTRAINTS

**ZERO live provider calls.** Campaign 481 holds fourteen leads, nine of them
deliberately `stopped`, and 451 is active with a scheduled send. Neither may
be touched. Use the fake transport the factory tests already use, and give it
a membership table so a colliding lead can be modelled.

## TESTS REQUIRED

- A contact whose address is already in another campaign in the client's
  estate is REFUSED at staging, by name, before any lead is created.
- The nine real cases above as a fixture: `bounced`, `in_sequence`,
  `stopped`, `sequence_finished`. Say which of those four states must block
  and which may pass - `sequence_finished` is not obviously the same answer
  as `in_sequence`, and `account_policy` already has an opinion. Do not
  invent a new one.
- A clean contact still stages.
- Break the check and confirm the intended test fails for the intended
  reason.

## EXPECTED OUTPUT

The refusal, the tests, your written answer to (3), and a corrected
`CAMPAIGN-FACTORY.md`.

## DONE CONDITION

A contact the client is already emailing cannot be staged into a Resonate
campaign, and a test proves it without a provider being present.

## RESULT

STATUS: DONE
COMMIT SHA: db77574
TESTS: 7 new tests in tests/test_staging_refuses_colliding_contacts.py, all
  passing. 89 existing factory tests also pass (updated to patch collision
  for empty estate). 96 total factory tests green.
FILES CHANGED:
  - src/bisonfactory.py: added _refuse_colliding_leads(), called in
    _ensure_leads before any lead is created
  - tests/test_staging_refuses_colliding_contacts.py: new test file
  - tests/test_staging_a_campaign_twice_builds_one.py: added collision patch
  - tests/test_lead_writes_respect_the_killswitch.py: added collision patch
  - tests/test_a_five_step_campaign_sends_five_different_emails.py: added
    collision patch
  - tests/test_two_campaigns_do_not_collide_at_the_provider.py: added
    collision patch
  - docs/CAMPAIGN-FACTORY.md: reconciled with the collision check at staging
FINDINGS:
  1. The collision check uses collision.check_account + account_policy, the
     same gates executionguard runs at send time. Account-level, because the
     account is the unit of outreach.
  2. Which states block (per account_policy, no new verdict invented):
     - in_sequence -> STOP -> block
     - stopped -> HOLD -> block
     - bounced -> HOLD -> block
     - sequence_finished -> ALLOW -> may pass (history, not live conflict)
  3. Design decision: narrower check (collision + killswitch) rather than
     full Authorization. Authorization is per-action with 60s TTL and ledger
     reservation; staging twenty leads is one batch, not twenty actions. A
     token minted for the batch re-opens the window revalidate() exists to
     close. Recorded in CAMPAIGN-FACTORY.md.
  4. The estate is fetched per domain, cached for the call duration. Each
     domain costs one paginated search; a campaign's leads typically span
     1-5 domains.
RISKS:
  - The collision check adds provider reads per domain to the staging path.
    For a campaign with 20 leads across 5 domains, that's 5 paginated
    searches. Acceptable for staging (not real-time), but worth monitoring
    if staging becomes a frequent operation.
  - An unreadable estate (CollisionUnknown) refuses staging. This is the
    right behavior ("we could not check" != "there is nothing there"), but
    it means a provider outage blocks staging entirely.
RECOMMENDED CLAUDE ACTION:
  Review the design decision about narrower check vs full Authorization.
  The task asked for a written answer; it's in CAMPAIGN-FACTORY.md under
  "WHY NOT A FULL AUTHORIZATION FOR STAGING". If Claude disagrees with the
  narrower check, the collision check in _refuse_colliding_leads can be
  replaced with a full executionguard.authorize() call, but that requires
  resolving the per-action vs batch tension.
