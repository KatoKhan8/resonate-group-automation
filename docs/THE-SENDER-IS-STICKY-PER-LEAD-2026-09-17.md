# 243 leads, 222 senders, zero rotations: EmailBison keeps one sender per lead

2026-09-17, measured by `scripts/bison_sender_stickiness.py` against the
client's own live campaigns. Read-only GETs.

## The question this answers

`executionguard._sender_for` refuses any campaign whose canonical row names
more than one sender: *"a guarded action is attributed to exactly one"*. The
failure it guards against is specific and real - a prospect hearing from Human
A in the opener and Human B in the follow-up because the provider rotated
mailboxes, with nothing recording which.

**Nobody had ever checked whether this provider does that.** So campaign 487
is pinned to one inbox while the same estate carries 2,595 emails a day of
measured idle capacity across 137 idle mailboxes.

Our own campaigns could not answer it. 481 holds two senders and has never
sent. 485 and 487 hold one each. The client's own campaigns can.

## The measurement

    campaign  senders  queue total  pages  leads   at >1 STEP  ROTATED
    352         222      95,726       30     240      210         0
    328          59      38,744       30     417       33         0
    327          59      48,759       30     450        0         0
    TOTAL                                             243         0

**243 leads appear in the scheduled-email queue at more than one sequence
step, and every single one of them carries the same `sender_email.id` on every
row. Zero exceptions.**

Three examples, verbatim but for the hashed lead key:

    c8dfc53849   step 3746 sender 2739 @ 2026-09-17T06:38
                 step 3747 sender 2739 @ 2026-09-22T13:35
    5fc78170aa   step 4194 sender 3437 @ 2026-09-18T09:16
                 step 4039 sender 3437 @ 2026-09-22T12:09
    cad1bc0477   step 4036 sender 3437 @ 2026-09-18T00:06
                 step 4037 sender 3437 @ 2026-09-20T09:01

Campaign 327 contributed no evidence: none of its 450 sampled leads appeared
at more than one step. That is reported as INCONCLUSIVE for 327 rather than as
support, because a lead seen once is not a lead that kept its sender.

## Classification, and it is not DOCUMENTED

**OBSERVED.** n=243, on this workspace, on one day, in one provider's
scheduled queue. It is behaviour, not a contract the vendor offers, and:

- It says **nothing about how the first sender is chosen** - round robin, hash,
  least-loaded, or arbitrary. Only that the choice is stable per lead.
- It cannot see across an already-SENT step and a future one. The queue holds
  scheduled rows; a lead's history is not in it.
- A vendor that behaves this way today has not promised to behave this way
  tomorrow.

`scripts/grok_provider_research.py --question sender_selection` asks the
vendor's documentation the same question. Until that comes back and agrees,
this stays OBSERVED.

## What it changes, and what it does not

**A 222-sender campaign exists in this workspace and is sender-sticky per
lead.** So the provider does not limit sender count and does not, in practice,
produce the failure the arity rule guards against. The ceiling on campaign
487's pool is ours, not EmailBison's.

**It does not license attaching a second inbox tomorrow.** Two things still
stand between the observation and a larger pool, and they are different pieces
of work:

1. **`SAFE_FOR_PRODUCTIVE = 0`.** Not one productive inbox has an attested
   owner, so `assignment.eligible_senders` returns `[]` regardless of the
   arity rule. See
   `docs/THE-ROSTER-NAMES-PEOPLE-WHO-DO-NOT-SEND-2026-09-17.md` - and the
   emptiness is protective, because the roster's seven `productive` humans do
   not exist at the provider.
2. **Attribution must be RECORDED, not assumed.** Stickiness means a lead's
   sender is stable; it does not mean this system knows who it is. What makes
   it knowable is that **`scheduled_emails` carries the full `sender_email`
   object per row BEFORE the send** - id, address, signature. So the honest
   shape is:

       attach N inboxes -> provider assigns one per lead -> READ BACK the
       queue -> record the observed human per lead -> reconcile -> send

   That is observation, which is what
   `docs/SENDER-ATTRIBUTION-DESIGN-2026-09-17.md` already says EmailBison
   supports: per-lead sender is OBSERVABLE but not CONTROLLABLE, and not
   observable before activation because the queue is empty until a campaign
   runs. **487's queue filling on 2026-09-17 is the first time that
   observation has been possible on one of our own campaigns.**

## The safe way to widen 487's pool, in order

Not as a plan to execute tonight - as the contract the work has to satisfy.

1. **Grok's documentation answer.** If the vendor documents per-lead
   stickiness, this moves from OBSERVED to DOCUMENTED and the rest gets
   cheaper. If the vendor documents rotation, the observation is an accident
   of configuration and everything below is void.
2. **Attest humans from provider truth, confirmed by a person.** The provider
   publishes a `name` per inbox and `email_sender_estate.py` groups all 225 by
   it. That is evidence, not proof - this estate holds two names differing by
   one letter, with 66 inboxes and 5.
3. **Attach inboxes belonging to ONE attested human first.** Then any choice
   the provider makes is that human, stickiness or not, and the arity rule's
   purpose is satisfied without relaxing anything. 487's human has six inboxes
   and 36/day of measured headroom - a fourfold increase on what the campaign
   can reach today, with zero attribution risk.
4. **Only then consider several humans**, and only with the readback recording
   which human each lead actually got, before the first send goes out.

Step 3 is the one worth having soon. It needs no new predicate, no change to
`executionguard`, and no provider behaviour we have not measured - only the
attestation, and a canonical row that can name more than one inbox for the
same person.
