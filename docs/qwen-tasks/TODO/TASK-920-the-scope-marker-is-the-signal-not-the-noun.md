PRIORITY: P0
SIZE: XS
DEPENDS: TASK-919

# TASK-920 — the scope marker is the signal, not the noun

**Operator, Zvonimir, 2026-09-29.** TASK-919 (`qwen-worker-8-r28` @
`0c13bdff`) is nearly there. Independently measured: TASK-918's given matrix
**PASS**, held-out round 1 **PASS**, held-out round 2 down from 7
counterexamples to **3**, every negative control clean, B scope clean, and
all B counterexamples fixed. **Change nothing except the one thing below.**

## THE RESIDUAL — THREE ESCAPES, ONE MECHANISM

Unlicensed, and currently ALLOWED on both channels:

    operators in your sector have raised utilisation
    shops of your size have improved margins
    outfits like yours have reduced admin time

The analogy markers already work — but only when the noun is one you listed.
Measured side by side:

    allow   operators in your sector have raised utilisation
    REFUSE  agencies  in your sector have raised utilisation
    allow   shops of your size have improved margins
    REFUSE  firms of your size have improved margins
    allow   outfits like yours have reduced admin time
    REFUSE  teams   like yours have reduced admin time

Identical sentence, identical marker, identical asserted outcome — the only
difference is whether the noun is in the group list. **The group-noun list is
still doing the work.**

## THE FIX

**An explicit analogy/scope marker makes the noun it attaches to an
analogous third party, whatever that noun is.** The markers are already in
your pattern:

    like yours
    in your industry / sector / space / market / position
    of your size

When one of those follows a noun, treat that noun as a third-party reference
without consulting the group list. Keep the group list for the bare cases
("several organisations", "other businesses") that carry no marker.

**Keep the asserted-outcome requirement exactly as it is.** It is what stops
the negative controls firing and it is already correct.

## Acceptance

1. The three sentences above REFUSE on email AND LinkedIn without licensed
   evidence, and are RELEASED when the evidence fixture licenses them.
2. **The outcome requirement is intact** — these must stay ALLOWED, and be
   evidence-insensitive. They carry the same markers and assert no outcome:

       operators in your sector plan capacity weekly
       outfits like yours juggle several clients
       how many agencies in your sector run multi-site work?
       do operators in your sector plan capacity weekly?
       Productive works the same for shops of your size
       we speak with comparable teams every week

3. Everything already passing stays passing: TASK-918's given matrix, both
   earlier held-out rounds, all A and B negative controls, B scope (no leak
   to LinkedIn notes or email bodies).
4. **MUTATION:** neuter the authority in-memory; acceptance 1 goes RED.
   Restore, verify byte-identical by sha256. **CRLF**. No mutation code
   committed.
5. Preserved green: TASK-913/914/915/916/917/918/919 suites, both
   CLIENT_SUPPLIED suites (byte-identical to master), `test_copylint`.
6. `test_generate` unchanged: `Ran 56`, `failures=2`, `errors=1`.

### ACCEPTANCE COMMANDS

    py -3 -m unittest tests.test_task920_scope_marker_is_the_signal
    py -3 -m unittest tests.test_task919_third_party_and_ps_generalisation
    py -3 -m unittest tests.test_task918_third_party_outcomes_and_ps_quality
    py -3 -m unittest tests.test_task917_an_outcome_needs_an_object
    py -3 -m unittest tests.test_task916_customer_outcome_negative_controls
    py -3 -m unittest tests.test_task915_customer_outcome_semantic_class
    py -3 -m unittest tests.test_task914_customer_outcome_claims
    py -3 -m unittest tests.test_task913_writer_contract_five_plus_five
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_lint
    py -3 -m unittest tests.test_generate

**Read exit codes OFF THE PROCESS, never through a pipe.**

## PRE-EXISTING — do NOT fix

    test_generate                                  Ran 56, failures=2, errors=1
    test_only_the_last_subject_may_claim_finality  Ran 19, failures=3

## Files

`src/claims.py` only, plus
`tests/test_task920_scope_marker_is_the_signal.py`. **`src/copylint.py` needs
no change — B is finished.** No existing assertion may be weakened.

**Do NOT touch** `src/verification.py`, `src/lint.py`, `src/offers.py`,
`src/generate.py`, `src/generate_campaign.py`, `src/copylint.py`,
`src/secondbrain.py`, `src/packfacts.py`, `src/copystages.py`,
`src/cadencelibrary.py`, `src/sequenceplan.py`, `src/skills/*`.

## RULES THAT OUTRANK FINISHING

- **YOU START ON `master`. YOUR FIRST COMMAND IS:**

      git merge --no-edit origin/qwen-worker-8-r28

  Verify before starting — must print `True`:

      py -3 -c "from src import claims; print(claims.customer_outcome_claim('teams like yours have reduced admin time') is not None)"

- **DO NOT SOLVE THIS BY ADDING `operators`, `shops` AND `outfits` TO THE
  LIST.** That is the third time the same fix would be attempted, and a
  reviewer holds a fresh held-out matrix with different nouns again.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **PROVIDER WRITES = 0.** `sending.live` false. Production `work/` READ-ONLY.
- **Commit every file you touch.** Push to your own branch, verify the remote.
  Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your branch head SHA.

**"agencies in your sector" and "operators in your sector" are the same
claim. Only one of them is refused.**
