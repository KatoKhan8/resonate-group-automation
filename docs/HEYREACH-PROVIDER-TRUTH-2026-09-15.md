# HeyReach provider truth, 2026-09-15

The operator could not see the expected campaigns in the HeyReach dashboard
and asked whether they had ever been created. Everything below was read from
the live HeyReach API this morning, read-only. Nothing is inferred from a
plan, a dry run, a passing test or a handoff document.

Machine-readable form: `docs/state/PROVIDER-CAMPAIGNS.json`, regenerate with
`py -3 scripts/provider_truth.py`. Committed, so a fresh session on another
machine can read it without this terminal.

---

## 1. THE ANSWER: IT EXISTS, IT IS EMPTY, AND IT HAS NEVER STARTED

    heyreach_campaign_id   599020
    name                   RESONATE - PRODUCTIVE LINKEDIN PRODUCTION V1
    status                 DRAFT
    created                2026-09-13T10:33:37Z
    startedAt              null          <- never started, not once
    lead list              933603, same name, USER_LIST
    lead count             0             <- the list is empty
    sender                 174892, Bruno Gudelj, active
    organization unit      118832
    sequence               24 nodes, readable, not truncated
    sequence_hash          32f8dde79bfa0f27

**The campaign is real.** It is returned by `GetAll` and by
`GetById?campaignId=599020`. It is not missing and it was not imagined.

**It is invisible in practice for two reasons that are both true at once:**
it is one DRAFT among 83 campaigns in an account whose history goes back to
April, and it has zero leads, so it shows no activity anywhere a dashboard
would surface it. A campaign with nobody in it and no start time looks
exactly like nothing happening, because nothing is happening.

## 2. EXPECTED vs FOUND

Exactly ONE campaign has ever been created by Resonate OS. Every other
campaign in the account predates this system and belongs to the client's own
history - they are reported for context and are not ours to claim.

    CREATED_AND_VERIFIED   0
    DRAFT                  1     599020
    LIVE                   0
    CREATED_BUT_INCOMPLETE 0
    MISSING                0

    account totals         83 campaigns
                           DRAFT 8, PAUSED 32, FINISHED 31, IN_PROGRESS 12
    linkedin accounts      41 available, 1 attached to 599020

**There is no second, third or fourth Resonate campaign that failed to
appear. Only one was ever attempted.** If more were expected, they were never
created, and no code path in this repository has created one since 2026-09-13.

## 3. INTERNAL STATE vs PROVIDER STATE - CONSISTENT

`work/campaigns.jsonl` holds 11 records. Two carry a HeyReach id:

    599020   internal "draft"    provider DRAFT     agree
    594061   internal "paused"   provider PAUSED    agree

    claims the provider does not confirm:   NONE

**No production consistency defect.** Internal state is not lying about a
campaign that does not exist. One cosmetic defect worth fixing: the id is
stored as the STRING `"599020"` on one record and the INTEGER `594061` on
another, so any comparison that does not normalise will silently miss.

## 4. THE SEQUENCE IS REAL, AND IT CARRIES NO VARIANTS

    nodes                  24 total
      MESSAGE               7
      END                  10
      VIEW_PROFILE          4
      CHECK_IS_CONNECTION   1
      CONNECTION_REQUEST    1
      FOLLOW                1
    nodes carrying copy     8   (7 MESSAGE + 1 CONNECTION_REQUEST)
    messages per node       1, on every single one

**Every copy-bearing node holds exactly ONE message.** The five-variant
machinery that TASK-084 and TASK-087 have been fixing has never reached this
campaign. Whatever the generator can now produce, the provider currently
holds one arm per step.

### Why this says 24 nodes where the readback says 17

They are both right and they count different things.
`scripts/heyreach_readback.py` strips the bare reply-stop `END` nodes the
provider inserts on its own, because those are not ours and comparing them
against a canonical graph would fail on the provider's own bookkeeping. 24
raw nodes, 10 of which are `END`; 17 after the provider's own additions come
out, with 3 `END` that we authored. Do not read the two numbers as a
contradiction.

### A false zero I published and corrected

