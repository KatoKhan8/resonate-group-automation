# EmailBison Cohort Design — 2026-09-15

TASK-102. The same cohort philosophy for EmailBison that TASK-096 applies to
the estate: coherent cohorts, not one campaign per lead. Supported variables
only. Correct signatures. Meaningful variants. Conversational sequences with
same-thread follow-ups.

**This document creates no campaign. It designs what one would look like if
the evidence supported it, and says plainly where the evidence stops.**

---

## 1. THE EMAIL CEILING

**Snapshot:** `work/queue.snapshot.jsonl`, stamped 2026-09-14T21:52:15Z from
master 0ac5e60, 300 records.

| Population | Count | Rule |
|------------|-------|------|
| Total records | 300 | all records in snapshot |
| Not-dropped records | 300 | status != 'dropped' (none are) |
| Contacts on not-dropped | 92 | one contact per record where present |
| Contacts with email | 87 (94.6%) | contact.email is non-empty |
| Sendable email contacts | 56 (64.4%) | contact.sendable == True |
| Not sendable | 31 | no verdict (22), accept_all/unsafe (9) |

**What "not sendable" means.** 22 of the 31 have no email verdict at all —
they were never verified. 9 have a verdict of `accept_all` with
`is_safe_to_send: False` from Reoon. Neither group may receive email. The
ceiling for any EmailBison campaign is **56 contacts**.

**Sample:** all 300 records, all 92 contacts, all 87 with email, all 56
sendable. No pagination issue — the snapshot is the whole estate.

---

## 2. FIELD COVERAGE FOR THE THREE EMAILBISON MERGE VARIABLES

EmailBison exposes exactly three provider-level merge variables for use in
email templates: `{HEADLINE}`, `{INDUSTRY}` and `{LOCATION}`. There is no
`{first_name}` and no `{company}` — the whole body travels as `{BODY_N}`.
(PROVIDER FACT — measured on campaign 352's sequence steps, documented in
`docs/BISON-PROVIDER-TRUTH-2026-09-14.md`.)

### 2a. {HEADLINE} — NOT AVAILABLE

**Coverage: 0/87.** The headline is a LinkedIn profile field. Our records do
not carry it. It is not in `contact`, `research`, `context`, `signal`, or
any other field on any record. The provider resolves it from the lead's
LinkedIn profile when EmailBison has one, but we do not populate it as a
custom variable and we do not have the data to do so.

**Verdict: this variable may not be used in any sequence design.** A template
containing `{HEADLINE}` would render against whatever EmailBison has on file,
which is nothing for leads we create. An empty or absent headline in a
greeting goes straight to the prospect.

### 2b. {INDUSTRY} — 100% COVERAGE

**Coverage: 87/87 email contacts (100%).** Source: `company_facts.industry`.

| Industry | Email contacts | Sendable |
|----------|---------------|----------|
| Advertising Services | 51 | 29 |
| Marketing & Advertising | 18 | 14 |
| Marketing Services | 14 | 10 |
| Design Services | 2 | 2 |
| Translation and Localization | 1 | 0 |
| Business Consulting and Services | 1 | 1 |

**Six distinct values, dominated by marketing/advertising agencies (85% of
sendable).** This is a real and usable variable, but the distribution is
heavily skewed. "Advertising Services" alone is 52% of the sendable pool.

**Caveat.** The industry field comes from the provider's LinkedIn
classification. It is the company's industry, not the contact's. A COO at an
advertising agency is in "Advertising Services" whether they personally do
advertising or not. For cohort grouping this is fine — the company is the
unit. For greeting personalisation it means `{INDUSTRY}` in a sentence like
"what we see with {INDUSTRY} agencies" is a company-level claim, not a
person-level one.

### 2c. {LOCATION} — 100% COVERAGE (WITH A SHAPE PROBLEM)

**Coverage: 87/87 email contacts (100%).** Source: `company_facts.offices`,
which is a list of address strings.

