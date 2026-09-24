# Step 4 and step 5 email copy - DRAFTS FOR OPERATOR APPROVAL

> **SUPERSEDED IN TWO PLACES, 2026-09-24 late. Read
> `docs/MERGE-REQUEST-2026-09-24-CADENCE-FOUR-STEPS.md` before acting on
> anything below.**
>
> 1. **"927 rendered rows" in the paragraph below is wrong.** 927 is the
>    journal's LINE count. 814 rendered and 113 were held - which the persona
>    counts four lines down already say, 621 + 193 = 814. The number that
>    survives lint and the company-name gate as well is 796.
> 2. **The `SUBJECT_2` / new-thread shape for em4 in section 2 cannot be
>    staged.** `bisonfactory._sequence_steps` refuses it: "step 3 is not a
>    thread reply but carries a distinct subject". That invariant is
>    operator-verified and was not weakened. The four steps shipped are
>    threaded on `{SUBJECT_1}` throughout and `thread_reply_pattern` is
>    `[false, true, true, true]`.
>
> The four bodies in sections 3 and 4 were approved and ARE wired in, in
> `src/cadence.TEMPLATES`. The ordering table in section 2 is not.

2026-09-24. Lane 1. **Nothing here is approved and nothing here is wired in.**
These are TEMPLATES in the register of `src/cadence.py`'s `TEMPLATES`, written
to be pasted there once approved. `src/cadence.py` was not edited.

Scope: one step-4 variant per persona (2), one step-5 variant per persona (2),
the 5-step ordering they belong to, and the problem that ordering had to solve.

Personas and angles are the live ones, measured from `work/stage/s7-copy.jsonl`
(927 rendered rows) and `config/clients/productive.yaml`:

    personas   economic_buyer  621 leads      champion  193 leads

    angles, by the {angle_phrase} the template actually receives
    (`cadence.angle_words` splits the configured angle on its first comma)

      economic_buyer  founder     profitability visible on Monday not two weeks late  479
                      operations  utilisation and capacity across live projects        79
                      finance     margin per project                                   63
      champion        delivery    live budget burn                                    159
                      operations  utilisation                                          34
                      resource_management  who is booked on what next week

    the {angle_word} a subject receives, from `angle_labels` (all <= 32 chars)

      founder  profitability on Monday        delivery  budget burn and resourcing
      finance  project margin at month end    operations  utilisation and capacity
      resource_management  who is booked next week
      fallback (`cadence.FALLBACK_ANGLE_WORD`)  the numbers behind the work

---

## 1. THE PROBLEM WITH APPENDING, AND WHAT IT COSTS TO IGNORE IT

`scripts/batch1_build.py` `CADENCE_STEPS` is three steps:

    em1  day 1  persona_pain
    em2  day 4  comparable_proof
    em3  day 8  breakup

`breakup` contains the sentence **"I will leave it here."** It is the close.

Appending a step 4 and a step 5 after em3 makes that sentence false on every
single send, with two further emails arriving after we said we were stopping.
That is not a tone problem. It is the same class of defect as the one already
fixed inside `breakup` itself and written out in the comment above it: a
sentence that asserts something about our own conduct which the record does
not support. `claims.py` cannot catch it - a claim about US carries no number,
month or event word - and `outreachclaims`, the authority on claims about us,
has no consumer on the send path. Nothing downstream would refuse it.

**A close is a terminal step. A sequence grows in the middle, never after the
close.** This codebase has already decided that once: the comment on
`cadencelibrary.EMAIL_EIGHT_LADDER` reads "rung 8 is the breakup moved from
rung 5". Lengthening a sequence MOVES the close; it does not bury it.

### THIS REORDERS WHAT em3 IS, and that is stated plainly

Under the ordering below, **em3 is no longer `breakup`.** `breakup` is retired
from the batch-1 cadence and its job is done at position 5 by `close_*` below,
where "I will leave it here" is true for the first time. `breakup` is NOT
deleted from `src/cadence.py` - it stays correct for any cadence that really
is three steps - it simply must not be named at em3 once there is an em4.

## 2. THE PROPOSED 5-STEP ORDERING

Rungs are `cadencelibrary.EMAIL_FIVE_LADDER`, which already defines what each
of five positions is for. This ordering is that ladder, not a new invention.

