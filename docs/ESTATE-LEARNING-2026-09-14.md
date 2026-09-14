# What the client's own EmailBison estate says works

Read-only, 2026-09-14, from the live EmailBison workspace bound to this
credential (workspace 10, PRODUCTIVE). 22 campaigns, 14 of which have sent
anything. **237,935 emails to 48,606 people, 2,139 unique replies.**

Nothing here was written yet. This is observation, and the sections are
separated on purpose: OBSERVATION is what the provider says, HYPOTHESIS is
what it might mean, EXPERIMENT is what would settle it. The operator's
instruction was explicit - do not rewrite production strategy on a small
sample - and the two places where the sample is small are marked.

---

## FIRST: TWO METRICS IN THIS ESTATE ARE UNUSABLE, AND KNOWING WHICH MATTERS

**Opens are zero on every campaign.** Not low - zero, across all 22, including
the ones with 90,000 sends. `open_tracking: false` on the campaign object.
So every open-based statement about this estate is meaningless, and any report
that quotes an open rate from here is quoting a switched-off counter. The
operator's instruction to "treat opens cautiously if tracking quality is
uncertain" is stronger than it needed to be: they are not uncertain, they are
absent.

**Unsubscribes are zero on every campaign**, for the same kind of reason:
`can_unsubscribe: false` and `unsubscribe_text: null`. There is no unsubscribe
link, so there is no unsubscribe signal. That has two consequences worth
stating plainly rather than burying: the estate cannot tell us which copy
annoys people, and opt-out arrives as a reply that something has to classify
rather than as a provider event. Suppression here rests entirely on reply
classification.

**`interested` is tagged 17 times across 2,139 replies (0.8%).** Nine of the
seventeen are on one campaign. That is a manual tag that nobody has been
applying, not a 0.8% qualification rate, and it cannot support a meeting
metric. The optimisation hierarchy the operator described - MEETING above
POSITIVE REPLY above MEANINGFUL REPLY - **cannot be measured in this estate
today above the level of "replied at all"**. Fixing that is a prerequisite for
optimising anything, not a reporting nicety.

So: **replies per contacted person is the only outcome metric this estate
supports.** Everything below uses it.

---

## OBSERVATION 1 - sequence length, and it is not monotonic

Reply rate by the number of steps in the campaign's sequence:

    steps  campaigns  contacted  replies   reply%   bounce%
        1          5       3163       27     0.85      2.43
        8          5      17690     1502     8.49      0.91
       22          2       2422       54     2.23      0.53
       35          1       4994       72     1.44      0.64
       44          1      20337      484     2.38      0.89

**One email is 0.85%. Eight is 8.49%. Forty-four is 2.38%.**

More is not better. The relationship rises steeply and then falls, and the
fall is not a small-sample artefact - the 44-step campaign is the second
largest in the estate at 20,337 people contacted, and it replies at less than
a third of the 8-step rate.

The single-step number deserves its own note, because it is the shape this
system has actually been running: campaign 451 is one step, and every campaign
in the 1-step row is from an earlier April batch. Those five also bounce at
2.43%, nearly three times the multi-step rate, so their lists were worse and
some of the gap is list quality rather than cadence.

### The part that is closest to controlled

The 22-step campaigns 334 and 335 use the SAME opening copy as the 8-step
campaigns 327 and 328 - the same first five subject lines, "how {COMPANY}
tracks margin today", "the 8% margin problem", "where the margin actually gets
lost". Same angle, same author, same period.

    8-step,  'margin today' copy     contacted 14839   replies 1245   8.39%
    22-step, SAME opening copy       contacted  2422   replies   54   2.23%

**3.8x, on the same words.** It is still confounded - 327/328 are USA and EU,
334/335 are Australia and a "NOVO" list - so this is not proof. It is the
strongest evidence in the estate and it points the same way as the table.

## OBSERVATION 2 - what the best-performing sequence actually does

