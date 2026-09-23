# Operator directives — 2026-09-23 evening

Two standing directives given this evening, recorded verbatim in substance so
they survive a context reset. **Neither is started.** Both are explicitly
additive and sequenced *after* the supply and stop-test work.

Nothing here changes existing campaigns or leads already in sequence. Both
directives say so in their own words, and §6 of the second says it outright.

---

## A. The research pack, between S5 and S7

### A1. The pack

Per account, **3 to 5 verified facts**, each carrying a **source URL, a date
and the exact snippet**:

| fact class | source | cost |
| --- | --- | --- |
| what the company does now | website crawl | zero credits |
| latest LinkedIn company posts | Apify | — |
| funding / news | web search, AI-ARK | — |
| open roles | Apify or the careers page | — |
| tech stack | AI-ARK | — |

**Cached 30 days**, refreshed by the signals layer once that exists.

### A2. S7 renders from the pack ONLY

- At most **one fact per step**.
- A **different fact class per step**: now / pain / signal / proof / breakup.
- **Never a name other than the recipient.** Never a verbatim review.
- A **confidence gate**: an empty pack falls back to persona-generic copy.
- The **never-invent rule**, with a **lint that flags any company claim not
  traceable to a pack fact**.

### A3. Learning tag

`research_depth` (0–3) on **every enrolled lead**. Reply rate by depth
reported in the learning doc **after two weeks**.

### A4. The pilot

Next batch: **200 leads with packs, 200 without**, same cohort and persona,
so the lift is measured. **Cost per pack reported in credits and tokens.**

### A5. Before

Post **five sample packs and their five rendered emails** in `#resonate-os`.

> **The instruction was truncated in transmission** — it ends "…in
> #resonate-os before". Before *what* is unknown: most likely before the
> pilot push. **Ask before acting on A5.**

---

## B. Copy quality is a first-class job, on both channels

> "COPY QUALITY is a first-class job of this system, on both channels, and it
> improves by measurement."

### B1. Packs everywhere

Every enrolled lead **from the next batch onward** gets a pack. Empty packs
fall back to persona-generic copy **and are counted as such**.

### B2. The copy standard, enforced by lint BEFORE any push

- Opens with something **specific to this person or company from the pack** —
  never with our product, never "I hope you are well".
- **One idea per message.** Under **60 words** for email step 1, under **280
  characters** for a LinkedIn connection note, under **400** for a LinkedIn
  message.
- The persona's **pain in their words**, the **angle from the playbook**, one
  **soft question** at the end. **No hard CTA before step 3.**
- Each step uses a **different fact class** (now / pain / signal / proof /
  breakup). **No hook repeated across steps.** No dashes, no buzzwords, first
  names capitalised.
- **LinkedIn register casual and short; email register polished.**
- **Never invent.** Every company claim traceable to a pack fact. No
  third-party names, no verbatim reviews.
- **The lint refuses a push on any violation and reports counts.**

### B3. Signals drive hook and timing

Job change, hiring, posts, funding and tech-stack facts select the angle. The
signals layer, once built, **re-opens copy for an account whose signal
changed**. Until then the pack refreshes every 30 days.

### B4. The weekly copy learning loop — Fridays

- Every enrolled lead carries: **persona, angle, fact class per step,
  research_depth, subject variant, sender, channel, cohort**.
- Every Friday: **reply rate, human-reply rate, positive rate, meeting rate**
  by each tag, **with sample sizes**, in `docs/COPY-LEARNING-<date>.md`.
- The system **proposes B-rules** with the evidence ("drop angle X for finance
  personas", "step-3 hiring hook outperforms"). **The operator promotes to C.
  Only C changes the cadence library. Nothing changes copy on its own.**
- Variants: **at most two per persona in flight**, allocated evenly, settled
  at a **stated sample size**; a winner enters the cadence library as a
  C-rule.

### B5. The quality bar before scale

For the **next two batches**, post **10 rendered emails and 10 LinkedIn
messages per batch** in `#resonate-os` for the operator's read **before the
push**. A rejected batch is **re-rendered, not sent**. After **two clean
batches** the sample drops to **5 per batch, standing**.

### B6. Scope

**Existing campaigns and leads in sequence are untouched.** This applies to
every new campaign and every new lead.

---

## Why B5 is not optional, measured the same evening

The blank-email incident (see the night handoff) is the argument for B2 and
B5 in one event: **76 blank emails reached real prospects today** — subject
`''`, body `'<p></p>'` — and one prospect replied to one. No lint stood
between the render and the provider, and nobody read a sample before the
push. B5 is the human half of that gate and B2 is the machine half.
