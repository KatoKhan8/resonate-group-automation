# Account-Based Outreach

The account is the unit of outreach, not the contact.

Read this before changing `src/account.py`, `src/outreachclaims.py`,
`src/fatigue.py` or `src/senderteam.py`. `CADENCE-MODEL.md` covers the graph
those modules run against.

---

## 1. What changed, and why the old model could not hold it

The previous model was one contact, one email sender, one LinkedIn sender, one
linear cadence. Every part of that is wrong for how Resonate actually runs
outbound:

```
ACCOUNT
  └── several decision makers
        └── several human senders          (2 email humans, 2 LinkedIn humans)
              └── several provider accounts (Anna owns 20 inboxes)
                    └── several channels
                          └── a branching cadence
                                └── account-level memory
```

A single prospect may legitimately hear from four different humans across two
channels in one coordinated campaign. A single company may have three decision
makers being worked in parallel. Neither is expressible as a list of steps with
a day number.

---

## 2. The graph is derived, never stored

`account.graph(rec)` walks the record's own event log and returns the whole
picture. There is no second copy of the truth.

That costs a walk per call and buys the property that matters: **the account
view and the contact view cannot disagree**, because one is a projection of the
other. A cached account summary would eventually contradict the events it came
from, and the first person to notice would be a client.

---

## 3. Confirmed means confirmed

The state vocabulary is `src/touch.py`'s, unchanged:

| Intention | Fact |
| --- | --- |
| `planned` | `sent` |
| `approved` | `delivered` |
| `payload_ready` | `replied` |
| | `positive_reply` |

Every account-level answer keeps the two apart. `touches()` returns both with a
`confirmed` flag; `confirmed_only=True` returns only facts.

This is the single distinction the whole architecture exists to protect. A
module that blurred it would let a message say "my colleague emailed you last
week" about an email still sitting in a queue.

---

## 4. The touch graph

One touch is: **one human**, reaching **one person**, on **one channel**, at
**one time**, through **one provider account**.

`graph()` answers, for any company:

- who have we contacted here
- which human contacted them
- on which channel, through which inbox or profile
- when
- was it planned, approved, payload-ready, confirmed sent, delivered
- did they reply, and what kind of reply
- did they refer us to somebody
- is the account suppressed, or just this contact

The sender on a touch is **the sender recorded on the event**, never the one
currently assigned. A reassignment must not rewrite who sent what — history is
not editable by changing a pointer.

---

## 5. The claim resolver

`src/outreachclaims.py`. Every statement a message makes about our own prior
outreach must be supported by a canonical event.

Seven claim types, cheapest to most demanding:

| Claim | Says | Needs |
| --- | --- | --- |
| `SAME_CONTACT_PRIOR_TOUCH` | "I wrote to you last week" | a confirmed touch from this sender to this contact |
| `SAME_CONTACT_COLLEAGUE_TOUCH` | "my colleague Anna emailed you" | a confirmed touch from Anna to this contact |
| `OTHER_DM_PRIOR_TOUCH` | "I also reached out to John" | a confirmed touch from this sender to John |
| `OTHER_DM_COLLEAGUE_TOUCH` | "Anna sent John a note" | a confirmed touch from Anna to John |
| `OTHER_DM_REPLY` | "John came back to us" | a recorded reply from John |
| `REFERRAL` | "John suggested I reach out" | a recorded referral edge John → this contact |
| `ACTIVE_CONVERSATION` | "I've been speaking with John" | a reply from John **and** a confirmed touch after it |

`ACTIVE_CONVERSATION` is deliberately the hardest. A sent message is not a
conversation. It is the claim most likely to be made carelessly and the easiest
for a prospect to check — they forward it to John, and John says no.

### Fails closed

`resolve()` returns a `Decision` with `allowed` false and a reason for every
path that cannot establish evidence. There is no "probably", and no caller can
get the boolean without the reason — so a preview cannot show a permitted claim
without showing what permits it.

### Two different refusals

"No evidence" and "the campaign has this switched off" are different problems
with different fixes, and the decision says which. `policy: False` means the
campaign; `policy: True` with a reason means the evidence.

---

## 6. Permission is not obligation

Evidence existing does not mean a message should use it.

Being told that four people at your company have been contacted by three
different strangers is not warmth. It is a prospect learning how they are being
sold to.

So every claim type has a campaign switch, and **everything naming a third
party is off by default**:

| Claim | Default |
| --- | --- |
| own prior touch | **on** |
| colleague handoff | **on** |
| referral | **on** |
| other decision maker touched | off |
| colleague → other decision maker | off |
| other decision maker replied | off |
| active conversation | off |