| pos | key | day | template | thread_reply | subject | ladder rung |
|-----|-----|-----|----------|--------------|---------|-------------|
| 1 | em1 | 1  | `persona_pain` (existing, unchanged) | false | SUBJECT_1 | 1 relevance, the pain, one question |
| 2 | em2 | 4  | `comparable_proof` (existing, unchanged) | true | SUBJECT_1 | 2 a different angle from email 1 |
| 3 | em3 | 8  | **NOT WRITTEN - see 2.1** | true | SUBJECT_1 | 3 name the product, one capability, one consequence |
| 4 | em4 | 13 | **`angle_shift_<persona>`** - drafted in 3 | false | SUBJECT_2 | 4 a different argument from every email before it |
| 5 | em5 | 18 | **`close_<persona>`** - drafted in 4 | true | SUBJECT_2 | 5 close the loop, easy no |

    thread_reply_pattern   [false, true, true, false, true]

That is the F,T,-,F,T family the estate's largest campaign runs and the shape
`docs/EMAILBISON-COPY-REQUIREMENTS.md` section 1 hypothesises. It remains a
DESIGN CHOICE and not a result: the 2026-09-15 findings say there is no
control group at any position, so nothing here should be quoted as evidence.

em4 opens a new thread, so it needs a second subject. The client config today
writes `"{SUBJECT_1}"` into all three steps; em4 and em5 need SUBJECT_2, and
em5 replies into em4's thread, so it carries SUBJECT_2 as well and EmailBison
prefixes "Re:" itself. Do not write "Re:".

### 2.1 The one position that is still empty, and why I did not fill it

Position 3 is rung 3: say what Productive is and what it is worth, one
capability from `product.capabilities` that fits this person's angle, one
concrete consequence. **No template in `TEMPLATES` does that job.**
`comparable_proof` is the nearest and it never names the product;
`comparable_proof_short` is its connection-accepted variant and restates it,
which fails "each step has a distinct purpose" in the section 6 checklist.
I was asked for two messages and have written two. A third, unasked, naming a
product capability is the kind of copy that should not appear in a diff
nobody requested.

**So there are two shippable readings, and the operator picks one:**

- **Ship 4 steps now.** Drop position 3, renumber: em1 d1, em2 d4,
  em3 = `angle_shift_*` d8, em4 = `close_*` d13.
  `thread_reply_pattern [false, true, false, true]`. No hole, no false
  sentence, no new copy beyond what is below. This is what I would ship.
- **Hold for 5.** Approve a rung-3 draft first, then ship the table above.

Either way em3 stops being `breakup`.

### 2.2 What must change in the same commit, or the build refuses

Listed because these are coupled and a half-applied change fails in a place
that does not name the cause.

1. `config/clients/productive.yaml` `email_sequence.steps` declares em1..em3
   and `bisonfactory` REFUSES when the provider sequence keys and the cadence
   keys disagree. `CADENCE_STEPS` in `scripts/batch1_build.py` and
   `email_sequence.steps` must gain the new keys together.
2. `thread_reply_pattern` is `[false, true, true]` today and must grow to
   match, in the same edit.
3. `wait_in_days` on the FINAL step must be `1`, never `0`. Campaign 485 was
   created and `set_sequence` raised on a 0, leaving it at 0 steps.
4. `work/stage/s7-copy.jsonl` carries `subject_1` and `body_1..body_3` per
   lead and nothing else. Two new steps need `subject_2` plus two more bodies,
   which means S7 re-renders for all 927 rows. Until that runs, these steps
   have nothing to send.
5. Every rendered body goes through `lint.check` with `MIN_WORDS = 40`. That
   floor is why an `em4` went unwritten for several records in an earlier
   generation pass. **Do not widen it.** See section 5.

---

## 3. STEP 4 - one new angle per persona

Rung 4: a different argument from every email before it. One focused idea, one
question, no recap, no new pitch. New thread, so a fresh subject.

**Neither of these may use `{line}`.** `{line}` is `persona_pain`'s variable
and on almost every record it resolves to the fallback sentence "I work with
<sector> teams on <angle>, and I do not know how <company> handles it" - which
is the first line of email 1. Reusing it at step 4 would open the fourth email
with the opening words of the first.

