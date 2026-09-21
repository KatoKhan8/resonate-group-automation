# Re-engagement copy, drafted for approval

**NOTHING IS ENROLLED ON THIS COPY.** The operator's instruction: "draft the
re-engagement email cadence (3 steps, threaded) and the LinkedIn message-only
cadence from the Productive playbook and send them to me for approval before
any REENGAGE enrollment." This is that draft.

## Who it is for, measured rather than assumed

From tonight's read-only inventory of the estate (`work/stage/reengagement-
inventory.jsonl`, 1,415 leads across 16 campaigns that `membership` could
answer for):

    REENGAGE    973   no reply ever, campaign archived, last touch 87-111 days
    REVIVE       37   replied, then silence - a human sends these, not a cadence
    UNKNOWN     379   mostly last touch inside the 90-day rule - they HOLD
    ACTIVE       17   being mailed right now - untouched
    NEVER         9   bounced

The three big client campaigns - 352, 327, 328 - are NOT in this count.
`membership` refuses past its page cap rather than returning part of a
96,045-row campaign as though it were the whole, so those leads are unread,
not absent.

## What makes this copy different from the cold copy

It acknowledges the prior contact in the first line and does not pretend to
be a first touch. That is the whole point, and it is also the thing that will
be checked: a re-engagement letter that opens like a cold one is worse than
no letter, because the recipient knows.

New thread, new subject. Never a reply into a dead thread from April.

The angle is the same angle their title already resolves to - the client's
own words from `config/clients/productive.yaml` - so a Project Manager who
was written to about budget burn in April is written to about budget burn
now. Changing the argument between touches would make the second letter read
as a different company.

---

## EMAIL, three steps, threaded

Merge fields are the ones already proven in the live copy: `{FIRST}`,
`{COMPANY}`, `{INDUSTRY}`, `{ANGLE}`, plus `{MONTHS}` - how long since the
last touch, computed per lead from the inventory, never guessed.

### Step 1 — subject: `{ANGLE}`

    {FIRST}, we spoke to {COMPANY} about {ANGLE} around {MONTHS} months ago
    and I do not think it went anywhere.

    That is usually one of two things: it was not the right quarter, or what
    we described did not sound different enough from what you already had.
    Either is a fair answer and neither needs explaining.

    The reason I am writing again is that the thing agencies your size come
    back to us about has not changed: the numbers arrive after the month they
    were about. If that is still true at {COMPANY}, it is worth ten minutes.
    If it is not, say so and I will close the file.

### Step 2 — thread_reply, 4 days later

    {FIRST}, one thing I should have led with.

    The teams who did move on this were not looking for a new tool. They were
    trying to stop the finance view and the delivery view being two different
    spreadsheets maintained by two different people, which is the part that
    makes utilisation and margin late rather than wrong.

    Would it help to see what that looked like for an agency about the size
    of {COMPANY}?

### Step 3 — thread_reply, 8 days later

    {FIRST}, closing the loop properly this time.

    If {ANGLE} is not something {COMPANY} is working on, I will stop here and
    not come back around in another six months.

    If it becomes relevant, the trigger is usually a project landing under
    margin with nobody able to say exactly when it went wrong. Happy to be
    useful then.

---

## LINKEDIN, message-only

**This is not a new graph.** The Productive standard chosen tonight - source
campaign `565765`, the best in the estate on both halves of the funnel, 13.6%
of requests accepted and 17.8% of accepted replying - opens with
`CHECK_IS_CONNECTION` and messages the connected branch. A lead who is
already connected simply takes that branch, which is exactly the
"message-only variant" the instruction asks for, with the connection-request
step skipped and nothing else removed.

So the only new words are the message itself, in the same shape as the
standard's three variants:

    Hey {FIRST_NAME},

    We talked to {COMPANY} about {ANGLE} a while back and it went quiet -
    no complaint, these things have a season.

    Still worth asking: is {ANGLE} something you are actually working on
    this quarter, or has it settled? If it has settled I will leave it.

---

## What I need from you

1. **Approve, edit or reject this copy.** No REENGAGE lead is enrolled until
   you do; the lane is built and the leads are classified and waiting.
2. **The 37 REVIVE leads** are a different question: they replied and then
   went quiet. Per the standing decision they go to `#replies-productive`
   with a drafted answer for a human, capped at 20 a day. That needs the
   reply-handling prompts, which exist, and your say-so to start posting.
3. **The three big campaigns are unread.** If the ~90,000 leads in 352, 327
   and 328 matter for re-engagement, that needs a different route than
   `membership` - probably a per-lead walk from the lead ids we already hold,
   which is hours of provider reads. Say whether it is worth it.
