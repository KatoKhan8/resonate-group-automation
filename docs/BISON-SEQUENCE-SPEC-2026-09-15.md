---
title: "EmailBison Sequence Specification — the contract, not taste"
task: "TASK-148"
date: "2026-09-15"
builds_on:
  - "docs/EMAILBISON-COPY-REQUIREMENTS.md"
  - "docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md"
  - "docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md"
  - "docs/BISON-THREAD-FINDINGS-2026-09-15.md"
  - "docs/BISON-RENDER-QA-2026-09-15.md"
  - "docs/PRODUCTION-SCALE-POLICY.md"
  - "COPY-EXPERIMENTS.md"
---

# EmailBison Sequence Specification — 2026-09-15

**TASK-148 deliverable.** A sequence specification complete enough that Claude
can write it to the provider without making a single copy decision afterwards.
Not a campaign — Claude creates campaigns. This is the shape, the variables,
the threading, the CONTROL, the CHALLENGERS, and the sender rule.

**Read `EMAILBISON-COPY-REQUIREMENTS.md` first.** It is standing and outranks
anything concluded here. This document builds to it.

---

## 1. THE STEP GRAPH

Five steps. Each makes a different argument. The ladder is `email_five` from
`src/cadencelibrary.py`, which already encodes the progression requirement.

| Step | Key | Order | Purpose (from ladder) | Delay after (days) |
|------|-----|-------|----------------------|-------------------|
| 1 | em1 | 1 | **INTRO / CONTEXT.** Relevance, and who is writing. Why THIS person at THIS company, in their operational language, one clause saying what the product is, one question answerable in a line. | 3 |
| 2 | em2 | 2 | **PROBLEM (different angle).** A different part of how the business runs, a different question. Not the same argument rephrased. | 4 |
| 3 | em3 | 3 | **PRODUCT / RELEVANCE.** Say what the product IS and what it is worth. Use the product's name. Say what it joins up (only capabilities that fit this person's angle). One concrete consequence a team their size would recognise. | 4 |
| 4 | em4 | 4 | **FOLLOW-UP (different argument).** One focused idea and one question. No recap of earlier messages, no new pitch beyond the single point this message carries. | 9 |
| 5 | em5 | 5 | **CLOSE / EASY OUT.** Give them an easy no. Make no new pitch. Ask for nothing beyond permission to stop. Wrong-person redirect. | 1 (terminal, no successor) |

### Why five, and why these delays

Five is the current production target from `PRODUCTION-SCALE-POLICY.md` §6 and
the `email_five` ladder. It is a starting design, not a finding. The delays
(3, 4, 4, 9, 1) are read from the client config's `email_sequence.steps` and
match the cadence gaps measured against campaign 352's live sends:

    em1 day 1 → em2 day 4 = 3 days
    em2 day 4 → em3 day 8 = 4 days
    em3 day 8 → em4 day 12 = 4 days
    em4 day 12 → em5 day 21 = 9 days

The terminal wait of 1 is required by the provider (0 was refused on campaign
481). It carries no meaning.

### The shape argument

This is the INTRO → PROBLEM → PRODUCT → FOLLOW-UP → CLOSE arc that
`PRODUCTION-SCALE-POLICY.md` §1 and `EMAILBISON-COPY-REQUIREMENTS.md` §1 both
name. Each step has a distinct job:

- em1 opens with relevance and sender identity
- em2 shifts to a different operational angle
- em3 names the product and gives evidence
- em4 adds one new thought without repeating em1-em3
- em5 closes with an easy out and a wrong-person redirect

**No step asks the same question twice.** That was the defect TASK-136 found
on the LinkedIn side and it is exactly the risk here. The ladder's rung briefs
enforce progression by naming what the PREVIOUS step established.

---

## 2. WHICH STEPS THREAD, AND HOW

### The pattern

From `cadencelibrary.THREAD_REPLY_PATTERNS["email_five"]`:

| Step | thread_reply | Mechanism |
|------|-------------|-----------|
| em1 | **False** | New thread. Own subject. |
| em2 | **True** | Same-thread follow-up. Provider auto-prepends "Re:". |
| em3 | **False** | New thread. Own subject. |
| em4 | **True** | Same-thread follow-up. Provider auto-prepends "Re:". |
| em5 | **False** | New thread. Own subject. |

