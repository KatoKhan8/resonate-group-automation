# The last step's subject is exempt from finality — fixed, and why that is not a loosening

**Branch `task-copylint-last-subject-exempt-rebased`, based on `origin/master`
`f6979300` (the `TASK-400` merge). Provider writes 0. No campaign touched.
`sending.live` untouched. Not merged.**

Closes the defect filed as
`docs/FINDING-THE-LAST-SUBJECT-IS-NOT-EXEMPT-FROM-FINALITY.md`, which is now on
master and which names what a fix must do and four things it must not. All four
holds are asserted, not claimed — see ITEMS below.

**`TASK-400` merged while this was being written**, which matters twice over:
the first base (`37c12335`) was stale by the time the first suite measurement
finished, so everything here was re-measured on `f6979300`; and the
`generate_campaign` path where `copylint`'s verdict is load-bearing is now ON
master, so the end-to-end proof below is against live code rather than a branch.

## THE CHANGE

`src/copylint.py`, `check_batch`, two hunks and one behavioural line:

    -            [str(b) for b in bodies[:-1]] + [subjects, extra]
    +            [str(b) for b in bodies[:-1]] + subject_list[:-1] + [extra]

`subject_list` is the per-step list `subjects` was already built from; the
pooled `subjects` string is unchanged and still feeds `rendered`, which is what
`unrendered_variable`, `empty_sentence`, `untraceable_company_claim`, `dash`,
`buzzword` and the two case-study rules read. **Exactly one rule's surface
moved.** `FINALITY_RE` is byte-identical, `RULES` is byte-identical, no other
offender list is touched, and no assertion anywhere was weakened, widened or
deleted.

## WHY IT IS AN ASYMMETRY BUG AND NOT A WIDENED GATE

`bodies[:-1]` already exempts the LAST BODY, and the comment beside it gives
the reason: there the sentence is TRUE, because it IS the last step. `subjects`
was the five subjects pooled into one blob and went in WHOLE, so the LAST
STEP'S SUBJECT never received the exemption its own body already had.

Three statements already in the file — none of them this change's invention —
say that is wrong:

- the rule is **named** `finality_before_last_step`;
- its declared message is *"a step claims to be the last one while a later step
  still sends"*;
- `FINALITY_RE`'s own docstring ends *"The LAST step is exempt: there, the same
  sentence is true."*

Nothing sends after the last step. Finality language in the last step's subject
is therefore true and appropriate, exactly as it already is in the last step's
body. The fix restores the rule to its own stated definition. It does not widen
it, and the measurement below is what makes that a falsifiable claim rather than
a sentence in a commit message: **an earlier subject, an earlier body, a P.S.
line and every LinkedIn message are still refused, each asserted separately.**

## WHY IT WAS URGENT

`src/copyprompts.py` instructs the writer for the canonical five-email cadence:

    em5  day 21  NEW THREAD, breakup, subject C - short, its own
    subject_breakup C - short, three or four words, no hook, no question

A short breakup subject is precisely what `FINALITY_RE` is built to match. With
`TASK-400` merged, `generate_campaign` acts on the verdict: a refused draft
costs the writer another attempt and after `MAX_WRITER_ATTEMPTS` the copy is
REFUSED, `sequences` and `subjects` are emptied and the contact is held
`copy_refused`. So the copy path could not produce a lead whose em5 subject is
the line the prompt asks for, and `TASK-425` could not run.

`generate_campaign` maps the writer's three subjects onto five steps as
**A, A, B, B, C** — so C is em5's, the last step's. That mapping is why a
per-step exemption is the right shape rather than a special case.

## ITEMS 1–8, EACH NAMED

`tests/test_only_the_last_subject_may_claim_finality.py`, **19 tests, 19 pass.**

    1  test_finality_in_the_last_subject_is_accepted              the fix
    2  test_finality_in_an_earlier_subject_is_still_refused       steps 1-4
    3  test_finality_in_an_earlier_body_is_still_refused          steps 1-4
    4  test_finality_in_a_linkedin_message_is_still_refused
    5  test_finality_in_a_ps_line_is_still_refused
    6  test_the_last_body_stays_exempt
    8  test_the_breakup_subject_copyprompts_asks_for_passes       5 phrasings
       test_a_breakup_subject_on_em5_now_produces_a_draft         end to end

Plus the tests that exist so none of the above can pass for the wrong reason:

    test_the_control_five_neutral_subjects_are_accepted            not refuse-all
    test_the_control_the_shipped_defect_is_still_refused           not accept-all
    test_that_same_breakup_subject_on_em4_is_refused               item 8 falsifier
    test_the_same_line_on_subject_b_still_holds_the_contact        end-to-end falsifier
    test_a_linkedin_message_is_not_exempted_by_being_last_in_its_dict
    test_it_is_still_a_refusing_rule_and_the_regex_is_untouched
    test_the_control_the_fixtures_own_neutral_subject_produces_a_draft
    test_the_control_a_clean_two_step_sequence_is_projected
    test_the_booby_trap_actually_fires

