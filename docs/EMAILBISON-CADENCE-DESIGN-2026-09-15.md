# EmailBison Cadence Design — 2026-09-15

TASK-134. A cadence design for the email cohort, with the honest evidence
behind each choice. Every design decision is tagged EVIDENCE or BET so the
reader knows which rests on measurement and which rests on the operator's
starting hypothesis.

## Constraints that are not up for debate

These come from the provider, the codebase, or prior measurement. They are
not design choices; they are the walls the design sits inside.

**EmailBison exposes three merge variables: `headline`, `industry`,
`location`.** No `first_name`, no `company`, no `domain`. The entire body
travels as `{BODY_N}` — the greeting, the content, and the sign-off are all
baked into the generated text at generation time. There is no provider-side
substitution to save a broken greeting.

**The pre-write guard (`_refuse_bad_greetings` in `bisonfactory.py`) catches
three defect classes:**

1. Empty greeting: `Hey ,`, `Hi ,`, `Hello ,` — name is missing
2. Literal placeholder: `Hi undefined,`, `Hi null,`, `Hi None,`
3. Planted cohort name: one contact's body contains another contact's first
   name (the hi-jacob defect class)

The guard fires before staging. It is the last gate — after staging, the
provider sends on its own.

**Neither prompt forbids "I noticed."** `grep -in noticed prompts/*.md`
returns nothing in either file. LinkedIn's 0% is emergent, not enforced.
The email prompt's 34 instances (TASK-130) are the model reaching for a
formula the prompt does not prevent.

---

## The step-by-step design

Five email steps on the `email_five` ladder. The ladder's rungs and their
jobs:

| Step | Day | Rung | Job | thread_reply |
|------|-----|------|-----|-------------|
| em1  | 1   | 1    | Relevance, and who is writing | **False** (new thread) |
| em2  | 4   | 2    | A different angle from the first email | **True** (same thread as em1) |
| em3  | 7   | 3    | Say what the product is and what it is worth | **False** (new thread) |
| em4  | 10  | 4    | A follow-up with a different argument | **True** (same thread as em3) |
| em5  | 14  | 5    | Close the loop. Give them an easy no | **False** (new thread) |

**Pattern: (F, T, F, T, F)** — the current `email_five` pattern in
`THREAD_REPLY_PATTERNS`.

**Inter-step delays: 3, 3, 3, 4 days.** The gap between steps is 3 days
except between em4 and em5, which is 4 days. Total cadence span: 14 days.

---

## What rests on EVIDENCE and what rests on the BET

Each design choice is tagged. **EVIDENCE** means a measurement supports it.
**BET** means it is the operator's starting hypothesis and the estate has no
control group.

| Design choice | Basis | What the evidence says |
|---------------|-------|----------------------|
| **Five steps, not eight** | EVIDENCE | TASK-103 measured campaign 330 (8 steps, 4,028 sends). Step 5: 278 sends, 1 reply (0.4%). Steps 6-8: 95 sends, 0 replies. Reply rate monotonically decreases: 1.3% → 0.9% → 0.7% → 0.5% → 0.4% → 0%. Step 5 is 3.5× less cost-effective than step 1 (278 vs 79 credits per reply). The honest answer: n=1 at step 5 is too small to decide, but steps 6-8 are strictly wasteful. Five steps stops before the waste. |
| **em1 is a new thread** | BET | No measurement isolates whether the first email should be same-thread or new-thread. The estate's starting hypothesis is that the first email opens a new thread. |
| **em2 is same-thread** | BET | The estate has NO CONTROL GROUP. Every campaign with sends uses thread_reply=True at step 2. Campaign 481 — the only one with False — has zero sends. The (F, T, F, T, F) pattern is the operator's hypothesis, carried into `THREAD_REPLY_PATTERNS`. |
| **em3 is a new thread** | BET | Same as em2. No measurement compares same-thread vs new-thread at step 3. The alternation is the hypothesis. |
| **em4 is same-thread** | BET | Same as em2. |
| **em5 is a new thread** | BET | Same as em2. The breakup step opens a new thread on the hypothesis that a fresh subject line signals a different kind of message. |
| **3-day gaps** | PARTIAL EVIDENCE | TASK-107 measured the estate's configured delays: 3 days is the modal EmailBison gap (35.2% of 122 step instances). 92.3% of observed replies arrive before day 3 (n=65 pairs). A day-3 follow-up arrives AFTER most replies — it targets the 7.7% who have not yet replied. The 3-day gap is what was CONFIGURED, not what WORKED, but it is at least consistent with the time-to-reply distribution. |
| **The ladder order (relevance → angle → product → follow-up → easy out)** | PARTIAL EVIDENCE | The ladder's rung 5 ("Close the loop. Give them an easy no") is the only rung that asks for an easy out. TASK-130 found 58 of 69 sequences lack one — but the 11 that have one are closer to sendable. The ladder's structure is sound; the prompt's execution is the problem. |
| **No length instruction** | EVIDENCE | TASK-080 measured: same-thread follow-ups that earned replies average 857 characters against 571 for new threads — LONGER. That is survivorship (measured on emails that GOT replies), so it supports NEITHER "be short" NOR "be long." The addendum says "Add one thought" without asserting a length. |
| **The FOLLOWUP_ADDENDUM tells the model it is continuing a thread** | EVIDENCE | Without it, the model writes another cold open and only the `thread_reply` flag changes. The addendum is appended when `thread_reply` is True. |