Shape: **F, T, F, T, F** — alternating new/follow-up/new/follow-up/new.

### Evidence

This is the pattern used by campaign 352, the estate's largest at 92,806 sent.
It is a DESIGN CHOICE, not evidence-backed performance.
`docs/BISON-THREAD-FINDINGS-2026-09-15.md` establishes that the estate has NO
control group at any position for same-thread vs new-thread. Every campaign
with sends uses `thread_reply=True` at step 2. Campaign 481 — the only one
with `False` there — has zero sends.

The pattern is recorded as a deliberate bet.

### The field that carries it

`thread_reply` is a boolean on the sequence step definition. PROVIDER FACT,
read from `GET /campaigns/{id}/sequence-steps`, field `thread_reply`. It is
also present on each scheduled email row. The two agree wherever both are
present.

### What the subject field contains for a thread reply

**A step carries an `email_subject` EVEN WHEN `thread_reply` is True.**
This is a provider fact measured on all 153 same-thread follow-ups in the
estate. The subject is carried for the provider's threading mechanism but the
prospect sees "Re: {original subject}" — the provider auto-prepends "Re:".

**Do not write "Re:" yourself.** The provider handles it. A template that
includes "Re:" would produce "Re: Re: ..." in the prospect's inbox.

The subject on a follow-up step should be a SHORT REFERENCE to the original
thread subject — it is the provider's anchor for threading, not a new subject
the prospect reads independently. The same subject as em1 (for em2) or em3
(for em4) is the correct choice, because the provider uses it to match the
thread.

### What this means for the sequence

| Step | Subject field | What the prospect sees |
|------|--------------|----------------------|
| em1 | `{SUBJECT_1}` — a full, standalone subject | The subject line |
| em2 | `{SUBJECT_2}` — same thread anchor as em1 | "Re: {em1 subject}" |
| em3 | `{SUBJECT_3}` — a new standalone subject | The subject line |
| em4 | `{SUBJECT_4}` — same thread anchor as em3 | "Re: {em3 subject}" |
| em5 | `{SUBJECT_5}` — a new standalone subject | The subject line |

em2's body must NOT re-introduce the sender from scratch. The
`FOLLOWUP_ADDENDUM` in `cadencelibrary.py` is appended to the rung's brief
when `thread_reply` is True, instructing the generator: "you are continuing
an existing conversation, not starting a new one. Add one thought. Do not
repeat what the earlier email said."

---

## 3. VARIABLES, VERIFIED

### The provider's custom variable system

EmailBison uses **single-brace, UPPERCASE** syntax: `{VARIABLE_NAME}`.
Measured on this estate 2026-09-14: 3,295 single-brace occurrences and ZERO
double-brace across 81 sequences. `{{first_name}}` would reach a prospect as
literal text.

The custom variables are declared on the workspace via
`bison.ensure_custom_variables()` and resolved against per-lead custom
variables at send time.

### What the provider accepts (from `bison.LEAD_VARIABLES`)

| Variable | Purpose | Source in our record |
|----------|---------|---------------------|
| `subject` | Single-step subject | Generated per lead |
| `body` | Single-step body | Generated per lead |
| `subject_1` through `subject_6` | Per-step subjects (numbered) | Generated per step per lead |
| `body_1` through `body_6` | Per-step bodies (numbered) | Generated per step per lead |
| `title` | Lead title/role | `contact.title` |
| `record_id` | Our internal record id | `record.id` |
| `contact_key` | Contact identifier | `contact.key` |
| `client` | Client slug | "productive" |
| `sender_id` | Sender identifier | Campaign sender config |
| `sender_account_id` | Sender account id | Campaign sender config |
| `provider_account_id` | Provider account id | Campaign sender config |

### Provider-side merge fields (from campaign 352 live evidence)

Three fields are resolved by the provider itself from lead data:

| Field | Provider resolves | Coverage on our 92 contacts |
|-------|------------------|---------------------------|
| `headline` | Yes | Low — requires LinkedIn headline |
| `industry` | Yes | 100% — from `company_facts.industry` |
| `location` | Yes | Low — requires LinkedIn location |

