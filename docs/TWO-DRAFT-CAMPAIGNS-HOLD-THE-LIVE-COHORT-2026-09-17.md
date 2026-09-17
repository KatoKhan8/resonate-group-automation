# Two unstarted campaigns hold the people 487 is already going to email

Measured 2026-09-17 (late evening) from provider truth, read-only, every
address hashed before it was compared. Nothing was mutated.

## The finding

    campaign  status  leads  senders      overlap with LIVE 487
       487    active     10  [2736]       - (this is the live one)
       485    draft      10  [2736]       10 of 10
       481    paused     23  [2736,2737]   9 of 23

**Draft 485 holds every single person live campaign 487 is queued to email,
from the same mailbox.** Paused 481 holds nine of the ten among its
twenty-three. 487's ten openers are already scheduled for 2026-09-23. If
either 485 or 481 is started, those people receive a second opener for the
same cohort from the same sender.

Both sit one provider action away from sending: `draft` and `paused` are
exactly the two states a Start button converts.

## What is NOT at risk

**Our own tooling cannot do this, and that was verified rather than assumed.**
`providerwrites.EMAIL_ACTIVATE` is conditional on
`_is_the_authorized_email_campaign`, which resolves the permitted provider id
from the canonical row `productive-email-control-v3` instead of a literal.
That row binds to 487, so the 2026-09-16 re-scope from the v2 campaign to the
v3 rebuild moved the permission automatically. Offering 485 refuses:

    this authorization covers EmailBison campaign 487 only, and this write
    names '485'. The 2026-09-16 grant is scoped to one campaign; activating
    another is a new operator decision. The transport was not reached

That refusal now has a test pinning the exact dangerous pairing - 485's
provider id offered with the CORRECT v3 canonical row - because the existing
cases paired 485 with the v2 row or a junk row, where the refusal could have
come from the row rather than from the binding.

The function's docstring, however, still opened *"True only for EmailBison
campaign 485"* - the opposite of what it does, naming the one campaign that
must never be started. Corrected in the same commit. The code was never
wrong; the sentence a future reader would have trusted was.

## What remains at risk

**A person clicking Start in the EmailBison UI.** No code of ours is in that
path. 485 additionally carries a sequence that violates the threading
invariant (step 2 `Re: {SUBJECT_2}`, step 3 `thread_reply: false` with its own
`{SUBJECT_3}`), so starting it would send copy that was rejected on its
merits as well as duplicating the cohort.

**This is an operator decision and is deliberately left undone here.**
Archiving a provider campaign is a destructive external mutation and neither
485 nor 481 was created tonight. The recommendation is to archive both, and
the reason to do it rather than rely on care is that the protection today is
entirely "nobody presses the button".

## How it was measured

    campaigns:  GET /api/campaigns  (24 total: 4 active, 5 draft, 1 paused,
                6 completed, 8 archived)
    leads:      GET /api/campaigns/{id}/leads, paged
    compare:    sha256 of the normalised address, first 12 hex, set intersection

The three active client campaigns (327, 328, 352) refuse to enumerate their
queues at all - `PartialInventory: 3251 / 2583 / 6382 pages to walk` - which
is `scheduled_emails` correctly raising rather than answering with its first
page. 487's ten rows are the only scheduled rows in this estate that can be
read in full.

**A consequence worth carrying forward:** the forward-book table in
`PRODUCTION-HANDOFF-2026-09-17.md` was built from a 9,000-row sample of those
unwalkable queues. Sampling can only ever UNDERCOUNT a mailbox's
commitments, so "2736 reads 15 of 15 on the 18th" is sound - a lower bound
that already reached the limit is a full mailbox. The same sample's zeros are
not sound, and the document already says so. The conclusion that 2736 is
booked on the 18th survives; "every mailbox is free on the 23rd" does not.

## The three inboxes that are free by construction

Separately measured, and relevant because a new campaign needs a mailbox with
an empty forward book:

    sender  connected  health    daily_limit  campaigns        human (hashed)
     3941      yes     warming        15      1, and it is DRAFT 418  9e58861fb87e
     3930      yes     warming        15      1, and it is DRAFT 418  7cc85aecf642
     3919      yes     warming        15      1, and it is DRAFT 418  2b4e867056bc

Campaign 418 is a draft holding 225 senders and **zero leads**, and a draft
schedules nothing - confirmed, it has 0 scheduled rows. So these three are
committed to nothing that can send, and their forward books are empty by
construction rather than by sample. Every other one of the 225 inboxes serves
at least one ACTIVE campaign.

Three caveats, none of which the numbers settle:

- All three are `warming`, not `ok`. Warmup is the reason they are idle.
- None has an attested human owner - `HUMAN_IDENTITY_ATTESTED = 0` across the
  entire estate, which is why `assignment.eligible_senders` returns `[]` and
  `SAFE_FOR_PRODUCTIVE` reads 0 against 2,391/day of measured headroom.
- They belong to three DIFFERENT humans, none of them 487's human
  (`c62bbb200b21`), so using one is a change of sender identity and not a
  continuation.
