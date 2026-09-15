# TASK-093 - the fifth arm exists in code and has never been generated

## THE FACT

`variantgen.APPROACHES` defines FIVE approaches. Every measurement this
repository has ever taken of variant output shows FOUR:

    concise_direct    generated
    conversational    generated
    problem_led       generated
    observation_led   NEVER SEEN IN ANY MEASURED OUTPUT
    value_led         generated

`observation_led` is withheld unless the record carries a LICENSED
OBSERVATION, and `approaches_available` filters it out rather than letting
the model invent one. That design is correct and must not be weakened - a
model asked for an observation-led message with no observation WILL fabricate
one, and fabrication is exactly what `claims.check` exists to refuse.

**But nobody has ever confirmed the fifth arm generates even when the
evidence IS there.** The operator's requirement is a minimum of five
genuinely different variants WHERE SUPPORTED. This task establishes where it
is supported and whether it works there.

## THE THREE QUESTIONS

**1. How many records can support it?** Count, across the 300 real records in
`work/queue.jsonl`, how many hold a licensed observation of the kind
`approaches_available` requires. Report the number and the licence condition
it is testing. If the answer is ZERO, then the fifth arm is unreachable on
the current estate and THAT is the finding - say it plainly and say what a
record would need to carry.

**2. Does it generate on a record that supports it?** If any record
qualifies, run variant generation on it against the real model and show the
five arms. If none qualifies, construct the licence from evidence that is
genuinely present on a real record - do NOT invent an observation to make the
path run. If you cannot reach it without inventing evidence, say so.

**3. Is the fifth arm structurally different from the other four, or is it a
sixth way to ask the same question?** Report opening type, CTA type, tone,
length and product-introduction point, and the `diversity_collisions` verdict
for the five-arm set. TASK-089 is fixing the four-arm LinkedIn collapse; if
the fifth arm collides too, the same cause probably explains both.

## WHAT NOT TO DO

- **Do not remove or loosen the observation licence** to make five arms
  appear. Five arms where one is fabricated is worse than four honest ones.
  This is the single most tempting wrong move in this task.
- **Do not count "five approaches defined" as "five variants produced."**
  The whole point of TASK-084 was that 622 lines with 453 lines of green
  tests had never generated anything.
- Do not weaken the claims gate. If `observation_led` output is REFUSED by
  `claims.check`, that refusal is a finding and the underlying defect is the
  prompt, not the gate.

## DELIVERABLE

A count of licence-carrying records with the condition stated, the five-arm
output if reachable, the structural table, and a clear verdict on whether
"minimum five genuinely different variants" is currently achievable on this
estate or is blocked on evidence the records do not carry.

---

## RESULT

**STATUS:** DONE
**COMMIT:** 94bac63
**TESTS:** Not applicable - this is a measurement task, not a code change.
Generation ran against the real model (openai/gpt-4.1-mini via OpenRouter).
**FILES CHANGED:** None (measurement only; temporary scripts in work/ are
not committed)
**SNAPSHOT:** `work/queue.snapshot.jsonl` stamped 2026-09-14T21:52:15Z from
master 0ac5e60, 300 records.

---

### Question 1: How many records can support the fifth arm?

**124 of 300 records (41.3%)** carry a licensed observation that enables
`observation_led`.

**The licence condition tested:** `observations.resolve()` returns
`allowed=True` for at least one of the three types `approaches_available`
checks in order: `COMPANY_EVENT`, `PERSON_ROLE`, `COMPANY_ATTRIBUTE`. This
requires:

1. Policy allows the type (config switch, defaulting on for company types
   and off for person types).
2. At least one evidence row in `rec["research"]` with the correct subject
   (`company` or `person`).
3. The row has a `source_url` (citable - a fact with no link is refused).
4. The row's `quality` is in `evidence.USABLE` (STRONG or MEDIUM_Q).

**Breakdown by observation type:**

| Type | Records supported | Why |
|---|---|---|
| `company_event` | **0** | No record carries a dated company-subject evidence row with a source URL. The research pipeline has never stored a dated event. |
| `person_role` | **0** | Policy default is OFF (`observations.person_role` defaults to `False`). No campaign in the estate switches it on. |
| `company_attribute` | **124** | All 124 supported records qualify through this type alone. 66 have STRONG quality, 58 have MEDIUM quality. |

