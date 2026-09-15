PRIORITY: P1
DEPENDS: 

# TASK-134 - an EmailBison cadence that reads as one conversation

## WHAT IS ALREADY SETTLED - DO NOT RE-DERIVE ANY OF IT

    same-thread follow-ups    BUILT. THREAD_REPLY_PATTERNS['email_five'] =
                              (F, T, F, T, F), carried ladder -> factory ->
                              payload -> readback, and the follow-up rung TELLS
                              THE MODEL it is continuing a thread rather than
                              only flipping a flag.

    merge variables           EmailBison exposes `headline`, `industry` and
                              `location` and NOTHING ELSE. No `first_name`, no
                              `company`. The whole body travels as `body_N`, so
                              the greeting CANNOT be delegated to the provider
                              and a broken one goes straight to a person.

    "be short"                REMOVED, and NOT replaced with "be long".
                              Same-thread follow-ups that earned replies average
                              857 characters against 571 for new threads -
                              LONGER. That measurement is survivorship, taken
                              only on emails that got replies, so it supports
                              NEITHER instruction. A test pins that the addendum
                              asserts no length in either direction.

    the alternating structure IS A BET. The estate has NO CONTROL GROUP: every
                              campaign with sends uses thread_reply=True at
                              step 2, and campaign 481 - the only one with
                              False there - has zero sends.

## WHAT THIS TASK PRODUCES

A cadence design for the email cohort, and the honest evidence behind each
choice.

1. **How many steps?** Five is a useful starting design, not a rule. The
   question is whether step 5 earns its place - not whether somebody eventually
   replied to a campaign that had five steps. TASK-103 examined step
   incrementality; read it before proposing a length.

2. **Which steps are same-thread?** (F, T, F, T, F) is current and it is a BET.
   Say which parts of your design rest on the bet and which rest on
   measurement. **Do not present the bet as evidence.**

3. **The greeting.** With no `first_name` variable the greeting is baked into
   `body_N` at generation time. Show what it renders as for a contact WITH a
   name and for one WITHOUT. The pre-write guard refuses "Hey ,",
   "Hi undefined,", "Hi null," and a planted cohort name - confirm it still
   fires against your design rather than assuming it.

4. **The signature.** Sender identity was in ZERO of 165 email steps before the
   ladder fix, and is now 93% on LinkedIn rung 1. What does the EMAIL path do?
   **Check for an asymmetry** - TASK-130 found "I noticed" in 34 emails because
   the email prompt lacks a rule the LinkedIn prompt was assumed to have, and
   neither actually had it. The same shape may apply to the signature.

5. **Delays.** 0-14 days observed, 3-day gaps most common. That is what was
   CONFIGURED, not what worked. TASK-107 examined delays and whether
   time-to-reply is computable at all; build on it rather than re-measuring.

## WHAT NOT TO DO

- No provider writes. Campaign 481 stays paused; 451 is completed and stays
  completed.
- Do not design with a merge variable EmailBison does not expose. There are
  three. Check before using anything.
- Do not propose a cadence length from a reply count with no denominator.
- One campaign per COHORT, never per lead.
- Hash prospect identifiers; do not quote a real reply.

## DELIVERABLE

`docs/EMAILBISON-CADENCE-DESIGN-2026-09-15.md`: the step-by-step design with
`thread_reply` per step, the greeting and signature rendered for a real contact
shape with identifiers hashed, and an explicit two-column split of which choices
rest on EVIDENCE and which rest on the BET.