Every subject/body/channel assertion also checks that **no other rule fired**,
so a refusal cannot be `step1_without_pack_fact`, `empty_sentence` or `dash`
wearing the finality rule's name.

**THE SPLIT THAT PROVES IT IS A FIX.** The same 19 tests, run against master's
`src/copylint.py` (sha256 `4d1220eb…`, checked out with
`git checkout origin/master --` and verified by hash):

    7 FAIL  — and all seven are the last subject being refused:
              test_finality_in_the_last_subject_is_accepted
              test_the_breakup_subject_copyprompts_asks_for_passes  (5 subtests)
              test_a_breakup_subject_on_em5_now_produces_a_draft
    12 PASS — every teeth test, every control and both falsifiers

Items 2 to 6 pass on **both** sides. That is the whole argument, measured: this
branch changes one false positive and nothing else.

## END TO END, THROUGH THE PRODUCTION GENERATION ENTRYPOINT

`generate_campaign.generate(client, account, contacts, model=…)` — the path
`TASK-400` just wired — with a stubbed fact-aware writer (no network, no real
model, no provider). The stub is
`tests/test_changing_an_approved_fact_changes_the_output._FactAwareModel`,
subclassed and unmodified, with only the writer's subjects varied:

    subject_breakup = "closing the loop"   (em5, the last step)
        -> a full five-step draft, gate_attempts 1, hold_kind None,
           subjects["C"] == "closing the loop",
           finality_before_last_step offenders []
        -> on master's copylint: hold_kind "copy_refused"

    subject_alt = "closing the loop"       (em3 AND em4, and em5 still sends)
        -> hold_kind "copy_refused", gate_attempts 3 (MAX_WRITER_ATTEMPTS),
           sequences {}, subjects {}, and `held` carries the rule's own
           sentence: "a step claims to be the last one while a later step
           still sends"

That second case is the rule keeping its teeth on the live path, and it is what
stops the first case from being satisfied by a `copylint` that had simply
stopped reading subjects.

## THROUGH THE REAL SEND PATH

`bisonfactory.stage(CID, config=…, live=False)`, with `providers.set_transport`
installed so any provider request RAISES rather than passing quietly, and the
trap's own firing asserted first. A dry run now runs the copy lint, so:

    test_a_dry_run_refuses_finality_in_an_earlier_body   item 3, entrypoint
    test_a_dry_run_leaves_the_last_body_exempt           item 6, entrypoint
    test_the_control_a_clean_two_step_sequence_is_projected
    test_the_booby_trap_actually_fires