### 3.1 `angle_shift_economic_buyer`

    subject   the cost of waiting for {angle_word}

    body      {first_name}, most teams treat {angle_phrase} as a reporting
              problem. I think it is a decision problem.

              The reporting catches up eventually. The decisions do not wait
              for it. Which project gets the next two people, whether the one
              that is slipping is worth rescuing, what the quarter actually
              looks like. Those get made on whatever numbers exist that week,
              and at an agency the size of {company} the numbers that exist
              that week are usually last month's.

              None of that shows up anywhere as a fault. It shows up as a
              quarter that came in lower than it should have, for reasons
              nobody can reconstruct cleanly afterwards.

              Is that roughly the position at {company}, or is there already
              something closing that gap?

**What it is trying to do.** em1 says the numbers arrive too late; em2 says
finance and delivery keep two spreadsheets. Both are about VISIBILITY. This is
the first message that is about a DECISION, which is the only argument that
reaches an economic buyer who has already decided reporting is somebody else's
job. It reframes the angle rather than restating it, which is what rung 4
asks for, and it costs nothing if they disagree: the question offers them the
answer "someone already owns this".

It asserts nothing about the reader. "most teams", "usually" and "an agency
the size of {company}" are the same class of hedged pattern claim
`persona_pain` already makes. There is no prior message in it.

### 3.2 `angle_shift_champion`

    subject   {angle_word}, and who assembles it

    body      {first_name}, the thing I find most often at agencies the size
              of {company} is that the answer already exists. Somebody
              assembles it.

              Usually that is one person pulling hours out of one system,
              budgets out of another and the plan out of a third, so that the
              end of week conversation has numbers in it. It works. It is
              also the most expensive hour of the week, because it is the
              hour that cannot be spent on the thing the numbers are about.

              What I would want to know in your position is not whether the
              number can be produced, but how long producing it takes and how
              far behind it is by the time it lands.

              How long does that take at {company} at the moment?

**What it is trying to do.** The champion is not being sold visibility,
because the champion already HAS the number - they are the person who built it
by hand. So the new argument is the cost of producing it, which is the one
cost they can quantify without asking anybody. The closing question asks for a
duration rather than an opinion: it is the cheapest possible reply, and an
answer to it is a qualification signal the earlier steps cannot produce.

The subject names the topic and asks who does the work, rather than asserting
that they keep a spreadsheet, which would be a claim about them.

---

## 4. STEP 5 - short breakup with the soft question

Rung 5: close the loop, give an easy no, make no new pitch, ask for nothing
beyond permission to stop. Same thread as em4, so SUBJECT_2, with "Re:" added
by the provider.

**These replace `breakup` at the end of the sequence.** They do the same job
in fewer words and per persona.

### 4.1 `close_economic_buyer`

    subject   the cost of waiting for {angle_word}

    body      {first_name}, I will stop here either way, so this only needs a
              reply if a reply is useful to you.

              If {angle_phrase} is not a priority at {company} this quarter,
              that is a complete answer and I will take it as one.

              Shall I leave it there, or is there a better month to raise it?

    58 to 63 words rendered, against `breakup`'s 76

**What it is trying to do.** It makes "no" the cheapest available reply and
makes no new argument at all, which is what rung 5 asks for: no pitch, nothing
requested beyond permission to stop. The soft question offers a month rather
than a meeting, which is the lowest-friction thing a buyer can concede and the
only opening left that is not a yes. It claims nothing about what we have
sent: "I will stop here" is a statement about what we will do next, which is
the construction the fixed `breakup` uses and the only version that is true
whenever it goes out, including on a record where this is the first message
that ever arrived.

### 4.2 `close_champion`

    subject   {angle_word}, and who assembles it

    body      {first_name}, no reply needed if the answer is no. I would
              rather you kept the time.

              If {angle_phrase} is handled well enough at {company} for now,
              that is the answer and a fine one. If nobody has had a free week
              to look at it, that is a different one.

              Which of those is closer, or shall I leave it there?

    61 to 67 words rendered, against `breakup`'s 76

**What it is trying to do.** It separates "we are fine" from "we have not got
to it", which are the two real states at a champion's level and which a
generic breakup collapses into one. The question is a choice between two
answers we have just supplied, so it can be answered in three words. It also
gives the champion a way to say the second thing without it being a commitment
to anything.

---

## 5. WHAT I CHECKED, AND WHAT I DID NOT

