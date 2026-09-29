PRIORITY: P0
SIZE: S
DEPENDS: TASK-916

# TASK-917 — an outcome claim needs an OBJECT

**Operator, Zvonimir, 2026-09-29.** TASK-916 (`qwen-worker-10-r25` @
`bef663de`) is **very close** and adversarially verified **BLOCKED** on two
counterexamples. Both reduce to ONE missing piece.

**What TASK-916 got RIGHT — preserve all of it.** Removing bare `see` from
the outcome verbs, the `(?<!\byour\s)` second-person exclusion, the
comparative branch, the benchmark-overlap rule. Independently measured on
that branch: the 23-item matrix **PASSES**, a 16-item held-out set **PASSES**,
and a 12-item overblocking probe **PASSES** — including every regression
TASK-916 was written to fix. **Do not undo any of it.**

## THE TWO COUNTEREXAMPLES

Measured through `generate._step_refusals` on BOTH channels:

**1. AN ESCAPE — an unsupported customer outcome ships:**

    ALLOWED   clients consistently see faster reporting cycles
    ALLOWED   clients see faster turnaround

`_COMPARATIVE_OUTCOME_RE` requires the complement to come from a CLOSED
metric list. `reporting cycles` and `turnaround` are not in it, so no branch
fires. The list is too narrow for the client's actual outcome vocabulary.

**2. AN OVERBLOCK — legitimate copy is refused:**

    REFUSED   agencies we speak with raise this constantly
    REFUSED   clients raise this constantly

`_CUSTOMER_OUTCOME_RE` fires on **subject + verb alone**, with no
requirement that an outcome be named. `raise` here means "bring up", not
"increase" — matched only because `rais` is an achievement stem. Compare
`customers mention this often`, which correctly does not fire only because
`mention` happens not to be in the stem list.

## THE FIX — ONE IDEA, BOTH DEFECTS

**An outcome claim needs an object.** "Our customers improved" is not a
claim about anything until it names WHAT improved.

- **Require an OUTCOME COMPLEMENT in the achievement branch.** A customer
  subject plus an achievement verb fires only when a business-outcome noun
  appears within the window (either side, so the reversed order
  "costs were reduced for our clients" still fires). This kills defect 2
  with no effect on any passing assertion — every one of them names a metric.
- **Widen the outcome vocabulary to the client's real domain**, and share
  ONE vocabulary between the achievement branch and the comparative branch.
  That kills defect 1. At minimum add:

      turnaround, reporting cycle(s), month-end close, close, capacity,
      throughput, productivity, billable hours, write-off(s), rework,
      delays, backlog, cash flow, forecasting, admin, admin time,
      resource allocation, project margin(s), utilisation

  keeping everything already there (margin, cost, time, revenue,
  profitability, utilisation, overhead, hours, allocation, efficiency,
  growth, spend, output, performance).

One vocabulary, two branches. **Do not add a third regex family.**

## Acceptance

1. **BOTH COUNTEREXAMPLES FIXED:**

       REFUSE   clients consistently see faster reporting cycles
       REFUSE   clients see faster turnaround
       allow    agencies we speak with raise this constantly
       allow    clients raise this constantly

2. **NOTHING REGRESSES.** Every assertion below still REFUSES on both
   channels, and is still RELEASED when evidence is licensed:

       our clients improve project margins          (+ past/progressive/
                                                     perfect/modal/habitual)
       customers reduce costs / save time / increase revenue
       customers increase profitability
       clients improve resource allocation
       typical clients see better margins
       a typical client improves margins
       firms see higher profitability
       clients have seen better margins
       our customers are seeing lower overhead
       the average customer sees stronger profitability
       clients we work with have cut reporting time
       studios typically raise utilisation
       firms in your space have increased margins with us
       costs were reduced for our clients
       nine in ten clients lower their admin hours
       agencies using Productive cut admin time
       teams that adopt it save hours each week
       most clients improve utilisation within a quarter
       we help clients improve project margins
       clients will improve margins / clients would reduce costs