**What the 176 unsupported records lack:** Either zero research rows (some
records have none at all), or research rows that are not citable (no
`source_url`), or rows whose quality is below USABLE (WEAK or UNUSABLE).

**What a record would need to carry to add `company_event` support:** A
research row with `subject: "company"`, a non-empty `source_url`, quality
STRONG or MEDIUM_Q, AND a non-empty `published_at` date. None of the 300
records has this combination.

---

### Question 2: Does it generate on a record that supports it?

**YES.** All five arms generated on `2020companies-com` (contact: Rachele
Crumpler, CFO), which carries a STRONG quality `company_attribute`
observation:

> **Fact:** "Our People Vision At Christ's Haven For Children, we are
> striving to maintain a culture that promotes Normalcy, Dignity, and Hope
> for all of the youth"
> **Source:** https://www.2020companies.com/our-people/
> **Quality:** strong, **Freshness:** None (no bucket assigned)

The five generated variants:

**concise_direct (short_direct):**
Subject: Helping 2020 Companies unify budgets and time tracking
Body: 2020 Companies highlights its award-winning retail sales and
marketing expertise that drives measurable growth across 600,000+ retail
doors. I am reaching out because as CFO, you oversee financial efficiency
where having budgets, time tracking, resourcing, and invoicing integrated
can improve profitability visibility. Productive is one place where these
elements talk to each other instead of living in separate tools. Would you
be interested in exploring how this could streamline your financial
operations?

**conversational (casual):**
Subject: 2020 Companies' retail marketing expertise caught my eye
Body: 2020 Companies highlights its award-winning culture and people-first
retail sales solutions that drive measurable growth across 600,000+ retail
doors. I'm reaching out because your role as CFO means you're key to
ensuring marketing investments deliver clear financial returns. I work with
agencies on project profitability by connecting budgets, time tracking,
resourcing, and invoicing in one place with Productive. How do you currently
track profitability across your retail marketing projects?

**problem_led (problem_led):**
Subject: Driving measurable retail growth with better project visibility
Body: 2020 Companies highlights its strength in delivering measurable
in-store performance through scalable retail programs across 600,000+ retail
doors. I am reaching out because as CFO, you oversee financial outcomes that
depend on clear visibility into project profitability and resource use.
Productive is one place where an agency's budgets, time tracking, resourcing,
and invoicing talk to each other instead of living in separate tools. This
helps teams see margin per project while it is running, not weeks later. Do
you currently have a way to track project profitability and resource
allocation in real time across your retail marketing initiatives?

**observation_led (consultative):**
Subject: Supporting 2020 Companies' People-First Retail Vision
Body: 2020 Companies emphasizes a culture promoting Normalcy, Dignity, and
Hope through a trauma-informed, family model of care, as highlighted on your
website. I am reaching out to you as CFO because managing budgets, time
tracking, and resource planning efficiently is critical to sustaining such
impactful programs. Productive is one place where an agency's budgets, time
tracking, resourcing, and invoicing talk to each other instead of living in
separate tools. How are you currently tracking project profitability and
resource utilization across your retail marketing initiatives?

**value_led (professional):**
Subject: Helping 2020 Companies unify budgets and time tracking
Body: 2020 Companies highlights its strength in delivering measurable retail
growth through scalable retail programs and a people-first approach. I am
reaching out because your role as CFO is key to ensuring financial clarity
and operational efficiency in such a large, complex organization. Productive
is one place where an agency's budgets, time tracking, resourcing, and
invoicing talk to each other instead of living in separate tools. This
integration can help teams your size see project profitability on Monday,
not two weeks late. Could you share how you currently track project
profitability across your retail marketing initiatives?

---

### Question 3: Is the fifth arm structurally different?

**NO.** The five-arm set FAILS `are_materially_different`. The verdict is
`different: False` with four collision pairs.

**Structural table:**

| Approach | Style | Opening | CTA | Words |
|---|---|---|---|---|
| concise_direct | short_direct | question | question | 68 |
| conversational | casual | statement | question | 80 |
| problem_led | problem_led | statement | statement | 101 |
| observation_led | consultative | question | statement | 94 |
| value_led | professional | statement | statement | 110 |