### THE CRITICAL FACT: no `first_name` and no `company` as provider variables

**There is no `{FIRST_NAME}` and no `{COMPANY}` merge variable on EmailBison.**
The whole email body — greeting included — travels as `{BODY_N}`. The
generator writes the greeting INTO the body text, and it travels as a custom
variable.

This means:
- The greeting is NOT delegated to the provider
- There is no provider-side substitution or fallback
- A broken greeting ("Hey ,") goes straight to the prospect
- The pre-write greeting guard (`bisonfactory._refuse_bad_greetings`) is the
  ONLY protection

### Variable coverage and empty-render behaviour

Measured against the 92 contacts on not-dropped records (from
`docs/BISON-RENDER-QA-2026-09-15.md`):

| Variable used in copy | Coverage | Empty-render behaviour |
|----------------------|----------|----------------------|
| first_name (in greeting) | 100% | **bisonfactory._plan() refuses contacts with no name.** The contact is excluded from staging. No variant sees them. |
| company (in body text) | 100% | Safe fallback: body text omits company references where the company is a domain string rather than a name. The generator is given the company value and decides whether to use it. |
| role/title (in body text) | 100% | Safe fallback: use sparingly, never as the only personalisation. The generator receives the title and may omit it. |
| industry | 100% (from company_facts) | Safe fallback: generic phrasing when industry is absent. |
| angle | 88% | **SAFE FALLBACK REQUIRED.** The generator receives the angle and writes to it. Where angle is absent, the body uses a generic operational framing. |
| specialties | 73% | **SAFE FALLBACK REQUIRED.** Never the only personalisation. Where absent, the body omits specialty references. |
| employee_range | 19% | **EXCLUDE THE RECORD** from any variant that uses it. Four out of five leads have nothing to put there. |
| company context (company_facts) | Variable | **Exclude the record** if facts are missing and the variant requires them. |
| trigger / researched observation | Very low | **Exclude the record.** Never invent. |

### The greeting rule

A greeting that renders empty fails the standing contract. The protection is
three-layered:

1. **`bisonfactory._plan()` refuses contacts with no first_name.** They never
   reach the generator.
2. **`bisonfactory._refuse_bad_greetings(plan)` checks every generated body**
   for three defect classes:
   - Empty greeting: regex `^(Hey|Hi|Hello)\s*,`
   - Literal placeholder: "undefined", "null", "None" in the first line
   - Planted cohort name: word-boundary match of another contact's first name
3. **The guard is wired into `_ensure_leads` on every `stage()` invocation.**
   Deleting the call makes the test fail — that is the wiring proof.

**Natural greeting style:** "Hey {first_name}," is appropriate where the tone
allows it. The client config's `tone.email` is "polished, professional, no em
dashes, no buzzwords, no fluff openers" — so "Hi {first_name}," or
"{first_name}," may be more appropriate than "Hey" for email. The variant
approach controls this (see §5).

### The signature rule

Sender identity comes from `clients.sender_identity(config)`:

    sender:
      name: Ivan
      role: founder
      company: Productive
      works_on: project profitability for agencies

**Do not hallucinate a sender name, title, company, phone number or anything
else.** The signature is baked into the body text by the generator, the same
way the greeting is. An invented sender is a claim about us the record cannot
support.

The signature should be present on every step. For very short same-thread
follow-ups, whether a full signature helps is an EVIDENCE question
(TASK-080 measures what the estate does). Until that evidence arrives, include
a brief signature on every step.

---

## 4. CONTROL AND CHALLENGERS

### CONTROL: the finding that none exists for email

**This is a FINDING.** The LinkedIn side has validated CONTROL copy: the
operator's hand-written fallbacks under `linkedin_sequence.fallbacks` in the
client config. Three human reads (TASK-098, TASK-130, TASK-136) compared
generated LinkedIn copy against those fallbacks and returned DOES NOT BEAT
FALLBACKS every time. So the fallbacks ARE the validated CONTROL arm for
LinkedIn.

**No equivalent exists for email.** The client config declares:

    linkedin_sequence:
      fallbacks:
        connection_note: hi, i work with agencies on...
        connected_1: how do you currently get visibility...
        ...

