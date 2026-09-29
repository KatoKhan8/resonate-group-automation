PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-914 — an unsupported customer-outcome claim must be refused

**Operator, Zvonimir, 2026-09-29.** Two items, both small. **Do NOT** change
the writer contract, qualification, Second Brain, Offer Engine, the
verification policy, or `copylint`'s existing acceptance rules. **Do NOT**
build a parallel claim framework. **No other account. No provider writes.**

## PART A — the unsupported customer-outcome claim (the real defect)

The Rachele generation produced, and every gate allowed, this LinkedIn message:

    "clients using report intelligence have improved resource allocation and
     project margins noticeably. can i share a benchmark example that might
     help your team?"

**That is a customer-outcome claim with no licensed evidence behind it.** The
system already knows it has none — `offers.missing()` returns, verbatim:

    {"gap": "customer case studies",
     "detail": "no documented customer outcomes or case studies available"}
    {"gap": "verified benchmarks",
     "detail": "no before-and-after metrics from comparable firms"}

So the claim is refuted by the system's own knowledge and still shipped.

### Fix the LOWEST EXISTING claim-safety boundary
Find where claims are already licensed against evidence — `src/claims.py`,
`src/copylint.py`'s `untraceable_company_claim` / `case_study_unsupported`
rules, and `src/packfacts.py` are the existing authorities. **Extend the one
that already owns this question.** Do not add a new module, a new rule engine,
a new taxonomy or a second licensing path.

**Do NOT hardcode this sentence.** The regression must cover the CLASS:

> a claim that customers/clients achieved an outcome or improvement, where no
> licensed customer-outcome or case-study evidence exists.

Including claims that customers/clients: improved margins, improved resource
allocation, increased profitability, reduced costs, saved time, increased
revenue — and the same claim shaped as a benchmark, a "typical result", or an
offer to share one.

**If licensed evidence DOES exist, the existing evidence rules remain
authoritative — do not block a supported claim.** And **do not weaken
CLIENT_SUPPLIED restrictions**: Productive knowledge still guides capability,
strategy, offer and value proposition, and still licenses nothing about a
prospect.

**The LinkedIn channel must use the SAME evidence authority as email.** This
claim escaped in a LinkedIn message; a weaker parallel path for LinkedIn is
itself the defect. Prove both channels consult one authority.

## PART B — an email hold must not be silent

`generate._candidate_steps` gates the whole email branch on:

    email_ok = bool(contact.get("email")) and lint.sendable(contact, ...)
    email_keys = _generated_keys(sequence, "email") if email_ok else []

When `email_ok` is False, **`email_keys` becomes `[]` and five email steps
vanish with no log line, no reason and no counter.** Measured on
`2020companies-com` / `rachele-crumpler`: `_generated_keys` finds
`['em1'..'em5']`, and the branch still returns only the LinkedIn steps.

**The reason exists and is good** — `verification.decide` returns:

    state    held
    sendable false
    reason   "contactout says valid but the primary is missing, and policy
              does not clear on the secondary alone"

**but nothing surfaces it at generation time.** That silence cost two
misdiagnoses: the drop looked like a consumer-migration bug and was in fact a
deliberate verification hold.

**Fix: make the hold observable.** When the email branch is skipped for an
unsendable address, record it the way other holds are recorded — a
`store.log` line naming the contact and carrying
`verification.decide(...)["reason"]`, or the existing hold mechanism if one
fits. **Do NOT make the emails generate. Do NOT relax `lint.sendable`, the
verification policy, or `trust_secondary_when_primary_unknown`.** An
unverified address must still refuse; it must simply say so.

## Acceptance

1. An unsupported customer-outcome claim in an EMAIL body is REFUSED.
2. The same claim in a LINKEDIN message is REFUSED — same authority.
3. The same claim shaped as a benchmark/"typical result"/offer-to-share is
   REFUSED.
