# Sequence QA — 2026-09-15

**Snapshot:** `work/queue.snapshot.jsonl`, stamped 2026-09-14T21:52:15Z from
master `0ac5e60`, 300 records.

**Denominator:** 81 sequences (one per contact across 68 records with a
cadence). 80 carry generated steps. 51 are email+LinkedIn, 30 are
LinkedIn-only.

**Entry point:** every cadence was read from `record.cadence[contact_name]`
in the snapshot. Step text was read from `step.body` (email) and
`step.note` (LinkedIn). No provider calls. No regeneration.

**Script:** `scripts/task110_sequence_qa.py`.

---

## 1. The five defects, with rates

### Defect 1 — Progression collapse (same ask in different words)

**Rate:** 39/81 sequences (48.1%)

The single most common defect. Multiple rungs ask the same discovery
question in slightly different wording. The LinkedIn ladder specifies six
different jobs (connect → question → consequence → product → new angle →
close); when progression collapses, the recipient reads the same message
six times.

Worst case: `seq-14204392c2` (record `seq-b53311c6e4`, state=approved) —
the LinkedIn sequence asks "how are you currently managing utilisation and
capacity" at steps li2, li3, li4, li5 AND li6. Five messages, one question.
The email sequence repeats "I noticed that [Company] focuses on..." across
all five emails with the same company description. 18 question-collapse
pairs detected.

The pattern is **universal** (a prompt problem), not per-record. The model
receives the ladder briefs but collapses them because the company
description and the discovery question dominate the prompt's context
window.

### Defect 2 — Tone drift / re-introduction

**Rate:** 38/81 sequences (46.9%)

A later step re-introduces the sender as if for the first contact: "I am
reaching out to you as [role]" or "I'm reaching out because..." appearing
at step 3 or later. The recipient has already read the connection note or
first email; a step that re-opens with an introduction pretends the earlier
steps did not happen.

Most common form: email steps opening with "I noticed that [Company] is
a..." — which is the same opener the first email used, making the second
email read as a duplicate first contact.

This is **universal** (a prompt problem). The prompt passes the company
description to every email rung, and the model reaches for it as an opener
regardless of whether an earlier step already used it.

### Defect 3 — Missing easy out

**Rate:** 23/81 sequences (28.4%)

The final step makes no provision for the recipient to decline without
awkwardness. The LinkedIn ladder's rung 6 specifies "Close the loop. No new
pitch, no summary." — but 23 sequences end on a question, a pitch, or a
generic pleasantry instead.

**All 6 approved sequences lack an easy out.** This is the most
operationally significant finding: the sequences closest to being sent are
the ones most likely to leave the recipient without a graceful exit.

This is a **per-record** defect — the ladder specifies the easy-out, and
18.3% of 6-step LinkedIn sequences comply. The prompt is not preventing
it; the model is not receiving or following the instruction for these
records.

### Defect 4 — Later steps pretending to be first contact

**Rate:** 25/81 sequences (30.9%) — silence never acknowledged

From step 3 onward, a follow-up should acknowledge that earlier steps went
unanswered ("just checking in", "following up", "circling back"). In 56/81
sequences (69.1%), no step from li3/em3 onward carries any acknowledgement
phrase. The sequence reads as a series of unrelated cold contacts rather
than one continuing conversation.

This is **universal** (a prompt problem). The ladder briefs for rungs 3-5
do not instruct the model to acknowledge the silence, so it does not.

### Defect 5 — Conceptual duplication

**Rate:** 21/81 sequences (25.9%) with at least one pair of steps above
0.5 text similarity

Two steps in the same sequence that say substantially the same thing in
substantially the same words. Distinct from Defect 1 (which counts
questions specifically): this measures the full body/note text.

The email channel is worse than LinkedIn here: 12/51 email sequences
(23.5%) have at least one pair of email bodies above 0.5 similarity, and
32/51 (62.7%) repeat the same company description in the opening sentence
across multiple emails.

This is **universal** (a prompt problem). The company description is passed
to every email rung and the model reproduces it.

