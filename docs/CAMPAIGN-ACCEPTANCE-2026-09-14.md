# Campaign rebuild: acceptance criteria, and what provider truth says today

The operator inspected both live campaigns and raised twelve points. Each is
recorded below with what the provider actually returns, because two of them
rest on a premise the API does not support and the rest are confirmed.

---

## P0-A - "the EmailBison campaign has only 2 email steps"

**NOT REPRODUCIBLE. The provider returns FIVE.**

`GET /campaigns/481/sequence-steps`, read 2026-09-14:

    step 1  id 4729  order 1  wait 3  active True  {SUBJECT_1} / {BODY_1}
    step 2  id 4730  order 2  wait 4  active True  {SUBJECT_2} / {BODY_2}
    step 3  id 4731  order 3  wait 4  active True  {SUBJECT_3} / {BODY_3}
    step 4  id 4732  order 4  wait 9  active True  {SUBJECT_4} / {BODY_4}
    step 5  id 4733  order 5  wait 1  active True  {SUBJECT_5} / {BODY_5}

Five steps, consecutive order, all `active`, each carrying its own numbered
merge fields. The whole workspace holds exactly two Resonate campaigns:

    481  5 steps  23 leads  paused   RESONATE - PRODUCTIVE - EMAIL - ...
    451  1 step    1 lead   active   RESONATE - PRODUCTIVE CANARY - ...

So there is no two-step Productive campaign to trace, and no point where five
became two.

**The likeliest explanation, and it is worth checking before anything is
rebuilt:** the UI shows the SEQUENCE, and this sequence is a template of merge
fields. A reader looking at it sees `{SUBJECT_1}`, `{BODY_1}` and no words -
the actual copy lives per lead in custom variables, not in the steps. If the
editor collapses or paginates, or only renders steps it considers complete,
that would present as "fewer steps than there are".

Confirming which campaign and which screen would settle it in a minute.
Nothing here should be rebuilt on the assumption that step 3, 4 and 5 are
missing when the API says they exist and are active.

## P0-K - provider structural assertion

Agreed and already partly true. `bisonfactory` reads the sequence back and
`heyreachfactory` compares the graph field for field. What does not exist is a
test that asserts FIVE provider-visible steps for a five-email cadence, rather
than "the readback matched what we sent". Worth adding: those are different
assertions, and only the first catches a cadence that shrank before it was
sent.

---

## WHAT IS CONFIRMED, from the copy actually staged on lead 203708

The operator's copy criticisms are right, and the evidence is stronger than
the complaint. Four of the five staged emails, read from the provider:

    em1  "AcqCom Digital Marketing describes itself as a full-service agency..."
    em2  "AcqCom Digital Marketing offers a wide range of services from..."
    em3  "AcqCom Digital Marketing partners closely with clients to deliver..."
    em5  "AcqCom Digital Marketing focuses on delivering data-driven..."

### P0-E - Productive is never explained. CONFIRMED, and worse than stated.

**The word "Productive" does not appear in any of the five emails.** The
closest is a positioning line - "our approach to making profitability visible
on Monday, not two weeks late" - which never says what the product is, what it
does, or that it is software. A recipient finishing all five emails still does
not know what they were being offered.

### P0-B - narrative progression. PARTLY PRESENT, structurally absent.

The ladder gives each rung a different JOB and those jobs do reach the model -
em3 is value, em5 is the close. The arguments do differ.

**But every email has the identical SHAPE:**

    [the company's own self-description]
    -> [why I am writing to you, by role]
    -> [question or pitch]

Four openings, four different sets of words, one formula. And "I am reaching
out to you as COO and Co-Founder" appears in both em1 and em2 - a repeated
frame, and one that reads as though the SENDER holds the title.

**This is why the repetition gate passed them.**
`quality.repetition_across_rungs` counts shared distinctive WORDS, and the
formula uses different words every time. It is a structural duplicate that no
vocabulary comparison can see. That is a direct and evidenced addition to
TASK-043, which must catch shape as well as content.

### P0-C - context before question. CONFIRMED for LinkedIn, NOT for email.

The email the operator objected to is not the email that was sent. Email 1
does earn its question - it opens with context, states why this person, then
asks.

The naked question - "how do you currently ensure profitability is visible in
your projects?" - is the HEYREACH graph, where it is the entire message. So
the rule is right and the defect is on the LinkedIn side, where messages are
one line and there is no room for the context that makes a question land.

### P0-D, P0-F, P0-G, P0-H, P0-I, P0-J, P0-L

Accepted as acceptance criteria. Notes where they change existing work:

- **P0-D, never invent pain.** `claims.check` already refuses an unevidenced
  assertion about the prospect, and the staged copy complies - it describes
  what the company says about ITSELF rather than asserting a problem. The gap
  is the vocabulary: OBSERVED / INFERRED / HYPOTHESIS / UNKNOWN is a finer
  distinction than the gate makes today.
- **P0-F/G, five variants per email step and subject.** TASK-044 covers
  generation; this extends it to email and to subjects, with subject and body
  paired so a result stays attributable.
- **P0-J, render all five emails.** Folded into TASK-046, which is running and
  must not be interrupted. It will need a second pass for the email side.
- **P0-L, do not scale defective campaigns.** Already the position: the
  HeyReach lane is blocked and campaign 481 is paused.
