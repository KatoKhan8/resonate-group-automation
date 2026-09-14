# Context reset checkpoint, 2026-09-14

Written at the end of the overnight run, immediately before a context reset.
Everything below was measured on this date against the repository or a
provider. Nothing is inferred from a plan.

Read this with `docs/CLAUDE-HANDOFF.md`, which carries the longer reasoning.
This file is the state.

---

## CURRENT PRODUCTIVE INVENTORY

    domains in the estate                                    300
    icp_pass* (structural verdict)                           113
    verified sendable contacts on those                       55
    accounts with a verified contact AND a usable name        53

    of those 53:
      already covered by the client's own campaigns           38   (hold 16, stop 22)
      TRUE NET-NEW, collision ALLOW                           15
      estate unreadable                                        0

    of those 15:
      in the staged cohort, all five steps clean              9
      excluded, copy not yet clean                            6

    email drafts stored across the estate                    149
    LinkedIn notes stored                                     194
    approved steps                                            238

**The 38 is the number that changes planning.** Any "qualified accounts"
figure that does not subtract the client's estate describes inventory nobody
may work. The bottleneck was never ICP, contact discovery or drafting - all
three now produce more than the estate can absorb.

---

## EXISTING-ESTATE COLLISION

**What was discovered.** Nineteen contacts were staged into EmailBison 481.
The provider refused five. Of the fourteen that attached, **nine were already
in the client's own campaigns 327 and 352** - one `in_sequence` (being
emailed at that moment), one `stopped` (the state a reply or unsubscribe
leaves), the rest `sequence_finished` or `bounced`. Nothing in this system
objected. `grep -c collision src/bisonfactory.py` returned **0**.

It was a gate never REACHED, not a gate that failed. `executionguard.
authorize()` consults collision; `_ensure_leads` never obtains an
Authorization. `eligibility.decide` returned `eligible, reasons=[]` for the
`stopped` contact and is not broken either - collision state must be fetched
from the provider and passed in, and the staging path fetched none.

**What was fixed** (TASK-015, integrated). `_ensure_leads` now calls
`collision.check_account` + `account_policy` per domain before any lead
write, and refuses by contact and reason. Verdicts are `account_policy`'s
own, not invented:

    in_sequence        STOP    blocked
    stopped            HOLD    blocked
    bounced            HOLD    blocked
    sequence_finished  ALLOW   may pass   (history is not a live conflict)

It FAILS CLOSED: an unreadable estate refuses the stage - *"a lead that
cannot be checked cannot be cleared"*.

Also (TASK-010, integrated): `_ensure_leads` consults
`killswitch.workspace_state` before any lead write, and re-reads provider
campaign status FRESH immediately before attaching rather than trusting
`_ensure_stopped` four calls earlier.

**Remaining invariant.** All fourteen colliding/divergent leads are `stopped`
at the provider, confirmed from membership. Tests:
`tests/test_staging_refuses_colliding_contacts.py`,
`tests/test_lead_writes_respect_the_killswitch.py`.

---

## COPY / SEQUENCE

**The finding.** 60 of 65 staged email steps repeated another step in their
own sequence. Three consecutive emails to 28 ROW opened with the identical
sentence; 23 shared distinctive words between em1 and em4.

**Root cause, and it was not the model.** `already_sent` reads the durable
event log, `touch.CONFIRMING_EVENTS` requires a confirmed touch, and nothing
has ever been sent - so it is EMPTY when writing em1, em3 and em5 alike. Each
of the five emails was written blind to the other four. The ladder gives every
rung a different job and `step.purpose` reaches the prompt correctly; both
were verified before blaming the model.

**Fix status: DONE** (TASK-017, integrated). `siblings_block` shows the other
stored drafts for this contact on this channel. `sent_so_far` is UNCHANGED
and must stay so - it is the only thing that licenses "as I mentioned".

**Does the full 5-step cadence now see prior generated siblings? YES**,
measured on `acqcom-com`:

    writing em1: sees ['em2','em3','em4','em5']
    writing em3: sees ['em1','em2','em4','em5']
    writing em5: sees ['em1','em2','em3','em4']
    already_sent when writing em3: []        <- still empty, correctly

