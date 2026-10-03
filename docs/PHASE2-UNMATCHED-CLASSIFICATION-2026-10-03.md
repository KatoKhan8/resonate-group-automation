# The 21 unmatched phase-2 scenarios, classified

**Lane 3, 2026-10-03.** Answers open decision 3 of
`docs/HANDOFF-2026-10-03-EVENING.md`: *"The 21 unmatched phase-2 scenarios
need classifying into defect / no rule / wrong scenario, and the 'no rule'
list is the operator's to decide."*

Every item below carries exactly one of three verdicts. None is reported as
"expected".

---

## 0. What "the 21" is, before anything is classified

The artefact exists and was found. It is not a separate file: it is the run
committed on branch `task-phase2-simclock` at `787fa450`, under
`docs/phase2-run-2026-10-03/`. `RUN-LOG.txt` ends

    firings 90, matched 69, unmatched 21, late 0

and `FINAL-TABLE.md` carries the per-scenario table plus two sub-tables,
"Every unmatched field" and "Every key no authority could answer".

**The handoff sentence is loose, and the looseness matters.** The run fired
30 scenarios three times each. The 21 are **21 unmatched FIRINGS**, which are
**7 distinct scenarios** - S09, S13, S15, S16, S17, S24, S29 - each failing
on all three of its firings, on a different account and a different simulated
day each time. Those 21 firings decompose into **16 distinct
(scenario, field) mismatches**. Because all three firings of a scenario failed
on identically the same fields, the verdict is a property of the scenario and
not of the firing.

So this document classifies at the field level, where the choosing actually
happens (16 rows, section 2), rolls that up per scenario (7 roots, section 3),
and restates it per firing so that literally all 21 carry a verdict
(section 4).

The 21 are **not** the "Every key no authority could answer" table. That is a
separate and larger list (63 rows) which the run already reports as
unanswerable rather than unmatched, and it is dominated by `rule2_step`, whose
absence that run and the catalogue both already state as a deliverable.

### How each verdict was reached

Everything below was executed on master `2bf7b8a5`, in worktree `wt-scen3`,
not read off the run's report. The reproduction scripts are in section 6. The
classifier output reproduced the run's `actual` column exactly for all six
classifiable rows, which is what licenses using master to judge a run made on
`task-phase2-simclock` (the two branches differ in `src/` only in
`copystages`, `generate`, `lint`, `providerwrites`, `skills` and `store` -
none of them a classifier, a gate or a policy map).

---

## 1. The three findings the 16 rows rest on

**F1. `channels` has no word for a stop.** `channels.email_verdict` and
`channels.linkedin_verdict` read `operator_excluded`, `unsubscribed`,
`suppressed`, `no_address`, `bounced`, MX, verification, `no_profile`,
`linkedin_url_not_canonical` and `duplicate_identity`. Enumerated, the
module's entire reason vocabulary is 16 constants and **not one of them names
a reply or a stop**. The authority that answers "may we contact this person"
is `eligibility.must_not_contact`, and it answers correctly:
`blocked:replied` when a reply event names the contact, and
`blocked:contact_stopped` when `contact["stopped"]` is set. Both are
contact-level, so both close *both* channels.

Measured, with a control:

    S29 after a NEGATIVE email reply
       channels.linkedin_verdict    = (True, None)
       eligibility.must_not_contact = ['blocked:replied', 'blocked:company_paused']

    S24 with contact['stopped'] = not_now
       channels.linkedin_verdict    = (True, None)
       eligibility.must_not_contact = ['blocked:contact_stopped']

    CONTROL - unsubscribed (the S01/S28 shape, which MATCHED in the run)
       channels.linkedin_verdict    = (False, 'unsubscribed')
       eligibility.must_not_contact = ['blocked:unsubscribed']

The control is the point: `channels` does read one person-level permission
fact, so the scenarios that asserted it for an unsubscribe matched and the
scenarios that asserted it for a stop could not.