There is no `email_sequence.fallbacks` block. The email sequence's copy is
generated per lead by the model, with no hand-written baseline to compare
against.

**Consequence:** CONTROL has to be defined before anything ships. The options
are:

1. **The operator writes email fallbacks** — five steps, same shape as the
   LinkedIn ones, asserting nothing about the reader, true of any agency.
   These become the email CONTROL.
2. **The first generated campaign IS the CONTROL** — but that is unvalidated
   copy by definition, and the three LinkedIn reads already showed generated
   copy does not beat hand-written fallbacks.
3. **The LinkedIn fallbacks are adapted for email** — they are the only
   validated copy in the system. They assert nothing about the reader, they
   are true of any agency, and they have survived three human reads. The
   adaptation would be: keep the words, adjust the format for email (add
   subject lines, add signature, adjust for thread_reply on steps 2 and 4).

**Recommendation:** Option 3 is the fastest path to a CONTROL that is
validated rather than merely generated. The LinkedIn fallbacks already make
the five-beat arc:

    connection_note → INTRO (who, why connect)
    connected_1 / message_2 → PROBLEM (how do you get visibility)
    connected_2 / message_3 → CONSEQUENCE (most agencies find out at the end)
    connected_3 / message_4 → PRODUCT (we built productive so...)
    connected_4 → CLOSE / EASY OUT (happy to leave it here, wrong person?)

That arc maps directly onto em1-em5. The adaptation is mechanical: add
subjects, add signature, adjust for same-thread on em2/em4.

**Until CONTROL is defined, generated copy runs as CHALLENGER against
nothing, and a "winner" has no baseline to beat.**

### CHALLENGERS: five variants per step, differing in angle

From `COPY-EXPERIMENTS.md` and `EMAILBISON-COPY-REQUIREMENTS.md` §5:

**At least five materially different variants per important position.** They
differ in ANGLE, TONE, STRUCTURE, HOOK and CTA — not synonyms.

The five styles for email (from `COPY-EXPERIMENTS.md` §2):

| Style | What differs |
|-------|-------------|
| **short and direct** | Brief body, gets to the point fast, minimal framing |
| **casual** | Conversational tone, "Hey" greeting, lower register |
| **professional** | Polished tone, "Hi" or name-only greeting, structured argument |
| **consultative** | Question-led, positions sender as advisor, asks before telling |
| **problem-led** | Opens with the pain, not the sender, leads with consequence |

Each variant is a COMPLETE message (subject + body), not a factorial of parts.
Five subjects × five bodies is 625 cells nobody has traffic to settle.

### How many variants the provider supports

From `docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md` §1.5:

**A variant is a first-class sequence step** with `variant: true` and
`variant_from_step: <parent_id>`. Campaign 352 carries 44 steps, 39 of which
are variants — 5 parents with up to 6 variants each.

The provider supports **at least 6 variants per parent step** (verified on
campaign 352: step 4035 has variants 4036, 4192, 4193, 4194, 4195, 4196 —
six siblings). `MAX_SEQUENCE_STEPS = 6` in `bison.py` caps the numbered
variables at 6, so the system supports up to 6 steps and the provider
supports at least 6 variants per step.

**Five variants plus one CONTROL = six arms per step.** That fits.

### How a lead is assigned to a variant

From `COPY-EXPERIMENTS.md` §4: `assign()` is a pure function of `(campaign,
step, contact, allocation version)`, hashed. The same planned touch resolves
the same way on every read. Each step assigns independently. Traffic lands
within a few percent of the configured shares.

**One contact, one variant, per step.**

### Variant identity is durable

From TASK-141: a scheduled email's `sequence_step_id` is the VARIANT step's
id, not the parent's. The variant is identifiable from provider data for all
time through the step listing. The events endpoint carries a compact
`sequence_step_variant` index but only for 10 days.

**The variant-to-step mapping must be preserved at send time.** The
sequence-steps listing gives the mapping today, but if steps are deleted or
renumbered, the mapping is lost.

### The evaluator's minimum

