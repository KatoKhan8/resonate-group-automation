---
title: "Email CONTROL Sequence Specification"
task: "TASK-159"
date: "2026-09-15"
builds_on:
  - "docs/EMAIL-CONTROL-2026-09-15.md"
  - "docs/EMAILBISON-COPY-REQUIREMENTS.md"
  - "docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md"
  - "docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md"
  - "docs/BISON-COHORT-LIVE-2026-09-15.md"
  - "docs/BISON-SEQUENCE-SPEC-2026-09-15.md"
---

# Email CONTROL Sequence Specification — 2026-09-15

**TASK-159 deliverable.** A sequence specification complete enough that Claude
can write it to EmailBison without making a copy decision afterwards.

**Source copy:** `cadence.TEMPLATES` — `persona_pain`, `comparable_proof`,
`breakup`. Decision recorded in `docs/EMAIL-CONTROL-2026-09-15.md`.

**Cohort:** 17 contacts. 8 from the cold cohort (verified, no bison_lead_id,
account-ALLOW) + 9 from the never-emailed bison group (campaign 481, 0 sends,
account-ALLOW). Documented in `docs/BISON-COHORT-LIVE-2026-09-15.md`.

---

## 1. THE OPENER

### Decision: `persona_pain` is the opener

`cadence.STEPS` marks day1 `generated: True` — there is no template for it.
`docs/EMAIL-CONTROL-2026-09-15.md` names `persona_pain` as the default opener.
Reading the body text against that claim:

**The body:**

```
{first_name}, {line}

The pattern I see in teams the size of {company} is that the numbers arrive
too late to act on. Utilisation and margin are known at the end of the month,
which is after the month when something could have been done about them. The
work itself is rarely the problem. The visibility into it is.

Is that roughly how it works at {company} today, or have you already put
something in place for it?
```

**Why it works as a first touch:**

1. **Question-led.** The opening line is `{first_name}, {line}` where `{line}`
   is either an evidence statement or a generic introduction ("I work with
   {sector} teams on {angle_phrase}, and I do not know how {company} handles
   it"). Neither asserts prior contact.

2. **No reference to previous messages.** The body contains no phrase like
   "following up", "as I mentioned", "I wrote to you before", or any other
   claim about a prior touch. This is the same defect class that `breakup`
   had (and was fixed for) — and `persona_pain` does not have it.

3. **The closing question is open-ended.** "Is that roughly how it works at
   {company} today?" is a first-conversation question. It does not presume
   the prospect has already engaged.

4. **`{line}` degrades safely.** When no evidence exists (which is the case
   for all 17 contacts — signal is 100% null), `{line}` renders as:
   "I work with {sector} teams on {angle_phrase}, and I do not know how
   {company} handles it." This is an honest introduction that asserts nothing
   about the prospect.

**Verdict: `persona_pain` reads correctly as a first touch. No new copy
needed.**

---

## 2. THE SEQUENCE

Three steps, drawn from `cadence.TEMPLATES`, mapped to the cadence's email
days:

| Step | Day | Template | Purpose |
|------|-----|----------|---------|
| 1 | day 1 | `persona_pain` | Opener: question-led, names the pain |
| 2 | day 5 | `comparable_proof` | Proof: same-size teams, concrete change |
| 3 | day 21 | `breakup` | Close: low-friction, wrong-person redirect |

### Step 1: `persona_pain`

**Subject:** `{angle_phrase}`

**Body:**
```
{first_name}, {line}

The pattern I see in teams the size of {company} is that the numbers arrive
too late to act on. Utilisation and margin are known at the end of the month,
which is after the month when something could have been done about them. The
work itself is rarely the problem. The visibility into it is.

Is that roughly how it works at {company} today, or have you already put
something in place for it?
```

### Step 2: `comparable_proof`

**Subject:** `how teams your size handle {angle_word}`

**Body:**
```
{first_name}, the teams I work with that look most like {company} tend to
arrive at the same place.

They stop reconciling hours after the fact and start seeing project margin
while the project is still running. The change that makes the difference is
not a new process for the delivery team, it is that the finance view and the
delivery view stop being two different spreadsheets maintained by two
different people.

Would it be useful to see what that looked like for a team your size?
```

### Step 3: `breakup`

**Subject:** `closing the loop`

**Body:**
```
{first_name}, if {angle_phrase} is not something you are looking at right
now, that is a fair answer in itself. I will leave it here.

If it becomes relevant later, the thing worth knowing is that most teams the
size of {company} start looking at this when a project lands under margin and
nobody can say exactly when it went wrong.

Anything you would want me to send over, or shall I leave it there?
```

---

## 3. THREADING, PER STEP

### The field: `thread_reply` (boolean on each sequence step)

`EMAILBISON-COPY-REQUIREMENTS.md` requires a sequence to be ONE CONVERSATION.
The provider field that carries this is `thread_reply` on each parent
sequence step. PROVIDER FACT, read from the live API
(`docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md`, section 3).

**A step carries `email_subject` even when `thread_reply` is True.** Thread
behaviour is governed by the flag, NOT by omitting the subject. The provider
stores both.

### Per-step threading

| Step | Day | `thread_reply` | Thread role | Subject behaviour |
|------|-----|----------------|-------------|-------------------|
| 1 | 1 | **False** | OPENS the thread | New subject: rendered `{angle_phrase}` |
| 2 | 5 | **True** | REPLIES in step 1's thread | Same subject as step 1; provider auto-prepends "Re:" |
| 3 | 21 | **False** | OPENS a new thread | New subject: "closing the loop" |

### Pattern: F, T, F

This matches the estate's dominant pattern. Campaign 352 (the estate's
largest at 92,806 sent) uses F,T,F,T,F. The CONTROL sequence is three steps,
so the pattern is F,T,F.