**F2. `unknown` has no policy, so a reply the classifier read correctly can
still have no consequence.** `accountpolicy.OUTCOME_POLICY` has an entry for
eleven of the twelve `OUTCOMES`; `unknown` is the one with none. Six
classifier categories map to it - `interested`, `meeting_intent`, `question`,
`objection`, `send_info`, `assistant_redirect` - so for those six nothing is
held, nothing is stopped and nobody is told. For the three taxonomy
categories this is deliberate and documented (TASK-074: "a taxonomy verdict
can never widen what automation is allowed to do"). **TASK-1004, on branch
`task-1004-positive-replies-reach-a-human`, at REVIEW and not yet on master,
already fixes the reachability half** with a new `NEEDS_A_PERSON` outcome for
`interested`, `meeting_intent` and `question`, and deliberately leaves
`objection` and `send_info` on `unknown`.

**F3. There is a dated operator definition of a positive, and it is the
authority three of these rows should have been judged against.**
`C:\Users\Zvonimir\Desktop\resonate-ops\copy-review\POSITIVE-SAMPLE-2026-10-03.md`,
written to the operator's own instruction on 2026-10-03, states it as applied:

> an explicit statement of interest, **a request to talk**, or **a question
> about the offer**. A referral is not positive. "Send me some information and
> I will see" is not positive.

and immediately flags the one limb that is still open: the three rows kept on
the question limb "are kept because each asks what the offer *is* or what it
*costs* ... if you read that limb more narrowly, the count drops from 10 to 7."

---

## 2. The classification - all 16 field-level mismatches

`expected` and `actual` are the run's own columns. `evidence` is what was
measured on master today.

| # | id | field | intent the field serves | verdict | evidence | action |
|---|---|---|---|---|---|---|
| 1 | S09 | `replies_classify` (`positive` vs `interested`) | a request for call times is a positive | **pravi defekt** | `POSITIVE_PATTERNS` carries `book (a/some) time`, `can we (schedule/arrange/...)`, `availability`, `calendar` - none covers "can you send some times". Nothing in `RULES` matched; the taxonomy's `interested` then matched "this is interesting" (not the production pattern, which is the whole word `interested`) at 0.60 and won by default. The operator's 2026-10-03 definition names "a request to talk" as a positive. | TASK-1010 |
| 2 | S09 | `replies_confidence_at_least` (`75` vs `60`) | - | **pravi defekt** | Same root as row 1: 0.60 is the taxonomy's constant for `interested`. Note the operator's own measurement that confidence is a per-class constant with zero within-class variation, so this field can only ever restate the class. | TASK-1010 |
| 3 | S09 | `accountpolicy_outcome` (`positive` vs `unknown`) | - | **pravi defekt** | Same root as row 1. `CLASSIFIER_OUTCOME['interested'] = 'unknown'`, and `unknown` is the one outcome with no `OUTCOME_POLICY` entry (F2). TASK-1004 moves this to `needs_a_person`, **not** to `positive`, so TASK-1004 alone does not close this row. | TASK-1010 |
| 4 | S09 | `notification_fired` (`True` vs `False`) | a positive reply goes to a human | **pravi defekt** | `inbound.handle` and `replies.apply` both announce on `replies.is_positive(verdict)` only. ALREADY TASKED - TASK-1004, at REVIEW, raises `notify.REPLY_NEEDS_A_PERSON` for this family. No duplicate opened. | TASK-1004 (merge it) |
| 5 | S13 | `replies_classify` (`referral` vs `not_relevant`) | a referral routes to a new person | **pravi defekt** | The phrase `wrong person` is a member of `NOT_RELEVANT_PATTERNS`, and `NOT_RELEVANT` ranks above `REFERRAL` in `RULES`. The reply matched `wrong person` (the evidence the classifier itself recorded) although `REFERRAL_PATTERNS` also matched `speak to`. | TASK-1011 |
| 6 | S13 | `accountpolicy_outcome` (`referral` vs `not_icp`) | and does not block the account | **pravi defekt** | `not_icp` resolves to `reply.on_negative` and labels the account "Not a fit"; `referral` resolves to `reply.on_referral` **and** `reply.activate_referred_contact`, the only path on which the named person is ever activated. `wrong_person` is a first-class `OUTCOME` with its own policy that **no classifier category can produce** - it is unreachable from `CLASSIFIER_OUTCOME`. | TASK-1011 |
| 7 | S15 | `replies_classify` (`question` vs `unknown`) | a question is a live conversation | **krivo napisan scenarij** | The lead `QUESTION_PATTERNS` rule requires a literal question mark. The scenario's invented text, "how would this work with the tooling we already run", is a question written as a statement. Measured: add the question mark and the classifier returns `question` at 0.75, exactly what the row expects. | fix the scenario text |
| 8 | S15 | `notification_fired` (`True` vs `False`) | it reaches a person | **pravi defekt** | `question` reached nobody, for the same reason as row 4. ALREADY TASKED - TASK-1004 at REVIEW covers `question` by name. | TASK-1004 (merge it) |
| 9 | S15 | `counts_as_positive` (`True` vs `False`) | the operator's metric | **nema pravila** | No module computes a `counts_as_positive` of any kind. The operator's 2026-10-03 definition does name "a question about the offer" as a positive limb, and that same file records the limb as unsettled - the broad reading keeps 10 rows, the narrow one 7. | **operator question Q1** |
| 10 | S16 | `replies_classify` (`objection` vs `unknown`) | an objection is neither a refusal nor a buying signal | **nema pravila** | `OBJECTION_PATTERNS` covers budget, time and resources, team size, "we already use" and "not a priority" - all four verified to classify as `objection` at 0.75. A past-failure objection ("we tried something like this before and it did not work for us") is a family the pattern set does not contain and no operator decision names. | **operator question Q2** |
| 11 | S17 | `accountpolicy_outcome` (`not_now` vs `unknown`) | an assistant is machinery, not the prospect | **krivo napisan scenarij** | `src/accountpolicy.py` lines 174-184 record the operator's own ruling verbatim: *"`assistant_redirect` maps to UNKNOWN, NOT to REFERRAL. The operator's words are 'routed to internal review only', and UNKNOWN is this module's name for that."* The scenario asserted `not_now`, which is where `automated` and `out_of_office` map - it read across from its own `rule:` line (`AUTOMATED_CATEGORIES includes assistant_redirect`), which is true and does not imply the outcome. | fix the expectation to `unknown` |
| 12 | S17 | `cadence_stopped` (`True` vs `False`) | - | **nema pravila** | Follows from F2: `unknown` has no policy, so nothing stops the cadence and the next step goes out to somebody who has just written "send anything for her through me". The operator said "routed to internal review only" and never said whether the cadence pauses while that person looks. | **operator question Q3** |
| 13 | S24 | `channels_email_allowed` (`False` vs `True`) | the return date never lifts the stop | **krivo napisan scenarij** | F1. `channels` has no reason constant that can express a stop, so the key's own legal value set (listed in the scenario README) cannot carry the assertion. `eligibility.must_not_contact` returns `blocked:contact_stopped` and holds it on day 18 and after. For this one the wrong key is in the CATALOGUE row itself, not only in the YAML. | restate as `eligibility_reason: blocked:contact_stopped` |
| 14 | S29 | `channels_email_allowed` (`False` vs `True`) | a negative email stops LinkedIn too | **krivo napisan scenarij** | F1. `eligibility.must_not_contact` returns `blocked:replied`. The CATALOGUE row for S29 told the author to prove the stop "through `bisonfactory.stage` and `heyreachfactory.ensure_leads`", and `heyreachfactory` line 1225 does call `eligibility.must_not_contact`. The YAML asserted the channel gates instead. | restate against `eligibility.must_not_contact` |
| 15 | S29 | `channels_linkedin_allowed` (`False` vs `True`) | - | **krivo napisan scenarij** | As row 14. | as row 14 |
| 16 | S29 | `cross_channel_stop` (`True` vs `False`) | - | **krivo napisan scenarij** | As row 14. The stop IS cross-channel: `_replied` is contact-level, so one reason closes both channels. The row defined `cross_channel_stop` as the conjunction of two `channels_*_allowed` flags, and it is that definition that fails, not the behaviour. | define it as "`must_not_contact` is non-empty" |

### Counts, by field

| verdict | n of 16 |
|---|---|
| **pravi defekt** | 7 |
| **krivo napisan scenarij** | 6 |
| **nema pravila** | 3 |

---

## 3. Rolled up per scenario - the root verdict

A scenario's root verdict is the verdict of the field that has to be resolved
first; the others are downstream of it and are listed so nothing is buried.

| id | intent | root verdict | why that is the root | what remains under it |
|---|---|---|---|---|
| S09 | A positive reply goes to a HUMAN and is never answered automatically | **pravi defekt** | one classification miss produces all four fields | 4 defect fields, one of which (row 4) is already TASK-1004 |
| S13 | A referral ROUTES to a new person and does not block the account | **pravi defekt** | one pattern-membership error produces both fields | 2 defect fields |
| S15 | A question is a live conversation, so it reaches a person and stops the cadence | **krivo napisan scenarij** | until the text is written as a question, nothing downstream can be judged | then one defect (TASK-1004) and one operator question remain |
| S16 | An objection is neither a refusal nor a buying signal | **nema pravila** | the class for this sentence has never been decided | - |
| S17 | An assistant answering for somebody else is machinery, not the prospect | **krivo napisan scenarij** | the expectation contradicts a ruling recorded in the code | one operator question remains |
| S24 | The return date arriving means LOOK AGAIN, and never lifts the stop | **krivo napisan scenarij** | the asserted key cannot express the assertion | - |
| S29 | A negative EMAIL reply must stop the LinkedIn sequence | **krivo napisan scenarij** | the same | - |

| verdict | scenarios |
|---|---|
| **pravi defekt** | 2 (S09, S13) |
| **krivo napisan scenarij** | 4 (S15, S17, S24, S29) |
| **nema pravila** | 1 (S16) |

---

## 4. All 21 firings

Each scenario fired three times, on a different account and a different
simulated day, and failed on identically the same fields every time. Every
firing therefore carries its scenario's root verdict.

| # | firing | id | intent | verdict | evidence | action |
|---|---|---|---|---|---|---|
| 1 | S09 x1 | S09 | A positive reply goes to a HUMAN | **pravi defekt** | sec 2, rows 1-4 | TASK-1010, and merge TASK-1004 |
| 2 | S09 x2 | S09 | the same | **pravi defekt** | the same | the same |
| 3 | S09 x3 | S09 | the same | **pravi defekt** | the same | the same |
| 4 | S13 x1 | S13 | A referral ROUTES to a new person | **pravi defekt** | sec 2, rows 5-6 | TASK-1011 |
| 5 | S13 x2 | S13 | the same | **pravi defekt** | the same | the same |
| 6 | S13 x3 | S13 | the same | **pravi defekt** | the same | the same |
| 7 | S15 x1 | S15 | A question is a live conversation | **krivo napisan scenarij** | sec 2, rows 7-9 | fix the text, then Q1 and TASK-1004 |
| 8 | S15 x2 | S15 | the same | **krivo napisan scenarij** | the same | the same |
| 9 | S15 x3 | S15 | the same | **krivo napisan scenarij** | the same | the same |
| 10 | S16 x1 | S16 | An objection is neither a refusal nor a buying signal | **nema pravila** | sec 2, row 10 | Q2 |
| 11 | S16 x2 | S16 | the same | **nema pravila** | the same | the same |
| 12 | S16 x3 | S16 | the same | **nema pravila** | the same | the same |
| 13 | S17 x1 | S17 | An assistant is machinery, not the prospect | **krivo napisan scenarij** | sec 2, rows 11-12 | fix the expectation, then Q3 |
| 14 | S17 x2 | S17 | the same | **krivo napisan scenarij** | the same | the same |
| 15 | S17 x3 | S17 | the same | **krivo napisan scenarij** | the same | the same |
| 16 | S24 x1 | S24 | The return date never lifts the stop | **krivo napisan scenarij** | sec 2, row 13 | restate the key |
| 17 | S24 x2 | S24 | the same | **krivo napisan scenarij** | the same | the same |
| 18 | S24 x3 | S24 | the same | **krivo napisan scenarij** | the same | the same |
| 19 | S29 x1 | S29 | A negative EMAIL reply must stop LinkedIn | **krivo napisan scenarij** | sec 2, rows 14-16 | restate the key |
| 20 | S29 x2 | S29 | the same | **krivo napisan scenarij** | the same | the same |
| 21 | S29 x3 | S29 | the same | **krivo napisan scenarij** | the same | the same |

| verdict | firings of 21 |
|---|---|
| **pravi defekt** | 6 |
| **krivo napisan scenarij** | 12 |
| **nema pravila** | 3 |

---

## 5. One side-finding, named rather than folded into a verdict

S24 and S29 are mis-specified, and the thing they stumbled into is real and
should not vanish with them. `channels` reads ONE person-level permission
fact (`unsubscribed`) and not the other two (`stopped`, and a reply). It is
documented in its own source as "the canonical answer to which channels can
this person be reached on ... consulted by the preview, the reports and the
coverage summary, none of which go through `eligibility`", and some fifteen
call sites across `web/api.py`, `nextaction`, `priority`, `contextpack`,
`demo_outreach` and `simulator` take its answer.

**No send escapes.** `eligibility.must_not_contact` is the send gate,
`executionguard` lists both `blocked:replied` and `blocked:contact_stopped`,
and `heyreachfactory` calls it directly. So this is a reporting and ranking
defect, not a sending one: a person who refused, or who is stopped on an
out-of-office, is counted as contactable in the operator's own view of the
estate. It is written into TASK-1011 as its second part rather than given a
verdict here, because it is not one of the 21.

---

## 6. Reproduction

Scripts in the `scratchpad/` of this session, and deliberately NOT in the
`%TEMP%` root - a stray `inspect.py` there shadows the stdlib and, on the
first attempt, drove this import chain into a live `bison.fetch_replies` that
failed only because `BISON_KEY` is absent.

    py -3 scratchpad/repro1.py   # classifier + accountpolicy, all 6 rows
    py -3 scratchpad/repro5.py   # F1, with the unsubscribed control
    py -3 scratchpad/repro7.py   # OUTCOME_POLICY, and that `unknown` has none
    py -3 scratchpad/repro8.py   # the S09 / S15 / S16 discriminators

The discriminator run is the one that separates "defect" from "wrong
scenario", and it is reproduced here in full:

    S09 as written                         -> interested       0.60   ['this is interesting']
    S09 + question mark                    -> interested       0.60   ['this is interesting']
    S09 without 'this is interesting'      -> unknown          0.00   []
    S09 realistic positive                 -> positive         0.75   ['sounds good']
    S15 as written                         -> unknown          0.00   []
    S15 + question mark                    -> question         0.75   [the whole clause]
    S15 'how does this work'               -> question         0.75   ['does this work', 'how does this work']
    S16 as written                         -> unknown          0.00   []
    S16 'we already use'                   -> objection        0.75   ['we already use']
    S16 'not a priority'                   -> objection        0.75   ['not a priority right now']
    S16 budget shape                       -> objection        0.75   ['too expensive']

S15 flips on one character, so the scenario is wrong. S09 does not flip on
anything the scenario could have written differently without writing a
different reply, so the system is wrong. S16 flips only if the sentence is
replaced by a different objection family, which is exactly the question
nobody has answered.

No provider write, no Slack post, no write to production `work/`, and no
suite run - pid 149644 holds it. Individual modules only.

---

# Odluke za operatera

Three decisions, and only these three. Each is one question with its options
and a recommendation. Nothing below is a defect and nothing below should be
coded until it is answered - the system has no rule, and inventing one here
would be this report deciding something that is yours.

---

### Q1 - Is "a question about the offer" the broad limb or the narrow one?

Your definition of a positive, 2026-10-03, names three limbs: an explicit
statement of interest, a request to talk, and a question about the offer. The
third limb has no boundary, and your own review file already measured what the
boundary is worth: on the broad reading 10 of 26 flagged replies are
positives, on the narrow reading 7.

Scenario S15 is the case. Its reply is *"how would this work with the tooling
we already run"* - a question about how the thing works, not about what it is
or what it costs.

| option | what counts | consequence |
|---|---|---|
| **A - broad** | any question about the offer, including how it works and how it fits | S15 counts; the positive rate rises; more replies wake a person |
| **B - narrow** | only what the offer IS or what it COSTS - your own wording for the three rows you kept | S15 does not count; the positive rate is 7 of 26 rather than 10 of 26, and is a harder number |
| **C - split the two jobs** | the broad set reaches a person; only the narrow set counts toward the positive METRIC | reachability and measurement stop having to agree |

**Recommendation: C.** The two things this limb is doing are different jobs.
"Should a human see this?" should be generous - the cost of a false positive
is one person reading one email. "Is this a positive for the client's
number?" should be strict, because that number is reported outward and 38.5%
precision is already the finding. C gives each its own answer and costs one
extra field. If you want one answer rather than two, take B: an inflated
positive rate is the more expensive error.

---

### Q2 - What class is a past-failure objection?

`OBJECTION_PATTERNS` today covers budget, time and resources, team size,
"we already use X", and "not a priority right now" - all verified. It does
not cover *"we tried something like this before and it did not work for us"*
(scenario S16), which lands as `unknown` and therefore reaches nobody.

| option | class | consequence |
|---|---|---|
| **A** | `objection` | routes with the other objections. Note that `objection` maps to `unknown` in `accountpolicy` and TASK-1004 deliberately leaves it there, so on its own this changes the label and nothing else - it is worth doing only together with an answer to Q3's shape |
| **B** | `negative` | treated as a refusal: the sequence stops and the lead is effectively closed |
| **C** | leave it `unknown` | nothing changes; the reply reaches nobody, as 278 of 899 real replies already do |

**Recommendation: A, and only alongside a decision on what an objection
actually does.** A past failure is a stated barrier, not a refusal - the
person is telling you why, which is the opposite of closing the door, and B
would blocklist somebody who is still talking. But A on its own is cosmetic
while `objection` resolves to `unknown`, so A is worth doing only if an
objection is going to reach somebody.

---

### Q3 - Does an EA redirect pause the cadence while a person looks at it?

You ruled that `assistant_redirect` maps to `unknown` - "routed to internal
review only" - and that ruling is recorded in `src/accountpolicy.py` and is
being honoured. What was never decided is what happens to the cadence in the
meantime. Because `unknown` is the one outcome with no policy entry at all,
the answer today is: nothing. The next step goes out on schedule to somebody
who has just written "I look after the diary, send anything for her through
me" (scenario S17).

| option | behaviour | consequence |
|---|---|---|
| **A - pause the contact** | `assistant_redirect` holds that contact until a person acts | no further automated mail to the gatekeeper; if nobody acts the lead stalls silently, and a hold that never clears is a defect you can only see as a duration |
| **B - carry on** | today's behaviour, made explicit | the cadence keeps writing to the EA; it reads as an agency that does not read its own inbox |
| **C - pause and raise it** | hold the contact AND raise a notification, the shape TASK-1004 builds for `needs_a_person` | the hold always has an actor; costs one more item in your feed per EA redirect, which is 3 in 899 in the real corpus |

**Recommendation: C.** It is the only option where the hold cannot become
invisible, the volume is 3 in 899 so it will not flood the feed, and
TASK-1004 has already built the mechanism - this is wiring
`assistant_redirect` into a route that exists rather than inventing one. It
does not touch your ruling: the outcome stays off `referral` and off
`positive`, and no automation answers the EA.

---

## Nothing else here is for you

The other 13 field-level rows need no decision from you. Seven are defects
with a reproduction and a task - TASK-1010, TASK-1011, and TASK-1004, which
is already written and at REVIEW - and six are scenarios that assert the
wrong thing and will be corrected in the catalogue and in the YAML.