Campaign 330 (Dutch, 12.23% reply, the highest in the estate) and its
siblings 327/328/329/331 share a shape. Read back from
`/campaigns/{id}/sequence-steps`:

    8 steps, waits 2 / 3 / 2 / 3 / 3 / 3 / 3 / 1     (about 20 days)

    step1  {hoe {COMPANY} marges bijhoudt|de ops-stack bij {COMPANY}|
            projectrentabiliteit bij {COMPANY}}
    step2  Re: {same three variants}
    step3  {het 8% margeprobleem|als je er te laat achter komt|...}
    step4  {waar de marge echt verloren gaat|het begint bij allocatie...}
    step5  {wat bureaus zoals {COMPANY} echt vinden als ze kijken|...}
    step6  {de kosten van de huidige setup|wat het spreadsheet-gepruts
            {COMPANY} echt kost|...}
    step7  {praat ik met de juiste persoon bij {COMPANY}?|snelle vraag voor
            ik stop|moet ik met iemand anders praten?}
    step8  {ik sluit de lus bij {COMPANY}|laatste berichtje van mij|
            ik laat de deur open}

Five things in that which our own campaign does not do:

1. **Three subject variants per step**, as provider-native spintax
   `{a|b|c}`. EmailBison rotates them itself. `COPY-EXPERIMENTS.md` already
   specifies five variants per step; the provider has supported it all along
   and campaign 481 sends ONE.
2. **`Re:` threading on the first follow-up only** - step 2 re-uses step 1's
   subject prefixed `Re:`, and steps 3-8 start fresh subjects. Campaign 352
   does it on steps 3, 4, 5 as well.
3. **`{COMPANY}` in the subject line** of six of the eight steps.
4. **A referral step at 7** - "am I talking to the right person at {COMPANY}?
   / quick question before I stop / should I talk to someone else?". This is
   the stakeholder-escalation move the operator's ABM section asks for, and
   it is in the client's best-performing sequence already.
5. **A breakup step at 8** - "closing the loop / last message from me / I'll
   leave the door open".

### Against our own campaign 481

    481   5 steps, waits 3 / 4 / 4 / 9 / 1
          step1..step5 subjects are {SUBJECT_1}..{SUBJECT_5}

One variant per step, no `Re:` threading, no referral step, no breakup step,
and `{COMPANY}` appears only if the generated subject happens to contain it.
The 9-day gap before step 4 is longer than any gap in the best performer,
whose largest is 3.

## OBSERVATION 3 - geography and language

Reply rate by campaign, same 8-step shape and same translated copy:

    330  Dutch      12.23%        327  USA         6.41%
    331  German     10.88%        334  Australia   2.69%   (22 steps)
    328  EU  (en)   10.69%        274  USA         1.44%   (35 steps)
    329  French      2.09%        265  UK          0.25%   (1 step)

The three highest are EU. French is EU, localised, the same shape - and
2.09%. So "localise the language" is not the rule; if it were, French would
not sit at a fifth of Dutch. Something else separates them and this estate
does not say what.

---

## HYPOTHESES, and none of them is a decision

**H1. The productive range is roughly 6-10 email steps over about 20 days,
and our 5 is under it.** Evidence: the table, and the same-copy comparison.
Against: length is confounded with recency and with list.

**H2. Multiple subject variants per step raise reply rate.** Evidence: every
campaign above 6% uses three; every campaign below 3% uses one or is an old
single-send. Against: perfectly confounded with the April-22 rebuild, which
changed copy, length and variants together. This is the weakest-supported
hypothesis here and the easiest to test.

**H3. A referral step and a breakup step are worth their place.** Evidence:
both are in the best performer and in none of the weak ones. Against: same
confound. Note this one is not only a rate question - the referral step is how
an account progresses to a second stakeholder, which `ACCOUNT-OUTREACH.md`
wants anyway.

**H4. Very long sequences actively hurt.** Evidence: 44 steps at 2.38% on
20,337 people, 35 at 1.44%. Against: both are older campaigns. This is the
hypothesis with the largest n behind it.

**NOT a hypothesis: anything about opens, unsubscribes or `interested`.**
Those three counters are off, absent and unused respectively.

## EXPERIMENTS this suggests, in the order they are worth running

Each changes ONE thing. The operator's instruction - "do not change five
variables simultaneously and then claim to know what caused the result" - is
exactly what the April-22 rebuild did, which is why H1, H2 and H3 cannot be
separated from the existing data no matter how it is sliced.

    E1  LENGTH      5 steps vs 8 steps, identical copy for the shared five.
                    Population: the Productive campaign-ready cohort.
                    Measures H1. Needs three more approved steps per contact.

    E2  VARIANTS    1 subject vs 3 subjects per step, same sequence length.
                    Measures H2 alone. Cheapest of the four - it is a
                    generation change and a `{a|b|c}` join, no cadence change.

    E3  REFERRAL    with and without a step-7 "right person?" ask.
                    Measures H3 and feeds stakeholder escalation.

    E4  THREADING   `Re:` on step 2 vs a fresh subject.