**Tests.** `tests/test_siblings_block.py`; the pair asserting siblings reach
the prompt while `already_sent` stays empty is what keeps the two meanings
apart. "as I mentioned" is still refused by `claims` and `lint`.

**A second fix the same finding needed.** The quality gate counted the
prospect's own company name as repetition - every message in a sequence names
that company. `acqcom-com`: two colliding pairs with "acqcom/digital/
marketing" counted, ZERO with them discounted. `repetition_across_rungs` and
`gate` now take an `ignore` set.

---

## CLAIMS

**The finding.** 26 stored drafts asserted things the record does not
support. EmailBison lead 203708 carried the subject *"Final note on our
previous discussions"* for a contact this system has never written to.

**Two separate failures let it through.**

`claims.check` ran in exactly ONE place - `executionguard`, at send time.
`generate.draft` called `lint.check` and nothing else. Meanwhile
`claims.prior_contact` WAS used in `generate` - to tell the prompt whether
prior contact existed, and never to check whether the answer was respected.

And it would have passed even at send time. The RELATIONSHIP patterns listed
those nouns singular and `\b` will not match inside "discussions", so *"our
previous discussion"* was refused and *"our previous discussions"* sailed
through. One letter.

**Fix status: DONE.** `claims.check` runs beside lint in `draft()` against
the same trial record; `plan` re-plans a stored draft that makes an
unsupported claim; the plural gap is closed with tests that *"most agencies we
speak to..."* and *"I will keep the email short"* stay clean.

**Regeneration status.** The nine-record cohort is fully regenerated and
carries ZERO unsupported claims across all 45 steps.

**Remaining unsafe drafts.** 17 unsupported-claim drafts remain in the wider
estate, all on records the collision gate BLOCKS, so none can be staged. They
will be regenerated when those accounts become workable.

---

## EMAILBISON

**Campaign 451** - the canary, and the only scheduled live action anywhere.

    status            active
    leads             1
    sequence          1 step, wait 3
    scheduled email   1, status `scheduled`, 2026-09-14T16:24:00Z
    sent_at           None      opens 0      replies 0

The scheduled time MOVED once during the night, 13:19Z -> 16:24Z, with
nothing staged or restaged in between. **A `scheduled_date` on this provider
is an intention, not a commitment.** Do not report it as "sending at X".

**Campaign 481** - the production campaign.

    name       RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - BUYER - LIHEAVY-V1
               [productive/productive-email-liheavy-v1]
    status     paused
    sequence   5 steps, waits 3 / 4 / 4 / 9 / 1, all active
    senders    2736, 2737          schedule Mon-Fri 09:00-17:00 Europe/Zagreb
    cap        20/day              scheduled emails 0
    leads      23  =  9 sending_paused  +  14 stopped

The nine live leads are the cohort. Each carries `subject_1`..`subject_5`,
`body_1`..`body_5`, and `record_id`/`contact_key`/`client` for reply
attribution - and NO unnumbered pair, which is the one-shape-per-campaign
property.

The fourteen stopped are every lead that must not receive anything: nine that
collided with the client's estate, one whose record could no longer reproduce
what was staged, four whose copy fails the quality gate.

**5-step production campaign status: BUILT AND VERIFIED.** Read back from the
provider, not asserted.

**Lead population status: DONE for the cohort.** 9 of 9.

### THE BLOCKER

`EMAIL_ACTIVATE` is **not** in `providerwrites.SUPPORTED`. 481 cannot send.

    SUPPORTED = heyreach.pause, bison.pause, bison.stop_lead,
                bison.create_campaign, bison.set_sequence,
                heyreach.set_sequence

To activate:

    1. add EMAIL_ACTIVATE to SUPPORTED in src/providerwrites.py
    2. bison.resume_campaign(481, expect_leads=9)

