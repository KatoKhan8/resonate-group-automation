# TASK-020 - An outcome is more than "replied"

Operator backlog: QWEN-25, and the prerequisite for QWEN-21 and every
experiment in `docs/ESTATE-LEARNING-2026-09-14.md`.

## GOAL

Make the reply classifier good enough that the operator's optimisation
hierarchy can actually be measured, and make its output land somewhere a
report can read.

    MEETING / QUALIFIED OPPORTUNITY
    POSITIVE REPLY
    MEANINGFUL REPLY
    CONNECTION ACCEPTANCE
    DELIVERY / EXECUTION

## WHY IT MATTERS - measured 2026-09-14 against the client's live estate

The estate reports 2,139 unique replies across 48,606 people contacted, a
4.40% reply rate. Classifying a sample of those replies with
`replies.classify(model=None)` says that number means much less than it looks:

    automated_reply flag set by the provider     71% of replies
    out_of_office by our own rules               29%
    NO RULE MATCHED AT ALL                       39%
    referral                                     10%
    unsubscribe / negative / not_relevant        16%
    positive                                      3%

So the headline reply rate is mostly robots, and two of every five real
replies fall through every rule we have. `interested`, the provider's own
field for a good reply, is set 17 times in the whole estate.

A campaign cannot be optimised on a metric where 71% of the signal is an
out-of-office auto-responder. Everything in the learning document - sequence
length, subject variants, the referral step - currently terminates in
"replied: yes/no", and that is the ceiling until this is fixed.

## CURRENT CONTEXT

- `src/replies.py` is rule-based, `VERSION = "rules-1"`, with the right
  categories already: positive, neutral, negative, unsubscribe,
  account_do_not_contact, out_of_office, not_now, referral, not_relevant.
- `classify(text, model=None)` runs rules first and falls back to
  `{"classification": "neutral", "confidence": 0.5, "reason": "no rule
  matched and no classifier was available"}`. THAT FALLBACK IS THE 39%, and
  reporting it as `neutral` is how "we could not tell" becomes "they were
  lukewarm". Those are different facts.
- Rows carry `automated_reply`, `interested`, `folder`, `type` and
  `text_body`. `bison.classify_reply_row` sorts reply/bounce/delivered/
  outgoing and is transport-level only - it says nothing about sentiment.

## SCOPE

1. **Separate "no rule matched" from "neutral" everywhere.** They are
   different answers and only one of them is a measurement. This is the
   single highest-value change in the task and it is small.
2. **Consume `automated_reply`.** A provider-flagged auto-reply is not a
   reply from a person. It must not count toward a reply rate and must not
   suppress outreach the way a human reply does - though an out-of-office
   should still defer the next touch, which `src/ooo.py` and
   `src/oooreturn.py` already model. Trace whether they are consumed.
3. **Raise rule coverage on the unmatched 39%.** Work from the real bodies;
   add patterns with evidence. Do not invent a category.
4. **A meeting is not a positive reply.** The hierarchy names them
   separately and nothing here distinguishes them. Decide whether `positive`
   splits, and say why in the code either way.
5. **Find the consumer.** A classification nothing reads is the defect this
   repository keeps rediscovering. Trace: reply row -> classification ->
   canonical state -> suppression -> report. Name every link that does not
   exist yet. If the chain is broken, say so in FINDINGS rather than adding
   a field nobody reads.

## FILES ALLOWED

`src/replies.py`, `tests/`, `docs/qwen-tasks/`, a report under `docs/`.

## FILES FORBIDDEN

`src/providers/**`, `src/providerwrites.py`, `src/executionguard.py`,
`src/killswitch.py`, `work/**`.

## PRODUCTION CONSTRAINTS

ZERO network. Work from fixtures. If you need real reply bodies, ask Claude -
they are live client correspondence and they do not go into fixtures, into
prompts, or into this repository. **Do not commit a real reply body, a real
name, a real address or a real company. `tests/test_fixture_hygiene` exists
because that has happened here before.**

## TESTS REQUIRED

Behavioural, on what `classify` returns for a given text.

- an unmatched body returns something that is NOT `neutral`, and a caller can
  tell the two apart;
- a provider-flagged automated reply does not count as a human reply;
- an out-of-office defers rather than suppresses;
- a referral is only a referral when it points at somebody - `_points_at_
  somebody` already enforces that and it must keep holding;
- every new pattern has a test with a body that is realistic and INVENTED.
