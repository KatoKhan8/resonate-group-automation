# COPY-ENGINE-SPEC-v2 — the copy strategy from 2026-09-25

**This is the spec the copy engine is built to. Where an operator override
below differs from anything else in this repository, the override wins.**

Claude owns the stage prompts (`src/copystages.py`) and the sequence-level
quality gate (`src/sequencegate.py`). Qwen implements stages A to H, the
preview and the tests.

---

## 0. THE OPERATOR OVERRIDES, WHICH WIN OVER EVERYTHING

1. **No dashes of any kind, ever.** Em, en, or " - " as a separator. In email
   bodies, subjects, P.S. lines and every LinkedIn message. `copylint` refuses,
   it does not warn, and it reads all of them.
2. **Threading is three threads, not one.**

        em1  day 1   NEW THREAD, subject A
        em2  day 4   reply in A            (provider prepends Re:)
        em3  day 8   NEW THREAD, subject B (subject_alt)
        em4  day 12  reply in B
        em5  day 21  NEW THREAD, breakup, subject C, short

   Both generated subjects are sent. Neither is a spare.
3. **P.S. on em1 and em3, always.** The arms are `ps_fact` and
   `ps_capability`. `ps_none` is retired.
4. **The sender's signature is rendered in the preview**, from the mailbox's
   own stored block, because `sender.mode: client_rep` means the inbox appends
   it. UNVERIFIED until a test send proves exactly one signature arrives.
5. **LinkedIn messages carry `{firstName}`, say who is writing, give one line
   on Productive, and correlate to the email.** Not a lowercase note, not the
   email in shorter form.
6. **The standing paragraphs in `productive.yaml` are no longer sent.** em1 is
   written whole by Sonnet at 60 to 90 words from a per-lead problem
   hypothesis and a role-based value proposition. Follow-ups come from an
   approved angle library with per-lead bridges.
7. **Assets for days 8 and 12 use only what exists in `productive.yaml`.**
   What is missing is listed in §7 for the client to supply. Nothing is
   invented.

---

## 1. THE CORE CHANGE

    FROM  research -> personalised opening -> generic pitch -> repetitive follow-ups
    TO    research -> ICP qualification -> business signal -> problem HYPOTHESIS
          -> matched capability -> personalised message -> value-driven follow-ups

The failure this replaces is measurable and was measured on 2026-09-25: a
personalised first sentence followed by an identical paragraph about project
margin, sent to every lead. **The opener changed per lead and nothing after it
did.**

---

## 2. THE EIGHT STAGES

| | stage | owner | output |
|---|---|---|---|
| A | Lead qualification | Groq | `is_agency`, confidence, evidence |
| B | Research extraction | Groq | facts with `source_index`, signal strength |
| C | Problem hypothesis | Groq | a hypothesis, explicitly flagged as one |
| D | Value proposition matching | Groq | one capability, per role |
| E | Sequence strategy | Groq | objective, angle, CTA per step, before any copy |
| F | Copy generation | **Sonnet** | em1 whole, bridges, P.S., LinkedIn |
| G | Quality validation | code + Groq | the sequence-level gate, §5 |
| H | Output | code | EmailBison variables, HeyReach steps, preview |

**Stages A to E run on the cheap model. Only F is Sonnet.** That is the cost
shape and it survives the override: the expensive model writes what a prospect
reads and nothing else.

**E BEFORE F IS THE POINT.** The strategy for all five emails and all four
LinkedIn messages is decided before a single sentence is written, so step 4 can
be required to differ from step 2 by construction rather than by inspection.

---

## 3. THE FOUR QUALIFICATION OUTCOMES

The existing HELD behaviour is preserved and SPLIT. Limited public research is
not proof that a company is unqualified.

    QUALIFIED_RICH     an agency, and a strong recent signal exists
    QUALIFIED_THIN     an agency, no strong signal, but a credible
                       business-model hypothesis can be made honestly
    INSUFFICIENT       an agency, and nothing supports a reason to write
    UNQUALIFIED        not an agency  (product company, network, university)