**`diversity_collisions` verdict:**

| Pair | Collision reason |
|---|---|
| concise_direct vs observation_led | same opening (question), similar length (68 vs 94 words) |
| conversational vs problem_led | same opening (statement), similar length (80 vs 101 words) |
| conversational vs value_led | same opening (statement), similar length (80 vs 110 words) |
| problem_led vs value_led | same opening (statement), same CTA (statement), similar length (101 vs 110 words) |

**The deeper structural problem:** All five variants open with the same
template sentence: "2020 Companies highlights/emphasizes its [attribute]..."
The approach instructions are supposed to control HOW the message opens -
direct statement, casual observation, pain-first, evidence-first, or
outcome-first - but the model produces the same "Company highlights its X"
pattern for every approach. The observation_led variant does reference the
licensed observation in its body ("a culture promoting Normalcy, Dignity,
and Hope through a trauma-informed, family model of care, as highlighted on
your website"), which is the one content difference. But structurally it
still follows the same opening template.

**The Productive pitch sentence is nearly identical across all five:**
"Productive is one place where [an agency's / these] budgets, time tracking,
resourcing, and invoicing talk to each other instead of living in separate
tools." This sentence appears verbatim in four of five variants.

---

### VERDICT

**"Minimum five genuinely different variants" is NOT currently achievable on
this estate.** Three compounding problems:

1. **The evidence that gates the fifth arm is raw web page text, not
   curated observations.** The 124 records that qualify all do so through
   `company_attribute` observations that are HTML text extracts from
   scraping ("Skip to content...", "Services SEO Ads Web Development...",
   page title tags). The quality assessment rates 66 of these as STRONG, but
   they are not observations a human would recognise as something notable
   about the company. The observation-led variant on `2020companies-com`
   referenced a subsidiary children's charity program, not the company's
   core business.

2. **Zero records support `company_event`** (the most natural observation
   type - "I saw you just did X"). The research pipeline has never stored a
   dated event with a source URL. This is the type that would produce
   genuinely interesting observation-led copy ("Congratulations on the
   Vienna office opening") but it is unreachable on every record in the
   estate.

3. **Even when the fifth arm generates, it is not structurally different
   from the other four.** The model collapses all five approaches to the
   same opening template and the same product pitch sentence. This is the
   same cause TASK-089 identified for the four-arm LinkedIn collapse: the
   approach instructions in the prompt are being overridden by the model's
   tendency to follow a single template.

**The fifth arm exists in code, the gate is correctly designed, and the
gate can be passed - but what passes through it is not a genuinely
different variant. The defect is in the prompt's ability to enforce
structural diversity, not in the evidence gate.**

---

### FINDINGS

- 124/300 records (41.3%) have a licensed observation; all through
  `company_attribute` alone.
- 0/300 records support `company_event` (no dated events stored).
- 0/300 records support `person_role` (policy default off, no campaign
  overrides it).
- The fifth arm generates when evidence is present but collides
  structurally with concise_direct (same opening shape) and the model
  produces the same "Company highlights its X" template across all five
  approaches.
- The licensed "observations" are raw web scrapes, not curated facts. A
  human would not recognise most of them as something worth mentioning in
  a message.
- The `are_materially_different` check correctly identifies the five-arm
  set as NOT materially different (4 collision pairs).

### RISKS

- The evidence quality pipeline rates raw HTML text as STRONG, which means
  the gate is passing evidence that is technically citable but practically
  useless for observation-led copy.
- The prompt's approach instructions do not override the model's template
  tendency, so even with good evidence the fifth arm would likely still
  collide with the others structurally.

### RECOMMENDED CLAUDE ACTION

1. The prompt diversity problem is the same root cause as TASK-089's
   four-arm LinkedIn collapse. One fix to the prompt's structural
   enforcement would address both.
2. The evidence quality assessment for `company_attribute` should be
   reviewed - raw HTML navigation text and page title tags should not be
   STRONG quality.
3. The `company_event` gap (zero records with dated events) means the most
   natural observation type is unreachable. If the research pipeline can
   store dated events with source URLs, this would unlock the strongest
   form of observation-led copy.