---

## 2. Additional measurements

| Measurement | Value | Denominator |
|---|---|---|
| Product "Productive" named somewhere in LI sequence | 65/81 (80.2%) | 81 sequences |
| Product named specifically at li4 (the ladder's product rung) | 46/60 (76.7%) | 60 sequences with 6 LI steps |
| Full correct ladder shape (all 6 rungs doing their job) | 11/60 (18.3%) | 60 sequences with 6 LI steps |
| "I noticed that..." opener in email bodies | 49/238 email steps (20.6%) | 238 email steps |
| "I noticed" repeated in 2+ emails in same sequence | 13/51 (25.5%) | 51 sequences with 2+ emails |
| Company description repeated (first sentence sim > 0.7) | 32/51 (62.7%) | 51 sequences with 2+ emails |
| "I'd love to hear" in LinkedIn step 4+ | 14/79 (17.7%) | 79 sequences with 2+ LI steps |
| Cross-channel overlap (em1 vs li2 similarity > 0.4) | 0/48 (0.0%) | 48 sequences with both em1 and li2 |
| Sender identity present in at least one step | 72/81 (88.9%) | 81 sequences |

---

## 3. The three worst sequences

All identifiers hashed. Full text available in
`.qwen/tmp/task110_full_output.txt`.

### Worst: `seq-14204392c2` (state=approved, 11 steps)

Every LinkedIn step asks "how are you currently managing utilisation and
capacity across your live projects?" — five times, verbatim. Every email
opens with the same company description. No product name. No easy out.
18 question-collapse pairs. This sequence is approved for sending.

### Second: `seq-5a933ccca8` (state=approved, 11 steps)

LinkedIn steps collapse to "how do you currently track profitability" and
"i'd love to hear how your team approaches profitability." Emails repeat
"I noticed that [Company] is a national retail sales agency trusted by
leading brands" across all five bodies. No product name. No easy out.

### Third: `seq-788f51dece` (state=approved, 11 steps)

LinkedIn li4, li5, and li6 all open with "i'd love to hear how your
team is managing utilisation and capacity" — three steps, one sentence.
Emails repeat the "Top Agricultural Marketing Agency in Europe 2026"
description across all five bodies. No product name. No easy out.

---

## 4. The three best sequences

### Best: `seq-c243fc8904` (state=held, 6 LinkedIn steps)

Textbook ladder compliance. li1 connects with sender identity and product
teaser. li2 asks a discovery question. li3 names the consequence. li4
names Productive and says what it joins up. li5 checks in with a new
angle. li6 gives an easy out ("no worries if this isn't a fit"). Six
rungs, six jobs.

### Second: `seq-09a37139f3` (state=held, 6 LinkedIn steps)

Same correct shape. Product named at li1, li4, and li6. li5 offers value
("compare notes on simplifying capacity planning") rather than asking
another question. li6 closes with "close the loop" and "wishing you
continued success."

### Third: `seq-b580268f93` (state=drafted, 11 steps, the reference sequence)

The sequence the task description names as "the one that got it right."
LinkedIn: six rungs, six jobs, product named once at li4, easy out at
li6. Email: five distinct subjects, each email making a different
argument. The one defect: email steps do not acknowledge prior silence —
but the email content itself progresses correctly.

---

## 5. Universal vs per-record — what decides the fix

### Universal defects (a prompt problem — fix once, all 81 sequences benefit)

| Defect | Rate | Root cause |
|---|---|---|
| Company description repetition in emails | 62.7% | The company description is passed to every email rung's prompt and the model reproduces it as an opener |
| Question collapse (LinkedIn) | 48.1% | The ladder briefs name different jobs but the model reaches for the same discovery question because the company context dominates |
| Re-introduction in later steps | 46.9% | The prompt passes "reaching out" context to every step; the model does not know an earlier step already introduced |
| Silence never acknowledged | 69.1% | The ladder briefs for rungs 3-5 do not instruct the model to acknowledge prior silence |

These four defects are structural. A prompt change — passing prior-step
summaries, suppressing the company description after em1, adding
"acknowledge that earlier steps went unanswered" to rungs 3+ — would move
all four at once.

### Per-record defects (a per-generation problem — fix by regenerating the specific sequence)

| Defect | Rate | Root cause |
|---|---|---|
| Missing easy out | 28.4% | The ladder specifies it but the model does not always comply; 18.3% of sequences do comply, so the prompt is not preventing it |
| Missing product name | 19.8% | Same: the ladder's rung 4 names the product, and 76.7% of sequences comply |
| High text similarity between steps | 25.9% | Stochastic: some generations happen to produce similar text, others do not |

These are fixed by regeneration of the specific sequence, not by a prompt
change. The prompt already specifies the correct behaviour; the model
sometimes fails to follow it.

---

## 6. The approved sequences — an operational finding

All 6 approved sequences carry defects. Every one lacks an easy out and
every one omits the product name. Five of six have question collapse.

These are the sequences closest to being sent. The approval predates the
ladder fix of 2026-09-14 (TASK-075/TASK-087), and the stored copy was not
regenerated after the fix. The task file states: "Regeneration costs 560
steps and 83 human approvals and is the operator's call." This report
does not recommend regeneration — it reports the before-number.

**State vs defect density:**

| State | Sequences | Avg defects | Zero-defect |
|---|---|---|---|
| approved | 6 | 2.0 | 0 (0%) |
| drafted | 47 | 0.4 | 33 (70%) |
| held | 21 | 0.3 | 16 (76%) |
| verified | 7 | 0.1 | 6 (86%) |

The approved sequences are the worst in the estate. This is a cohort
effect: they were generated before the ladder fix and approved before the
QA this task performs.

---

## 7. What is proven, what is hypothesised

### OBSERVATIONS (with n)

1. 39/81 sequences (48.1%) have question collapse — multiple rungs asking
   the same discovery question (n=81, automated check at similarity > 0.55).
2. 32/51 email sequences (62.7%) repeat the company description in the
   opening sentence across multiple emails (n=51, first-sentence similarity
   > 0.7).
3. 38/81 sequences (46.9%) re-introduce the sender in step 2+ as if for
   the first time (n=81, phrase match for "reaching out" variants).
4. 23/81 sequences (28.4%) have no easy-out phrase in the final step
   (n=81, phrase match for decline-granting language).
5. 25/81 sequences (30.9%) carry no acknowledgement of prior silence from
   step 3 onward (n=81, phrase match for follow-up language).
6. All 6 approved sequences carry at least two of defects 1-5.
7. 11/60 sequences (18.3%) follow the full correct ladder shape across all
   six LinkedIn rungs (n=60, automated check of each rung's job).
8. Cross-channel overlap (em1 vs li2) is 0% — emails and LinkedIn messages
   are saying different things (n=48).

### HYPOTHESES

1. The company description in the prompt is the single largest contributor
   to repetition defects. It is passed to every email rung and the model
   reproduces it. Removing it from rungs 2+ should reduce defects 2 and 5
   simultaneously.
2. The approved sequences are defective because they were generated before
   the ladder fix (2026-09-14) and were not regenerated afterwards. The
   ladder briefs now specify the correct shape; the stored copy predates
   the briefs.
3. The 18.3% ladder compliance rate is a lower bound on what the prompt
   can produce — the reference sequence (`seq-b580268f93`) shows the model
   CAN follow the ladder, and the 81.7% that do not are failing to follow
   instructions they received, not missing instructions.

### PROVEN LEARNINGS

None survive a sample-size objection at the sequence level. The 11
compliant sequences prove the model can follow the ladder; the 49
non-compliant prove it sometimes does not. Whether a prompt change moves
the rate is untested.

---

## 8. Reproducing this measurement

```
py -3 scripts/task110_sequence_qa.py
```

Reads `work/queue.snapshot.jsonl` (300 records, 81 sequences). No provider
calls. All identifiers hashed. Full per-sequence text in
`.qwen/tmp/task110_full_output.txt`.
