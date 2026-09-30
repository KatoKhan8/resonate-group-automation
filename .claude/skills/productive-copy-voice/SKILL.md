---
name: productive-copy-voice
description: Voice and shape rules for prospect-facing Productive copy — cold email steps em1-em5, LinkedIn li1-li5, subjects and P.S. lines. Use when writing, reviewing, regenerating or debugging refused outreach copy, or changing a writer prompt. Covers founder/operator tone, banned phrases, the question-not-assertion rule, P.S. policy, opt-out and signature shape, and the single CTA. It POINTS at the canonical files for offers, capabilities and facts and never restates them.
---

# Productive copy voice

**This file carries VOICE AND SHAPE ONLY.** It deliberately contains no offer, no
capability, no case study, no benchmark, no URL and no fact about Productive or
about any prospect. Those have one source each, and a second copy is a second
thing to go stale:

| What you need | The one place it lives |
|---|---|
| Offers, spines, `step_objectives` 1-5, messaging rules, evidence, mechanisms | `config/clients/productive-offers.yaml` |
| Client identity, sender, personas, angle labels, tone, cadence, booking link, verification policy | `config/clients/productive.yaml` |
| The capability keys that may be named at all | `copystages.CAPABILITY_KEYS`, filled from the client config at call time |
| The writer prompts themselves | `src/copystages.py` (+ `src/copyprompts.py` for stages A and B) |
| Every refusal rule and its exact pattern | `src/copylint.py` (`RULES`, `BUZZWORDS`, `DASH_RE`, `FINALITY_RE`), `src/lint.py` (`BANNED_PHRASES`, `MIN_WORDS`) |
| Second-person operational assertions | `src/claims.py` |
| Step ordering across the sequence | `src/sequencegate.py` |
| The opt-out wording | `src/optout.py` (`OPT_OUT_LINE`) |
| Sequence contract: one conversation, threading, greetings | `EMAILBISON-COPY-REQUIREMENTS.md` |
| Standing copy decisions in force | `docs/OPERATING-MODE.md` — decisions 1-4 (copy path), 5-6 (scope and offers), 7 (`CLIENT_SUPPLIED`), 17 (old copy) |

If a rule here and one of those files disagree, **the file wins and this file is
wrong**. Read the offers file for what to say; read this one for how to say it.

## The voice

Operator direction, Zvonimir, 2026-09-29. **A founder/operator writing to one
person.** Human, casual, short, specific, plain English, confident without hype.
Not a marketing department. Contractions are right. Short paragraphs. Vary the
syntax between steps — do not stamp every message out of one template.

**Who that person is comes from the sender identity, never from this file**:
the `sender:` block in `config/clients/productive.yaml`, resolved by
`clients.sender_identity` and rendered by `sendersignature.compose`. Read the
name from there; never type one into the copy and never invent one.

The register to aim at: *"That's basically why we built Productive."* ·
*"Random one, but..."* · *"Can show you what that looks like."* ·
*"Worth a yes or no on this one?"*

The register that is refused as machine-written: *"Productive delivers a clear
view..."* · *"This insight can guide timely adjustments"* · *"One reason I
reached out is..."*. `src/copystages.py` carries the full paired lists; read them
before writing.

## Banned outright

`lint.BANNED_PHRASES` and `copylint.BUZZWORDS` are the canonical lists and they
refuse the whole step, not just the sentence. Do not maintain a copy — read them.
The classes they cover:

- **Filler openers and follow-up clichés** — "i hope this email finds you well",
  "i wanted to reach out", "circling back", "just following up", "touching base".
- **Machine register the operator named** — "would you be interested".
- **Our own routing taxonomy.** `economic_buyer` is internal metadata that picks
  the offer. A prospect never reads "economic buyer", "financial leaders" or
  "decision maker persona". This is a correctness defect, not a style preference:
  it leaks our taxonomy into somebody else's inbox. It is **gated** rather than
  asked for, because the prompt was told twice and produced it anyway — guidance
  alone drifts back on the next generation.
- **Consultant buzzwords** — synergy, leverage, seamless, robust, innovative,
  streamline, unlock, empower, and the rest of `BUZZWORDS`.
- **Fake personalisation at every level** — "love what you're doing at X",
  "looks like exciting growth", "saw you're doing great work".
- **Dashes and curly punctuation.** No em dash, no en dash, no `" - "` between
  clauses, anywhere: subjects, bodies, P.S. lines, LinkedIn. Plain ASCII
  apostrophes and quotes only. A hyphen inside a hyphenated word is fine.