3. **NOTHING OVERBLOCKS.** Every sentence below is NOT refused by this rule
   and is EVIDENCE-INSENSITIVE:

       finance teams see budget against actuals in one place
       your teams can see margin per project while work runs
       teams see where hours are going each week
       Productive gives teams one view of utilisation
       Productive puts margin and utilisation on one screen
       the tool shows teams where hours are going
       saw your team's post about the new Dallas office
       noticed your agency picked up three retail accounts
       how do your teams track margin today?
       do your teams cut the month-end close manually?
       do your teams see margin before a project closes?
       could your firm cut reporting time in half?
       would your team save time with one view of this?
       we work with agencies that see the same problem
       agencies we speak with raise this constantly
       most teams track this in spreadsheets
       your clients expect faster turnaround
       Productive provides real-time project margin visibility.
       Would improving margin visibility be useful?
       Are you trying to reduce the time spent reconciling project data?

4. **EVIDENCE-SENSITIVITY IS THE DISCRIMINATOR.** Every refusal in 1 and 2
   disappears when evidence is licensed; every sentence in 3 behaves
   identically with and without it. Assert this explicitly — it is what
   separates a customer-outcome rule from a word ban.
5. CLIENT_SUPPLIED suites green and **UNEDITED** (byte-identical to master).
6. TASK-913 chain green; `li5` survives; one authority.
7. Part B observability decision-neutral; `lint.sendable` and the
   verification policy unchanged — assert it.
8. **MUTATION:** neuter your rule in-memory; acceptances 1 and 2 go RED.
   Restore, verify byte-identical by sha256. **CRLF** files. **Do not commit
   mutation code.**
9. `test_generate`: `Ran 56`, `failures=2`, `errors=1`. Unchanged.

### ACCEPTANCE COMMANDS

    py -3 -m unittest tests.test_task917_an_outcome_needs_an_object
    py -3 -m unittest tests.test_task916_customer_outcome_negative_controls
    py -3 -m unittest tests.test_task915_customer_outcome_semantic_class
    py -3 -m unittest tests.test_task914_customer_outcome_claims
    py -3 -m unittest tests.test_task913_writer_contract_five_plus_five
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_lint
    py -3 -m unittest tests.test_linkedin_lint
    py -3 -m unittest tests.test_a_linkedin_note_is_claim_checked_too
    py -3 -m unittest tests.test_a_case_study_claim_must_appear_on_the_page
    py -3 -m unittest tests.test_a_cost_claim_names_its_evidence
    py -3 -m unittest tests.test_heyreachfactory
    py -3 -m unittest tests.test_generate

**Read exit codes OFF THE PROCESS, never through a pipe.**

## PRE-EXISTING — do NOT fix

    test_generate                                  Ran 56, failures=2, errors=1
    test_only_the_last_subject_may_claim_finality  Ran 19, failures=3

Red identically on master and every branch in this chain. **If either
signature changes at all, STOP and report it.**

## Files

`src/claims.py` — the detector only. Plus
`tests/test_task917_an_outcome_needs_an_object.py`, which you write. Earlier
TASK-914/915/916 suites may be EXTENDED; **no existing assertion may be
weakened or deleted.**

**Do NOT touch** `src/verification.py`, `src/lint.py`, `src/offers.py`,
`src/generate.py`, `src/secondbrain.py`, `src/packfacts.py`,
`src/copystages.py`, `src/cadencelibrary.py`, `src/sequenceplan.py`,
`src/generate_campaign.py`, `src/skills/*`.

## RULES THAT OUTRANK FINISHING

- **YOU START ON `master`. YOUR FIRST COMMAND IS:**

      git merge --no-edit origin/qwen-worker-10-r25

  That branch (`bef663de`) carries TASK-913, 914, 915 and 916. Verify before
  starting — both must print `True`:

      py -3 -c "from src import claims; print(claims.customer_outcome_claim('clients improve margins') is not None)"
      py -3 -c "from src import claims; print(claims.customer_outcome_claim('saw your team post about Dallas') is None)"

  If either prints otherwise, STOP.
- **A COMPLEMENT REQUIREMENT CAN SILENTLY UN-REFUSE.** Acceptance 2 lists 20+
  assertions precisely because narrowing the achievement branch is the easy
  way to drop them. Run acceptance 2 before you claim done.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **PROVIDER WRITES = 0.** `sending.live` false. Production `work/` READ-ONLY.
- Suite logs OUTSIDE the repository; a suite with no `Ran N tests` line is an
  absent measurement.
- **Commit every file you touch.** Push to your own branch, verify the remote
  with `git rev-parse`. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your branch head SHA.

**"Our customers improved" is not a claim until it says what improved.**
