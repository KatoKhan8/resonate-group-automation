PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-430 — ICP verdicts for the 786 contacts in 491-500 that never had one

**Operator decision, Zvonimir, 2026-09-27 evening:** "Run the ICP classifier on
their companies now (read-only, Qwen or Groq, cost reported), record verdicts; do
not touch the live campaigns; report how many would not have qualified. Decision
on those campaigns comes to me afterwards."

## WHY THIS EXISTS

TASK-426 made `bisonfactory.stage()` work for the first time since 2026-09-26.
The gates downstream of it became REACHABLE, and the first thing they found was
this: **nine staged campaigns — 491, 492, 493, 494, 495, 496, 497, 498, 500 —
hold 786 sendable contacts whose companies carry no ICP verdict at all**
(`qualify.state_of` returns `not_processed`). The now-working sequence gate
refuses them, which is the CORRECT fail-closed answer under CLAUDE.md's
"Company first: no paid person-level call before a company reaches an explicit
ICP verdict, and rejected, review and unknown all mean zero person credits".

**491-498 have already SENT.** So this is not a hypothetical gate argument: real
emails went to people at companies this system never qualified. That is the
problem to size, and sizing it is this task. It is P0 because the answer changes
what the operator decides about live campaigns.

## THE ONE THING THAT MAKES THIS TASK SAFE

**READ-ONLY with respect to production. Provider writes = 0, provider reads = 0
for the campaigns themselves.**

- **Do not touch the live campaigns.** No pause, no resume, no activation, no
  enrolment, no attachment, no lead edit, no suppression change. The production
  freeze covers every one of those and this task has no grant for any of them.
- The classifier runs on the COMPANIES, from research and facts already stored.
  It writes ICP verdicts onto the records through `src/store.py`, never by
  editing `work/queue.jsonl` directly.
- A verdict is NOT permission to send and NOT an instruction to do anything. It
  is a recorded classification. Nothing downstream may act on it in this task.

## SCOPE

1. **Identify the population exactly, and show your working.** Start from the
   nine campaigns and their sendable contacts; report the count you actually
   find rather than assuming 786, and if it differs, say why (a contact may have
   been suppressed or stopped since the figure was measured). Report per campaign.
2. **Run the ICP classifier on each distinct COMPANY**, not once per contact —
   the account is the unit, and classifying the same company nine times is nine
   times the cost for one answer. De-duplicate by domain first and report both
   numbers (contacts, distinct companies).
3. **Model routing, per `docs/OPERATOR-DIRECTIVES-2026-09-26-MODEL-ROUTING.md`
   and the operator's own words: Qwen or Groq.** Groq is for trivial fast
   classification; Qwen for bulk. Do NOT use a max-reasoning model for this.
   Every model slug comes from `config/model_policy.yaml` and nowhere else.
4. **Report the cost**, and report it from the ledger rather than from an
   estimate. Every paid call goes through `enrich`'s `spend()`, which writes the
   waterfall ledger; a provider call that skips it is invisible to the spend
   audit. If the classifier path is free (local Qwen), say so explicitly and
   state what you verified that against — free is a claim like any other.
5. **Record each verdict** on the company record, with the model that produced
   it, the date, and the evidence it reasoned from. A verdict whose evidence is
   not recorded cannot be re-checked and is worth much less.
6. **Missing evidence is never positive evidence.** A company with too little
   stored research to classify is `UNKNOWN` or `review`, never `qualified` by
   default. `UNKNOWN` is not a failure of this task — it is the honest answer and
   it must be counted separately. Score and confidence are different questions.

## THE DELIVERABLE

`docs/ICP-VERDICTS-491-500-2026-09-27.md`, committed and pushed:

- Per campaign: sendable contacts, distinct companies, and the verdict
  distribution (`qualified` / `rejected` / `review` / `unknown`).
- **The headline the operator asked for: HOW MANY WOULD NOT HAVE QUALIFIED.**
  State it as a count and a percentage, and state plainly how many of those had
  already been SENT to. That second number is the one that matters.
- Cost, from the ledger, per provider, with the unit named (this repo has been
  burned by summing mixed units — cents, credits, microusd and ticks are not
  interchangeable).
- The companies that could not be classified and what evidence they lacked.
- **No prospect PII in the committed file.** `work/` is gitignored because it is
  real companies and real contacts. Report counts, domains only where necessary,
  and never a person's name, email address or phone number. `tests/
  test_fixture_hygiene.py` and `test_campaign_audit.py` enforce this class of
  rule and a leak has already cost a red test this week.

## ACCEPTANCE

1. The deliverable exists, is committed and is pushed, and every number in it
   can be re-derived from a named source.
2. Verdicts are recorded on the records through `store.py`, and re-running the
   task does not duplicate or overwrite a verdict with a different one silently.
3. **Zero provider writes and zero campaign mutations**, demonstrated rather
   than asserted — state what you did to prove nothing was written (the
   `providers.set_transport` seam and `tests/base.py`'s cassette are the tools
   this repo uses to prove exactly that).
4. The cost figure comes from the spend ledger, with its unit named.
5. `UNKNOWN` counted separately from `rejected`. They are different answers.
6. A short Croatian summary is NOT part of this task — the operator gets the
   decision from Claude once the numbers exist.

## WHAT THIS TASK MUST NOT DO

Decide anything about the nine campaigns. The operator said the decision on them
comes to them afterwards. Do not propose pausing them in the deliverable as
though it were agreed, do not suppress anybody, and do not add a task that does.
Produce the numbers; the decision is the operator's.