**`expect_leads=9` IS MANDATORY.** A resumed campaign sends to EVERY lead it
holds and 481 holds 23. `resume_campaign` refuses if the provider's count
disagrees with what the caller expects; passing the wrong number is how a
campaign meant for nine reaches twenty-three. The fourteen stopped ones should
not send, but the count guard is the thing that proves the caller understood
what is in there.

A smaller first rung needs no code change at all:
`bison.set_limits(481, name, emails_per_day=1)` paces it to one person a day.

---

## HEYREACH

**Campaign 599020** - provider truth:

    status    DRAFT
    seat      174892          listId  None          leads  0
    sequence  24 nodes: CHECK_IS_CONNECTION 1, CONNECTION_REQUEST 1,
              MESSAGE 7, VIEW_PROFILE 4, FOLLOW 1, END 10
    "NOT APPROVED COPY" markers: 0      "must not be started": 0

Real approved copy, written through the sealed door with a
`/campaign/GetCampaignSequence` readback.

**Real leads present: NO. Zero.** Activation status: cannot be activated -
`Resume` and `StartCampaign` are deliberately absent from `WRITE_ROUTES` and
asserted absent by the seals.

**AddLeadsToCampaign status.** Built and proven offline, NOT enabled.
`/campaign/AddLeadsToCampaignV2` is on `heyreach.WRITE_ROUTES`;
`LINKEDIN_ADD_LEAD` is **not** in `SUPPORTED`. The operator authorised
enabling it after review for verified Productive leads; that review is done
and the route has not been crossed.

Honest unknowns for the first live call, from TASK-009: the success response
body shape, what a duplicate returns, what a rejection returns, and whether
it is atomic or per-lead. The verdict comes from the readback either way.

**TASK-009: DONE and integrated.** **TASK-013: DONE and integrated** -
`src/heyreachfactory.py` maps `li1`..`li6` onto the graph's roles.

Two facts from TASK-013 worth carrying:

- The graph has FOUR message slots and the cadence names five. `li5` and
  `li6` have no position. Four message opportunities is exactly the
  operator's spec; it is `productive_li_heavy_v1` that carries one more than
  the provider graph can express. The absence is REPORTED in the plan's
  `touch_report`, not silent.
- The InMail branch is OMITTED by default and the report always says which.
  `include_inmail=True` is opt-in and refuses without approved InMail copy.

---

## QUALITY

**The staged cohort of 9 is FULLY CLEAN.** All 45 email steps pass lint,
claims and quality. Verified per record immediately before this checkpoint.

The earlier "4 of 13 failing" is superseded: the cohort was narrowed to the
nine that pass, and the four were dropped.

**Six collision-clean accounts are NOT in the cohort** and are the work
queue:

    28row-com           4 steps, em5 missing, 4 failing quality
    csquaredsocial-com  5 steps, 5 failing quality
    ethoscreate-com     5 steps, 5 failing quality
    roaringmedia-co     5 steps, 5 failing quality
    semcasting-com      5 steps, 5 failing quality
    viralityllc-com     4 steps, em4 missing, 4 failing quality

Every failure is `repetition_across_rungs`. Two also have a missing step:
`28row-com`'s em5 and `viralityllc-com`'s em4 will not clear on the current
model - em5's rung asks for a close-the-loop message against a 40-word floor,
and em4's asks for "the shortest message in the sequence". The rules were NOT
widened.

**Convergence, with the gate refusing at store time and feeding the reason
back:**

    pass 0   60 of 65 steps failing
    pass 1   40 of 65
    pass 2   30 of 65
    pass 3   20 of 65,  9 records fully clean

Further passes on the six should continue to converge. `LLM_MODEL` is
`openai/gpt-4.1-mini`; `gpt-4o-mini` produced 5 of 65 clean and failed em5 six
times running.

---

## TESTS

Measured on the settled tree, `py -3 scripts/run_suite.py --timeout 2400`,
exit code read from unittest rather than from a pipe:

    TOTAL               8291
    PASS                8241
    FAIL                  22
    ERROR                  7
    SKIP                   5
    expected failures     16
    wall clock          1381s
    exit_code              1

**NOT GREEN.** 29 tests are failing or erroring. That is down from **134** at
the start of this run, which is the first time anybody had seen the number at
all.

