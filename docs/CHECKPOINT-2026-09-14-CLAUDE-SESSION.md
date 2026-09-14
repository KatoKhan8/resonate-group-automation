# Session checkpoint, 2026-09-14, after the context reset

Everything here was measured today against the repository or a provider.
Read it after `docs/CONTEXT-RESET-2026-09-14.md`, which it CORRECTS in four
places.

---

## THE HEADLINE

**Three prospect-facing defects were found and fixed, all of them one
authorised call away from reaching real people, and none of them visible from
a green test run.**

1. HeyReach campaign 599020 carried ONE contact's personalised copy for
   fourteen records. "hi jacob... at &Partner?" would have gone to thirteen
   other people at thirteen other companies.
2. The already-connected branch of that graph sent the identical sentence
   twice, three days apart.
3. Eight of the fifteen contacts that campaign would have pushed carried
   LinkedIn copy asserting things the record does not support, including
   "our previous discussions" to a stranger.

All three lived in code with **no tests at all** - not failing tests, none.
`heyreachfactory._plan` and `stage` had zero coverage while 36 tests around
them covered the mapping, the refusals and the graph shape.

## WHAT WAS BLOCKED, AND IT IS NOT THE REPOSITORY

Three workstreams could not run in this session because the Claude Code
permission classifier refused them. They are environment permissions, not
code:

    qwen.cmd                        dispatching the parallel worker
    py -3 -m src.generate --live    any copy generation
    heyreachfactory.stage(live=True)  any live provider WRITE

Read-only provider calls, offline tests, commits and pushes all ran normally.
So: no Qwen task was dispatched, no copy was regenerated, and the corrected
HeyReach sequence has NOT been written to the provider. Everything else in
this document was done.

To unblock, the operator adds Bash permission rules for those commands.

## CORRECTIONS TO THE CONTEXT-RESET CHECKPOINT

**1. HeyReach 599020 HAS a bound list.** The checkpoint recorded `listId
None`. Provider truth: `linkedInUserListId` **933603**, named the same as the
campaign, reporting `campaignIds: [599020]`, holding **0** items. The
substantive claim - no leads - holds. The difference matters: a campaign with
a bound empty list is one route call from holding people.

**2. "17 unsupported-claim drafts remain" was EMAIL ONLY.** The 194 stored
LinkedIn notes had never been audited. Measured today: **17 email + 26
LinkedIn = 43 unsupported steps across 20 records.**

**3. `bison.WRITE_ROUTES` enforced nothing.** It claimed "the same guarantee
`heyreach.WRITE_ROUTES` gives" and was a comment. It had already drifted -
`update_lead` writes `PATCH /leads/{id}`, a route the tuple did not name.

**4. `EMAIL_ACTIVATE`'s reason was wrong.** It read "no documented route".
The route is established: `PATCH /api/campaigns/{id}/resume` answered 200
twice on 2026-09-13. What is missing is permission, not a contract.

## PROVIDER TRUTH, read today

    EmailBison 451   active, 1 lead, 1 scheduled email
                     2026-09-14T16:24:00Z, status `scheduled`, sent_at None
                     NOT MOVED since the checkpoint. opens 0, replies 0.
                     16:24Z is 18:24 Europe/Zagreb, not 16:24 local.

    EmailBison 481   paused, 23 leads = 9 sending_paused + 14 stopped
                     5 steps, waits 3/4/4/9/1, 0 scheduled emails
                     ALL NINE LIVE LEADS CARRY CLEAN COPY - checked against
                     `variables_of(lead(id))`, the words actually held at the
                     provider, not the local store. 45 of 45 steps pass
                     claims, lead 203708 included.

    HeyReach 599020  DRAFT, seat 174892, list 933603 (0 items), 0 leads
                     24 nodes, 4 distinct message texts, all Jacob's
                     THE PROVIDER STILL HOLDS THE BAD SEQUENCE. The fix is
                     committed; writing it needs the blocked live path.

## WHAT WAS SHIPPED (8 commits, all pushed to master)

    a4043bb  EmailBison's write allowlist was a comment; make it a door
    d38e82e  EMAIL_ACTIVATE is unauthorized, not undocumented
    4f93f2f  599020 was one call from sending fourteen people Jacob's message
    d0549d1  An already-connected prospect was sent the same sentence twice
    3192153  The HeyReach sequence carries variables, not one contact's words
    2c6ae0c  _plan walked the whole estate; scope it to the campaign
    63bc446  Eight of fifteen LinkedIn leads asserted something unsupported
    dbe12e8  An approval is not a fact-check, and for email it was the only gate
    ee108bc  The fallback copy is prospect-facing and nothing guarded it

Plus `cd053ab`, the estate learning study, and `4a3fc00`, six Qwen tasks.

Every one was attacked: the guard was broken deliberately and the intended
test confirmed to fail for the intended reason. Two tests were found WRONG
this way and fixed before commit - one built its fixture per role when the
defect was per step, one proved a function worked without proving anything
called it.

## THE TWO PROVIDERS ARE NOW THE SAME SHAPE

That is the substantive architectural change. A HeyReach sequence is
campaign-level, so it carries `{connection_note}`, `{connected_1}`... and each
lead's approved words travel in `customUserFields` - exactly what EmailBison
already did with `{SUBJECT_1}`..`{BODY_5}`.

Not a new mechanism, and proven on this workspace: the client's own live
campaign 565765 uses `{FIRST_NAME}`, `{COMPANY}` and a custom `{Icebreaker}`
today. `refuse_unsupported_sequence` refuses the push unless EVERY lead
supplies EVERY variable - traced end to end: a complete lead accepted with
zero hazards, a batch one lead short of `connected_4` refused by name.