- **Finality before the last step.** "this is the last email", "I'll leave it
  here", "closing the loop" are false at any step but the final one, and the
  arithmetic is the lint's job, not a reviewer's.

## The question-not-assertion rule

**The refusal that costs the most drafts.** Never write a flat second-person
sentence that says what THEY do and carries an operational word (margin,
profitability, utilisation, capacity, resourcing, budget, forecast, delivery,
billing, scope). `claims.check` refuses it unless a stored fact about that
company contains the word, and no company publishes its margin or its resourcing.

Three forms are always safe, and every sentence about their operations takes one
of them:

    1. a QUESTION          "How do you decide who is booked next week when
                            margin is tight?"
    2. hedged with if/whether
    3. a sentence about what Productive does, with no "you" in front of the verb

This collides with the approved ladder on purpose, and there is exactly one way
they fit: **put the rung's own words in a sentence that is not a claim about
them.** Measured 2026-09-30: em3 was refused on ten of ten attempts, on every
account tried, until it was written as a question. It is completely acceptable to
open with a question — good relevance beats fake personalisation.

The rung topics, their vocabulary, and which rung may name an AI capability come
from `productive-offers.yaml` `step_objectives`. **Never invent a rung, reorder
them, or move a rung's vocabulary to a different step** — `sequencegate` checks
that each step carries at least one word of its own objective literally, and that
a rung's words do not appear at another step and nowhere in its own.

## P.S. policy

On `em1` and `em3`, **when there is a fact worth it**. Operator direction,
2026-09-29:

- A P.S. carries a **genuinely interesting verified fact about them**, drawn from
  a DIFFERENT fact than em1's opening line used. One sentence, human.
- **It does not repeat the Productive pitch.** If no worthwhile verified fact is
  left, write an **empty** P.S. An empty P.S. ships; a recycled pitch does not.
- **Never list their services.** Restating what a prospect already knows they
  sell is not personalisation; `copylint.service_list_ps` refuses it and it costs
  the whole contact. Measured five attempts running.
- Most packs carry one or two facts and em1 has already spent one, so
  `"ps": {"em1": "..."}` with em3 absent is **the normal case, not a failure**.
- Do not type the `P.S.` label — the renderer applies it. Write the sentence.

Whether a step's P.S. is required is decided on the approved step itself
(`_ps_is_intact`), so "deliberately none" and "written and then lost" stay
different things. Do not invent a filler P.S. to clear a gate.

## Opt-out and signature

- **The writer never types a signature.** The **renderer composes it**, from the
  mailbox owner, **exactly once**: `sendersignature.compose`, applied through
  `trailingcontent.compose`, which both the rendered email and the EmailBison
  projection call with the same inputs. Read those two files for the block's
  shape and its source — do not restate it here.
- **An empty signature BLOCKS, and so does a duplicate.** Empty is a data
  problem at the mailbox owner, never something to paper over by typing a name
  into the body; the duplicate check is `sendersignature.refuse_if_duplicate`
  and it refuses rather than double-signing. Operator decision A, TASK-906,
  taken because the provider does **not** append one: measured 2026-09-28,
  **0 of 99** provider messages carried the mailbox signature. Any guidance
  saying the sending inbox adds its own is false and superseded.
- **The opt-out is appended by the renderer**, exactly once, from
  `optout.OPT_OUT_LINE`. It is a reply-based instruction, not a hyperlink.
  Do not write one yourself: `missing_opt_out` and `duplicate_opt_out` both
  refuse, and the duplicate is deliberately not de-duplicated silently.
- Changing the wording is one edit in `src/optout.py` and nowhere else.

## Single CTA

**One CTA per message, the one in the plan**, and exactly one prospect-facing URL
in the copy — the booking link in `config/clients/productive.yaml`. Any other URL
is refused by `cta_link_not_allowlisted`, and a link that does not resolve is
refused too. Never invent a URL, a client, a number, a tool they use or a case
study.

## Shape, briefly

Three subjects only — A for em1, B for em3, C for em5; em2 and em4 are
same-thread replies and carry none. All three must be different sentences. A
subject is a phrase with grammar in it, four to seven words, lowercase except
real proper nouns — never a keyword list. Bodies are 45 to 180 words, em2-em5
included. Name their company once, maybe twice. LinkedIn messages must not
restate an email: pick the vocabulary that is not in the emails, and a different
rung's question.

## When a draft is refused

**Regenerate. Never widen a rule** (OPERATING-MODE decisions 1-4). A draft that
failed a gate is never stored as a send candidate, a model error HOLDS the record
rather than passing silently, and approved or sent copy is never overwritten
because regeneration invalidates the approval hash.