**The shape problem.** EmailBison's `{LOCATION}` resolves to a LinkedIn
location — typically a city or metro area like "Zagreb" or "Greater New York
City". What we have is full street addresses: `"Islands Brygge 79A,
København S, Hovedstaden, 2300, DK"`. These are 74 distinct values across 87
contacts.

To use `{LOCATION}` we would need to extract a city or country from the
address string and populate it as a custom variable. The addresses are
messy but parseable — the country code is always the last token, and the
city is usually present. But this is a RESONATE RECONSTRUCTION, not a
provider fact, and it would need its own extraction logic and its own
fallback for addresses that do not parse cleanly.

**Verdict: usable but not free.** An extraction function could populate a
`location` custom variable at 100% coverage with city or country. It has not
been written. Until it is, `{LOCATION}` is available in principle but not in
practice.

---

## 3. FIELD COVERAGE FOR COHORT GROUPING

Beyond the three merge variables, these fields are available for deciding
which contacts go into which cohort.

| Field | Coverage (n=56 sendable) | Distinct values | Cohort-safe? |
|-------|--------------------------|-----------------|-------------|
| `company_facts.industry` | 56/56 (100%) | 5 | YES — company-level, stable |
| `contact.angle` | 53/56 (95%) | 5+1 | YES — role-based signal |
| `contact.persona` | 56/56 (100%) | 2 | YES — buyer role |
| `contact.title` | 56/56 (100%) | 40+ | TOO FINE for cohort keys |
| `company_facts.employee_range` | 0/56 (0%) | — | NO — null everywhere |
| `company_facts.employees` | 56/56 (100%) | 56 | CONTAMINATED — 7 conflicts, 64 disagreements across 300 records |
| `qualification.verdict.icp_grade` | 56/56 (100%) | 2 | YES — borderline_icp (48) / clear_non_icp (8) |
| `qualification.verdict.icp_confidence` | 56/56 (100%) | 3 | MAYBE — low (44), medium (11), high (1) |
| `signal.type` | 0/56 (0%) | — | NO — null everywhere |

**Angle distribution (sendable, n=56):**

| Angle | Count | Share |
|-------|-------|-------|
| founder | 34 | 61% |
| operations | 14 | 25% |
| delivery | 2 | 4% |
| finance | 2 | 4% |
| economic_buyer | 1 | 2% |
| (missing) | 3 | 5% |

**Persona distribution (sendable, n=56):**

| Persona | Count | Share |
|---------|-------|-------|
| economic_buyer | 45 | 80% |
| champion | 11 | 20% |

---

## 4. THE HONEST VERDICT ON SIZE

**The entire sendable estate is 56 contacts.** The policy target is ~50 per
cohort. The estate supports **one cohort of 56** and nothing else at that
size.

Splitting by industry produces:

| Industry (sendable) | Count | Viable as standalone cohort? |
|---------------------|-------|------------------------------|
| Advertising Services | 29 | No — below 50, below 25 |
| Marketing & Advertising | 14 | No |
| Marketing Services | 10 | No |
| Design Services | 2 | No |
| Business Consulting and Services | 1 | No |

No single industry reaches 25. The only honest cohort at this estate's
scale is **all 56 sendable contacts as one cohort**, with industry variation
expressed through the `{INDUSTRY}` merge variable in the copy rather than
through separate campaigns.

**What it would take to reach a second cohort:** more discovery (the signal
field is null for all 300 records), more enrichment (employee_range is null,
headline is absent), or more leads entering the pipeline from a new batch.
None of these are engineering problems — they are pipeline problems.

---

## 5. THE COHORT-SHAPED CAMPAIGN DESIGN

### 5a. Hypothesis

Marketing agency decision-makers (founders, COOs, operations leads) at
agencies with 10-1000 employees will reply to a five-email sequence that
leads with industry-specific operational relevance, names the product
explicitly at step 3, and uses same-thread follow-ups at steps 2 and 4 to
continue the conversation rather than restarting it.

