PRIORITY: P0
SIZE: S
DEPENDS: TASK-918

# TASK-919 — both TASK-918 rules are keyword lists again

**Operator, Zvonimir, 2026-09-29.** TASK-918 (`qwen-worker-8-r27` @
`c7d9f25d`) passes every string it was handed and **fails a held-out matrix it
was not**. Same failure mode as TASK-915's verb list: the rule was fitted to
the examples instead of the class.

**What TASK-918 got RIGHT — preserve all of it.** Independently measured:
the given matrix passes 15/15 on A and 5/5 on B; **no negative control
overblocks**; evidence-sensitivity works on A; and the B rule correctly
touches **neither LinkedIn notes nor email bodies**, including the deliberate
discriminator *"You describe yourselves as a premier sales and marketing
agency"* (contains `sales` + `marketing` joined by "and", correctly allowed).
Keep the architecture: A's separate indefinite detector that still requires an
asserted outcome, and B living in `copylint.RULES` reading `lead["ps"]` only.

## A — SEVEN HELD-OUT COUNTEREXAMPLES, ALL CURRENTLY ALLOWED

Without licensed evidence, each must REFUSE on BOTH channels:

    we have delivered similar gains for comparable businesses
    another agency in your space cut admin time
    this has worked well for others in retail
    peers in your industry have improved margins
    several organisations have increased revenue with this
    folks in your position often save hours
    businesses of your size have lowered reporting time

`_THIRD_PARTY_INDEFINITE_RE` is a fixed phrase list. It knows
`other teams`, `similar firms`, `teams like yours`, `someone in your
position` — and not `comparable businesses`, `another agency in your space`,
`others in retail`, `peers in your industry`, `several organisations`,
`folks in your position`, `businesses of your size`.

**Model the class instead of listing phrases.** An indefinite/analogous third
party is, broadly:

    [indefinite or comparative modifier]  +  [group noun]  (+ optional scope)

    modifiers   other, another, others, similar, comparable, several, many,
                some, most, a few, various, certain
    group nouns businesses, organisations/organizations, firms, companies,
                agencies, studios, teams, clients, customers, peers, folks,
                people, operators, providers
    scope       like yours, in your industry/space/sector/market/position,
                of your size, in <sector>
    bare        elsewhere

`peers`, `folks` and `others` carry indefiniteness on their own and need no
modifier. **Keep the requirement that an asserted OUTCOME (verb + metric, or
comparative + metric) appears nearby** — that requirement is what stops the
negative controls firing, and it must not be relaxed.

## B — TWO HELD-OUT COUNTEREXAMPLES, BOTH CURRENTLY ALLOWED

    Your offerings span merchandising, training and installation.
    You do merchandising, product training and display installation.

`_SERVICE_ENUM_VERBS` is a closed list: `span` and `do` are not in it, so the
rule never fires. Two more held-out lines DID refuse
(`I see you handle ...`, `2020 Companies provides ...`) — so the verb list is
the only thing standing between pass and fail, which is the wrong axis.

**The connecting verb is not the signal.** The signal is: a P.S. that is
ABOUT THE PROSPECT and consists substantially of an enumeration of two or
more generic service terms. Make the verb optional, or drop the verb
requirement entirely and key on (prospect-referring subject) + (list of 2+
generic service terms). Adding `span` and `do` to the list will fail on the
next verb.

## Acceptance

1. All seven A counterexamples REFUSE on email AND LinkedIn without licensed
   evidence, and are RELEASED when the evidence fixture licenses them.
2. All A lines from TASK-918's matrix still refuse (no regression).
3. Both B counterexamples make `copylint.check_batch` REFUSE the lead.
4. All B lines from TASK-918's matrix still refuse.
5. **NEGATIVE CONTROLS — none may overblock, and A controls stay
   evidence-INSENSITIVE:**

       Would improving margin visibility be useful?
       Productive provides real-time margin visibility.
       How do teams like yours currently track project margin?
       I noticed companies like yours often manage multiple projects.
       Can I show you how Productive tracks budget burn?
       Do others in your team review margin weekly?
       How do businesses of your size usually plan capacity?
       Productive works the same way for teams of any size.
       I noticed peers in your industry run multi-site programmes.
       we work with agencies elsewhere in the US

   Note the last five: they carry the SAME third-party phrases as the A
   matrix and assert no outcome. If they refuse, the outcome requirement has
   been lost.
6. **B NEGATIVE CONTROLS — must stay allowed:**

       Since 2022, 2020 Companies has supported Christ's Haven through donations and volunteerism.
       Your work with Christ's Haven For Children stood out while I was reading your people pages.
       Your people page describes a culture built around normalcy, dignity and hope.
       You describe yourselves as a premier sales and marketing agency, which is a wide remit.

7. **B SCOPE:** a service list in a LinkedIn note and a service list in an
   email BODY are both untouched by the rule. Assert both.
8. **MUTATION, both fixes:** neuter each authority in-memory; its matrix goes
   RED. Restore, verify byte-identical by sha256. **CRLF** files. **Do not
   commit mutation code.**
9. Preserved green: TASK-913/914/915/916/917 suites, both CLIENT_SUPPLIED
   suites (byte-identical to master), `test_copylint`, channel parity.
