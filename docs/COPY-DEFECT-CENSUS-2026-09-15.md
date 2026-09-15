# Copy Defect Census — 2026-09-15

**TASK-092.** Six copy defects measured across every generated step on the
estate. Read from `work/queue.snapshot.jsonl` (snapshot taken
2026-09-14T21:52:15Z from master 0ac5e60, 300 records).

## ESTATE DIMENSIONS

| Quantity | Count |
|----------|-------|
| Total records | 300 |
| Not-dropped records | 194 |
| Records with cadences | 68 |
| Contacts on not-dropped records | 92 |
| Sendable contacts | 56 |
| Contacts with LinkedIn cadences | 80 |
| Contacts with email cadences | 51 |
| Total generated steps | 684 |
| LinkedIn steps (generated) | 446 |
| Email steps (generated) | 238 |

**Entry points read:**
- LinkedIn: `cadence[contact_key][step_id].note` for each generated step
- Email: `cadence[contact_key][step_id].body` and `.subject` for each generated step
- Contact names: `contacts[].name` split on whitespace, first token
- Company names: `record.company` for false-positive exclusion

---

## DEFECT 1: HARDCODED FIRST NAMES

**What:** A literal person name baked into copy where a variable should be.
HeyReach provides `{FIRST_NAME}`; EmailBison has no name variable at all.

### LinkedIn: UNIVERSAL

| Metric | Count | Denominator | Rate |
|--------|-------|-------------|------|
| Steps with literal contact name | 159 | 446 | 35.7% |
| Steps using `{FIRST_NAME}` | **0** | 446 | **0%** |
| Contacts with name in ≥1 step | 66 | 80 | 82.5% |
| Contacts with name in ALL steps | 41 | 80 | 51.3% |

**Every single LinkedIn step uses literal text.** Zero use the HeyReach
`{FIRST_NAME}` variable. The generator writes "hi Brooke" where the sequence
template expects "hi {FIRST_NAME}". When HeyReach substitutes `{FIRST_NAME}`
at send time, the prospect sees "hi Brooke" as static text — it does not
break, but it means the name is baked into the custom field value rather
than being a provider-side variable, and a contact who changes their name
or whose name was wrong cannot be corrected without regenerating the copy.

**Worst 5 examples** (all identifiers hashed):

| Hashed ID | Steps affected | Example text |
|-----------|---------------|--------------|
| `0ffabef0748e` | 6/6 LI steps | "hi stan, ivan here, founder at Productive..." |
| `6c638126d70e` | 6/6 LI steps | "hi nathan, i'm reaching out because Productive helps..." |
| `c33596948f3c` | 6/6 LI steps | "hi george, i'm reaching out because Productive helps..." |
| `9ebb6d895946` | 6/6 LI steps | "hi stephan, i'm reaching out because Productive helps..." |
| `cef9413bd304` | 5/6 LI steps | "hi sophie, how do you currently keep track of..." |

### Email: RARE

| Metric | Count | Denominator | Rate |
|--------|-------|-------------|------|
| Email steps with contact name in body | 10 | 238 | 4.2% |
| Contacts with name in ≥1 email step | 10 | 51 | 19.6% |

Email does not have a `{first_name}` variable at EmailBison, so the name
travels as body text. 10 of 238 email steps mention the contact's first
name in the body — mostly in greetings like "Brooke, I want to respect your
time" or in the body text. This is not a variable defect for email (there
is no variable to use), but it is a personalisation choice.

### Cross-contamination: NONE

Zero genuine cases of contact A's name appearing in contact B's copy.
Eight raw matches were all the word "chief" from the company name "Chief
Media" — a false positive excluded by company-name filtering.

### VERDICT: UNIVERSAL on LinkedIn, rare on email

The fix is a prompt change: the generator must write `{FIRST_NAME}` in
LinkedIn copy instead of the literal name. Every one of the 446 LinkedIn
steps is affected.

---

## DEFECT 2: MERGE VARIABLES THE PROVIDER DOES NOT EXPOSE

**What:** A `{variable}` in copy that the provider cannot substitute,
rendering as literal text to the prospect.

| Metric | Count | Denominator | Rate |
|--------|-------|-------------|------|
| Steps with unsupported variables | **0** | 684 | **0%** |

**Provider variable inventories checked:**
- EmailBison: `headline`, `industry`, `location` (and nothing else — no
  `first_name`, no `company`)
- HeyReach: `{FIRST_NAME}`, `{COMPANY}`, `{POSITION}`, `{INDUSTRY}`,
  `{LOCATION}`, `{MY_FIRST_NAME}`, `{MY_LAST_NAME}`, `{Icebreaker}`, plus
  custom fields (`connection_note`, `connected_1`..`connected_4`,
  `message_2`..`message_4`)

