# The last step's subject is exempt from finality — fixed, and why that is not a loosening

**Branch `task-copylint-last-subject-exempt`, based on `origin/master` `37c12335`.
Provider writes 0. No campaign touched. `sending.live` untouched.**

Closes the defect filed as
`docs/FINDING-THE-LAST-SUBJECT-IS-NOT-EXEMPT-FROM-FINALITY.md` on
`task400-rework3-rebased`, which named what a fix must do and four things it
must not. All four holds are asserted, not claimed — see ITEMS below.

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

A short breakup subject is precisely what `FINALITY_RE` is built to match.
`copylint.check_batch`'s verdict on generated copy is read by nothing on the
campaign path on master, so the false positive is invisible. **`TASK-400` makes
that verdict load-bearing**, and from the moment it merges a correct lead is
regenerated `MAX_WRITER_ATTEMPTS` times and then HELD — so the copy path could
not produce a lead and `TASK-425` could not run.

`generate_campaign` (post-`TASK-400`) hands the lint subjects `A, A, B, B, C`
for `em1..em5`, C being that breakup subject. That exact shape is the item-8
fixture.

## ITEMS 1–8, EACH NAMED

`tests/test_only_the_last_subject_may_claim_finality.py`, **16 tests, 16 pass.**

    1  test_finality_in_the_last_subject_is_accepted              the fix
    2  test_finality_in_an_earlier_subject_is_still_refused       steps 1-4
    3  test_finality_in_an_earlier_body_is_still_refused          steps 1-4
    4  test_finality_in_a_linkedin_message_is_still_refused
    5  test_finality_in_a_ps_line_is_still_refused
    6  test_the_last_body_stays_exempt
    8  test_the_breakup_subject_copyprompts_asks_for_passes       5 phrasings

Plus four that exist so none of the above can pass for the wrong reason:

    test_the_control_five_neutral_subjects_are_accepted        not refuse-all
    test_the_control_the_shipped_defect_is_still_refused       not accept-all
    test_that_same_breakup_subject_on_em4_is_refused           item 8's falsifier
    test_a_linkedin_message_is_not_exempted_by_being_last_in_its_dict
    test_it_is_still_a_refusing_rule_and_the_regex_is_untouched

Every assertion also checks that **no other rule fired**, so a refusal cannot be
`step1_without_pack_fact`, `empty_sentence` or `dash` wearing the finality
rule's name.

**THE SPLIT THAT PROVES IT IS A FIX.** The same 16 tests were run against
master's unfixed `src/copylint.py` (sha256 `4d1220eb…`, restored with
`git checkout --` and verified by hash):

    6 FAIL  — and all six are the last subject being refused:
              test_finality_in_the_last_subject_is_accepted
              test_the_breakup_subject_copyprompts_asks_for_passes  (x5 subtests)
    10 PASS — every teeth test, both controls and the falsifier

Items 2 to 6 pass on **both** sides. That is the whole argument, measured: this
branch changes one false positive and nothing else.

## ITEM 7 — THE MUTATION

`subject_list[:-1]` replaced by nothing at all, i.e. **subjects exempted
GENERALLY** instead of only the last — the exact over-fix the brief forbids.
Applied and restored in binary mode, hashes printed on both transitions,
because a patch silently no-opping while the suite reports OK has happened here
and because this tree is CRLF (a text-mode rewrite normalising to LF is not a
restoration even when the diff looks empty).

    clean      697aa989 2dfceed0 558762e2 e6d183a8 08f1af63 1a361bc6 e24e80d0 7ee624
    mutated    a9cbbc03 5533569612de4c9597388cfb75c2769171c87a11aa33dc77fe8bad2c
    restored   697aa989…  byte-identical, CRLF 904 / bare LF 0, `git status` clean

Under the mutation **item 2's test FAILS** — all four of its subtests, steps 1
through 4 — together with item 8's falsifier, 9 failures in total. Nothing else
moved, so the intended tests failed for the intended reason and no other guard
fired first.

## THROUGH THE REAL SEND PATH

`bisonfactory.stage(CID, config=…, live=False)`, the production entrypoint, with
`providers.set_transport` installed so that any provider request RAISES rather
than passing quietly, and with the trap's own firing asserted first. A dry run
now runs the copy lint, so:

    test_a_dry_run_refuses_finality_in_an_earlier_body   item 3, entrypoint
    test_a_dry_run_leaves_the_last_body_exempt           item 6, entrypoint
    test_the_control_a_clean_two_step_sequence_is_projected
    test_the_booby_trap_actually_fires