The cadence-to-graph mapping changed with it. Each role now resolves to
exactly one step and no branch repeats:

    not connected yet    li1 invite -> li2 -> li3 -> li4
    already connected    li2 -> li3 -> li4 -> li5    (no invite needed)

`li5` finally has a position. `li6` still has none, reported in
`touch_report` rather than dropped silently.

## WHAT THE CLIENT'S OWN ESTATE SAYS

Full study in `docs/ESTATE-LEARNING-2026-09-14.md`. 237,935 emails, 48,606
people, 2,139 replies.

    steps   contacted   reply%
        1        3163     0.85
        8       17690     8.49
       22        2422     2.23
       35        4994     1.44
       44       20337     2.38

Our campaign 481 runs five. Same-copy comparison - 334/335 use the SAME first
five subjects as 327/328 at 22 steps instead of 8 - gives 2.23% against 8.39%.

**Opens are zero on all 22 campaigns** (`open_tracking: false`).
**Unsubscribes are zero on all 22** (`can_unsubscribe: false` - no link, so no
signal; opt-out arrives only as a reply). **`interested` is tagged 17 times**
across 2,139 replies. So the operator's optimisation hierarchy cannot be
measured above "replied at all" today.

A partial classification of the real replies (699 of them so far, rules only,
no model) says the 4.40% reply rate is not what it looks like: 35% match no
rule at all, 22% are negative, 13% are unsubscribe requests in words, 14% are
referrals, and 5% are positive.

## THE CAMPAIGN-READY FUNNEL, recomputed with today's gates

Measured across all 300 Productive records, applying the gates as they now
stand - including the two added today:

    productive domains                       300
    icp_pass*                                113
    + a verified sendable contact             54
    + a usable company name                   45
    contacts with 5 approved email steps      20
      EMAIL-READY (no repeat, no claim)        8
    contacts with li1-li5 approved + URL      13
      LINKEDIN-READY (no claim)                9

    ready on BOTH channels                     7 records

**The bottleneck is copy, and copy is the thing that cannot be generated in
this session.** Forty-five accounts are qualified, have a verified sendable
contact and a usable company name. Twenty of them have five approved email
steps. Eight survive the quality gates.

So the gap between 45 and 8 is entirely generation and regeneration:

    25 qualified accounts have no five-step email copy at all
    12 of the 20 that do have copy fail repetition or claims

That is what unblocking `generate --live` is worth - roughly 45 email-ready
accounts instead of 8, against a client estate that will only absorb the
collision-clean subset of them anyway.

The seven records ready on both channels are the natural first account-based
cohort, since `ACCOUNT-OUTREACH.md` makes the account the unit:

    (the seven account ids are in `work/queue.jsonl`, which is
    gitignored. A client's prospect list does not belong in a tracked
    file - `tests/test_fixture_hygiene` enforces that and caught this.)

A caution on one number: "usable company name" here is `name != domain
prefix`, which is close to but not identical with `cadence.company_name`'s own
test. The readiness counts below it are exact; that one is indicative.

## THE SUITE, MEASURED

`py -3 scripts/run_suite.py --timeout 2400`, exit code read from unittest
rather than from a pipe:

    failures      24        (was 29 at the context-reset checkpoint)
    wall          1795.8s   (slower than the 1381s baseline - four Qwen
                             workers were competing for the machine)
    timed_out     False
    exit_code     1

NOT GREEN, and not claimed to be.

**This run started at 09:12Z, BEFORE TASK-021 and TASK-020 were integrated**,
and two of the 24 are defects those tasks fixed:

    test_validating_the_capability_is_the_only_thing_that_changes_it
    test_a_pending_request_carries_a_date_and_an_unread_one_does_not

So the tree as it stands should be near 22. That has not been re-measured and
is not being claimed.

The clusters, unchanged in character from the checkpoint:

    fixture hygiene   3   real names, client domains and non-reserved email
                          addresses in fixtures. This is a PRIVACY finding,
                          not a cosmetic one, and TASK-018 is told to fix it
                          by replacing the data rather than widening the rule
    test_e2e          8   seven-step cadence expectations, stale since the
                          cadence moved to productive_li_heavy_v1
    preproduction     2   the same
    waterfall/ledger  2
    the rest          9   assorted, classified by TASK-018

## OPEN, IN ORDER

1. **Campaign 451 sends at 16:24Z.** Do not mutate it. Record `sent_at`,
   `status`, opens, replies, and whether the time moved.
2. **Unblock the three permission-classified commands** - without them no
   copy can be generated, no Qwen task can run, and no provider write can
   happen.
3. **Write the corrected sequence to 599020.** `LINKEDIN_SET_SEQUENCE` is
   already SUPPORTED and non-prospect-facing; this replaces Jacob's words
   with variables and is strictly a safety improvement.
4. **Regenerate** the 43 unsupported steps and the 98 repeating email steps.
   Both gates now refuse them, so this is the only route.
5. **`LINKEDIN_ADD_LEAD`** - the caller is specified as TASK-019 and does not
   exist. TASK-009 built the transport and nothing calls it.
6. **`EMAIL_ACTIVATE`** - one line, then `resume_campaign(481,
   expect_leads=N)` with N read from the provider first.

## FOR THE NEXT READER

The pattern in all three defects today was the same, and it is worth carrying:
**every piece was individually correct and nothing checked what they produced
together.** The mapping was tested. The graph builder was tested. The write
door was tested. The function that assembled them into what a prospect
receives was called by nobody in any test, and that is where all three lived.