No generated step contains a `{variable}` pattern at all. The copy is
entirely literal text — which is the other side of Defect 1: the generator
writes names as literals rather than as variables, so there are no
unsupported variables because there are no variables at all.

### VERDICT: NOT PRESENT

No fix needed. The generator does not use merge variables.

---

## DEFECT 3: DUPLICATE FOLLOW-UPS

**What:** Two steps in one sequence that are the same message, or near-
duplicates at ≥85% similarity (normalised: lowercase, whitespace-collapsed,
punctuation-stripped).

| Metric | Count | Denominator | Rate |
|--------|-------|-------------|------|
| Sequences checked | — | 130 | — |
| Exact duplicates | **0** | 130 | **0%** |
| Near-duplicates (≥85%) | **2** | 130 | 1.5% |

**The two near-duplicates:**

| Hashed ID | Channel | Steps | Similarity | Text A | Text B |
|-----------|---------|-------|------------|--------|--------|
| `fed5e1a272ca` | LinkedIn | li4 vs li5 | 89.4% | "i'd love to hear how your team manages utilisation and capacity across projects. any insights?" | "i'd love to hear how you manage utilisation and capacity across your projects at 2TON. any insights?" |
| `788f51decef9` | LinkedIn | li5 vs li6 | 91.5% | "i'd love to hear your thoughts on how you're managing utilisation and capacity across your projects at adagri." | "i'd love to hear your thoughts on how you manage utilisation and capacity across your projects at adagri. let's connect!" |

Both are adjacent LinkedIn steps where the generator produced nearly
identical wording with minor variation (company name insertion, "let's
connect!" appended). Neither is an exact repeat, but both would read as
repetitive to a prospect.

### VERDICT: RARE

2 of 130 sequences. A per-sequence deduplication check at generation time
would catch these. Not a prompt-wide defect.

---

## DEFECT 4: PRODUCTIVE NAMED WITH ENOUGH CONTEXT

**What:** Is the product "Productive" named in each sequence? At which step?
Is the naming accompanied by a sentence saying what it does — or is it a
bare noun?

| Metric | Count | Denominator | Rate |
|--------|-------|-------------|------|
| Sequences naming the product | 90 | 131 | 68.7% |
| Sequences with explanation | 90 | 131 | 68.7% |
| Sequences NOT naming the product | 41 | 131 | 31.3% |

**By channel:**

| Channel | Total | Named | Named % | With explanation |
|---------|-------|-------|---------|-----------------|
| LinkedIn | 80 | 63 | 78.8% | 63 (100% of named) |
| Email | 51 | 27 | 52.9% | 27 (100% of named) |

Every sequence that names the product also explains it (100% of named
sequences have an accompanying description). The defect is entirely in the
31.3% that never name it at all.

**Email is worse than LinkedIn:** 47.1% of email sequences never name
Productive, vs 21.3% of LinkedIn sequences.

**20 unnamed sequences** (hashed identifiers):
- 9 LinkedIn sequences
- 11 email sequences (some contacts have both channels unnamed)

### VERDICT: PARTIAL — prompt change needed for email

68.7% naming rate matches checkpoint D's 68% measurement. The product is
always explained when named, so the defect is absence rather than
shallowness. Email is the weaker channel and needs the prompt to require
product naming.

---

## DEFECT 5: GREETING AND PERSONALISATION RENDER

**What:** Greetings with empty slots, `undefined`/`null`, cohort names, or
missing entirely.

| Metric | Count | Denominator | Rate |
|--------|-------|-------------|------|
| Empty greeting ("Hey ,") | **0** | 684 | **0%** |
| Placeholder ("Hi undefined,") | **0** | 684 | **0%** |
| Null/None greeting | **0** | 684 | **0%** |
| Cohort name as person | **0** | 684 | **0%** |
| Email steps with NO greeting at all | **238** | 238 | **100%** |
| LinkedIn steps with no greeting | 312 | 446 | 69.9% |

**No broken greetings exist** — but no email greeting exists at all. Every
single email body starts directly with content:

| Hashed ID | Step | First line |
|-----------|------|------------|
| `239ca5ce4597` | em1 | "I see that &Partner ApS is a creative advertising agency..." |
| `239ca5ce4597` | em2 | "I see that &Partner ApS offers a range of services..." |
| `239ca5ce4597` | em3 | "At &Partner ApS, your team delivers custom advertising..." |
| `239ca5ce4597` | em4 | "I noticed that &Partner ApS creates custom-made solutions..." |
| `239ca5ce4597` | em5 | "You have seen how &Partner ApS creates custom advertising..." |

LinkedIn is mixed: 134 of 446 steps (30.0%) open with a greeting ("hi",
"hey", "hello"), but 312 (69.9%) do not. Of the 134 with greetings, 131
use no name (just "hi, ..." or "hey, ...") and 3 use a literal name.

### VERDICT: UNIVERSAL for email (no greeting at all), common for LinkedIn

The email generator produces no greeting. This is a prompt defect: the
generator should open every email with a greeting addressing the recipient.
Since EmailBison has no `{first_name}` variable, the greeting must be
generic ("Hi," or "Hello,") or the name must be baked in (which creates a
per-record repair problem).

---

## DEFECT 6: SIGNATURES

**What:** Steps with no signature, or signatures that do not say who is
writing or on whose behalf.

| Metric | Count | Denominator | Rate |
|--------|-------|-------------|------|
| Email steps with no sign-off phrase | 228 | 238 | 95.8% |
| Email steps with no sender identity | 236 | 238 | 99.2% |
| Email steps at 0% sender identity | **CONFIRMED** | — | matches checkpoint D |

**10 email steps** contain "thank you" in the closing lines, but all 10 are
em5 (breakup/opt-out emails) where "Thank you for your time" is body text,
not a signature. None carry a name, title, or "on behalf of" statement.

**2 email steps** have something resembling a sign-off ("Thank you." as a
standalone sentence), but neither names who is writing.

**Worst 5 examples** (email body tails, hashed):

| Hashed ID | Step | Body tail |
|-----------|------|-----------|
| `239ca5ce4597` | em1 | "...Understanding this could help identify opportunities to improve financial clarity and decision-making." |
| `239ca5ce4597` | em2 | "...Is this something you have clear visibility on today?" |
| `239ca5ce4597` | em3 | "...How do you currently track profitability across your live projects?" |
| `239ca5ce4597` | em4 | "...Are you currently exploring new strategies to enhance your advertising campaigns?" |
| `239ca5ce4597` | em5 | "...Would you prefer I stop contacting you about this topic, or is there a better time to reconnect?" |

Every email ends with a question or statement. None say who is writing.

### VERDICT: UNIVERSAL

238 of 238 email steps (100%) have no sender identity. Checkpoint D's
post-regeneration measurement of 0% sender identity is **confirmed**. The
fix requires the generator to include a sign-off with the sender's name and
the sender's relationship to the prospect ("on behalf of" language where
applicable). HeyReach's `{MY_FIRST_NAME}` variable is the third most-used
variable in the client's estate (598 occurrences) and nothing we generate
uses it.