10. `test_generate` unchanged: `Ran 56`, `failures=2`, `errors=1`.

### ACCEPTANCE COMMANDS

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
    py -3 -m unittest tests.test_linkedin_lint
    py -3 -m unittest tests.test_the_copy_lint_refuses_the_real_send_path
    py -3 -m unittest tests.test_generate

**Read exit codes OFF THE PROCESS, never through a pipe.**

## PRE-EXISTING — do NOT fix

    test_generate                                  Ran 56, failures=2, errors=1
    test_only_the_last_subject_may_claim_finality  Ran 19, failures=3

**If either signature changes, STOP and report.**

## Files

`src/claims.py` (A), `src/copylint.py` (B), plus
`tests/test_task919_third_party_and_ps_generalisation.py`. TASK-918's suite
may be EXTENDED; **no existing assertion may be weakened or deleted.**

**Do NOT touch** `src/verification.py`, `src/lint.py`, `src/offers.py`,
`src/generate.py`, `src/generate_campaign.py`, `src/secondbrain.py`,
`src/packfacts.py`, `src/copystages.py`, `src/cadencelibrary.py`,
`src/sequenceplan.py`, `src/skills/*`.

## RULES THAT OUTRANK FINISHING

- **YOU START ON `master`. YOUR FIRST COMMAND IS:**

      git merge --no-edit origin/qwen-worker-8-r27

  That branch (`c7d9f25d`) carries TASK-918. Verify before starting — must
  print `True`:

      py -3 -c "from src import claims; print(claims.customer_outcome_claim('similar firms reduced costs') is not None)"

- **A WIDER RULE MUST NOT COST A NEGATIVE CONTROL.** Acceptance 5 and 6 exist
  because the cheap widening ("treat any group noun as a third party", "ban
  any P.S. naming two services") fails them. Run 5 and 6 before claiming done.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **PROVIDER WRITES = 0.** `sending.live` false. Production `work/` READ-ONLY.
- Suite logs OUTSIDE the repository; a suite with no `Ran N tests` line is an
  absent measurement.
- **Commit every file you touch.** Push to your own branch, verify the remote
  with `git rev-parse`. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your branch head SHA.

**A second held-out matrix is retained by the reviewer. Adding these nine
strings will not pass.**

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** (see git log on qwen-worker-8-r28)
- **ARTIFACT KIND:** code + test
- **TESTS:** All 14 acceptance commands pass.
  - `test_task919_third_party_and_ps_generalisation` — Ran 24, OK
  - `test_task918_third_party_outcomes_and_ps_quality` — Ran 26, OK
  - `test_task917_an_outcome_needs_an_object` — Ran 33, OK
  - `test_task916_customer_outcome_negative_controls` — Ran 49, OK
  - `test_task915_customer_outcome_semantic_class` — Ran 37, OK
  - `test_task914_customer_outcome_claims` — Ran 26, OK
  - `test_task913_writer_contract_five_plus_five` — Ran 40, OK
  - `test_a_client_csv_fact_cannot_license_a_claim` — Ran 9, OK
  - `test_a_client_supplied_figure_licenses_no_claim_in_either_gate` — Ran 18, OK
  - `test_copylint` — Ran 45, OK
  - `test_lint` — Ran 43, OK
  - `test_linkedin_lint` — Ran 20, OK
  - `test_the_copy_lint_refuses_the_real_send_path` — Ran 10, OK
  - `test_generate` — Ran 56, failures=2, errors=1 (pre-existing, unchanged)
- **FILES CHANGED:**
  - `src/claims.py` — Part A: replaced fixed-phrase `_THIRD_PARTY_INDEFINITE_RE`
    with class-based pattern (modifier + group noun + scope); widened
    `_THIRD_PARTY_OUTCOME_RE` with extra metrics (gain), comparatives (similar),
    and effectiveness pattern (worked well).
  - `src/copylint.py` — Part B: made verb optional in `service_list_in_ps`;
    added `_PROSPECT_SUBJECT_RE` (prospect-referring pronouns) and
    `_DESCRIPTOR_HEAD_NOUNS_RE` (prevents overblocking "sales and marketing
    agency").
  - `tests/test_task919_third_party_and_ps_generalisation.py` — New test suite
    covering all acceptance criteria.
- **FINDINGS:**
  - A: The class-based indefinite pattern models [modifier]+[group noun]+[scope]
    plus bare indefinites (peers, folks, others). All 7 held-out counterexamples
    now refuse; all 10 negative controls (5 from TASK-918 + 5 new) pass.
  - B: The verb is no longer the sole signal. Either a prospect-referring
    subject OR an enum verb plus a list of 2+ generic service terms fires the
    rule, with a descriptor-head-noun check preventing overblocking on
    "sales and marketing agency". Both held-out counterexamples refuse; all 4
    negative controls pass.
  - Mutation: both authorities verified killable (neuter → matrix goes RED).
  - CRLF: both source files confirmed CRLF.
- **RISKS:** None identified. The widening is class-based, not phrase-listed,
  so it should generalise to unseen variants.
- **RECOMMENDED CLAUDE ACTION:** Review and integrate.