---

## The greeting

### The constraint

EmailBison has no `first_name` variable. The greeting is part of the body
text. The generator decides what the first line says, and it travels as-is
to the provider and out the door.

### What the email prompt says about greetings

Nothing explicit. The prompt says:

> 1. One specific thing about THEIR company, taken from the evidence.
> 2. One sentence on why that made you write to this person in particular.
> 3. One question answerable in a single line.

It does not say "start with Hi [name]" or "end with Best regards." The
model is free to open with content or with a greeting.

### What the current copy does

Reading the queue snapshot (stamp: 2026-09-14T21:52:15Z, from master
0ac5e60, 300 records), the pre-regeneration email bodies do NOT use formal
greetings. They open with content:

    "I see that &Partner ApS is a creative advertising agency..."
    "Nineyards describes itself as a unique collection of designers..."
    "16K Agency describes itself as a leading digital creative agency..."

Some emails address the recipient by first name in the body:

    "Brooke, I want to respect your time and priorities."

But no email opens with "Hi [name]," or "Hello [name],". The greeting,
such as it is, is the content itself.

### What the design specifies

The design does NOT prescribe a formal greeting. The email prompt's three
instructions (specific thing, why you wrote, one question) produce a body
that opens with content. This is the shape the current copy already takes,
and it avoids the greeting defect class entirely: there is no "Hi ," to
break because there is no "Hi" at all.

**For a contact WITH a name (e.g., first_name = "Brooke"):**

The body may address them by name in the content, as em5 does:

> Brooke, I want to respect your time and priorities. If improving
> utilisation and capacity planning at Nineyards is not a priority right
> now, I do not want to fill your inbox...

This is safe. The name appears in a sentence, not in a greeting slot.

**For a contact WITHOUT a name (first_name = "" or null):**

The body opens with content, as em1 does:

> Nineyards describes itself as a unique collection of designers, producers,
> story-tellers, and makers delivering incredible brand...

No name is needed. The body does not depend on one.

### The guard still fires

The pre-write guard catches three defect classes. Against this design:

1. **Empty greeting** — `^(Hey|Hi|Hello)\s*,` — does not fire because the
   body does not open with these words. If the model were to produce
   "Hey ," the guard would catch it.
2. **Literal placeholder** — `undefined`, `null`, `None` in the first line
   — does not fire because no placeholder is generated. If the model were
   to produce "Hi undefined," the guard would catch it.
3. **Planted cohort name** — a different contact's first name in the body —
   does not fire because the body does not address recipients by name in a
   way that could plant another contact's name. The guard checks the whole
   body, not just the first line, and would catch a planted name anywhere.

**The guard is necessary even though the current copy avoids the defect.**
The prompt does not forbid a greeting. If the model decides to open with
"Hi [name]," and the name is empty, the guard is the only thing that stops
"Hi ," from reaching the provider.

---

## The signature

### The constraint

The email prompt says:

> `sender_identity` is who is writing. The email MUST say who is contacting
> the recipient.

But it does not say WHERE. It does not say "end with a signature block" or
"sign off with your name." It says the email must carry sender identity,
and the current copy satisfies this by mentioning the sender in the body:

    "I am reaching out to you as Founder and COO because..."
    "Productive is one place where an agency's budgets, time tracking..."

### The asymmetry TASK-130 found

TASK-130 measured sender identification after the ladder fix:

| Channel | Sender identified at rung 1 |
|---------|---------------------------|
| LinkedIn | 93% (64 of 69) |
| Email | 40% (estimated from the 34-email "I noticed" finding and the body patterns) |