4. **NEGATIVE CONTROL:** a customer-outcome claim WITH licensed supporting
   evidence is NOT refused.
5. **NEGATIVE CONTROL:** a Productive capability statement
   ("Productive shows margin per project while it is running") is NOT refused —
   it is a capability, not a customer outcome.
6. **NEGATIVE CONTROL:** CLIENT_SUPPLIED knowledge still cannot license a
   prospect-side claim. `test_a_client_csv_fact_cannot_license_a_claim` and
   `test_a_client_supplied_figure_licenses_no_claim_in_either_gate` stay green
   and **unedited**.
7. A skipped email branch logs the verification reason; the log names the
   contact and the reason string.
8. **`lint.sendable` and the verification policy are unchanged** — assert it,
   do not merely avoid touching it.
9. **MUTATION:** remove your claim rule; acceptance 1 and 2 must go red for
   that reason. Restore and verify byte-identical by sha256. Files are
   **CRLF** — an `\n`-anchored regex matches zero times and the mutation
   becomes a silent no-op.

### ACCEPTANCE COMMANDS

    py -3 -m unittest tests.test_task914_customer_outcome_claims
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate
    py -3 -m unittest tests.test_task913_writer_contract_five_plus_five
    py -3 -m unittest tests.test_task911_second_brain_canonical_status
    py -3 -m unittest tests.test_task910_writer_contract
    py -3 -m unittest tests.test_render_preview
    py -3 -m unittest tests.test_task904_opt_out
    py -3 -m unittest tests.test_task906_signature_composed_into_copy
    py -3 -m unittest tests.test_approve
    py -3 -m unittest tests.test_generate

    py -3 -c "import sys; from src import lint, verification; import inspect; s=inspect.getsource(verification.decide); sys.exit('policy logic changed') if 'trust_secondary_when_primary_unknown' not in s else print('OK: verification policy intact')"

**Read exit codes OFF THE PROCESS, never through a pipe.**

## PRE-EXISTING test_generate — do NOT fix
    56 collected · 53 passed · 2 failed · 1 error
    ERROR test_a_draft_that_breaks_a_rule_is_regenerated_not_patched  KeyError: 'rowan-blake'
    FAIL  test_the_model_is_told_what_failed_rather_than_the_draft_being_edited  AssertionError: 2 != 1
    FAIL  test_the_retry_names_the_banned_phrase_rather_than_the_code            AssertionError: 2 != 1

Red at `143f132f` and every commit since. **If the signature changes at all,
STOP and report it.**

## Files
The existing claim-safety module you extend (`src/claims.py` or
`src/copylint.py` — pick the one that already owns this and say which),
`src/generate.py` for Part B's log line, plus your own tests. **Do NOT touch**
`src/verification.py`, `src/lint.py`'s `sendable`/policy, `src/secondbrain.py`,
`src/offers.py`, `src/packfacts.py`'s CLIENT_SUPPLIED semantics,
`src/copystages.py`, `src/skills/cold_email_writing.py`.

## RULES THAT OUTRANK FINISHING

- **START FROM A CLEAN BRANCH OFF `origin/master`.** **First command:**
  `git merge --no-edit origin/qwen-worker-3-r22` — the validated 5+5 writer and
  LinkedIn consumer migration live there and must be preserved.
- **NEVER WIDEN A GATE.** This task only ever makes the system refuse MORE.
- **Do not manufacture or rewrite copy downstream.** If a claim is unsupported
  the draft is refused and regenerated, never patched.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **PROVIDER WRITES = 0.** `sending.live` false. Production `work/` READ-ONLY —
  copy it if you need estate data.
- Suite logs OUTSIDE the repository; a suite with no `Ran N tests` line is an
  absent measurement.
- **Commit every file you touch.** Push to your own branch, verify the remote
  with `git rev-parse`. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your branch head SHA.

**The operator read this copy and caught the claim himself. The gate should
have caught it first.**