### 5b. The 5-step sequence

| Step | Day | thread_reply | Purpose |
|------|-----|-------------|---------|
| 1 | 0 | **False** (new thread) | Relevance and who is writing. Why THIS person at THIS company, in their operational language. One clause saying what the product is. One question they can answer in a line. |
| 2 | 3 | **True** (same-thread) | A different angle from the first email. Not the same argument rephrased: a different part of how the business runs, and a different question. |
| 3 | 6 | **False** (new thread) | SAY WHAT THE PRODUCT IS AND WHAT IT IS WORTH. Use the product's name. Say in one line what it joins up — only the capabilities that fit this person's angle. Give one concrete consequence a team their size would recognise. |
| 4 | 9 | **True** (same-thread) | A follow-up that makes a DIFFERENT argument from every email before it. One focused idea and one question — no recap of earlier messages and no new pitch beyond the single point this message carries. |
| 5 | 13 | **False** (new thread) | Close the loop. Give them an easy no, make no new pitch, ask for nothing beyond permission to stop. |

**Thread-reply pattern: (F, T, F, T, F).** This is `THREAD_REPLY_PATTERNS['email_five']` from `src/cadencelibrary.py`. The follow-up addendum is appended to the rung's purpose in the generation prompt so the model knows it is continuing a thread.

### 5c. Variables used

| Variable | Source | Coverage | How it travels |
|----------|--------|----------|----------------|
| `{INDUSTRY}` | `company_facts.industry` → custom variable `industry` | 56/56 (100%) | Declared as custom variable, populated per lead at staging |
| `{BODY_N}` | Generated copy per step | 56/56 | Custom variable `body_1` through `body_5` |
| `{SUBJECT_N}` | Generated subject per step | 56/56 | Custom variable `subject_1` through `subject_5` |

**Variables NOT used:**
- `{HEADLINE}` — not in our records (0/87). Cannot be used.
- `{LOCATION}` — available in principle but the extraction function has not been written. Not used in this design.
- `{first_name}` — does not exist at EmailBison. The greeting is baked into the body text and travels as `{BODY_N}`. The pre-write greeting guard (`_refuse_bad_greetings`) is the only protection.

**The `{INDUSTRY}` variable needs to be added to `LEAD_VARIABLES` in `src/providers/bison.py`** if it is not already there. Currently `LEAD_VARIABLES` carries `subject`, `body`, `title`, `record_id`, `contact_key`, `client`, `sender_id`, `sender_account_id`, `provider_account_id`, and the numbered `subject_N`/`body_N` pairs. `industry` is not in the list. The older campaigns (335, 274, 327, 328, 352) carried it as a provider-defined variable, but our code does not declare or populate it.

### 5d. Variants per position

Five variants per step, differing in angle, hook, or framing — never a
synonym swap. The style vocabulary is from `COPY-EXPERIMENTS.md`:
short-and-direct, casual, professional, consultative, problem-led.

| Step | Variant A | Variant B | Variant C | Variant D | Variant E |
|------|-----------|-----------|-----------|-----------|-----------|
| 1 (new thread) | Pain-led: the operational cost of invisible delivery | Industry pattern: what we see across {INDUSTRY} agencies | Peer story: a similar agency that changed what was visible | Product framing: what the product joins up | Direct question: the one thing that would change this quarter |
| 2 (same-thread) | Different angle: resource planning, not time tracking | Different angle: margin visibility, not utilisation | Different angle: client communication, not reporting | Different angle: scaling delivery, not hiring | Different angle: project economics, not billing |
| 3 (new thread) | Product name + capability match for founders | Product name + capability match for operations | Product name + capability match for delivery leads | Product name + capability match for finance | Product name + capability match for growth |
| 4 (same-thread) | One focused idea: the cost of reconstructing after the fact | One focused idea: what changes when visibility is live | One focused idea: the conversation that becomes possible | One focused idea: the decision that was blocked by missing data | One focused idea: what the team already knows but cannot see |
| 5 (new thread) | Easy no: "if this isn't relevant, just say so" | Easy no: "happy to close the loop if the timing is wrong" | Easy no: "no hard feelings if this isn't a priority" | Easy no: "I'll stop here unless you'd like to continue" | Easy no: "totally understand if this isn't for you" |