The first run of `scripts/provider_truth.py` reported **0 nodes carrying
copy** on a campaign whose readback passes 27/27 on its message texts. The
script read `data.message`, `data.text` and `data.note`. None of those exist
on this provider's graph - the copy lives in `payload.messages` - and
`heyreach.connection_notes` documents exactly that, in a docstring written
after the same mistake sent an unapproved default note to real people.

A zero and a wrong lookup are indistinguishable from the outside. This is the
fourth time that sentence has had to be written in this repository in two
days, and the first time it was caught before the number was believed.

## 5. WHY IT IS NOT LIVE - TWO BLOCKERS, BOTH DELIBERATE

Neither is a bug, and neither may be removed by an engineer acting alone.

**BLOCKER 1 - the copy has not passed a human read.**
`docs/LEADS-ARE-BLOCKED-2026-09-14.md`. Two independent human reads,
TASK-064 on LinkedIn and TASK-063 on email, found that copy passing every
automated gate in this repository fails a person. Productive was named zero
times in the 12 pushable LinkedIn messages; sender identity appeared in zero
of 165 email steps. On both channels the operator's hand-written fallbacks
beat everything the model produced. The lead block is a decision, not a
defect, and it stands until a human read passes.

**BLOCKER 2 - the add-leads route is not enabled.**
`src/providerwrites.SUPPORTED` currently holds six routes:

    heyreach.pause          bison.pause         bison.stop_lead
    heyreach.set_sequence   bison.create_campaign   bison.set_sequence

`heyreach.add_leads` is NOT among them. That is why the list is empty: the
door is shut on purpose, and opening it is an operator decision with its own
review, not a side effect of wanting a campaign to look populated.

### A documentation defect found on the way

The module docstring of `src/providerwrites.py` states that **"`SUPPORTED` is
empty. Every attempt refuses."** That was true when written and is false now -
six routes are enabled, including two that write sequences. The docstring
even lists "configure sequence: no documented route" for HeyReach, which is
how campaign 599020's sequence was in fact written.

This is the same class of defect that cost a whole task overnight, when
`QWEN.md` told a worker it had no credentials while it held all three. **A
document about the environment that is believed without checking is how an
engineer reasons correctly to a wrong conclusion.** Fixed in this commit.

## 6. WHAT A LIVE CAMPAIGN WOULD REQUIRE, IN ORDER

Steps 1-4 are already done and verified at the provider. Nothing about them
needs repeating, and repeating the sequence write would be an action taken
against production for no gain.

    1. CREATE DRAFT            DONE   599020, 2026-09-13
    2. CONFIGURE LEAD LIST     DONE   933603 attached, currently 0 leads
    3. CONFIGURE SENDERS       DONE   174892 Bruno Gudelj, active
    4. WRITE FULL SEQUENCE     DONE   24 nodes, hash 32f8dde79bfa0f27
    5. CONFIGURE SCHEDULE      NOT CONFIRMED - GetById returns no schedule
                               field; whether that means absent or merely not
                               exposed on this route is UNRESOLVED and must
                               not be assumed either way
    6. PROVIDER READBACK       DONE   27/27 PASS, re-verified 2026-09-15
    7. VERIFY VARIABLES        DONE   merge variables present, 8 per-variable
                               fallbacks, no double-brace leakage, no
                               hardcoded first name, no repeated message on
                               any path
    8. VERIFY VARIANTS         FAILS THE REQUIREMENT - 1 message per node
    9. ADD LEADS               BLOCKED - route not in SUPPORTED, and the copy
                               has not passed a human read
   10. START                   BLOCKED on 9
   11. READBACK AGAIN          after 10

**The immediate blocker to a live campaign is not the provider and not the
plumbing. It is that nobody has approved the copy, and the copy currently in
the campaign carries one arm per step where five were specified.**

## 7. WHAT WAS NOT DONE, DELIBERATELY

No writes were performed against HeyReach in producing this document. No
campaign was created, started, unpaused or populated. The sequence was not
rewritten. Campaign 599020 is in exactly the state it was in before this
session began, and `sequence_hash 32f8dde79bfa0f27` is the proof to compare
against next time.