**What that path CANNOT reach, stated rather than glossed over:**
`bisonfactory._copylint_batch` hands the lint `{"body": …}` per step and no
`subject`, `ps` or `linkedin` key at all, so the subject, P.S. and LinkedIn
surfaces of this rule are unreachable on the EmailBison staging path. The
2026-09-27/28 handoff already records this (*"`_copylint_batch` builds steps
with no subject key, so this defect was unreachable there"*). It is NOT changed
here — `src/bisonfactory.py` belongs to `TASK-447`.

## PROTECTED PROOFS — ALL PASS, COUNTS AS SPECIFIED

    test_a_dry_run_runs_the_sequence_gate                              8/8
    test_a_client_supplied_figure_licenses_no_claim_in_either_gate    18/18
    test_a_client_csv_fact_cannot_license_a_claim                      9/9
    test_compliance_gate                                             34/34
    test_one_plan_decides_both_providers                              11/11
    test_lead_writes_respect_the_killswitch                            5/5
    test_staging_hands_the_sequence_gate_its_inputs                   12/12
    test_sending_live_off_blocks_only_our_new_writes                   6/6
    test_the_copy_lint_refuses_the_real_send_path                     10/10

And the modules with a standing opinion about this rule or this path, none of
them edited: `test_a_step_may_not_claim_to_be_the_last_one` 7/7,
`test_copylint` 45/45, `test_the_sequence_gate_catches_what_copylint_cannot`
19/19, `test_generate` 51/51,
`test_changing_an_approved_fact_changes_the_output` 3/3.

## SUITE — 128-NAME BASELINE, DIFFED BY NAME. BASELINE NOT REGENERATED.

`py -3 -m unittest discover -s tests -v`, the command
`docs/state/SUITE-BASELINE-2026-09-26.txt` names for its own regeneration.
Both sides normalised with `normalise_test_name` from
`scripts/glm_verify_branch.py`. Measured TWICE on this branch — at `d74d2138`
(13544 tests, 2050s) and again at `06e8acbb` with the three end-to-end tests
included (**13547 tests in 1975s, failures=95 errors=25**). Both runs give the
same name sets:

    baseline names  128
    measured names  120
    NEW               4       every one of them the brief's known-master names
    CLEARED          12

`test_only_the_last_subject_may_claim_finality` appears in the final run with
zero failures and zero errors, as do `test_copylint`,
`test_a_step_may_not_claim_to_be_the_last_one`, `test_generate` and
`test_changing_an_approved_fact_changes_the_output`.

Order dependence checked separately, because a new module that patches
`offers.load`, `secondbrain.for_task` and clears `campaignstrategy`'s cache is
exactly the shape that leaks: the new module was run in ONE process with the
fixture module, `test_generate`, `test_copylint` and
`test_a_step_may_not_claim_to_be_the_last_one`, in both orders — 125 tests, OK
both ways — and in one process with every protected proof, 132 tests, OK.

The four NEW: `test_an_offer_cannot_be_invented` (it asserts NO offer is
approved, and the operator approved Offers A and B), two `test_fixture_hygiene`
(`productive.io` in tracked files, the client's own domain and the approved CTA,
not a PII leak), and one `test_the_cadence_reacts_to_what_the_prospect_did`.
**No new failure is attributable to this branch.**

**A THIRD WAY TWO MEASUREMENTS OF THIS SUITE DISAGREE WITH NO CODE CHANGING.**
An earlier run of the same tree from PowerShell reported **nine** new names
rather than four. The five extra — four `setUpClass` errors in
`test_provision_survives_its_own_firewall` and
`test_waterfall_order.TestXaiOffByDefault.test_xai_has_no_caller_in_src` — all
die inside `subprocess.run` with `FileNotFoundError [WinError 2]`: they shell
out to `bash` and to `grep`, neither of which is on PATH under PowerShell.
Re-run from Git Bash: **27 tests, OK (1 skip).** Neither module touches
`copylint`. This sits alongside the `tests.offline`-versus-per-module split the
2026-09-27 handoff documents: **the harness is part of the measurement, and a
suite number without its shell is not comparable.**

**NO COPYLINT, FINALITY OR SUBJECT NAME APPEARS IN THE BASELINE AT ALL**, so
the answer to "did items 2–6 turn a currently-failing name green" is **none**:
the finality rule's tests were green on master and are green here.

The 12 CLEARED names are master's, not this change's, and that is measured
rather than argued. Each cleared module was run standalone with MASTER's
`copylint` in place and again with the fix, and the verdicts are identical:

    module                              master copylint      with the fix
    test_e2e                            63 tests, 9F+1E      63 tests, 9F+1E
    test_set_regeneration               14 tests, 1F         14 tests, 1F
    test_nothing_writes_to_a_provider    7 tests, OK          7 tests, OK
    test_secrets                        20 tests, 2F         20 tests, 2F
    test_a_resume_leaves_a_ledger_row   15 tests, OK         15 tests, OK

Two of them are already green with master's `copylint`, and the standalone
numbers for the other three do not move when the fix is applied. The clears are
`TASK-400`'s merge, which modified `test_e2e`, `test_set_regeneration`,
`test_audit`, `test_preproduction` and `test_run` by name, plus the earlier
integrations that touched `test_secrets` and `test_nothing_writes_to_a_provider`.
The baseline's own header flags the `test_a_resume_leaves_a_ledger_row` group as
pre-existing red.

**The baseline file was NOT edited and NOT regenerated.**

## THE MUTATION (item 7)

`subject_list[:-1]` replaced by nothing at all — **subjects exempted GENERALLY**
instead of only the last, the exact over-fix the brief forbids. Applied and
restored in binary mode with hashes printed on both transitions, because a patch
silently no-opping while the suite reports OK has happened here, and because
this tree is CRLF: a text-mode rewrite normalising to LF is not a restoration
even when the diff looks empty.

    clean      697aa9899d2fceed0558762e2eb6d183a808f1af631a361bc6e24e80d07ee624
    mutated    a9cbbc035533569612de4c9597388cfb75c2769171c87a11aa33dc77fe8bad2c
    restored   697aa989…   byte-identical, CRLF 904 / bare LF 0, `git status` clean

Under the mutation **item 2's test FAILS** — all four of its subtests, steps 1
through 4 — together with item 8's falsifier: 9 failures, and nothing else
moved. So the intended tests failed for the intended reason and no other guard
fired first. Performed twice, once on each base.

## WHAT THIS DOES NOT FIX

- `src/bisonfactory.py`'s `_copylint_batch` still passes no subject, no P.S.
  and no LinkedIn text, so on the EmailBison staging path this rule sees email
  bodies only. `TASK-447` owns that file.
- `tests/test_changing_an_approved_fact_changes_the_output.py` still pins
  `subject_breakup` to a non-finality phrase and carries a long comment
  explaining that it is a workaround for this defect. The workaround is now
  unnecessary. It was deliberately NOT reverted here: the module is not this
  branch's, the comment is an accurate record of why the fixture is shaped that
  way, and removing a pin is a change to somebody else's falsifiability proof.
  A one-line follow-up for whoever next touches that file.