**This is a design, not generated copy.** The variants above describe the
*direction* of each variant, not the words. The words come from the
generator, which takes the ladder's purpose string and the style hint and
produces the actual subject and body.

### 5e. Signature

The signature is carried in the body text (no provider-side variable for
sender name). The estate's existing pattern:

    Best,
    Alex Chen
    Founder, Resonate Group

This is baked into every generated body. A variant that changes the
signature is a variant that changes what is true about the sender, and
`COPY-EXPERIMENTS.md` §10 says style may not change what is true.

---

## 6. CAMPAIGN 481 — THE EXISTING VEHICLE

**PROVIDER FACT.** Campaign 481 is paused with 23 leads, 5 provider steps,
and 0 sent.

| Property | Value |
|----------|-------|
| id | 481 |
| status | paused |
| emails_sent | 0 |
| total_leads | 23 |
| open_tracking | FALSE |
| thread_reply pattern | (F, F, F, F, F) — all new thread |
| steps | 5 parent steps |

**Campaign 481 is the only all-new-thread campaign in the estate.** Every
other campaign with sends uses `thread_reply=True` at step 2 at minimum.
Campaign 481 was designed as the control that does not exist — an
all-new-thread sequence against which the alternating pattern could be
compared. It has never sent.

### Is 481 the right vehicle?

**Arguments for using 481:**
- It already has 23 leads staged and a 5-step sequence defined.
- It is paused and `EMAIL_ACTIVATE` is not in `providerwrites.SUPPORTED`, so
  nothing can send accidentally.
- Its all-new-thread pattern provides a natural comparison arm: if the
  sequence is rebuilt with (F, T, F, T, F), the 23 leads could be split
  between the two patterns.

**Arguments against:**
- The 23 leads may have been staged under the old copy, which was generated
  against a different ladder. The sequence step templates on the provider
  would need to be rebuilt from scratch — EmailBison sequence steps are
  append-only, and the existing steps cannot be replaced.
- The 23 leads are a subset of the 56 sendable. Using 481 means working
  with a pre-selected group rather than the full cohort.
- A new campaign with all 56 leads and the (F, T, F, T, F) pattern from the
  start is simpler than retrofitting 481.

**Verdict: 481 should be left alone.** It is a paused experiment that was
designed to answer a different question (all-new-thread vs alternating).
Rebuilding its sequence would not answer that question because the leads
were staged under the old copy. A new campaign with the full sendable pool
and the designed pattern is the cleaner vehicle. 481's value is as a
structural reference — it proves the all-new-thread arm was considered and
deliberately not run.

---

## 7. EVIDENCE VS BETS

### What rests on evidence

| Claim | Evidence kind | Source |
|-------|--------------|--------|
| 56 sendable contacts exist | PROVIDER FACT | queue.snapshot.jsonl, sendable=True, reoon valid |
| Industry is 100% covered | PROVIDER FACT | company_facts.industry, 87/87 email contacts |
| EmailBison has {INDUSTRY}, {LOCATION}, {HEADLINE} and nothing else | PROVIDER FACT | campaign 352 sequence steps, BISON-PROVIDER-TRUTH |
| The ladder is 5 steps with purposes | PROVIDER FACT | EMAIL_FIVE_LADDER in cadencelibrary.py |
| The thread_reply pattern is (F, T, F, T, F) | PROVIDER FACT | THREAD_REPLY_PATTERNS['email_five'] |
| The follow-up addendum tells the model it is continuing a thread | PROVIDER FACT | FOLLOWUP_ADDENDUM in cadencelibrary.py |
| The greeting guard runs before the write | PROVIDER FACT | _refuse_bad_greetings in bisonfactory.py |
| open_tracking is False estate-wide | PROVIDER FACT | every campaign row |
| 8.49% reply rate for 8-step sequences | UNREPRODUCED — may not be quoted | — |

