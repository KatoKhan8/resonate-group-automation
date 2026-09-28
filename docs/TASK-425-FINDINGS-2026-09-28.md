# TASK-425 — what the one-account dry run found

**Everything here was MEASURED during the run, on 2026-09-28, against the real
production entrypoints with zero provider writes. Nothing is inferred from a
refusal message: where a refusal is quoted, the reason was reproduced.**

The artifact itself is `docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md`, generated
by `scripts/task425_one_account_dry_run.py`. This file carries the findings that
are ABOUT THE SYSTEM rather than about the run, so they can become tasks without
anybody having to re-read a 2,000 line artifact.

Each entry says whether it was FIXED in this change, REPORTED and left alone, or
BLOCKS something. A finding that is reported and not fixed says why not.

---

## 1. FIXED — the strategy path could not read its own model

`campaignstrategy._call_model` did a bare `json.loads` on the model answer.

    LLM_MODEL=openai/gpt-4.1-mini returns ```json ... ```
    -> json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

Raised out of `_decide_strategy`, which `generate()` calls OUTSIDE the
per-contact `try`, so **one fenced answer ended the whole run before a single
contact was processed**, and the exception named a JSON column rather than a
model that fences.

`llm.parse` has tolerated a fenced block all along and so has
`generate_campaign._parse_json`; the strategy path was the only reader that did
not. It now uses `llm.parse`. Nothing is loosened: prose is still refused and a
non-object answer is still refused.

**Why it had never been seen:** `generate_campaign.generate` has never had a
production caller on master until `TASK-400`, and every test passes a
`ScriptedModel` whose answers are already bare JSON.

## 2. FIXED — the offer's approved ladder was recorded and read by nothing

`config/clients/productive-offers.yaml`, `messaging_rules`:

    enforced_by: sequencegate checks step_objectives; copylint traces every claim
    enforcement_status: DATA_ONLY_NOT_YET_ENFORCED

Two adjacent lines, one claiming enforcement and one admitting there is none.
`sequencegate.check` did not read `step_objectives`, `campaignstrategy` DROPPED
the field when it projected offers into the strategy prompt, and the writer was
never told the ladder existed. So the ladder was a paragraph of configuration.

Now: `sequencegate.check` takes `offer` and `messaging_rules` and adds
`step_objectives`, `ai_one_per_message` and `ai_is_supporting`;
`_offers_for_segment` carries the objectives, the licensed AI capability names
and the mechanism into the strategy prompt; `generate_campaign` puts the
objectives into the writer's plan; and `bisonfactory._refuse_sequence_gate` asks
`generate_campaign._select_offers` which offer the contact's persona selects.

Proof: `tests/test_the_offer_ladder_is_enforced_as_step_objectives.py`, 15/15,
with the ladder mutated inert in source — **10 of the 15 went red and the 5
controls stayed green**, source restored and verified byte-identical.

## 3. FIXED — `no_repetition` refused a correctly threaded sequence

`sequencegate.no_repetition`'s own message is *"two of the three THREAD subjects
are the same"*. It was written for the writer's `{A, B, C}`: one entry per
thread. `bisonfactory._refuse_sequence_gate` handed it one entry per **STEP**.

`EMAILBISON-COPY-REQUIREMENTS.md` requires that "a sequence is one conversation,
same-thread follow-ups use the provider's `thread_reply` rather than a new
subject every step", so `em2` legitimately carries `em1`'s subject. Five steps
carrying three thread subjects therefore read to the check as three duplicates
and **REFUSED the push on copy that had passed every other gate.**

Fixed at the call site, which is where the fault was: only a step the projection
marks as NOT a `thread_reply` contributes a subject. The check keeps its whole
power — a client whose cadence really does open three threads with two identical
subjects is still refused — and stops refusing one conversation for being one.

Same class as the defect `TASK-426` fixed here: a check handed the wrong inputs
cannot answer the question it was written for.

## 4. REPORTED — three answers to "how many threads does this cadence have"

    generate._PLAN_SUBJECT_OF              em1,em2 -> A · em3,em4 -> B · em5 -> C
                                           => THREE threads
    productive.yaml thread_reply_pattern   [false, true, true, true, true]
                                           => ONE thread
    the EmailBison projection              every step renders {SUBJECT_1}
                                           => ONE subject

The writer is asked for three subjects, two of which reach no prospect. NOT
fixed: which is canonical is a copy-strategy decision, not a wiring one, and
`_PLAN_SUBJECT_OF` belongs to the path `TASK-364`/`TASK-400` own.

## 5. REPORTED — every LinkedIn step is linted as a 300 character connection request

`lint.is_connection_note(step)` is `step.get("requires") != "connection_accepted"`.

    cadencelibrary.PRODUCTIVE_LI_HEAVY_V1   li2..li5 declare requires="connected"
    lint.CONNECTION_ACCEPTED                 "connection_accepted"
    generate._candidate_steps                writes NO `requires` key at all

    lint.NOTE_MAX_CHARS      300   <- what every LinkedIn step gets
    lint.MESSAGE_MAX_CHARS  1900   <- what a message is supposed to get

