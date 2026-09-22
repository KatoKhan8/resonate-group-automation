# Reply classification policy — automated, assistant redirects, and what counts as positive

**Decided by:** Zvonimir Bešlić (operator)
**Date:** 2026-09-22
**Status:** items 1, 3 and 4 decided and built; item 2 decided and
deliberately NOT built — it is gated on item 1 being live.

This file is the record. `src/replies.py` and `src/accountpolicy.py` carry
the implementation and quote this decision at the lines that enforce it.

---

## THE DECISION, AS GIVEN

> 1. Reply classification: add class "automated" (out-of-office,
>    auto-acknowledgement, ticketing, assistant or EA redirect, "thanks for
>    your email" with no content). Automated is never positive_reply.
>    Assistant redirects get their own class "assistant_redirect": logged
>    as a new contact candidate at that account, routed to internal review
>    only. Positive requires intent: a question, interest, a meeting ask, a
>    request for more. Re-run the classifier on today's replies and report
>    how many positives survive.
> 2. Route positive_reply to #productive-resonate-outbound (C0ADUMGQX8S) as
>    well as #replies-productive, in a client-facing format: company,
>    contact role, one-line quote, which of their senders received it,
>    suggested next step. Never the internal campaign name; say "Kresimir,
>    US cohort". Only after item 1 is live and tested; until then positives
>    stay internal.
> 3. Milestones (first_send, first_reply, first_bounce) stay internal;
>    remove them from #replies-productive, they are noise there.
> 4. Recorded as policy with my name and date. Tests: an EA redirect like
>    today's is classified assistant_redirect, not positive; a client
>    channel never receives an internal campaign name.

---

## 1. THE ANSWER TO THE QUESTION ASKED: ZERO POSITIVES SURVIVE

The classifier was re-run over every reply EmailBison recorded on
2026-09-22. 36 rows dated today: 26 replies, 9 bounces, 1 row that is not a
reply and was dropped rather than guessed at.

    classification         BEFORE  AFTER
    assistant_redirect          0      1
    automated                   0      1
    negative                    3      3
    not_relevant                3      3
    out_of_office               7      7
    positive                    1      0     <--
    referral                    1      1
    unknown                    11     10

    under the automated umbrella   7 -> 9

**One positive existed in the whole day and it does not survive.** It was
an executive assistant explaining that she manages her principal's inbox —
the exact reply the operator named. It matched `POSITIVE_PATTERNS` on the
warmth of its prose while nobody at that account had expressed interest in
anything. It is now `assistant_redirect`.

The other move was a ticketing acknowledgement, `unknown → automated`:
*"Your request has been received and is being reviewed by our support
team."*

For context on how little the words were telling us: the provider's own
`automated_reply` flag was **true on 21 of the 26**, including on both
replies that moved. The flag and the classifier now agree more often, and
where they disagree the classifier is the conservative one.

---

## 2. HOW IT IS BUILT, AND THE TWO JUDGEMENT CALLS

### 2a. `out_of_office` keeps its own label

The decision lists out-of-office as a kind of `automated`. It is not folded
into the new class, and that is a deliberate departure worth your sign-off.

`out_of_office` is named directly in `events`, in `inbound`, and in
`accountpolicy.CLASSIFIER_OUTCOME`, and **a pure out-of-office is the one
reply shape that skips the cadence pause** — `src/replies.py`'s own
docstring, rule 2. Collapsing the label would change which replies pause a
cadence, which is a sending-behaviour change nobody asked for.

Instead the umbrella is a predicate:

    replies.AUTOMATED_CATEGORIES = (OUT_OF_OFFICE, AUTOMATED,
                                    ASSISTANT_REDIRECT)
    replies.is_automated(classification) -> bool

One definition, which the never-positive guarantee, the 18:00 summary and
every automated-vs-human count all read. If you would rather have the
single flat class, say so and it is a small change — but it moves a pause.

### 2b. `assistant_redirect` maps to UNKNOWN, not REFERRAL

Your words are "routed to internal review only", and `UNKNOWN` is this
module's name for exactly that: a person looks at it and no automation acts
on it.

`REFERRAL` was the tempting mapping — an assistant does point at somebody —
and it was rejected because `reply.on_referral` is a policy a workspace may
set to keep contacting. **A new class must not inherit a permission nobody
granted it.**

The contact candidate is preserved in the classification and its evidence;
wiring it into a candidate record at that account is not built here and is
listed in §5.

### 2c. Positive requires intent — and the gate is narrow on purpose

Three `POSITIVE_PATTERNS` are bare nouns: `pricing`, `calendar`,
`availability`. They appear in warm replies and equally in signatures, in
autoresponders, and in sentences about somebody else's diary — *"I look
after her calendar"*, which is the reply this decision came from. Only
those three are gated; every other positive pattern already carries a verb
somebody chose.

The first implementation gated all 34 and dropped "Yes please", "Show me"
and "Sure, happy to discuss" to `unknown`. **A false negative on a real
buying signal costs a meeting**, so the narrowness is asserted by
`test_the_gate_applies_only_to_the_bare_nouns`.

### 2d. And a precedence bug worth recording

The "thanks for your email with no content" check was first placed before
the rule table. `No, thank you.` / `Not for me, thanks.` / `No interest,
thanks.` are all short, carry no intent, and end in a thanks — so every one
of them became `automated`. **A classification softening a refusal**, which
is the single thing `src/replies.py`'s docstring forbids. Three existing
tests caught it immediately; it now sits at `AUTOMATED`'s own place in the
table, below every refusal, and
`ARefusalIsNeverSoftenedByTheNewClasses` keeps it caught.

---

## 3. ITEM 3 — MILESTONES OUT OF #replies-productive

**This is one config key and it is yours, not this session's.** No code
change is needed and none was made.

    src/notify.py   CAMPAIGN_MILESTONE -> ("slack.notify_campaign_milestones", False)

The switch already defaults to **off**. Productive's workspace policy turns
it on explicitly:

    work/workspaces.jsonl, workspace `productive`, settings.policy
        "slack.notify_campaign_milestones": "on"     <- set this off

`work/` is production state and this session does not edit it. Setting that
key to `off` removes first_send / first_reply / first_bounce from
`#replies-productive` and nothing else; milestones remain available
internally.

---

## 4. ITEM 2 — DECIDED, NOT BUILT, AND WHY

Your own condition: *"Only after item 1 is live and tested; until then
positives stay internal."*

Item 1 is built and tested. It is **not live**: it is on branch
`slack-agent`, and the running `slack_agent_loop.py` (PID 109832, started
19:21:55) imports at start and does not reload. So the gate has not opened
and positives stay internal, which is the current behaviour and needs no
change to preserve.

What is already in place for it, so the next increment is small:

- `plain_campaign_label()` renders a client-safe campaign label.
- `carries_internal_label()` decides when a name must be replaced — **and
  §6 below fixes a live hole in it that this decision's own test found.**
- `AClientChannelNeverReceivesAnInternalCampaignName` is written now,
  against the existing guard, so the renderer inherits a test that already
  says what it may not do.

Still to build when you open the gate: the client-facing payload itself
(company, contact role, one-line quote, which of their senders received it,
suggested next step), and the second destination on `POSITIVE_REPLY`.

The `"Kresimir, US cohort"` form in your instruction names **the client's
own sender**, which is theirs to hear, and a plain cohort word instead of
the campaign. That is the shape the renderer will take.

---

## 5. WHAT THIS DELIBERATELY DOES NOT DO

- **No candidate record is written** for an assistant redirect yet. The
  classification and its evidence carry it; creating a contact at that
  account is a write, and writes get their own increment.
- **No automation changes.** Both new classes map to outcomes that pause or
  hold. Neither is in `ALERTING`, so neither wakes anybody.
- **The model seam is untouched.** Rules decide all of this for free; a
  model is still only consulted for what rules leave open.

---

## 6. FOUND WRITING THE TEST: 37 LIVE CAMPAIGN NAMES REACHED CLIENTS INTACT

Your second named test failed on its first run, against real data, and the
fix is in this increment.

`slackagenttools._plain_labels` rewrites a campaign `name` **only when
`carries_internal_label` recognises it**. A name it does not recognise
reaches a client verbatim.

Every one of the 37 live HeyReach campaigns is named:

    RESONATE <CLIENT> LI B1 SEAT <provider seat id>

and **not one word of that was on `INTERNAL_LABEL_WORDS`** — "B1" is not
"batch", and "seat" was not on the list at all. So the provider seat id was
reaching client answers inside the campaign's own name, which is precisely
what increment 2 decided a client channel never carries: seat counts,
never an attributed seat.

`seat` and `resonate` are now on the list. The cost of a false positive
there is small and stated in the code: a word on this list only makes a
campaign read as "LinkedIn campaign 613761", which is still a useful
answer — unlike `INTERNAL_EXPERIMENT_TERMS` next door, where a false
positive discards a whole correct reply, and which is deliberately
narrower for that reason.

---

## 7. TESTS

    tests/test_an_assistant_is_not_a_buying_signal.py     25  NEW

Both of your named tests are in it, under
`TheOperatorsTwoNamedTests` and
`AClientChannelNeverReceivesAnInternalCampaignName`.

The rest guard the edges the first implementation got wrong: a refusal is
never softened, an unsubscribe still outranks everything, the intent gate
stays narrow, and both new classes are wired into `CATEGORIES`,
`CLASSIFIER_OUTCOME` and out of `ALERTING`.