**Note:** this is a design choice, not evidence-backed. The estate cannot
separate same-thread from new-thread at the same position (TASK-080 finding).
Every campaign with sends uses `thread_reply=True` at step 2, and campaign
481 — the only one with `False` at step 2 — has zero sends.

### Why step 3 opens a new thread

`breakup` has its own subject — "closing the loop" — which is thematically
distinct from the opener's `{angle_phrase}`. A new thread gives the close
its own visibility and does not bury it under a "Re: {angle_phrase}" subject
that the prospect may have already triaged. The body also reads as a
standalone message: "if {angle_phrase} is not something you are looking at
right now" does not reference the thread.

### What the subject field must contain for a thread reply

For step 2 (`thread_reply: True`): **the same subject as step 1.** The
provider auto-prepends "Re:" on all 153 same-thread follow-ups measured in
the estate. ZERO new-thread emails carry it. Do not write "Re:" yourself.

The subject field on a `thread_reply: True` step is NOT ignored by the
provider — it is stored and used as the basis for the "Re:" prefix. It must
be a valid, rendered subject, not empty and not different from the parent.

---

## 4. VARIABLES, AND WHAT AN EMPTY ONE DOES

### The critical fact: EmailBison has no `{FIRST_NAME}` or `{COMPANY}`

**There is no provider-side merge field for first name or company on
EmailBison.** The entire body — greeting included — travels as custom
variables (`{BODY_1}`, `{BODY_2}`, `{BODY_3}`). The generator (or, for
CONTROL, the template renderer) resolves all variables BEFORE staging.
EmailBison stores the rendered text and sends it.

This means:
- The greeting is NOT delegated to the provider
- There is no provider-side substitution or fallback
- A broken greeting ("Hey ,") goes straight to the prospect
- The pre-write greeting guard (`bisonfactory._refuse_bad_greetings`) is the
  ONLY protection

### Variable map

| Template variable | Source | Resolution | Fallback | Empty-render risk |
|-------------------|--------|------------|----------|-------------------|
| `{first_name}` | `contact.name` → first token | `contact.get("name").split()[0]` | **"there"** — renders as "there," | LOW: fallback always fires; `bisonfactory._plan()` refuses contacts with no name before they reach staging |
| `{company}` | `company_facts.name` or `rec.company` | `cadence.company_name(rec)` | **NONE — raises `CompanyNameUnusable`** | MEDIUM: a record with only a domain-shaped company name cannot render this variable. The step is held, not sent. |
| `{angle_word}` | Client config `angle_labels[angle]` or first clause of angle phrase | `cadence.angle_word()` | **"the numbers behind the work"** | NONE: fallback is always available, client-agnostic, not marketing copy |
| `{angle_phrase}` | Client config `personas[persona].angles[angle]` | `cadence.angle_words()` → first clause | **"how the work is tracked"** | NONE: fallback always fires when contact has no angle or persona has no angles |
| `{sector}` | `company_facts.industry` | `facts.get("industry") or "services"` | **"services"** | NONE: always resolves |
| `{line}` | Evidence or generic intro | `evidence[0]` or constructed fallback | **"I work with {sector} teams on {angle_phrase}, and I do not know how {company} handles it"** | NONE: the fallback is an honest introduction that asserts nothing |

### EmailBison custom variables for CONTROL

Since the templates are rendered per-contact before staging, the rendered
text travels in the same custom variables the generated path uses:

| Custom variable | Content for CONTROL |
|-----------------|---------------------|
| `subject_1` | Rendered step 1 subject (the angle phrase) |
| `body_1` | Rendered step 1 body (greeting + persona_pain text) |
| `subject_2` | Rendered step 2 subject ("how teams your size handle {angle_word}") |
| `body_2` | Rendered step 2 body (greeting + comparable_proof text) |
| `subject_3` | Rendered step 3 subject ("closing the loop") |
| `body_3` | Rendered step 3 body (greeting + breakup text) |