So a 420 character `msg1` refused the whole contact on `note_too_long`, three
attempts running, **and took the five emails down with it** because
`generate._step_refusals` refuses the SET rather than the step. The library's own
comment says the decision is made "from `requires` rather than from a day number
[so it] keeps it true when the cadence is reconfigured" — and the cadence uses a
different word for the same state.

NOT fixed: correcting it makes the lint LESS strict on li2..li5, which is a
change to what may ship and therefore not a wiring decision. The writer prompt
now targets 280 characters, which is what actually applies. Same class as
`sequencegate.BLOCKING_QUALIFICATIONS` needing `INSUFFICIENT_DATA` rather than
`INSUFFICIENT`: a check written to stop a value that does not match the value
that arrives.

## 6. REPORTED — the sequence gate's verdict is not read where the copy is written

`generate_campaign._process_contact` computes `result["sequence_gate"]` and the
retry loop breaks on `copylint` alone. A sequence the gate REFUSED is returned
exactly like one it passed, written into the record by
`generate._adapt_plan_to_cadence`, and stopped two gates later by
`bisonfactory._refuse_sequence_gate`.

Measured twice:

- the first real run of this entrypoint had `em5` refused for
  `hypothesis_not_asserted` ("I know your schedule is busy") and reported the
  contact as written, one attempt, no rejections;
- this suite's own canonical GOOD draft (`HARBOURLINE_SEQUENCES` in
  `tests/test_generate.py`) is refused by `channels_complement` on `msg1` and
  `msg2` — *"is em5 in shorter form"*, *"is em1 in shorter form"* — and is stored
  anyway.

NOT fixed by folding the gate's failures into that list, because **`offers.py` is
single-tenant**: `_offers_path()` resolves `productive-offers.yaml` whatever
client is generating, so that would make Productive's approved ladder refuse copy
for a client that never approved it. That is a decision about licensed claims.

The `validate` seam already lets a caller demand it for one client, and
`TASK-425`'s harness passes the gate's failures through it — which is how the
ladder was enforced where the copy is written, for the one client whose ladder it
is.

## 7. REPORTED — `offers.py` is single-tenant

`offers._offers_path()` returns `<clients dir>/productive-offers.yaml`
unconditionally. So `generate_campaign._select_offers` and `_check_offers` gate
EVERY client on Productive's library, and a second client's run would be refused
by, or licensed by, offers it has nothing to do with. Pre-existing and invisible
while one client exists.

## 8. REPORTED — the approved ladder and `claims.check` pull against each other

`claims.check` refuses a sentence that BOTH opens one of eighteen second-person
markers (`you are`, `you're`, `you have`, `you run`, `you track`, `your team is`,
…) AND carries an operational word, unless a STORED fact about that company
contains the word:

    "You need to see profitability while you can still do something about it."
    -> 'profitability' is asserted about them and nothing stored supports it

**The step objectives are built from exactly those words.** Rung 1 of Offer A is
"margin visibility"; rung 3 is "resource decisions that move margin". Telling the
writer to use the objective's own words therefore walks it straight into this
refusal. Measured: `capacity`, `profitability` and `budget` each held a whole
contact.

The two rules do fit together, one way only, and the writer prompt now says so:
put the objective's words in a QUESTION, behind a hedge (`if`, `whether`), or in
a sentence about what the product does. Nothing was loosened. Recorded because it
is a real constraint on what this copy engine can say, and because a reader of
the ladder would not expect it.

## 9. REPORTED — an invented figure passes both claim gates when the sentence is impersonal

`copylint.untraceable` only examines a sentence that matches `COMPANY_CLAIM`
(you / your / they / their / announced / …). A figure in an impersonal sentence is
never checked. Observed in real generated copy before the prompt was tightened:

    "A 40% margin project can quietly slide to 25% when scope creep hits."
    "...can save 10-15% margin per project."

Neither names the prospect, so neither is examined, and `claims.check` did not
object either. **Both numbers were invented by the model.** The writer prompt now
forbids it explicitly, but a prompt is a request and this is not a gate.

**This is the finding with the most direct route to a real prospect** and it is
recommended as the next task after the operator's review.

## 10. REPORTED — `report["sequencegate"]` has a SECOND way to lie

The brief's trap 1 is that the key is ABSENT for a zero-lead campaign, so
`report.get("sequencegate", {}).get("passed")` is `None`.

Measured here: the key can be **PRESENT with `passed: True` and `leads: []`**.
`_refuse_sequence_gate` writes `{"passed": not refused, "leads": checked}`, and
when no lead carries approved copy `checked` is empty and `refused` is empty too,
so `not refused` is `True`. A gate asked about NOBODY reports exactly what a gate
that passed EVERYBODY reports.

The artifact therefore asserts the key is present AND counts the leads, and calls
the empty case VACUOUS rather than PASSED.

## 11. REPORTED — the writer emits four LinkedIn artifacts against a five step cadence