### What rests on a bet

| Claim | Why it is a bet |
|-------|----------------|
| The alternating (F, T, F, T, F) pattern is the right one | The estate has NO CONTROL GROUP. Every campaign with sends uses thread_reply=True at step 2. Campaign 481 (F, F, F, F, F) has zero sends. The alternating structure is a design choice, not an evidence-backed one. |
| 56 contacts is enough for a meaningful cohort | It meets the ~50 target but is the entire sendable pool. There is no holdout, no A/B split with statistical power, and no second cohort to compare against. |
| Five variants per position is the right number | The copy experiment framework supports five as a minimum. With 56 contacts, each variant at each step gets ~11 exposures — below the 30-exposure minimum the evaluator needs before it may declare anything other than `insufficient_data`. |
| {INDUSTRY} in the copy improves relevance | It is available and populated, but whether "what we see with {INDUSTRY} agencies" reads as relevant or as generic is a judgement call, not a measured finding. |
| The cohort is one group of 56, not split by industry | The alternative — separate campaigns per industry — produces campaigns of 29, 14, 10, 2, and 1. None is viable. But "one cohort" is a practical conclusion from small numbers, not an evidence-backed finding that the industry does not matter. |

---

## 8. WHAT MUST EXIST BEFORE THIS CAMPAIGN CAN RUN

1. **`industry` must be added to `LEAD_VARIABLES`** in `src/providers/bison.py`
   and declared via `ensure_custom_variables`. Currently absent.

2. **The generation pipeline must populate `industry`** per lead at staging
   time, reading from `company_facts.industry` and writing to the custom
   variable.

3. **The copy must be generated** — five variants at each of five positions,
   25 messages total. Each must pass `campaignqa` lint, the greeting guard,
   and the claim safety check.

4. **A human must read the sequence** before promotion. `pushable` was
   retired as the promotion criterion; the human read is the gate.

5. **`EMAIL_ACTIVATE` must be added to `providerwrites.SUPPORTED`** or the
   campaign must be activated manually. Currently it is not in the supported
   set.

---

## OBSERVATIONS (with n)

- The estate is 300 records and 92 contacts. 56 are sendable by email. The
  entire email campaign capacity is one cohort of 56. (n=300 records, n=92
  contacts, n=56 sendable)

- Industry is 100% covered but heavily skewed: 85% of sendable contacts are
  in three adjacent marketing/advertising categories. (n=56)

- Angle is 95% covered and dominated by founders (61%). (n=53 with angle)

- The signal field is null for all 300 records. No signal-based cohort
  grouping is possible. (n=300)

- 29 of 87 email contacts already have a `bison_lead_id`, meaning they were
  previously staged at EmailBison (in campaigns 352 or earlier). They are
  not available for a new campaign without deduplication. (n=87)

## HYPOTHESES

- A single cohort of 56 sendable contacts, using `{INDUSTRY}` for in-copy
  personalisation and five variants per position, will produce measurable
  reply variation across variants if the variants are genuinely different in
  angle.

- The alternating (F, T, F, T, F) thread-reply pattern will produce replies
  at steps 2 and 4 that are at least 80% of the adjacent new-thread steps,
  consistent with campaign 352's observed ratio. (Based on ATTRIBUTION
  HYPOTHESIS data from TASK-080: 82% at step 1→2, 89% at step 3→4.)

## PROVEN LEARNINGS

None survive the sample-size objection. The estate has 56 sendable email
contacts, zero control groups, and no reproduced reply rate. TASK-059 left
this section empty for the same reason and was right to.
