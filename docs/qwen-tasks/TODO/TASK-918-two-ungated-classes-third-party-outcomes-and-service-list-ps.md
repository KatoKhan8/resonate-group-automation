PRIORITY: P0
SIZE: M
DEPENDS: TASK-917

# TASK-918 — two measured ungated classes

**Operator, Zvonimir, 2026-09-29.** Evidence:
`docs/RACHELE-BLOCKED-ON-UNGATED-COPY-QUALITY-2026-09-29.md`. Two holes let
copy through that must not ship. **Fix ONLY these two.**

**Do NOT** redesign the writer, or change qualification, Second Brain, Offer
Engine, verification, or the provider projections. **Do NOT** hand-edit
Rachele's copy. **Do NOT** weaken TASK-914/915/916/917. **No provider writes.**

## WHY REGENERATION CANNOT FIX THIS — READ BEFORE YOU START

Do not try to solve either item by regenerating copy. Measured:
four canonical whole-set regenerations produced a **byte-identical** artifact,
`generate.store_step` was called **zero** times, and every `complete()` in
`src/llm.py` is `temperature=0`. The canonical path regenerates a step only
when a GATE REFUSES IT. Neither class is gated, so nothing is ever rewritten.
**The fix is the gate. The copy follows.**

---

# A — INDEFINITE / ANALOGOUS THIRD-PARTY OUTCOME CLAIMS

The escaped Rachele sentence, which every gate allows today:

    "Can I share a brief example of how real-time margin insights have
     improved resource decisions for others?"

    claims.check              -> []
    customer_outcome_claim    -> None

TASK-917's subject alternation is
`clients|customers|users|teams|companies|firms|agencies|studios`. The claim
escapes because its third party is **indefinite** ("others") rather than one
of those nouns.

**DO NOT fix this by adding "others" to the subject list.** The semantic class
is:

    PRODUCT / CAPABILITY / INTERVENTION
      + ASSERTED BUSINESS OUTCOME
      + INDEFINITE OR ANALOGOUS THIRD PARTY

Third-party forms include, and are not limited to: *for others, for other
teams, for other companies, for similar firms, for similar agencies, for
companies like yours, for teams like yours, for someone in your position, for
organisations like yours, elsewhere, across other businesses*.

## A — matrix, all must REFUSE without licensed evidence

    real-time margin insights improved resource decisions for others
    this helped other teams improve margins
    similar firms reduced costs with this approach
    companies like yours have improved profitability
    teams like yours save time using this
    someone in your position can reduce reporting time
    we've seen better resource allocation elsewhere
    other businesses increased profitability
    similar agencies improved project margins
    organisations like yours can reduce admin

    this improves margins for other teams                     (present)
    similar firms are reducing costs with this                (progressive)
    other agencies have saved time with this                  (perfect)
    companies like yours could increase profitability         (modal)
    organisations like yours usually reduce reporting time     (habitual)

**Six of these already escape on master** — `others`, `someone in your
position`, `elsewhere`, `other businesses`, and both `organisations like
yours` forms. The rest already refuse via TASK-917 and **must keep refusing**.

## A — negative controls, must NOT be refused, and EVIDENCE-INSENSITIVE

    Would improving margin visibility be useful?
    Productive provides real-time margin visibility.
    How do teams like yours currently track project margin?
    I noticed companies like yours often manage multiple projects.
    Can I show you how Productive tracks budget burn?

"teams like yours" and "companies like yours" appear in BOTH lists. That is
deliberate: the third-party phrase alone is not the claim — the claim is the
phrase **plus an asserted outcome**. A rule that fires on the phrase alone
overblocks two of the operator's own controls.

## A — the rest of Rachele's em4, measured

All three are clean today. Required verdicts:

    3. "...have improved resource decisions for others?"   MUST REFUSE
    1. "having margin visibility in real time often leads to smarter
        resource choices that directly affect profitability."
    2. "When teams can act on current financial data, they avoid costly
        misallocations."

Sentences 1 and 2 assert no realized third-party outcome — they are
conditional/general capability framing. **Measure and REPORT what your rule
does to them; do not contort the rule to catch them.** 2 is the closest call.

## A — evidence

Licensed evidence remains authoritative: every A refusal must DISAPPEAR when
`offers.missing()` no longer reports `customer case studies` /
`verified benchmarks`. Use a controlled fixture. Invent no evidence.

## A — scope

Email AND LinkedIn, through the one existing authority. **No LinkedIn-only
regex.** Extend `src/claims.py` where TASK-917 lives.

---

# B — SERVICE-LIST / GENERIC-FACTUAL P.S.

Rachele's em3 P.S., factually supported and worthless:

    "Their services include retail merchandising, product training, and
     display installation."

