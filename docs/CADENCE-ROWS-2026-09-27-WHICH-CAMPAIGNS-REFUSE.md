# Which campaigns refuse, and what the canonical cadence is — 2026-09-27

Measured while wiring TASK-364 rework 2, because the question was asked as
"60 of 64 productive campaigns refuse a gate and which cadence is right".
Both halves are answered from the repository's own evidence. **Nothing was
written to any campaign row, no cadence was changed, and no gate was
widened.**

Authority for every number below: `work/campaigns.jsonl` as it stood at
2026-09-27 22:5xZ, read through `src/campaigns.py` with `CAMPAIGNS` pointed at
the production file. Authority for the canonical cadence:
`docs/OPERATING-MODE.md`, `config/clients/productive.yaml` and
`docs/MERGE-REQUEST-2026-09-25-CADENCE-FIVE-STEPS.md`.

**THIS AGREES WITH `docs/OPERATING-MODE.md` ENTRY 9 AND RECONCILES ITS COUNT.**
That entry was written independently the same night and says 64 rows: 48 with
nothing stored, 12 three-step, 3 five-step, 1 `em1` alone. It counts the
PRODUCTIVE rows. The file holds 67 rows in total - 64 productive, 2 contactout
and 1 demo-client, and those three carry no `cadence_steps` either - which is
the whole of the difference. Both counts are right about the same file. What
this document adds is WHICH campaigns are in which bucket, and what that means
for the twelve, because the entry's "migrate them, or leave them refused" is
not a free choice for all twelve.

## 1. WHAT THE ROWS DECLARE — 67 rows, four shapes

    51   no `cadence_steps` at all                 (48 of them productive)
    12   em1@1, em2@4, em3@8                        (three steps)
     3   em1@1, em2@4, em3@8, em4@12, em5@21        (five steps)
     1   em1@1 only

**The two refusals are different gates and they are not interchangeable.**

The 51 are refused by `bisonfactory._require_declared_cadence`, which is about
the CAMPAIGN: it never declared what it runs, so the sequence it would send
comes from whatever the client config falls back to. That refusal fires on the
dry-run path too.

The 12 + 1 are refused one step later, by the plan: `email_sequence.steps`
declares em1..em5 and those rows' cadences declare em1..em3 (or em1), so the
declared delays cannot be matched to the cadence gaps they claim to reproduce.
Since TASK-364 that refusal is raised by `sequenceplan` and re-raised by
`bisonfactory._derive_bison_sequence` — the same refusal, from the module that
builds the plan.

## 2. WHICH ROWS, AND WHY IT MATTERS THAT THEY ARE THE OLD ONES

Every three-step row is an OLDER provider campaign; every five-step row is a
2026-09-25 one:

    485, 487, 489, 491, 492, 493, 494, 495, 496, 497, 498, 500   three steps
    501                                                          one step
    503, 504, 505                                                five steps

**487, 489 and 493 are the three ACTIVE campaigns that are ours, and all three
are three-step rows.** That is the load-bearing fact. `bison.set_sequence`
APPENDS — there is no replace and no per-step delete, measured 2026-09-13 —
so re-declaring one of those rows as five steps and re-staging it would leave
the provider holding its existing three steps PLUS five more and sending
duplicates to a cohort that has already been mailed. The refusal is protecting
the live estate, not obstructing it.

## 3. THE CANONICAL ANSWER: FIVE EMAILS, DAYS 1 / 4 / 8 / 12 / 21

Three independent statements in the repository agree, and none of them is this
document:

1. `docs/OPERATING-MODE.md`, ARCHITECTURAL INVARIANTS: "Cadence is fixed.
   Five emails, days 1/4/8/12/21 — em1 new/A · em2 reply A · em3 new/B ·
   em4 reply B · em5 new/C — pending §6 reconciliation."
2. `config/clients/productive.yaml` ships five `email_sequence.steps` with
   waits 3/4/4/9/1, which are exactly the gaps of days 1/4/8/12/21, and its
   own comment says rows written before the change "still carry em1/em2/em3
   and are refused by this config".
3. `docs/MERGE-REQUEST-2026-09-25-CADENCE-FIVE-STEPS.md` records how it became
   five: four steps landed 2026-09-24 with rung 3 deliberately empty, and the
   operator approved rung 3 on 2026-09-25, which took that position as `em3`.
   The other keys never moved.

So the three-step rows are pre-2026-09-24 artifacts. **The canonical cadence is
not in doubt; what is in doubt is what those twelve campaigns run**, and that
is a per-campaign operator decision rather than a code change.

## 4. WHAT MUST NOT BE DONE ABOUT IT

The five-step merge request already settled this and its reasoning holds:

> Nothing was written to any row to make it pass. Filling `cadence_steps` in
> for the sixteen would hand them a cadence nobody chose, which is the same
> defect one level down. They are refused until somebody decides what they
> run.

Concretely, and each of these would be a worse system:

- **Do not change the cadence** to em1..em3 to match the old rows. It would
  contradict OPERATING-MODE, the shipped client config and an operator
  approval, and it would shorten a sequence three campaigns were built for.
- **Do not add a fourth cadence.** There are already three named ladders and
  the reconciliation §6 asks for fewer, not more.
- **Do not write `cadence_steps` into a row** so that it passes. A cadence
  nobody chose is the original defect.
- **Do not widen the key check.** It is what stands between a live three-step
  campaign and a five-step append.

## 5. WHAT A DECISION WOULD LOOK LIKE

Per campaign, and only from the operator:

- **A campaign that has sent** (487, 489, 493 and the paused 491-498) keeps its
  three-step row. Its sequence exists at the provider and cannot be replaced;
  a five-step version of that cohort is a NEW provider campaign, not an edit.
- **A campaign that has not sent and is not wanted** is retired rather than
  re-declared.
- **A new cohort** is built five-step from the start, which is what 503/504/505
  already are — those three carry 0 records today and are the shape the
  config declares.

Until that decision, 64 of 67 rows refuse, and every one of those refusals is
a campaign nobody has decided about rather than a bug.

**So "migrate the thirteen" is not one decision.** Per
`docs/state/PROVIDER-CAMPAIGNS.json` (generated 2026-09-26T18:29:43Z, and a day
old is a reason to re-read provider truth before acting): of the twelve
three-step rows, **three are ACTIVE** - 487, 489, 493 - four are PAUSED (491,
492, 494, 496), one is archived (495), two are completed (497, 498) and two
(485, 500) that snapshot does not classify. The nine that are not ACTIVE could
in principle be re-declared; the three that are cannot, because the sequence
they already hold cannot be replaced. A migration script that walked
the thirteen and rewrote `cadence_steps` would look complete and would have
armed exactly those three for a duplicate-sending append the next time
anything staged them. That is the shape of defect this repository keeps
paying for, which is why the list above names them individually.