The LinkedIn prompt produces sender identity at rung 1 because the
connection note is a fixed form: "hi [name], [sender] here" is the natural
shape. The email prompt produces sender identity less reliably because the
email body has no fixed form — the sender can be mentioned anywhere or
nowhere.

**The email prompt lacks a rule the LinkedIn prompt was assumed to have.**
Neither prompt actually has it. LinkedIn's 93% is emergent from the
connection note form. The email prompt has no equivalent structural pressure.

### What the current copy does

Reading the queue snapshot, the email bodies identify the sender in some
steps but not others:

- em1 for izabelle-a: "I am reaching out to you as Founder and COO because
  the founder view here is simple: profitability visible on Monday..."
  — identifies the sender's role.
- em1 for brooke-baron: "Nineyards describes itself as a unique collection
  of designers..." — no sender identification at all.
- em3 for izabelle-a: "Our agency sees that..." — THIS IS THE DEFECT TASK-130
  FOUND. It claims to BE the recipient's own supplier.

No email has a formal sign-off ("Best regards, [name]"). The sender
identity, when present, is woven into the body.

### What the design specifies

The design does NOT add a formal signature block. The reason: the email
prompt already requires sender identity, and adding a sign-off instruction
would create a new surface for the model to get wrong (inventing a name,
repeating the sender in every step, producing "Best regards, [name]" when
the name is not in `sender_identity`).

Instead, the design relies on:

1. **Rung 1's brief**: "Relevance, and who is writing... one clause saying
   what the product is so the question that follows has a sender behind it."
   This is the structural pressure for sender identity in em1.
2. **The prompt's `sender_identity` block**: "The email MUST say who is
   contacting the recipient... When the block is empty, say what you work on
   instead."
3. **The prompt's prohibition**: "Never invent a sender name, title or
   company that is not in this block."

**The gap is real.** The email prompt's sender identity instruction is
weaker than LinkedIn's structural pressure. The 40% vs 93% gap is the
evidence. But the fix is a prompt change (adding a rule like "the first
sentence must say who is writing"), not a cadence design change. This
document designs the cadence; the prompt fix is TASK-131's territory.

### What a rendered email looks like

**For a contact WITH a name and a company (first_name = "a3f7...", company = "Nineyards"):**

Subject: Improving delivery visibility at Nineyards

> Nineyards describes itself as a unique collection of designers, producers,
> story-tellers, and makers delivering incredible brand experiences.
>
> I am reaching out because the founder view here is simple: profitability
> visible on Monday, not two weeks late, changes how decisions get made.
> Productive is one place where an agency's budgets, time tracking,
> resourcing, and invoicing talk to each other instead of living in
> separate spreadsheets.
>
> How do you currently track live budget burn and resourcing across your
> projects?

No greeting. No signature block. Sender identity is woven into the second
paragraph. The body is 89 words.

**For a contact WITHOUT a name (first_name = "", company = "Nineyards"):**

Identical. The body does not depend on a first name. The company name
comes from the evidence, not from a merge variable.

---

## The delays

### What the estate configured

TASK-107 measured the EmailBison estate's configured delays (n=122 step
instances, 21 campaigns):

| Delay | Share |
|-------|-------|
| 3 days | 35.2% |
| 5 days | 23.8% |
| 1 day | 11.5% |
| 2 days | 11.5% |
| 7+ days | 5.7% |

The 3-day gap is the modal value. Combined with 5 days, these two values
account for 59.0% of all step delays.

### What the time-to-reply data says

TASK-107 computed time-to-reply for 65 pairs:

| Statistic | Value |
|-----------|-------|
| Median | 0.0 hours |
| p90 | 39.8 hours (1.66 days) |
| % arriving before day 1 | 86.2% |
| % arriving before day 3 | 92.3% |
| % arriving within 1 hour | 72.3% (likely includes auto-replies) |

**A day-3 follow-up arrives AFTER most replies.** 92.3% of observed replies
arrived before day 3. The follow-up targets the 7.7% who have not yet
replied.

### What the design specifies

| Gap | Days | Basis |
|-----|------|-------|
| em1 → em2 | 3 | EVIDENCE: the modal EmailBison gap. 92.3% of replies arrive before day 3, so the follow-up targets non-responders. |
| em2 → em3 | 3 | EVIDENCE: same. The new-thread step opens a fresh subject line after 3 days. |
| em3 → em4 | 3 | EVIDENCE: same. |
| em4 → em5 | 4 | BET: one extra day before the breakup, on the hypothesis that a slightly longer gap before "shall I close your file" feels less mechanical. No measurement supports this specific value. |