Nothing scores P.S. quality, so nothing can refuse it.

## B — where the rule goes

`src/copylint.py`'s `RULES` registry — the lowest existing canonical
copy-quality boundary, already run pre-approval by
`generate_campaign` (`result["copylint"] = copylint.check_batch([lead])`) and
fed back into regeneration by `_campaign_validator`. **A REFUSING rule, not a
warning.** No UI-only notice, no second pipeline, no reliance on human review.

**READ THE P.S. FIELD DIRECTLY.** The existing helper that flattens `ps`
merges it with every LinkedIn message into one string. Using it would apply
the service-list heuristic to LinkedIn notes. Your rule reads `lead["ps"]`
only, and must not touch email bodies — listing services in a body can be
contextually legitimate.

## B — matrix, all must REFUSE

    Their services include retail merchandising, product training, and display installation.
    You offer merchandising, training, and installation services.
    Your services include sales, marketing, and retail support.
    I saw you provide merchandising, product training, and display installation.
    2020 Companies offers merchandising and product training.

Vary the prefix: the rule targets the CLASS (a generic enumeration or
restatement of the prospect's own services, carrying no relevance), not one
opening phrase.

## B — negative control, must remain ALLOWED

    Since 2022, 2020 Companies has supported Christ's Haven through donations
    and volunteerism.

Specific, evidenced, and not a service list. **Do not require a date, a
charity, or any one style.** Do not ban factual P.S. content generally — other
specific, evidenced personalisation must stay possible.

## Acceptance

1. Every A matrix line REFUSES on BOTH channels without licensed evidence.
2. Every A refusal is RELEASED when the evidence fixture licenses it.
3. Every A negative control is unrefused AND evidence-insensitive.
4. Every B matrix line makes `copylint.check_batch` REFUSE the lead.
5. The Christ's Haven P.S. does NOT refuse.
6. The B rule reads `lead["ps"]` only — prove a LinkedIn note listing
   services is untouched by it, and that an email BODY is untouched.
7. **MUTATION, both fixes:** neuter each authority in-memory; its matrix goes
   RED. Restore, verify byte-identical by sha256. Files are **CRLF**. **Do not
   commit mutation code.**
8. Preserved green: TASK-917's outcome matrix, TASK-913's 5+5 chain,
   `test_a_client_csv_fact_cannot_license_a_claim` and
   `test_a_client_supplied_figure_licenses_no_claim_in_either_gate`
   (byte-identical to master), channel parity, copylint's existing rules.
9. `test_generate` unchanged: `Ran 56`, `failures=2`, `errors=1`.

### ACCEPTANCE COMMANDS

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
    py -3 -m unittest tests.test_linkedin_lint
    py -3 -m unittest tests.test_a_linkedin_note_is_claim_checked_too
    py -3 -m unittest tests.test_the_copy_lint_refuses_the_real_send_path
    py -3 -m unittest tests.test_generate

**Read exit codes OFF THE PROCESS, never through a pipe.**

## PRE-EXISTING — do NOT fix

    test_generate                                  Ran 56, failures=2, errors=1
    test_only_the_last_subject_may_claim_finality  Ran 19, failures=3

Red identically on master. **If either signature changes, STOP and report.**

## Files

`src/claims.py` (A), `src/copylint.py` (B), plus
`tests/test_task918_third_party_outcomes_and_ps_quality.py`. Earlier suites
may be EXTENDED; **no existing assertion may be weakened or deleted.**

**Do NOT touch** `src/verification.py`, `src/lint.py`, `src/offers.py`,
`src/generate.py`, `src/generate_campaign.py`, `src/secondbrain.py`,
`src/packfacts.py`, `src/copystages.py`, `src/cadencelibrary.py`,
`src/sequenceplan.py`, `src/skills/*`.

## RULES THAT OUTRANK FINISHING

- **YOU START ON `master` (`62d1b842`).** It already carries TASK-913 through
  917. Verify before starting — must print `True`:

      py -3 -c "from src import claims; print(claims.customer_outcome_claim('clients improve margins') is not None)"

- **A REFUSAL YOU ADD MUST NOT OVERBLOCK.** Acceptance 3 and 5 exist because
  the cheap version of each rule ("ban 'like yours'", "ban any P.S. naming a
  service") fails them.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **PROVIDER WRITES = 0.** `sending.live` false. Production `work/` READ-ONLY.
- Suite logs OUTSIDE the repository; a suite with no `Ran N tests` line is an
  absent measurement.
- **Commit every file you touch.** Push to your own branch, verify the remote
  with `git rev-parse`. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your branch head SHA.

**A held-out matrix is retained by the reviewer. Fitting these strings alone
will not pass.**