Checked by rendering all four templates across every live persona and angle
combination, plus the `FALLBACK_ANGLE_WORD` case and a record with no first
name, and running the REAL constants and regexes out of `src/lint.py` over the
rendered text - `MIN_WORDS`, `MAX_WORDS`, `MAX_SUBJECT`, `BANNED_PHRASES`,
`SUBSTITUTED_PUNCTUATION`, `ATTACHMENT_RE`, `PLACEHOLDER_RE` and the
hard-wrap rule. 4 templates x 8 combinations. Result: no violation.

    [x] every rendered subject is under MAX_SUBJECT 60
        measured longest      51
        theoretical ceiling   "the cost of waiting for " 24 + ANGLE_WORD_MAX
                              32 = 56, and 32 + ", and who assembles it" = 54,
                              so both survive an angle label at the cap
    [x] every rendered body is between MIN_WORDS 40 and MAX_WORDS 180
        measured range  58 to 129 words
        angle_shift_economic_buyer  124 to 129    close_economic_buyer  58 to 63
        angle_shift_champion        127           close_champion        61 to 67
    [x] no BANNED_PHRASES: no "just following up", no "circling back",
        no "touching base", no "as per my last email"
    [x] no SUBSTITUTED_PUNCTUATION: ASCII only, no em dash, en dash,
        non-breaking hyphen or curly apostrophe. "month's" uses a straight
        apostrophe
    [x] no ATTACHMENT_RE trigger, nothing is attached
    [x] paragraphs separated by one blank line, no hard wrapping inside a
        paragraph (the indentation above is this document's, not the copy's)
    [x] only {first_name}, {company}, {angle_phrase}, {angle_word} are used.
        No other merge variable exists and an invented one renders empty,
        which is the 09-22 incident
    [x] {line} deliberately not used, for the reason in section 3
    [x] no prior message is asserted anywhere, on any of the four
    [x] no sender name, title, company, phone or signature is invented
    [x] no Productive capability is described, so none can be invented
    [x] no prospect name, company name or address appears in this document

Not checked, and these are the blocking ones:

    [ ] NOT rendered through `bisonfactory` by `scripts/render_preview.py`.
        A preview through a second path proves nothing, and until S7 emits a
        fourth and fifth body there is nothing for it to render
    [ ] NOT read back from EmailBison. A 2xx is not evidence
    [ ] the greeting path is inherited unchanged from the existing templates
        ("{first_name}, " with `cadence.template_vars` falling back to
        "there"). The fallback was rendered and lints clean, but that is my
        check against lint's constants, not a run of `lint.check` on a real
        record through `bisonfactory`

**One correction to the operator's brief, stated rather than quietly applied.**
Step 5 was asked for as "short". `docs/EMAILBISON-COPY-REQUIREMENTS.md`
records the opposite finding, measured 2026-09-15: same-thread follow-ups that
earned replies averaged 857 characters against 571 for new-thread emails. That
is survivorship and does not prove long follow-ups cause replies, but it means
brevity is NOT established and should not be treated as a rule.

The closes above ARE short, and measurably so: 58-63 words for the buyer and
61-67 for the champion, against `breakup`'s 76. An earlier pass of these two
came out at 79 and 83 words - LONGER than the thing they replace - and was
rewritten, because "short" asserted in a document and not counted is exactly
the kind of claim this repository keeps rediscovering. They were not cut
further: `MIN_WORDS` is 40, and a close written down to that floor is the
failure mode that already left an `em4` unwritten for several records.

## 6. WHAT HAPPENS NEXT, IN ORDER

1. Operator approves, rejects or amends the four bodies above.
2. Operator picks 4 steps now or 5 steps after a rung-3 draft (section 2.1).
3. Approved bodies go into `src/cadence.py` `TEMPLATES` as
   `angle_shift_economic_buyer`, `angle_shift_champion`,
   `close_economic_buyer`, `close_champion`.
4. `CADENCE_STEPS`, `email_sequence.steps` and `thread_reply_pattern` change
   in ONE commit (section 2.2), with em3 no longer naming `breakup`.
5. S7 re-renders so every lead carries `subject_2` and the new bodies.
6. `scripts/render_preview.py` over several representative leads, including
   one missing a first name and one per angle.
7. Provider write, then readback. Only then is any of this real.
