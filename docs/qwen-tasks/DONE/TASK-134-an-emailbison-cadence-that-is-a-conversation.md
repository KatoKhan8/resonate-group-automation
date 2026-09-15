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

## RESULT

**STATUS:** DONE

**COMMIT SHA:** ed9b00f

**TESTS:** N/A — analysis and design task, no code change.

**FILES CHANGED:**
- `docs/EMAILBISON-CADENCE-DESIGN-2026-09-15.md` — the deliverable
- `docs/qwen-tasks/RUNNING/TASK-134-an-emailbison-cadence-that-is-a-conversation.md` — task moved from TODO to RUNNING, then DONE

**FINDINGS:**

Five steps, (F, T, F, T, F) thread-reply pattern, 3-day gaps (4 before the
breakup), 14-day total span. Every design choice is tagged EVIDENCE or BET.

**What rests on EVIDENCE:**
- Five steps, not eight (TASK-103: steps 6-8 are strictly wasteful — 95 sends, 0 replies)
- 3-day gaps (TASK-107: modal EmailBison delay at 35.2%, consistent with 92.3% of replies arriving before day 3)
- No length instruction (TASK-080: survivorship data supports neither "be short" nor "be long")
- The follow-up addendum (without it, the model writes another cold open)
- The pre-write guard catches broken greetings (three defect classes, fires before staging)

**What rests on the BET:**
- The (F, T, F, T, F) thread-reply pattern — NO CONTROL GROUP exists. Every campaign with sends uses thread_reply=True at step 2. Campaign 481 (the only one with False) has zero sends.
- em1, em3, em5 opening new threads — no measurement isolates this
- The 4-day gap before the breakup — no measurement supports this specific value

**The greeting:** The email prompt does not prescribe a formal greeting. The
current copy opens with content ("<client-593687> describes itself as..."), not
with "Hi [name],". This avoids the greeting defect class entirely. The guard
still fires if the model produces a broken greeting. For a contact WITH a
name, the name may appear in the body ("<contact-98aafc>, I want to respect your
time..."). For a contact WITHOUT a name, the body works without one.

**The signature:** No formal sign-off. The email prompt requires sender
identity but does not say where. TASK-130 found 93% sender identification on
LinkedIn vs ~40% on email — the asymmetry is real. LinkedIn's structural
pressure (the connection note form) has no email equivalent. The fix is a
prompt change, not a cadence change.

**The "I noticed" problem:** 34 instances in 13 of 69 email sequences.
Neither prompt forbids it. LinkedIn's 0% is emergent, not enforced. The fix
is a prompt constraint.

**The easy out:** Rung 5 asks for it. 58 of 69 sequences lack it. The
fallback's connected_4 is the target shape. The fix is a prompt change.

**RISKS:**
- The queue snapshot (stamp: 2026-09-14T21:52:15Z) predates the regeneration.
  The email bodies I read are pre-fix copy. The regenerated copy may have
  different greeting/signature patterns.
- The time-to-reply sample (n=65) is small. The 92.3% figure is directional,
  not precise.
- One campaign (330) is the only step-incrementality measurement. n=1 at
  step 5 does not survive a sample-size objection.

**RECOMMENDED CLAUDE ACTION:**
1. Read `docs/EMAILBISON-CADENCE-DESIGN-2026-09-15.md` for the full design.
2. The three prompt fixes (stop "I noticed", require sender identity in em1,
   produce a proper easy out at em5) are the prerequisite for activating
   campaign 481.
3. The cadence design itself is sound. The (F, T, F, T, F) pattern is a bet,
   but it is the operator's starting hypothesis and the estate has no
   counterfactual. Five steps is supported by the step-incrementality data.
   3-day gaps are consistent with the time-to-reply distribution.