Widening is a deliberate campaign setting made by somebody who wants it.

---

## 7. Fatigue

`src/fatigue.py`. Multi-sender outreach creates a problem single-sender
outreach does not have:

> Anna emails Monday. Petar connects Monday. Sarah messages Tuesday. Mark
> emails Tuesday.

Nobody planned that. It is what four independently-correct plans produce when
they share a recipient, and it is invisible to anything looking at one cadence
at a time.

Two levels:

**Contact** — minimum hours between touches, maximum per rolling week,
maximum per sequence, and a warning when more than two different humans have
written in a week.

**Account** — maximum decision makers active at once, minimum hours between
opening two different people, maximum touches per company per week.

Every limit is configurable, and `limits()` reports whether the value in force
was **configured or defaulted**. A screen showing "max 3 per week" without
saying whether anybody chose 3 invites an operator to treat a default as a
decision.

`check()` is advisory at plan time and blocking at QA time. Somebody drafting a
campaign should see "this is too dense" while still holding a half-built plan;
nothing should be able to launch through it.

---

## 8. Referrals

Recorded, never inferred.

An edge exists because `events.REFERRAL_RECORDED` was written with **both ends
named**. Nothing reads "Sarah handles this" out of free text and creates one.

An inferred referral is a fabricated introduction. It arrives in a stranger's
inbox as "John suggested I reach out" when John did no such thing, and the
first thing that prospect does is ask John.

`account.referrals()` refuses an edge missing either end.

---

## 9. Sender teams

`src/senderteam.py`. A team is a closed set of humans authorised for a
campaign, and it makes one guarantee:

> A sender outside the authorised team never enters a prospect's cadence.

`cadencegraph.validate` refuses a graph naming anybody else.

Three different questions, never conflated:

| Question | Answered by |
| --- | --- |
| who **may** appear | the team |
| who **does** | the sticky assignment on the contact |
| who **did** | the touch log |

A team is an allowlist, not a pool to shuffle. Nothing here picks a sender — a
prospect who gets three emails from three people because a load balancer felt
like it has learned exactly what this is.

**No team configured** means no restriction *recorded*, and `allows()` says so
in words rather than silently returning true.

---

## 10. Reply effects

A reply from one person may affect that contact, everybody else at the
account, or nothing but the sequence it answered. Which of those it does is a
policy decision, resolved through `src/accountpolicy.py`, and it is applied
by exactly one function: `accountpolicy.apply_reply`.

Every entry point comes through it — the provider webhook in `events.apply`,
the hand-recorded reply in `cadence.record_event`, and the classifier in
`replies.apply` — so there is one answer to "what does a reply do" rather
than one per door.

### What each outcome does

| Outcome | The person who replied | Everybody else there |
| --- | --- | --- |
| Positive | held | held (account) |
| Neutral | held | carries on |
| Not interested / not now / not a fit | sequence ends | carries on |
| Wrong person | sequence ends | carries on |
| Left the company | sequence ends | carries on |
| Referral | held | carries on |
| Existing client | held | held, **and a person must look** |
| Unsubscribe | **suppressed permanently** | carries on |
| Company-wide do-not-contact | **suppressed permanently** | **whole account suppressed** |
| Unclassified | held | held, **and a person must look** |

Every row is derived from `(action, scope)` on the policy, so a workspace
that reconfigures `reply.on_positive` gets a different table without any code
changing.

### Four things that never move

**The replier is never left to carry on.** Whatever the reply said, somebody
who answered is not somebody to keep cold-sequencing, so the mildest effect
available to them is that their own sequence ends. That is not a policy
choice; it follows from their having replied.

**Uncertainty never narrows.** An outcome nobody classified resolves to a
review at *account* scope — the old blanket pause, plus a flag. So a broken
classifier fails to the behaviour this system has always had, and every
narrower effect requires a classification that earned it.

**Only a removal request suppresses.** "They left the company" and "please
remove me" both end a sequence and they are not the same fact: one is a dead
address, the other is a decision about us that we are obliged to keep. Only
`unsubscribe` and `account_do_not_contact` set `unsubscribed`.

**Nothing subtracts.** `apply_reply` writes only state that is absent. A
reclassification, a replay, or a later reply can add a hold or a suppression
and can never lift one — which is what stops "not interested, we already
bought" from being a route back into somebody's inbox.

### Referrals

The edge is the relationship and it is never touched by a transition:
`account.referrals` reads `REFERRAL_RECORDED`, and that event is written only
when a classification named both ends. What the policy decides is whether the
referred contact is *activated* for outreach, which is
`reply.activate_referred_contact` and is off by default — turning somebody on
is a campaign decision, not a classifier's.