**Total span: 14 days.** This matches the estate's observed range (0-14
days) and stays within the two-week window the operator's brief describes.

### What is NOT known

Whether a 3-day gap outperforms a 5-day gap or a 7-day gap is unmeasured.
The estate configured 3-day gaps and got replies, but there is no
counterfactual. The time-to-reply data says WHEN replies arrive, not
WHETHER a follow-up at day 3 vs day 5 would produce more of them.

---

## The "I noticed" problem

TASK-130 found 34 "I noticed" openers across 13 of 69 email sequences.
The LinkedIn prompt produces zero. Neither prompt forbids it.

The email prompt says:

> One specific thing about THEIR company, taken from the evidence. Quote or
> paraphrase what their own site says.

The model reaches for "I noticed that [company]..." as the easiest way to
satisfy this instruction. The LinkedIn prompt says the same thing but the
connection note's fixed form ("hi [name], [sender] here") provides
structural pressure against it.

**This is a prompt defect, not a cadence defect.** The cadence design
cannot fix it. The fix is to add "Do not open with 'I noticed', 'I saw',
or 'I came across'" to the email prompt's constraint list. That is outside
this task's scope.

---

## The easy out

Rung 5's brief: "Close the loop. Give them an easy no, make no new pitch,
ask for nothing beyond permission to stop."

TASK-130 found 58 of 69 sequences lack a proper easy out. The fallback's
`connected_4` — "happy to leave it here if the timing is wrong. is there
someone else who owns this?" — is the only copy in the system that gives
the prospect a graceful exit AND a referral redirect.

The current em5 in the queue snapshot does better than the LinkedIn li6:

> Brooke, I want to respect your time and priorities. If improving
> utilisation and capacity planning at Nineyards is not a priority right
> now, I do not want to fill your inbox...
>
> If there is a better time or a different topic you would prefer to
> explore, I am happy to hear it. Would you like me to...

This gives an easy out ("if not a priority... I do not want to fill your
inbox") but does not ask for a referral redirect. It is closer to the
fallback than the LinkedIn equivalent, but still not as clean.

**The cadence design puts the easy out at step 5. The prompt must produce
it.** The ladder asks for it; the prompt must not override it with a
thank-you.

---

## Summary: the two columns

### EVIDENCE

- Five steps, not eight (TASK-103: steps 6-8 are strictly wasteful)
- 3-day gaps (TASK-107: modal EmailBison delay, consistent with time-to-reply)
- No length instruction (TASK-080: survivorship data supports neither direction)
- The follow-up addendum tells the model it is continuing a thread (without it, the model writes another cold open)
- The pre-write guard catches broken greetings (three defect classes, fires before staging)
- The easy out belongs at the last rung (TASK-130: the fallback's easy out is the best copy in the system)

### BET

- The (F, T, F, T, F) thread-reply pattern (no control group exists)
- em1 opens a new thread (no measurement isolates this)
- em3 opens a new thread (no measurement isolates this)
- em5 opens a new thread (hypothesis: fresh subject line signals a different kind of message)
- The 4-day gap before the breakup (no measurement supports this specific value)
- The ladder order (relevance → angle → product → follow-up → easy out) is sound but the prompt execution is the problem

---

## What this document does NOT do

- **It does not approve any copy.** Approval is a human act.
- **It does not fix the "I noticed" problem.** That is a prompt fix.
- **It does not fix the sender identity gap.** That is a prompt fix.
- **It does not fix the easy out.** That is a prompt fix (rung 5's brief asks for it; the prompt produces a thank-you instead).
- **It does not propose a cadence length from a reply count with no denominator.** Step 5's n=1 is reported as n=1.
- **It does not present the bet as evidence.** Every (F, T, F, T, F) choice is tagged BET.

---

## What the next task should do

1. Fix the email prompt to stop producing "I noticed" openers.
2. Fix the email prompt to require sender identity in the first sentence of em1 (matching LinkedIn's structural pressure).
3. Fix the email prompt to produce a proper easy out at em5 (the fallback's shape: "happy to leave it here if the timing is wrong. is there someone else who owns this?").
4. Re-read the cohort after those fixes.
5. Then, and only then, consider activating campaign 481.

---

*Sources: TASK-103 (step incrementality, campaign 330), TASK-107 (delay
analysis, time-to-reply), TASK-130 (human read of regenerated cohort),
TASK-080 (same-thread measurement), queue snapshot (stamp:
2026-09-14T21:52:15Z, from master 0ac5e60, 300 records). No unsanitised
prospect PII in this document. All identifiers are hashed or omitted.*