The EmailBison sequence step templates reference these as `{SUBJECT_1}`,
`{BODY_1}`, etc. The provider resolves them against per-lead custom variables
at send time.

### "Hey ," is a defect — the protection layers

A greeting that renders empty fails the standing contract
(`EMAILBISON-COPY-REQUIREMENTS.md` §2). Three layers of protection:

1. **`bisonfactory._plan()` refuses contacts with no `first_name`.** They
   never reach the renderer. The template's "there" fallback is a second
   line of defence, not the primary one.

2. **`bisonfactory._refuse_bad_greetings(plan)` checks every rendered body**
   for three defect classes:
   - Empty greeting: regex `^(Hey|Hi|Hello)\s*,`
   - Literal placeholder: "undefined", "null", "None" in the first line
   - Planted cohort name: another contact's first name in the body

3. **The guard is wired into `_ensure_leads` on every `stage()` invocation.**
   Deleting the call makes the test fail — that is the wiring proof.

For the CONTROL templates specifically: the greeting is `{first_name},` at
the start of every body. With the "there" fallback, the worst case is
"there," — which is grammatically odd but not a blank greeting. The
`_refuse_bad_greetings` guard catches the regex patterns; "there," does not
match `^(Hey|Hi|Hello)\s*,`.

---

## 5. THE 17: PER-CONTACT VARIABLE RESOLUTION

### The cohort

**8 from the cold cohort** (verified, no bison_lead_id, account-ALLOW):

| # | Domain | Pool |
|---|--------|------|
| 1 | digitalthirdcoast.com | Cold |
| 2 | feddirect.com | Cold |
| 3 | inmobi.com | Cold |
| 4 | ritway.com | Cold |
| 5 | skyad.com | Cold |
| 6 | thecommunity.ca | Cold |
| 7 | viralityllc.com | Cold |
| 8 | wearejsa.com | Cold |

**9 from the never-emailed bison group** (campaign 481, 0 sends,
account-ALLOW):

| # | Name | Domain | Campaign 481 status |
|---|------|--------|---------------------|
| 9 | Jacob Faertz | ogpartner.dk | sending_paused |
| 10 | Rik De Veirman | anewagencyworld.com | sending_paused |
| 11 | Brian Price | acqcom.com | sending_paused |
| 12 | Ranjan Damodar | adcuratio.com | sending_paused |
| 13 | Collette Savoie | portsidemarketing.com | sending_paused |
| 14 | Al Scornaienchi | agency59.ca | sending_paused |
| 15 | Paula Savage Hansen | savagebrands.com | sending_paused |
| 16 | Michelle Payne-witten | mischacommunications.com | sending_paused |
| 17 | Jennie Johnson | mypersonalestatesale.com | sending_paused |

**Excluded from the 17** (never-emailed but HOLD domain):
- Janie Karas (28row.com) — HOLD
- Christine Xoinis (ethoscreate.com) — HOLD
- Jason Baker (roaringmedia.co) — HOLD
- Ray Kingman (semcasting.com) — HOLD

### Variable resolution analysis

For each variable, the resolution path and what can go wrong:

#### `first_name` — ALL 17 RESOLVE

All 9 never-emailed bison contacts have names (proven by the provider lead
rows). All 8 cold-cohort contacts have names (required by
`bisonfactory._plan()` for staging; verified contacts without names are
excluded before they reach this point).

The template fallback "there" is a second line of defence and should not be
needed for any of the 17.

#### `company` — NEEDS VERIFICATION

`cadence.company_name(rec)` resolves from `company_facts.name` first, then
`rec.company`. It refuses domain-shaped values (values with a TLD in the
last word).

**Risk:** Records that have only a domain as their company field (e.g.
`company: "inmobi.com"` with no `company_facts.name`) will raise
`CompanyNameUnusable`. The step is held, not sent — this is fail-closed
behaviour, not a silent defect.

**Mitigation:** The 9 never-emailed bison contacts were previously enriched
for campaign 481 staging and likely have `company_facts`. The 8 cold-cohort
contacts need to be checked against the snapshot.

**Script:** `scripts/task159_variable_resolution.py` checks all 17 against
the snapshot. Run on a worktree with `work/queue.snapshot.jsonl`.

#### `angle_word` — ALL 17 RESOLVE (via fallback)

The resolution chain:
1. Contact's angle → client config `angle_labels[angle]` → if fits in 32 chars, use it
2. First clause of angle phrase → if fits in 32 chars, use it
3. Fallback: "the numbers behind the work" (31 chars, fits)

All 17 resolve. Contacts without an angle or with a persona that has no
configured angles get the fallback. The fallback is client-agnostic and
asserts nothing specific.