### Where the state lives

| Field | Means | Reversible |
| --- | --- | --- |
| `contact["paused"]` | this person is held | yes, by an operator |
| `contact["stopped"]` | this person's sequence ended | yes |
| `contact["unsubscribed"]` | removal request honoured | no |
| `rec["paused"]` | the whole account is held | yes |
| `rec["review"]` | a person must look first | yes |
| `rec["suppression"]` | company-wide do-not-contact | no |

`eligibility` reads these and nothing else: it does not re-derive an outcome
from event text, because the one rule that must not have two implementations
is the one about honouring a removal request.

---

## 11. Decision-maker priority

`primary`, `secondary`, `tertiary`, `referral`. A campaign says who to open
with and who to escalate to. Nothing in this module decides that on its own,
and escalation conditions are cadence branches (`other_dm_replied`,
`referral_received`) rather than hidden rules.

---

## 12. Revival

`src/revival.py` answers one question about an account that has gone
quiet: is there anything new to say to it.

**A timer means re-evaluate, not send.** "Ninety days have passed" is not
a reason to write to somebody; it is a reason to look again. So the module
produces a verdict per account and never an action, never a draft, never a
queued step. What gets built from a `READY` account goes through the
campaign builder, the approval gate and the eligibility gate exactly as a
first approach would - going quiet earns an account no exemptions.

**Reviving with the angle that already failed is a repeat.** An account
that heard "your utilisation reporting is manual" and said nothing does
not need to hear it again in March. If the only thing that has changed is
the date, the honest verdict is `NOTHING_NEW`, and that queue is on the
screen rather than hidden - an invisible one is where a repeat campaign
comes from.

Four things can make a case, and any one is enough:

| case | what it means |
| --- | --- |
| `new_signal` | something happened there since we last wrote |
| `new_person` | a selected decision maker we have never approached |
| `unused_angle` | a pain this client sells against that we never led with |
| `employment_change` | somebody we wrote to has left |

Three rules keep those honest. A signal dated before the last touch is
not new - we already knew it when we wrote. A signal older than the
freshness floor is not new either, or an account last touched two years
ago revives on something from eighteen months ago, which is new only in
the arithmetic. And engagement signals are excluded entirely: they are
readings of what *we* did, and counting them would revive every quiet
account on the strength of being quiet.

**Four verdicts, and the first two are not the same answer.** Merging
them would be the expensive mistake in both directions - re-approaching
somebody who asked us to stop, or permanently writing off an account that
is simply mid-conversation this week.

| verdict | when |
| --- | --- |
| `NEVER` | unsubscribed, account-level removal, an existing client, dropped |
| `NOT_YET` | never contacted, a live conversation, a booked meeting, fatigue, or not long enough yet |
| `NOTHING_NEW` | eligible, and nothing has changed since we last wrote |
| `READY` | eligible, and at least one thing has |

The permanent checks run first, before any signal is read. An account
that asked us to stop must not have its news scanned to see whether it has
become interesting again.

### The cross-channel stop, and what carries it

A reply on either channel stops the other. Two independent guards do it and
they fail for different reasons, which is why both are worth naming:

`eligibility._paused` reads the account hold. It is channel-agnostic
because there is one hold, not one per channel - a reply pauses the
company, and no part of that decision knows which channel it arrived on.

`eligibility._replied` scans the event log for a reply from this person and
does not look at the channel either. This is the one that survives a
resumed run, a hand-edited record, or a hold somebody lifted.

Both are asserted at the payload boundary rather than only at the reply
handler, in `tests/test_lifecycle_attacks.py`: a LinkedIn reply that
arrives after approval makes `push.verify_before_payload` refuse to build
the email payload, including for an item a caller assembled by hand from
state it fetched first. Removing either guard fails exactly one test, so
neither is standing in for the other.

---

The clock starts at a **confirmed** touch. A payload that was built and
never left is not outreach that happened, and a cooling period measured
from it would start the clock on a message nobody received.

---

## 13. What this module will not do

- infer a referral *edge* from reply text - `src/referral.py` records what
  a reply said and `src/replies.py` classifies it, and neither writes
  `REFERRAL_RECORDED` or activates anybody. The edge is still only ever
  written by a person
- treat a planned touch as a touch
- let a reassignment rewrite history
- cache the graph
- pick a sender
- invent a fatigue limit and present it as best practice
- allow a claim whose evidence it cannot name
- send anything because a timer expired