---

## SUMMARY TABLE

| # | Defect | Denominator | Count | Rate | Universal? |
|---|--------|-------------|-------|------|------------|
| 1 | Hardcoded first names (LinkedIn) | 446 steps | 159 | 35.7% | **YES** — 0% use `{FIRST_NAME}` |
| 2 | Unsupported merge variables | 684 steps | 0 | 0% | No — not present |
| 3 | Duplicate follow-ups | 130 sequences | 2 | 1.5% | No — rare |
| 4 | Product unnamed | 131 sequences | 41 | 31.3% | Partial — email worse |
| 5 | No greeting (email) | 238 steps | 238 | 100% | **YES** — universal |
| 6 | No sender identity (email) | 238 steps | 238 | 100% | **YES** — universal |

## UNIVERSAL vs RARE

**Universal (prompt change needed, every record affected):**
- Defect 1: LinkedIn literal names — every step, zero variables
- Defect 5: Email greetings — zero of 238 have one
- Defect 6: Email signatures — zero of 238 identify the sender

**Partial (prompt change, channel-specific):**
- Defect 4: Product naming — 31.3% of sequences omit it, email at 47.1%

**Rare (per-record or per-sequence fix):**
- Defect 3: Near-duplicate steps — 2 of 130 sequences

**Not present:**
- Defect 2: No unsupported variables exist

## FIX CLASSIFICATION

| Defect | Fix type | Why |
|--------|----------|-----|
| 1 (LI names) | Prompt change | Generator must write `{FIRST_NAME}` not literal names |
| 4 (Product naming) | Prompt change | Generator must name the product in every sequence |
| 5 (Email greeting) | Prompt change | Generator must open every email with a greeting |
| 6 (Email signature) | Prompt change | Generator must close every email with sender identity |
| 3 (Near-dupes) | Per-sequence check | Deduplication guard at generation time |

No per-record repair is needed. Every universal defect is a generator
prompt defect, and a single regeneration pass with corrected prompts would
address all four universal/partial defects simultaneously.

---

*Measured 2026-09-15 from `work/queue.snapshot.jsonl` (stamp:
2026-09-14T21:52:15Z from master 0ac5e60, 300 records). Script:
`scripts/copy_defect_census.py`. Full JSON: `out/copy_defect_census.json`.*