#### `angle_phrase` — ALL 17 RESOLVE (via fallback)

The resolution chain:
1. Contact's angle → client config `personas[persona].angles[angle]` → first clause
2. First angle in the persona's angle dict → first clause
3. Fallback: "how the work is tracked"

All 17 resolve. The fallback fires for contacts without an angle.

#### `sector` — ALL 17 RESOLVE (via fallback)

`company_facts.industry` or "services". All 17 resolve.

#### `line` — ALL 17 RESOLVE (via fallback)

Evidence or generic intro. All 17 contacts have signal=100% null, so all 17
use the generic fallback: "I work with {sector} teams on {angle_phrase}, and
I do not know how {company} handles it". This is an honest introduction.

### Summary: who cannot be sent to

| Contact | Risk | Blocking? |
|---------|------|-----------|
| Any of 17 with domain-only company and no `company_facts.name` | `CompanyNameUnusable` | YES — step held, not sent. Fail-closed. |
| Any of 17 with no `contact.name` | Greeting renders as "there," | NOT blocking — fallback fires, but reads oddly |

**The contact who cannot fill a variable is not in the first batch.** Finding
that now is cheaper than finding it at the gate. The script
(`scripts/task159_variable_resolution.py`) must be run against the production
snapshot before staging.

---

## 6. WHAT MUST BE TRUE BEFORE STAGING

1. **Run `scripts/task159_variable_resolution.py`** against the production
   snapshot. Every contact must have a resolvable `company`. Contacts that
   fail are excluded from the first batch.

2. **The sequence templates in EmailBison** use `{SUBJECT_N}` / `{BODY_N}`
   syntax, NOT the raw template variables. The rendering happens in Resonate
   OS before staging.

3. **`ensure_custom_variables`** must have been called for `subject_1`
   through `subject_3` and `body_1` through `body_3`. These are already in
   `bison.LEAD_VARIABLES` (which covers up to 6 steps).

4. **The thread_reply pattern** is `[False, True, False]` — set on the
   sequence steps when writing them to the provider.

5. **No "Re:" in any subject.** The provider auto-prepends it on
   `thread_reply: True` steps.

6. **The greeting guard** (`_refuse_bad_greetings`) runs on every rendered
   body before staging. It is wired into `_ensure_leads` and has 16 tests
   proving the wiring.

---

## 7. WHAT THIS DOES NOT SETTLE

- **Whether F,T,F is the right threading pattern.** It is what the biggest
  campaign does, and it is a design choice. TASK-080 measured no significant
  difference. An experiment is needed to prove it.

- **Whether three steps is the right number.** The CONTROL sequence uses
  three templates. The production target is five. The gap between three and
  five is filler that has no validated copy — and inventing filler to reach
  five is the thing this specification deliberately does not do.

- **Whether the 17 are the right cohort.** They are who survived all gates.
  Signal is 100% null, so the cohort is "nobody rejected them" — necessary
  but not a hypothesis.

- **The signature.** The CONTROL templates carry no signature. The sender
  identity is `Ivan, founder, Productive, works on project profitability for
  agencies` (from `config/clients/productive.yaml`). Whether to append a
  signature to the CONTROL bodies is an operator decision. The templates as
  they stand do not include one.

---

## 8. SUMMARY TABLE

| Dimension | Decision | Evidence |
|-----------|----------|----------|
| Opener | `persona_pain` — question-led, no prior-contact claim | Body text read against first-touch criteria |
| Steps | 3: persona_pain → comparable_proof → breakup | `cadence.TEMPLATES`, `EMAIL-CONTROL-2026-09-15.md` |
| Days | 1, 5, 21 | `cadence.STEPS` email days |
| Threading | F, T, F | `thread_reply` boolean on step; estate pattern |
| Thread field | `thread_reply` on each parent step | PROVIDER FACT from API route evidence |
| Subject on follow-up | Same as step 1; provider auto-prepends "Re:" | All 153 same-thread carry it automatically |
| Subject on step 3 | "closing the loop" — new thread | Distinct subject, standalone body |
| Variable syntax | Rendered per-contact, stored as `{BODY_N}` / `{SUBJECT_N}` | No `{FIRST_NAME}` or `{COMPANY}` on EmailBison |
| `first_name` fallback | "there" | `cadence.template_vars`; `_plan()` refuses before this |
| `company` fallback | NONE — raises `CompanyNameUnusable` | `cadence.company_name`; fail-closed |
| `angle_word` fallback | "the numbers behind the work" | `cadence.FALLBACK_ANGLE_WORD` |
| `angle_phrase` fallback | "how the work is tracked" | `cadence.angle_words` default |
| Cohort | 17 contacts | `BISON-COHORT-LIVE-2026-09-15.md` |
| Blocking risk | `company` unresolvable for domain-only records | Script checks all 17 |