`copystages.WRITER_SYSTEM` emits `connect`, `msg1`, `msg2`, `msg3` at days
1/3/8/14. The canonical LinkedIn cadence is `li1`..`li5` at days 1/3/6/10/15, and
`generate._candidate_steps` maps the writer's four onto the first four by ordinal
and breaks. So `li5` never has generated copy, and
`heyreachfactory.stage(live=False)` refuses:

    approved LinkedIn copy is missing for: contact '...', step 'li5'
    -> role 'connected_4'

Both halves of launch blocker 7 in one place: four artifacts against five steps,
and 1/3/8/14 against 1/3/6/10/15.

## 12. REPORTED — the copy path is marginal on this account, and the number is in the artifact

Identical input, repeated invocations of `generate.run(live=True)`. Each
invocation already regenerates three times internally with the reason fed back.
Some invocations produced a full ten-step sequence passing every gate; others held
on one sentence — a dash, a second-person operational assertion, an AI capability
at the wrong rung, a body under forty words.

The artifact records how many invocations each matrix run needed and what held
each one. **This is the honest statement of how close the copy engine is to
working, and it is not "it works".**

Six gaps between the writer's prompt and a gate it is judged by were each found
as a hold and closed by telling the writer the rule: plain ASCII punctuation
(`lint` refuses both curly single quotes and the prompt never mentioned them),
the objective's own words, no LinkedIn message restating an email, 280 characters
rather than 600, at least 45 words per body, and no two emails sharing half their
content words.

## 13. REPORTED — `sendable: True` on a contact is read by nothing that decides

`verification.is_sendable` recomputes from the evidence list every time, on
purpose, so nothing that can write a state string can make an address sendable.
Productive's policy names `deliverable` primary, `reoon` secondary and requires
TWO confirmations.

A fixture contact with `sendable: True` and `verified: True` and no evidence is
NOT sendable, so `generate._candidate_steps` built **no email candidates at all**:
the run stored four LinkedIn notes, zero emails, and **reported no error.** The
email half of the deliverable was simply missing and nothing said why.

Not a defect — the gate is right — but a trap for anybody building a fixture or
reading a run report, and the silence is the dangerous part.

## 14. REPORTED — "spend 0" means "no PRICED call", not "no call"

`config/model-prices.yaml` carries `claude-sonnet-4-20250514` and not
`anthropic/claude-sonnet-4`, which is the id an OpenRouter-shaped endpoint is
asked for. So every completion this run made was ledgered with
`expected_cost: 0`. That is the file's own design — its header says "a model
absent from this file still gets a ledger row … so the call is VISIBLE and
visibly unpriced. A missing row and a free call are indistinguishable in the
ledger, and that is the failure `TASK-323` fixes" — and it is working. But
`expected_total: 0` in a report reads as "nothing was spent" unless something
says otherwise, so the artifact now prints the ledger row count, whether the
model id is priced, and which calls went in unpriced.

Real money WAS spent with the operator's OpenRouter credential. The number of
calls is in the artifact; the cost is not, because nothing in this repository
knows the price of that model id.

---

## ONE DISCLOSURE ABOUT PRODUCTION STATE

A throwaway probe run early in this task (`work/probe_model.py`, one model call to
confirm an endpoint was reachable) did NOT isolate its store, so it appended ONE
row to the production spend ledger, `work/spend-ledger.jsonl`:

    client "unattributed" · provider "openrouter" · call "complete:openai/gpt-4.1-mini"
    · expected_cost 0 · 2026-09-28T06:45:05Z

It is an accurate record of a call that really happened and it corrupts nothing.
It is disclosed because `store.refuse_production_write` only fires when
`unittest` is in `sys.modules`, so a plain script gets no such fence — which is
worth knowing before anybody writes the next probe. The RUN itself went through
`store.use_directory`, and every ledger row it wrote is in its own temporary
directory.

---

## WHAT THIS RUN DID NOT MEASURE

- **The killswitch.** `sending.live` is `off` for `productive` and a dry run
  never reads it: `bisonfactory.stage` returns above the workspace read. This run
  is NOT evidence that the killswitch works. `tests/test_sending_live_off_blocks_
  only_our_new_writes.py` is.
- **`heyreachfactory.ensure_leads`.** Its dry run is NOT network-free: the
  killswitch, the tenant check, the membership readback and the seat lookup all
  reach a provider before it returns. Only `stage(live=False)` is read-only
  local, and that is the only LinkedIn path this run drove.
- **`copylint` on LinkedIn copy on the staging path.** `bisonfactory.
  _copylint_batch` builds leads with email bodies only, and `heyreachfactory` has
  no `copylint` gate at all. The LinkedIn copy in this artifact went through
  `lint`, `claims` and the repetition gate, and NOT through `copylint`.
- **`sequencegate` on LinkedIn copy on the staging path.** `_refuse_sequence_gate`
  passes `emails` and `subjects` only, so `channels_complement` never runs there.
  It DOES run on the generation path, which is where it refused `msg1`.
- **A real signature.** None exists to measure. See the artifact's criterion 2.
- **Ten accounts.** Out of scope by the operator's explicit instruction.