From `COPY-EXPERIMENTS.md` §6: 30 exposures per variant, 8 outcomes total,
below which the answer is `insufficient_data` whatever the rates look like.
With 6 arms (5 challengers + CONTROL) and 30 exposures each, a step needs
180 leads before the evaluator can call anything.

### What the validated fallback stays CONTROL means

The operator's instruction: "the validated fallback stays CONTROL; generated
copy runs as CHALLENGER." For LinkedIn this is settled — the
`linkedin_sequence.fallbacks` are CONTROL. For email, **CONTROL must be
defined first** (see the finding above). Until it is, every generated email
is an uncontrolled experiment.

---

## 5. SENDERS

### The email sender estate

From `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md` §8:

- **225 sender-emails** on the EmailBison workspace (PRODUCTIVE, id 10)
- All 225 are in `Connected` status
- 86 Productive-branded domains represented
- Each carries a `daily_limit` field (typically 15-50 per inbox)
- 224 of 225 have warmup enabled
- `emails_sent_count` on each row shows current utilisation

**Ownership is unprovable.** `provider_account_id` is populated on all 225
inboxes, but the codebase has no EmailBison inbox ownership route. The system
cannot prove which human owns which inbox. This is a known gap
(`PRODUCT-GAPS.md`).

### The allocation rule

**Multiple inboxes per campaign, where capacity safely allows.** The
allocation rule:

1. **Read `daily_limit` from each sender row.** This is the provider-stated
   ceiling for that inbox.
2. **Read `emails_sent_count` to determine current utilisation.** An inbox at
   45/50 has 5 slots; an inbox at 10/50 has 40.
3. **Assign 3-5 senders per campaign of ~50 leads.** This spreads the load
   and protects individual inbox reputation.
4. **Never raise a configured `daily_limit` to make a number work.** The
   sender estate is never made to carry more by raising a limit. Add inboxes
   or add days.

### Where the capacity number comes from

The `daily_limit` is a provider-side field on each sender-email row, set by
the workspace administrator. It is NOT a Resonate OS configuration — it is
read from `GET /sender-emails` and reflects the limit configured in the
EmailBison UI.

**Do not raise it.** `PRODUCTION-SCALE-POLICY.md` §3: "Never raise a per-seat
limit to gain throughput. Add senders, or add days."

### The constraint that actually binds

Email capacity is currently idle. From `PRODUCTIVE-PILOT-PLAN.md`: "15
campaigns, none sending." The 225 inboxes are connected and warmed up but
have no active sends. Email throughput is not the constraint — approval and
copy quality are.

---

## 6. WHAT MUST BE TRUE BEFORE THIS SHIPS

### The checklist

1. **CONTROL must be defined for email.** Either the operator writes email
   fallbacks, or the LinkedIn fallbacks are adapted. Until then, generated
   copy has no baseline.
2. **Variable coverage must be measured against the real queue.** This
   worktree has no `work/` directory. The measurement must happen on
   Claude's worktree where `work/queue.jsonl` exists.
3. **The greeting guard must run on every generated body.** It already does
   (`bisonfactory._refuse_bad_greetings`, wired into `_ensure_leads`). The
   test suite proves the wiring.
4. **Render representative leads through `bisonfactory`.** Not a second
   path. `scripts/render_preview.py` renders through the same code that
   builds the real payload.
5. **Read back from the provider after writing.** The provider state, not
   the local payload, is the final truth.
6. **No variant performance claim where attribution is not measurable.**
   Attribution IS measurable on EmailBison (TASK-141 established this),
   but only when the variant-to-step mapping is preserved.

### What may not happen

- No hardcoded name reaching more than one lead
- No blank, undefined or null greeting
- No invented sender, signature, capability, metric or history
- No five-steps-that-are-one-step-five-times
- No widening a quality gate to make copy pass — regenerate the copy
- No promotion on a 2xx without a readback
- No `{{double_brace}}` syntax — single-brace only
- No "Re:" written by hand — the provider auto-prepends it

---

## 7. SUMMARY TABLE