`QUALIFIED_THIN` is the one this spec adds. It sends, and it says less. It must
never pretend to have discovered an internal problem.

---

## 4. SIGNAL STRENGTH — WHAT COUNTS AS A REASON TO WRITE

**STRONG** (recent, operational, checkable): new clients or major projects;
hiring for operations, project management, delivery or finance; service
expansion; acquisitions or restructuring; delivery-team growth; pricing or
service-model change; publicly discussed operational challenges; relevant
technology adoption; leadership change.

**WEAK** (true, and not a reason to write): founding date, company history,
mission statements, marketing slogans, service lists, awards.

Per fact, five questions: verified? relevant to THIS role? supports a plausible
problem? connects naturally to a capability? establishes a credible reason for
outreach?

**A pack of five weak facts is `QUALIFIED_THIN`, not `QUALIFIED_RICH`.** The
2026-09-25 run held 8 of 10 on exactly this, and holding a real agency because
its homepage is boilerplate is the wrong answer.

---

## 5. THE SEQUENCE-LEVEL QUALITY GATE

A sequence is not approved because each message is grammatical. Ten checks over
the whole campaign, in `src/sequencegate.py`:

1. lead qualified
2. research credible, every claim traceable to a fact
3. problem relevant to the role
4. capability matches the problem
5. em1 states the reason for writing
6. **each follow-up introduces something the earlier ones did not**
7. email and LinkedIn complement rather than duplicate
8. copy reads naturally
9. every claim supported
10. no unnecessary repetition

**A failure names the step that caused it.** The gate does not say "regenerate
the sequence"; it says "em4 repeats em2's argument", and only em4 is rewritten.
Regenerating everything hides which message was wrong.

---

## 6. ROLE-BASED VALUE PROPOSITION

Never the same capability for everyone. `profitability` is not the default.

    CEO / Founder          profitability, visibility, growth, decisions
    COO / Operations       resourcing, delivery efficiency, utilisation
    Project / Delivery     budgets, scope creep, workload, planning
    Finance                financial visibility, budgeting, forecasting, invoicing

Mapped to the six real capabilities in `product.capabilities`. No other
capability may be named.

---

## 7. ASSETS — WHAT EXISTS, AND WHAT THE CLIENT MUST SUPPLY

**Audited in `config/clients/productive.yaml`, 2026-09-25.**

PRESENT: six capabilities (`project_management`, `time_tracking`, `budgeting`,
`resource_planning`, `billing`, `profitability`) and `product.what_it_is`.

**MISSING, and needed for improvements 4 and 10:**

- customer case studies: a named agency, what changed, permission to name it
- verified benchmarks on agency utilisation or margin
- a dashboard or workflow example that can be described or linked
- a profitability calculator, if one exists
- a short demo link

**BROKEN: `booking_link: https://productive.test/get-started/`.** `.test` is a
reserved TLD that resolves nowhere. Any CTA offering a link currently offers a
dead one. Left as found rather than guessed.

**Until those arrive, days 8 and 12 use a concrete product workflow described
in plain words.** No invented case study, statistic, customer name or URL. Ever.

---

## 8. WHAT THE PREVIEW MUST SHOW

Per lead: qualification status (one of the four), verified facts with sources,
**the problem hypothesis marked visibly as a hypothesis**, the selected
capability and why, all five emails with thread and subject, all four LinkedIn
messages, each message's objective, the gate's results, and any warning.

**A hypothesis is never displayed as a company fact.** Different styling,
labelled in words.

---

## 9. WHAT WOULD MAKE THIS A FALSE PASS

- A hypothesis rendered as a statement of fact about the company.
- The same capability selected for every lead.
- Follow-ups that differ in wording and repeat the argument.
- LinkedIn asking a question already asked by email.
- Any invented case study, statistic, customer or URL.
- A sequence gate that passes because it only checked individual messages.
- Reporting cross-channel synchronisation as working without measuring it.
  **The email to LinkedIn stop is NOT verified** and HeyReach's
  `StopLeadInCampaign` 404s on a lead its own read endpoints report present.
- Treating a thin pack as UNQUALIFIED.