None can start until there is volume to run them on, and
`COPY-EXPERIMENTS.md`'s own rule applies - the evaluator refuses to call a
winner from four replies against three. At the current cohort size of nine to
fifteen contacts, **none of these four experiments can reach a verdict.** They
are written down now so the instrumentation is built before the volume
arrives, not after.

## WHAT TO FIX BEFORE ANY OF THAT

The measurement gap is more urgent than the experiments, because without it
every experiment above terminates in "replied: yes/no":

1. **Nothing in this estate distinguishes a positive reply from "take me off
   this list".** `interested` is the provider's field for it and it has 17
   entries. Reply classification already exists in `src/replies.py` and
   `bison.classify_reply_row`; what is missing is that nothing has ever run it
   over the client's 2,139 historical replies. That is a read-only backfill
   against data that already exists, and it would turn the single usable
   metric into the four the operator wants.
2. **No unsubscribe link means no unsubscribe event.** Worth raising with the
   client as a compliance question rather than an engineering one.

## WHAT THE REPLIES ACTUALLY SAY

Added after the rest of this document, by walking `/replies` and running
`replies.classify(model=None)` - rules only, no model, no credits - over every
inbound row. A provider read timeout ended the walk at 3,000 feed rows, which
gave **794 classified replies**: roughly the most recent 37% of the estate's
2,139, and NOT a random sample. Read every number below as "of the recent
794".

    NO RULE MATCHED AT ALL       279   35.1%
    negative                     166   20.9%
    referral                     119   15.0%
    unsubscribe                  115   14.5%
    positive                      41    5.2%
    out_of_office                 37    4.7%
    not_now                       24    3.0%
    not_relevant                  11    1.4%
    account_do_not_contact         2    0.3%

Four things follow, and the first is the one to act on.

**1. 115 people asked to be taken off the list, and the provider recorded
zero unsubscribes.** `can_unsubscribe: false` means there is no link, so
opt-out arrives here ONLY as a reply that something has to classify and act
on. That is 14.5% of replies - roughly one in seven - and it is a compliance
exposure rather than a metrics gap. It is the strongest argument in this
document for fixing reply classification before running any experiment.

**2. More than a third of replies match no rule.** `classify` reports those
as `neutral` with confidence 0.5 and the reason "no rule matched and no
classifier was available". So a third of the inbound signal is recorded as a
lukewarm human opinion when it is actually "we could not read this". Those
are different facts and only one of them is a measurement.

**3. Referrals are 15%.** Higher than positive replies by three to one. The
client's best-performing sequence has a step-7 "am I talking to the right
person?" ask, and this says the answer comes back often. That is the
stakeholder-escalation path `ACCOUNT-OUTREACH.md` wants, arriving already,
with nothing downstream reading it.

**4. Positive replies are 5.2% of replies**, so about 0.23% of people
contacted. That is the real top of the funnel and it is the number any
promotion ladder should be sized against - not the 4.40% reply rate.

### A correction, recorded because it is the exact error this document warns about

An earlier commit message today said "71% of the estate's replies carry the
provider's automated flag". That was read off the FIRST 119 rows. Across all
794 the flag is set 84 times - **10.6%** - and every one of them falls in that
first, most recent slice.

So the true statement is narrower and more interesting: automated replies are
concentrated in recent campaigns, at an estate-wide rate of about one in ten.
Concluding "the reply rate is mostly robots" from 119 rows was overfitting a
small sample, which is precisely what the operator's instruction warned
against and what the HYPOTHESES section above tries to avoid. It is left here
rather than quietly edited out.

## PROVENANCE

Everything above comes from `GET /api/campaigns` (22 rows, `meta.total` 22)
and `GET /api/campaigns/{id}/sequence-steps`, read 2026-09-14. Step counts
were read per campaign rather than inferred. No write of any kind was made to
this workspace, and campaign 451's scheduled email was not touched.