| Dimension | Decision | Evidence |
|-----------|----------|----------|
| Steps | 5, keyed em1-em5 | `email_five` ladder, client config |
| Purposes | INTRO → PROBLEM → PRODUCT → FOLLOW-UP → CLOSE | `EMAIL_FIVE_LADDER` in `cadencelibrary.py` |
| Delays | 3, 4, 4, 9, 1 days | Client config, measured against campaign 352 |
| Threading | F, T, F, T, F | `THREAD_REPLY_PATTERNS["email_five"]` |
| Thread field | `thread_reply` boolean on step | PROVIDER FACT from API |
| Subject on follow-up | Same as parent, provider auto-prepends "Re:" | All 153 same-thread carry it |
| Variable syntax | Single-brace UPPERCASE: `{BODY_1}` | 3,295 occurrences, 0 double-brace |
| first_name | NOT a provider variable; baked into body | No `{FIRST_NAME}` on the workspace |
| Greeting protection | `_refuse_bad_greetings` + `_plan()` refusal | 16 tests, wiring proven |
| Signature | From `clients.sender_identity(config)` | Ivan, Founder, Productive |
| CONTROL (email) | **DOES NOT EXIST YET** — finding | No `email_sequence.fallbacks` in config |
| CONTROL (LinkedIn) | Operator's fallbacks, validated by 3 human reads | `linkedin_sequence.fallbacks` |
| CHALLENGERS | 5 styles: short-direct, casual, professional, consultative, problem-led | `COPY-EXPERIMENTS.md` §2 |
| Variants per step | Up to 6 (provider supports ≥6, system caps at 6) | Campaign 352: 6 siblings verified |
| Assignment | Hashed pure function, sticky per contact per step | `COPY-EXPERIMENTS.md` §4 |
| Evaluator minimum | 30 exposures/variant, 8 outcomes total | `COPY-EXPERIMENTS.md` §6 |
| Senders | 225 inboxes, 3-5 per campaign, never raise limits | `GET /sender-emails`, 225 total |
| Sender capacity | Currently idle — 15 campaigns, none sending | `PRODUCTIVE-PILOT-PLAN.md` |

---

## 8. FILES CHANGED

- `docs/BISON-SEQUENCE-SPEC-2026-09-15.md` — this document

## 9. RESULT BLOCK

    STATUS: DONE
    COMMIT SHA: (see git log)
    TESTS: No code changes. Specification document only.
    FILES CHANGED:
      docs/BISON-SEQUENCE-SPEC-2026-09-15.md — new
    FINDINGS:
      1. No email CONTROL exists. The client config has
         linkedin_sequence.fallbacks but no email_sequence.fallbacks.
         Generated email copy has no validated baseline to beat.
         RECOMMENDATION: adapt the LinkedIn fallbacks for email, or have
         the operator write email-specific fallbacks.
      2. The greeting is NOT a provider-side variable. EmailBison has no
         {FIRST_NAME} merge field. The entire body including greeting
         travels as {BODY_N}. A broken greeting goes straight to the
         prospect.
      3. The F,T,F,T,F threading pattern is a design choice, not
         evidence-backed. The estate has no control group for same-thread
         vs new-thread at any position.
      4. Same-thread follow-ups that got replies are LONGER (857 chars)
         than new-thread emails (571 chars). The "be short on follow-ups"
         hypothesis is not supported.
      5. The provider auto-prepends "Re:" on all 153 same-thread
         follow-ups. Do not write "Re:" in templates.
      6. 225 EmailBison inboxes exist, all Connected, currently idle.
         Email throughput is not the constraint — approval and copy
         quality are.
      7. employee_range coverage is 19% — exclude the record from any
         variant that uses it, do not fallback.
      8. Variable coverage must be measured on the production worktree
         where work/queue.jsonl exists. This worktree has no work/.
    RISKS:
      - Without email CONTROL, a "winner" among challengers has no
        baseline and the experiment is uncontrolled
      - The greeting is baked into body text with no provider-side
        safety net; the pre-write guard is the only protection
      - 225 inboxes with unprovable ownership — the system cannot prove
        which human owns which inbox
    RECOMMENDED CLAUDE ACTION:
      1. Define email CONTROL — adapt LinkedIn fallbacks or write new ones
      2. Measure variable coverage on production worktree
      3. Create the campaign (Claude creates campaigns, not Qwen)
      4. Stage, read back, promote within the established gates
