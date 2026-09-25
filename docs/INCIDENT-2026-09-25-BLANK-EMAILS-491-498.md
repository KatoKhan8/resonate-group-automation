# INCIDENT, CRITICAL — 77 blank emails were sent from 491-498

**Found 2026-09-25 ~15:55Z while running the operator's retroactive check over
491-498. Contained at 16:02Z. This is a DIFFERENT defect from the same day's
Resonate-copy incident in 503/504/505 and shares none of its cause.**

## What happened

77 emails with an **empty subject and an empty body** (`<p></p>`) were
transmitted to real prospects from the client's mailboxes, dated 2026-09-23.
Provider status `sent`. A further 102 were queued.

Read back from EmailBison's own record of what it transmitted
(`scheduled_emails`), not from our CSV.

| campaign | status now | blank SENT | blank STOPPED |
|---|---|---|---|
| 491 | paused | 43 | 51 |
| 492 | paused | 21 | 24 |
| 493 | **active, clean** | 0 | 0 |
| 494 | paused | 7 | 7 |
| 495 | archived | 1 | 1 |
| 496 | paused | 0 | 11 |
| 497 | completed | 5 | 4 |
| 498 | completed | 0 | 4 |
| | | **77** | **102** |

Containment: 491/492/494/496 paused, provider-confirmed. The pause moved every
queued blank row to `stopped`, which is SETTLED — not `sending_paused`, which
`emptyrender.scan` deliberately treats as still-pending because a pause is one
click from being undone. Verified explicitly rather than assumed.
**`emptyrender.scan` now reports 0 pending across all eight.**

493 was left ACTIVE: zero blanks sent, zero queued. Stopping a clean campaign
has a cost too.

## Mechanism

491-498's sequence steps are `{SUBJECT_1}` and `<p>{BODY_1}</p>`. Every word of
every email comes from per-lead custom variables. **EmailBison does not refuse
an unresolved merge field — it renders it to nothing and sends the shell.**

46 leads in 491 carry no `subject_1`/`body_1`. Their variable signatures:

    29x  ['headline', 'location']
    16x  []                            <- no variables at all
     1x  ['headline', 'industry', 'location']

against, for every lead that renders correctly:

    ['body_1','body_2','body_3','client','contact_key','record_id','subject_1']

`headline`, `location` and `industry` are enrichment fields, not email copy.
None of the 46 carry `record_id`, `contact_key` or `client`, which the factory
always writes. **These leads never went through `bisonfactory.stage` at all** —
they were attached by a path that writes profile fields and no copy.

### A second consequence, not yet addressed

Those same 46 leads have no `record_id` and no `contact_key`. If one of them
replies, `match_record` has no unambiguous branch to match on — the same
identifier gap that `adapters._custom` was fixed for earlier today. A blank
email is unlikely to draw a reply, but "unlikely" is not a mechanism.

## Why two days passed

`src/emptyrender.py` **already names campaign 491 in its own comments.** On
09-24 a blank row there was found and a real bug fixed: `PENDING_STATUSES` was
an allowlist, so 491's paused queue read `sending_paused`, fell through to the
bucket labelled "already sent or stopped", and blank rows looked contained when
the only thing containing them was the pause. That fix was correct and is why
nothing blank can send today.

**It counted what was about to send and never asked what had already gone.**
Both witnesses — the watcher heartbeat and a direct provider read — agreed on
"0 pending", and both were right. Nobody ran the same classifier over rows with
`sent_at` set. The 77 sat in the provider's record the whole time, readable by
code already written to read them.

The recurring failure class, seventh instance this week: **a check that passes
because the thing it checks is absent.** Here it passed because it was pointed
only at the future.

## The refuse-list finding (separate, and it prevents a bad gate)

While scanning I first flagged 6 of 8 sampled 491 leads as carrying incident
copy. **That was wrong.** The refuse-list matched `"I work with"` as a bare
substring, and Productive's own approved opener is:

> "Renee, I work with Marketing & Advertising teams on profitability visible on
> Monday not two weeks late, and I do not know how L&P Marketing handles it"

**286 of 333 leads in 491 hit the broad refuse-list. 0 carry the incident.**
The Resonate pitch is confined to 503/504/505.

Implemented as substring matching, the operator's refuse-list would refuse the
client's own approved copy at an 86% rate, and a gate that fires on 86% of
legitimate work is switched off within a day. What actually discriminates:

- the full phrase `"I work with agency founders"`, never the fragment
- `"we run the outbound side"`, never `"we run"`
- **signature ≠ mailbox owner** — the strongest single test, and exact rather
  than fuzzy. Productive's approved bodies end on a question with no sign-off;
  the incident bodies end `"Zvonimir"`.
- the operator's name anywhere in a client body stays an exact refusal

## Corrections made in the course of this

Recorded because each cost a wrong reading and the next session will hit them:

1. `sequence_steps` rows use **`email_subject`/`email_body`**, not
   `subject`/`body`. Reading the wrong keys makes every step look empty and
   would have supported a much worse conclusion.
2. `scheduled_emails` rows carry **`row["lead"]["id"]`**, not `lead_id`.
   Joining on `lead_id` silently matches nothing and reads as "no problem".
3. `lead_campaign_data` spans **every campaign a lead is in**. Summing
   `emails_sent` across it attributes other campaigns' sends to this one — it
   turned 40 into 784.
4. My own blank-detector scored `'<p></p>'` as non-empty because
   `'<p></p>'.strip()` is truthy, and reported "0 bad" over rows that were
   visibly blank on the next line of output. Production's `emptyrender`
   classifier is the authority and found 77 where my regex found 76.

## CAUSE, CONFIRMED 2026-09-25 16:10Z

EmailBison keeps **one lead record per address per workspace.** Where the
client already had a person, our push attached **that existing lead by id** -
inheriting their enrichment variables and never writing ours. Where the person
was new, we created the lead and the copy rendered correctly. The split is
total:

                                   blank (46)   rendering (60 sampled)
    also in a client campaign          44               0
    lead id range               133283-204967    204781-205079
    carries record_id/contact_key      no              yes

So **"this lead already exists" was simultaneously the cause of the blank email
and the proof that the client already had that person.** Nothing read it as
either. Two gates were needed at one moment in the push and neither existed:
refuse a lead whose copy variables we did not write, and refuse a lead already
in another live campaign in the same workspace.

The first is now covered by `emptyrender`. The second is the account/collision
gate, and this is the measurement that sizes it.

## THE COLLISION, WHICH IS THE LARGER FINDING

Client campaigns **327** (47,305 sent) and **328** (38,335 sent) are ACTIVE.
Full per-lead walk of the cohort, from the provider:

    campaign  leads  blank  in ACTIVE client campaign  both
    491         333     46                         73    43
    492         206     25                         50    23
    493          22      0                         18     0
    494          76      7                         18     7
    495          60      1                         27     1
    496          43      0                         30     0
    497          20      4                         16     4
    498          15      0                         14     0
    TOTAL       775     83                        246    78

**246 of 775 - 32% of the cohort - are people the client's own live campaigns
are emailing.** 78 of them got a blank email from us on top of it.

**493 was left ACTIVE** because it is clean on copy, and it is the highest
collision rate in the cohort at 18 of 22. Not paused because the operator's own
LinkedIn directive - *"491-498 cohort is excluded from LinkedIn permanently
(client already runs them)"* - shows the overlap is known and was scoped to
LinkedIn deliberately. Whether the EMAIL overlap was intended is the operator's
question to answer, not production's to assume in either direction.

## What is NOT yet established

- Whether the email overlap with 327/328 was intentional. Escalated, unanswered.
- Whether anything still attaches leads this way TODAY. The empty-render gate
  blocks the send, but a gate blocking the symptom is not the cause being gone.
- 492-498's blank leads were counted but not profiled by variable signature;
  the 44-of-46 pre-existing finding is proven for 491 only and assumed to
  generalise from the identical blank/collision correlation.

## A sampling error worth recording

The first collision check sampled 60 correctly-rendering leads, found zero
overlap, and looked like clean evidence that collisions were confined to the
blanks. They were not. The sample was the first 60 of a list that happened to
be the newly-created 204781+ leads - the exact population that by construction
cannot collide. **The full 333-lead walk produced 73.** A sample drawn from an
ordered list is not a random sample, and the order encoded the answer.

## Scans

    work/491-gate-scan.json            per-lead, 491, refuse-list + body presence
    work/491-498-blank-scan.json       first pass, ad-hoc regex
    work/491-498-emptyrender-scan.json production classifier, pending/settled
    work/491-498-blank-final.json      per-campaign sent/stopped split