**What that path CANNOT reach, stated rather than glossed over:**
`bisonfactory._copylint_batch` hands the lint `{"body": …}` per step and no
`subject`, `ps` or `linkedin` key at all, so the subject, P.S. and LinkedIn
surfaces of this rule are unreachable on the EmailBison staging path today. The
2026-09-27/28 handoff already records this (*"`_copylint_batch` builds steps
with no subject key, so this defect was unreachable there"*). It is NOT changed
here — `src/bisonfactory.py` belongs to `TASK-447` — which is also why the fix
is invisible in production until `TASK-400`'s `generate_campaign` path lands.
The subject surface is exercised through `copylint.check_batch` itself, the
function `bisonfactory`, `generate_campaign` and `packfacts` all call.

## PROTECTED PROOFS — ALL PASS, COUNTS AS SPECIFIED

    test_a_dry_run_runs_the_sequence_gate                              8/8
    test_a_client_supplied_figure_licenses_no_claim_in_either_gate    18/18
    test_a_client_csv_fact_cannot_license_a_claim                      9/9
    test_compliance_gate                                             34/34
    test_one_plan_decides_both_providers                             11/11
    test_lead_writes_respect_the_killswitch                            5/5
    test_staging_hands_the_sequence_gate_its_inputs                   12/12
    test_sending_live_off_blocks_only_our_new_writes                   6/6
    test_the_copy_lint_refuses_the_real_send_path                     10/10

And the three modules with a standing opinion about this rule, none of them
edited: `test_a_step_may_not_claim_to_be_the_last_one` 7/7, `test_copylint`
45/45, `test_the_sequence_gate_catches_what_copylint_cannot` 19/19.

## SUITE — 128-NAME BASELINE, DIFFED BY NAME. BASELINE NOT REGENERATED.

`py -3 -m unittest discover -s tests -v`, the command
`docs/state/SUITE-BASELINE-2026-09-26.txt` names for its own regeneration.
Ran 13472 tests in 2104s. Both sides normalised with
`normalise_test_name` from `scripts/glm_verify_branch.py`.

    baseline names  128
    measured names  130
    NEW              9        4 known-master + 5 environment artifacts
    CLEARED          7

**4 of the 9 are the names the brief records as master's, not this branch's:**
`test_an_offer_cannot_be_invented` (the operator approved Offers A and B),
two `test_fixture_hygiene`, one `test_the_cadence_reacts_to_what_the_prospect_did`.

**The other 5 are a HARNESS artifact and are proved to be one, not argued to
be.** Four `setUpClass` errors in `test_provision_survives_its_own_firewall`
and `test_waterfall_order.TestXaiOffByDefault.test_xai_has_no_caller_in_src`
all die inside `subprocess.run` with `FileNotFoundError [WinError 2]`: they
shell out to `bash` and to `grep`, and the suite was run from PowerShell, where
neither is on PATH. Re-run from Git Bash where both are: **27 tests, OK
(1 skip).** Nothing in either module touches `copylint`. Worth recording on its
own — this is a third way two measurements of this suite disagree without any
code changing, alongside the `tests.offline`-versus-per-module split the
2026-09-27 handoff documents.

**No new failure is attributable to this branch. No copylint, finality or
subject name appears in the baseline at all**, so the answer to "did items 2–6
turn a currently-failing name green" is **none: the finality rule's tests were
green on master and are green here.** The 7 cleared names (five in
`test_a_resume_leaves_a_ledger_row`, `test_nothing_writes_to_a_provider`,
`test_secrets`) are the handoff's own "7 new and 7 cleared" against a 09-26
reference point, pre-existing on master and not this change — the baseline's
header explicitly flags the `test_a_resume_leaves_a_ledger_row` group as
pre-existing red.

**The baseline file was NOT edited and NOT regenerated.**

## WHAT THIS DOES NOT FIX

- `src/bisonfactory.py`'s `_copylint_batch` still passes no subject, no P.S.
  and no LinkedIn text, so on the EmailBison staging path this rule sees email
  bodies only. `TASK-447` owns that file.
- `generate_campaign` still builds `em2`/`em4` with `"subject": ""` on master,
  which trips `empty_sentence` on the concatenated render. That is `TASK-400`'s
  defect and its rework fixes it by threading the reply subject through; it is
  deliberately untouched here.