Four of the 22 were seals that the `LINKEDIN_SET_SEQUENCE` enablement broke
and that I had missed when updating the others -
`test_the_write_layer_is_still_sealed`,
`test_the_write_allowlist_is_exactly_the_stop`,
`test_nothing_is_supported_until_it_has_actually_worked_once`,
`test_and_nothing_else_came_with_it`. **Fixed after the run**, each updated
deliberately with the reason, plus a new test asserting directly that the
four verbs which CAN reach a person - `heyreach.add_lead`,
`heyreach.activate`, `bison.add_lead`, `bison.activate` - are all still
sealed. 95 write-layer tests green.

So the number to expect on the next full run is roughly **25**, not 29. It
has not been re-run since; do not claim otherwise.

Known remaining clusters, none of them a regression from tonight:

    test_fixture_hygiene          3   real names/domains in fixtures
    test_e2e                      4   seven-step cadence expectations
    test_preproduction            2   same
    test_personalization_e2e      1
    test_the_cadence_reacts...    2   the generic hold-code defect (P1)
    test_mutation_anchors         1
    test_waterfall                1

---

## QWEN

    completed and integrated   12   TASK-001 003 007 008 009 010 011 013
                                    014 015 016 017
    currently running           0
    queued                      5   TASK-002 004 005 006 012
    commits awaiting review     0

Every commit was reviewed before merge. **Four were corrected on review**: a
LinkedIn-only angle rule applied to email (it failed the human-approved
canary), a canonical campaign id used as a provider id, a report reading
state off a stale record, and generated logs declined twice. Two task
findings were carried as honest open defects rather than papered over.

---

## OPEN P0

1. **`EMAIL_ACTIVATE` is not in `SUPPORTED`.** 481 cannot send. Requires the
   one-line change and `expect_leads=9`. This is an operator decision, not an
   engineering one.
2. **Six collision-clean accounts are not campaign-ready** - all failing
   `repetition_across_rungs`, two also missing a step that will not clear on
   the current model.
3. **`LINKEDIN_ADD_LEAD` is not in `SUPPORTED`.** HeyReach 599020 holds zero
   leads and cannot hold one. Reviewed and authorised; not crossed.

## OPEN P1

- Four tests fail in `test_the_cadence_reacts_to_what_the_prospect_did`, all
  pre-existing and behavioural rather than fixture: the state machine answers
  a generic `linkedin:step_requirement_unmet` where
  `ls.HELD_REQUEST_OUTSTANDING` exists and nothing produces it.
- One expected failure in `test_linkedinstate_redteam`: an already-connected
  person's `li1` returns WAIT instead of SKIP, because the Open Profile
  alternative names an unproven capability.
- `test_a_finished_campaign_with_no_reply_still_authorizes` - a real policy
  disagreement between the account-collision gate and the test, on a send
  path.
- Four cost estimators multiply by `cadence.GENERATED_KEYS`, which still
  reads two generated emails while Productive generates five and six notes.
- `sender_id` null on all 285 sender rows blocks per-human attribution.

---

## PRODUCTION PRIORITY AFTER RESET

In this order:

1. **Preserve and observe campaign 451's provider truth.** It sends at
   2026-09-14T16:24Z and is the first real send this system will have made.
   Do not mutate it to observe it. Record `sent_at`, `status`, opens,
   replies, and whether the scheduled time moved again.
2. Fix the remaining P0s.
3. Validate and regenerate clean 5-step copy for the six excluded accounts.
4. Finish campaign 481's provider-ready state.
5. Finish the HeyReach real-lead path.
6. Create provider-visible Productive production campaigns.
7. Progressively expand live cohorts, on evidence rather than a timer.
8. Continue processing Productive inventory in parallel throughout.

## NEXT SINGLE BEST ACTION

Observe campaign 451's send at 2026-09-14T16:24Z and record what the provider
says afterwards. Confirmed touches are zero across this entire system; that
one send is the evidence every promotion decision is currently waiting on,
and it arrives without anybody doing anything.
