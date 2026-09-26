# RESONATE OS — GLM CANARY READINESS REVIEW

## REVIEW STAMP

- START MASTER SHA: `b33369748a91435f23524ede40ad74b1c54fb7cf`
- END MASTER SHA: `b33369748a91435f23524ede40ad74b1c54fb7cf`
- MASTER MOVED DURING REVIEW: NO
- REVIEW BRANCH: `review/glm-b333697`
- REVIEW WORKTREE: `C:\Users\Zvonimir\glm-review\glm-review-b333697` (detached
  from `origin/master`, `git status --porcelain` empty before the audit)
- REVIEW SCOPE: six canary-critical areas only
- RUNTIME VERIFICATION PERFORMED: **NO** (all findings are CODE-LEVEL; the
  long-lived loops import at process start, so this says nothing about what is
  running right now)

## EXECUTIVE RESULT

The copy-certification core is genuinely hardened: both provider factories
require a fingerprint *and* an accountable approver, both fail closed, and the
two holes an earlier independent pass found are fixed with real negative
controls. The previously known preview cadence divergence is gone.

One P0: `EMAIL_RESUME` was added to `SUPPORTED` on 2026-09-24 while its
operation metadata still declares `prospect_facing=False`. Resume is the verb
that puts a paused sequence back in front of everyone the campaign holds, and
the non-facing branch of `_perform` skips the suppression re-check, the
Authorization, the spend gate and the action-ledger reservation. Nothing else
on the resume path re-evaluates suppression either.

Four P1s: LLM spend is recorded but never checked; LinkedIn provider timing is
a second source of cadence truth; the static write audit cannot see the shape
the repo's own transport uses; `researchpack` has no production consumer.

## AREA COVERAGE

| # | Area | Status |
|---|------|--------|
| 1 | Approval identity | REVIEWED — NO DEFECT FOUND |
| 2 | Provider write gate | REVIEWED — DEFECTS FOUND |
| 3 | Suppression + cross-channel stop | REVIEWED — DEFECTS FOUND |
| 4 | Cadence single source | REVIEWED — DEFECTS FOUND |
| 5 | Spend ceiling | REVIEWED — DEFECTS FOUND |
| 6 | Account identity | PARTIALLY REVIEWED |

### 1. APPROVAL IDENTITY — REVIEWED — NO DEFECT FOUND

- Canonical source / owner: `src/approval.py:59` `fingerprint(step)` over
  channel + subject + body + note; `src/approval.py:31`
  `is_accountable_approver(by)`.
- Invariant: prospect-facing copy is staged only when a fingerprint covers the
  exact words being staged **and** a person can be held to the approval.
- Enforcing code, email: `src/bisonfactory.py:927` `_certified_copy` — `:962`
  refuses a missing fingerprint, `:966` refuses a non-accountable approver,
  `:973-976` recomputes the hash over the entry's *own* subject/body,
  `:978-995` refuses prospect-facing fields arriving through `extra`.
- Enforcing code, LinkedIn: `src/heyreachfactory.py:163` refuses a fingerprint
  that does not cover the step, `:170` refuses a non-accountable approver,
  `:196-215` refuses copy that would come from `message` (a field the hash does
  not cover). The variant path lifts the variant's own approval onto the step
  (`src/heyreachfactory.py:288`) and re-verifies through the same extractor.
- Test coverage with real negative controls:
  `tests/test_the_fingerprint_does_not_cover_every_field.py:63` (copy in
  `extra` is refused), `:84` (asserts the premise that `message` is outside the
  hash), `:88` (an InMail edited after approval yields nothing).
- REPRODUCE: `sed -n '955,1000p' src/bisonfactory.py` and
  `sed -n '160,215p' src/heyreachfactory.py`
- RUNTIME VERIFICATION REQUIRED: NO for the code path.

Residual, reported as an observation and not as a defect: the fingerprint binds
the words, not the recipient address, the send day or the sender. Approval is
structurally contact-scoped (`rec["cadence"][contact_key][step_key]`,
`src/approval.py:70`), so a different contact cannot inherit it, but a
correction to the *same* contact's email after approval does not move the hash.
No path was found that rewrites a contact's address between approval and
staging, so this is stated rather than raised.

### 2. PROVIDER WRITE GATE — REVIEWED — DEFECTS FOUND

- Canonical source / owner: `src/providerwrites.py:2035` `_perform`, the single
  door. `src/providers/bison.py:515` `_allow` and `heyreach.WRITE_ROUTES` are
  the second, route-level door.
- Invariant chain proven present for facing operations
  (`src/providerwrites.py:2052-2120`): a real `executionguard.Authorization`
  object, channel match, **operation** match, `_require_approved_words`,
  `require_conditional_permission`, `authorization.spend()`, and an open
  action-ledger reservation.
- HTTP chokepoint holds today: every mutating call in `src/providers/bison.py`
  goes through `_post`/`_patch`/`_put`/`_delete`, each of which calls `_allow`
  (`src/providers/bison.py:524-541`), and `_allow` refuses any path not on
  `WRITE_ROUTES`.
- Direct provider calls outside `perform` exist but are staging verbs inside the
  factories, and the two that reach people self-gate:
  `src/providers/bison.py:1414` `_require_approval_for_topup` (fails closed on
  an unreadable status) and `src/providers/bison.py:1884-1885`
  `reviewapproval.require(campaign_id)` inside `resume_campaign`.
- DEFECTS: see P0-1 and P1-3.

### 3. SUPPRESSION + CROSS-CHANNEL STOP — REVIEWED — DEFECTS FOUND

- Suppression authority: `src/eligibility.py:49-65` (`blocked:suppressed`,
  `blocked:replied`, `blocked:unsubscribed`, `blocked:account_suppressed`,
  `blocked:contact_stopped`).
- Re-check at write time: `src/providerwrites.py:2189-2190` —
  `if facing: executionguard.revalidate(authorization)`.
- DEFECT: see P0-1. Nothing on the resume path reaches that line.
- Cross-channel stop: `EMAIL_STOP_LEAD` was enabled 2026-09-23
  (`src/providerwrites.py:515-530`) and its own comment records that only the
  LinkedIn-reply-stops-email direction was measured live. Provider-level stop in
  the reverse direction is CODE PATH EXISTS — RUNTIME VERIFICATION REQUIRED.

### 4. CADENCE SINGLE SOURCE — REVIEWED — DEFECTS FOUND

- Canonical source / owner: `src/cadencelibrary.py:327`
  `PRODUCTIVE_LI_HEAVY_V1`, one interleaved graph carrying both channels.
  Measured at this SHA: `li1..li5` on days 1 / 3 / 6 / 10 / 15 and `em1..em5` on
  days 1 / 4 / 8 / 12 / 21 — both match the expected structure exactly.
- The previously known preview divergence is **ALREADY FIXED**: no `1/3/8/14`
  literal exists anywhere in `src/` or `scripts/` at this SHA, and
  `src/preview.py:215` and `:234` read `step["day"]` rather than recomputing it.
  Preview is a projection.
- DEFECT: see P1-2 — the LinkedIn provider graph is a second source of timing.

### 5. SPEND CEILING — REVIEWED — DEFECTS FOUND

- Canonical source / owner: `src/spendledger.py:591` `check(...)` — the only
  function that raises `BudgetExceeded`; `:720` `reserve`, `:779` `holding`.
  `MissingCeiling` (`:228`) subclasses `BudgetExceeded`, so an undeclared
  ceiling refuses rather than reading as unlimited. `LedgerUnreadable` (`:240`)
  raises rather than treating an unreadable ledger as zero. This is the right
  shape.
- Correct consumers: `src/enrich.py:927` and `src/verification.py:754` both
  catch `BudgetExceeded` from a pre-call check.
- DEFECT: see P1-1 — the LLM path is not one of them.

### 6. ACCOUNT IDENTITY — PARTIALLY REVIEWED

Proven at this SHA:

- Account-level facts are admitted by one rule, fail-closed:
  `src/packfacts.py:78` `identity_of` returns `REFUSED` for a missing domain
  (`:97-98`) and for a `record_id` mismatch (`:100-103`), `ADMITTED` only when
  the row's own site field or its `source_url` host is the same site as the
  record's domain (`:104-108`), and `UNVERIFIABLE` when the row carries neither.
  `pack_for` (`:110`) puts only `ADMITTED` rows into `{"facts": ...}`, so UNKNOWN
  never becomes admitted. Live consumer: `src/bisonfactory.py:559`.
- Research cache keys are account-scoped by construction:
  `src/researchpack/cache.py:33` `key_for(domain, profile)` — `domain` for
  company-level work, `domain::profile` for a person, and an empty domain raises.

NOT reached, and the reason this area is PARTIALLY REVIEWED rather than
reviewed: the joins in `src/enrich.py`, `src/companies.py` and
`src/providers/contactout.py` (LinkedIn company/person matching, website
redirects, name similarity) were not traced, and the "2–3 decision makers are
one account plus contacts" representation was not verified end to end.
`FREE_MAIL` (`src/enrich.py:417`) has exactly one consumer
(`src/enrich.py:404`) and is not consulted when a research key is built — worth
a second pass, but no path was traced that derives a research domain from a
personal address, so it is not raised as a finding.

## P0 BEFORE CANARY

### P0-1 — `EMAIL_RESUME` is enabled as a non-facing operation, so resuming a campaign skips the suppression re-check, the spend gate and the ledger reservation

- SEVERITY: **P0**
- STATUS: CODE-LEVEL VERIFIED
- FILE:LINE:
  - `src/providerwrites.py:406` — `EMAIL_RESUME: ("email", False, ...)`, i.e.
    `prospect_facing=False`, and the prose there still asserts "It is NOT in
    SUPPORTED".
  - `src/providerwrites.py:561` — `EMAIL_RESUME` **is** in `SUPPORTED` (added
    2026-09-24).
  - `src/providerwrites.py:2189-2190` —
    `if facing: executionguard.revalidate(authorization)`.
  - `src/orchestrator.py:660-661` — the resume transport,
    `lambda pid: bison.resume_campaign(pid)`, passing **no** `expect_leads`.
  - `src/orchestrator.py:648` — the docstring still says "BOTH VERBS ARE SEALED
    TODAY and that is the point of calling them".
- SYMBOL: `providerwrites._perform`, `orchestrator._resume_at_providers`
- REPRODUCE:

      git grep -n "EMAIL_RESUME" src/providerwrites.py
      sed -n '2186,2191p' src/providerwrites.py
      sed -n '646,666p' src/orchestrator.py

- INVARIANT THAT FAILS: a write that puts a sequence back in front of people
  must re-read the stops from disk immediately before the transport, because the
  pause window is exactly when replies and unsubscribes accumulate.
- FAILURE SCENARIO: campaign is paused. During the pause a prospect replies or
  unsubscribes and `eligibility.decide` would answer `blocked:replied` /
  `blocked:unsubscribed`. An operator resumes. `orchestrator.resume`
  (`src/orchestrator.py:616`) runs `campaigns.validate(..., ignore_status=True)`
  — whose 17 checks (`src/campaigns.py:691-709`) do not include eligibility or
  suppression at all; `check_recipients_sendable` (`src/campaigns.py:495`)
  delegates to `verification.is_sendable` (`src/verification.py:475`), which
  decides address *deliverability*, not whether the person asked us to stop.
  `perform(EMAIL_RESUME)` then passes `require_supported`, takes the `else`
  branch because `facing` is False, and never reaches line 2190. The campaign
  resumes and sends to everyone it still holds.
- WHY CANARY-BLOCKING: `EMAIL_ACTIVATE` — the other verb that starts an email
  campaign sending — is `facing=True` (`src/providerwrites.py:444`) *and*
  carries a provider-state condition (`src/providerwrites.py:1410`
  `CONDITIONAL[EMAIL_ACTIVATE]`). `EMAIL_RESUME` has neither, and reaches the
  same outcome. A canary that is ever paused and resumed runs the ungated verb.
- WHAT DOES STILL PROTECT IT (so the fix is scoped, not panicked):
  `bison.resume_campaign` requires an operator-approved review file
  (`src/providers/bison.py:1884-1885` `reviewapproval.require(campaign_id)`),
  and `EMAIL_RESUME` is absent from `REPEATABLE` (`src/providerwrites.py:724`)
  so `staged_already` refuses an identical repeat. Neither of those reads
  suppression.
- SMALLEST FIX: flip `src/providerwrites.py:406` to `("email", True, ...)` so
  resume takes the facing branch, and give `src/orchestrator.py:660-661` an
  `expect_leads` count so `src/providers/bison.py:1888-1898` can refuse a
  campaign whose reach is not what the caller believes. Correct the stale prose
  at `:407-409` and the stale docstring at `src/orchestrator.py:648` in the same
  change. Flipping the flag will demand an `Authorization` for the operation,
  which is the intended ladder — expect the executionguard mint for
  `EMAIL_RESUME` to need wiring, and that is the real work here.
- RUNTIME VERIFICATION REQUIRED: **YES**, for blast radius only. Whether a
  resumed campaign would actually reach a suppressed person depends on whether
  the reply loops had already pushed per-lead `EMAIL_STOP_LEAD` to the provider
  during the pause. The skipped re-check is code-level certain; the reach is not.

## P1 BEFORE SCALE

### P1-1 — LLM spend is recorded after the call, never checked before it, and the ceiling's own refusal is swallowed

- STATUS: CODE-LEVEL VERIFIED
- FILE:LINE: `src/llm.py:275-297` `_record_spend`; `src/llm.py:286-287`
  (`if provider is None: return`); `src/llm.py:296-297`
  (`except Exception: pass`); `src/spendledger.py:316` `record` (append-only);
  `src/spendledger.py:591` `check` (the only function that raises).
- SYMBOL: `llm.OpenAICompatibleModel._record_spend`
- REPRODUCE: `grep -n "spendledger\." src/llm.py` — one hit, `record`.
- FAILURE SCENARIO: three separate failures on one path. (a) `_record_spend`
  takes `usage`, so it runs after the model answered — a ceiling checked here
  could not prevent the spend even if it raised. (b) It never calls
  `spendledger.check`, so no LLM call is refused at any ceiling. (c)
  `except Exception: pass` discards `BudgetExceeded` / `MissingCeiling` if
  `record` ever raises one. Additionally `if provider is None: return` means any
  base URL that is not groq/anthropic/openrouter — xAI, GLM, a local server, the
  next provider added — writes **no ledger row at all**, so that spend is
  invisible rather than merely unrefused.
- SMALLEST FIX: call `spendledger.holding(...)` around `complete()` the way
  `src/enrich.py:927` and `src/verification.py:754` already do, and let
  `BudgetExceeded` propagate. Narrow the `except` to the ledger's own I/O
  errors. Make an unknown provider a refusal or a named row, not a silent
  return.

### P1-2 — LinkedIn step timing is a second source of cadence truth; the canonical graph cannot change what the provider executes

- STATUS: CODE-LEVEL VERIFIED
- FILE:LINE: `src/heyreachfactory.py:365` `_build_sequence_no_inmail` and
  `:404-409`; `src/providers/heyreach.py:1198` `linkedin_sequence` and
  `:1227-1261`; both reached from `src/heyreachfactory.py:557` `build_sequence`.
- SYMBOL: `heyreachfactory.build_sequence`
- REPRODUCE:

      grep -n '_node("MESSAGE"' src/providers/heyreach.py src/heyreachfactory.py
      grep -n "cadencelibrary" src/heyreachfactory.py

- FAILURE SCENARIO: the graph the campaign runs is built from literal relative
  delays (`MESSAGE, 3, "HOUR"`, `MESSAGE, 3, "DAY"`, `VIEW_PROFILE, 2, "DAY"`,
  `MESSAGE, 5, "DAY"`, `MESSAGE, 7, "DAY"`). Accumulated, the connected branch
  puts messages at roughly day 0.1 / 3.1 / 10.1 / 17.1 against the canonical
  `li1..li5` days of 1 / 3 / 6 / 10 / 15. `heyreachfactory` imports
  `cadencelibrary` only to find steps naming `CAP_INMAIL`
  (`src/heyreachfactory.py:736`); no code maps a canonical `day` onto a node
  delay. Editing `PRODUCTIVE_LI_HEAVY_V1` therefore changes preview, QA and the
  email lane, and changes nothing about when LinkedIn actually sends. This is
  the same class as the preview divergence that was already fixed, on the
  representation that sends.
- SMALLEST FIX: derive the node delays from consecutive `li*` day deltas in the
  canonical graph and assert the built graph's cumulative days equal the
  canonical days. No new abstraction is needed — one derivation plus one test.

### P1-3 — the static write audit cannot see the shape this repo's own transport uses, and two undeclared POSTs exist today

- STATUS: CODE-LEVEL VERIFIED
- FILE:LINE: `tests/test_nothing_writes_to_a_provider.py:155-160` (the `CALLS`
  regex); `src/providers/__init__.py:765` (the transport:
  `urllib.request.Request(url, method=method, data=data, ...)` then
  `urlopen(req)`); `src/web/oidc.py:359-365`; `src/socketmode.py:76-77`.
- SYMBOL: `NoUndeclaredProviderWrite.writes`
- REPRODUCE:

      sed -n '155,161p' tests/test_nothing_writes_to_a_provider.py
      sed -n '359,366p' src/web/oidc.py
      sed -n '76,80p' src/socketmode.py

- FAILURE SCENARIO: `CALLS` matches three spellings — `request("VERB", ...)`,
  `requests.post(...)`, and `urlopen(..., method="VERB")`. It does not match a
  verb carried on the `Request` **object**, which is precisely how the repo's
  own transport issues every write, nor `Request(url, data=...)` with no
  `method=` at all, which urllib sends as POST. Two live examples:
  `src/web/oidc.py:359` sets `method="POST" if data is not None`, and
  `src/socketmode.py:76` passes `data=b""` with no method. Neither is in
  `ALLOWED`, and the test passes reporting zero undeclared writes. Both are
  infrastructure rather than prospect-facing, so this is P1 — but the test's own
  failure message claims "every HTTP write in the repository is declared", and
  at this SHA that claim is false.
- SMALLEST FIX: add a fourth alternative to `CALLS` for
  `Request(... method="VERB" ...)` plus a rule for `Request(` carrying `data=`
  with no `method=`, declare `src/web/oidc.py` and `src/socketmode.py` in
  `ALLOWED` with their reasons, and add a positive control asserting the scanner
  catches the `Request`-object shape.

### P1-4 — `researchpack` produces account research that no production module consumes

- STATUS: CODE-LEVEL VERIFIED
- FILE:LINE: `src/researchpack/pack.py:195` `build`; the only caller in the
  repository is `scripts/capture_researchpack.py:102`, a cassette-capture tool.
- SYMBOL: `researchpack.build`
- REPRODUCE:

      grep -rn "researchpack" --include=*.py src/ scripts/ | grep -v "^src/researchpack/"

- FAILURE SCENARIO: no `src/` module imports `researchpack`. The live email path
  gets its account facts from `packfacts.pack_for(rec)`
  (`src/bisonfactory.py:559`), which reads `rec["research"]` — a different store
  from `researchpack.cache`. So `researchpack`'s Apify actor spend, its cache and
  its account/person fact split are a producer with zero production consumers,
  and there are two research stores. Not a safety defect: facts do reach copy, by
  the other route, under `packfacts`' fail-closed identity rule.
- SMALLEST FIX: decide which store is canonical. If `packfacts` is, say so in
  `src/researchpack/__init__.py` and stop paying for the actors; if
  `researchpack` is, wire `build` into the path that fills `rec["research"]`.
  Prefer wiring one in to deleting the other, and only after the operator picks.

## KNOWN FINDINGS — CURRENT STATUS

| Historical finding | Status at `b333697` | Evidence |
|---|---|---|
| Approval hash not enforced at provider call sites | **ALREADY FIXED** | `src/bisonfactory.py:962-976`, `src/heyreachfactory.py:163-175`; negative controls in `tests/test_the_fingerprint_does_not_cover_every_field.py` |
| Self-recorded approvals (`by: "claude"`) stay current forever on generated steps | **ALREADY FIXED** | `src/approval.py:31` consulted at `src/bisonfactory.py:966` and `src/heyreachfactory.py:170` |
| Copy arriving through `extra` after the fingerprint proof | **ALREADY FIXED** | `src/bisonfactory.py:978-995` raises `FactoryRefused` |
| InMail body from the unhashed `message` field | **ALREADY FIXED** | `src/heyreachfactory.py:196-215` fails closed |
| Suppression not re-evaluated on resume | **CONFIRMED — still present, in a new form** | P0-1. The earlier shape was `facing=False` metadata on a resume; at this SHA the verb is additionally in `SUPPORTED` |
| Preview LinkedIn cadence divergence (1/3/8/14) | **ALREADY FIXED** | no such literal in `src/` or `scripts/`; `src/preview.py:215,234` project `step["day"]` |
| Provider / action-ledger stale state read as zero | **ALREADY FIXED** for the write classes | `src/providerwrites.py:1689-1695` — `UNKNOWN` is a distinct class and "NEVER retryable"; `src/providers/bison.py:1427-1433` fails closed on an unreadable status |
| Provider-level cross-channel stop not runtime-proven | **RUNTIME VERIFICATION REQUIRED** | `src/providerwrites.py:515-530` records that only the LinkedIn→email direction was measured |
| Unsupported claims licensed as facts | **ALREADY FIXED** at the admission rule | `src/packfacts.py:78-121` — only `ADMITTED` reaches the pack |

## UNVERIFIED SUSPICIONS

No P0/P1 severity. Each of these is a shape worth one grep, not a finding.

1. The approval fingerprint does not cover the recipient address, the send day
   or the sender identity (`src/approval.py:59-67`). No path was traced that
   changes a contact's address between approval and staging, so no failure
   scenario is offered.
2. `FREE_MAIL` (`src/enrich.py:417`) has one consumer and is not consulted when
   a research cache key is built (`src/researchpack/cache.py:33`). Whether any
   caller can pass a personal-mail domain as an account domain was not traced.
3. LinkedIn-side pagination and any `campaign_lead_count` equivalent were not
   inspected; only the EmailBison `meta.total` fix was read
   (`src/providers/bison.py:1888-1898`).
4. `src/web/app.py:1586` calls `api.create_campaign(...)`. Whether the web
   surface reaches provider staging outside the factories was not traced.

## FALSE ALARMS

- `FREE_MAIL` is referenced at `src/enrich.py:404`, thirteen lines *above* its
  definition at `:417`. This is not a `NameError`: the reference is inside a
  function body and resolves at call time. Recorded so nobody else spends the
  same two minutes on it.
- `EMAIL_RESUME` being absent from `CONDITIONAL` looked like a second hole next
  to P0-1, but `require_conditional_permission` runs in the non-facing branch
  too (`src/providerwrites.py:2149-2150`); the operation simply has no condition
  registered. The defect is the `facing` flag, not the condition plumbing.
- The many direct `bison.*` / `heyreach.*` calls in `src/bisonfactory.py` and
  `scripts/activate_*.py` looked like gate bypasses. Most are
  `transport=lambda ...` arguments being passed *into* `providerwrites.perform`,
  which is the intended shape.

## TESTS THAT GIVE FALSE CONFIDENCE

### T-1 `tests/test_a_model_call_writes_a_priced_ledger_row.py:184` `test_anthropic_ceiling_refuses_when_exceeded`

- CLAIMED GUARANTEE: its name and docstring — "Set a $1 ceiling, spend $2 worth,
  check REFUSES the next call."
- FAILURE MODE: it makes one real `model.complete()` call, then calls
  `spendledger.check(...)` **by hand** and asserts that raises. It never makes a
  second `complete()` call, so it proves a property of `check`, not of the model
  path — and the model path never calls `check` (P1-1). Delete `_record_spend`
  entirely and the assertion still passes.
- RECOMMENDED NEGATIVE CONTROL: after setting the exceeded ceiling, call
  `model.complete("second call")` and assert it raises `BudgetExceeded` **and**
  that `providers.request` was not invoked (the surrounding tests already stub
  it, so the spy is free).

### T-2 `tests/test_nothing_writes_to_a_provider.py:214` `test_every_http_write_in_the_repository_is_declared`

- CLAIMED GUARANTEE: its failure message — "HTTP writes nobody declared".
- FAILURE MODE: the scanner cannot see a verb carried on a `urllib` `Request`
  object, which is the shape the repo's own transport uses, nor
  `Request(url, data=...)` with no `method=`. Two undeclared POSTs exist at this
  SHA and the test is green (P1-3). A new module copying
  `src/providers/__init__.py:765` and POSTing to a provider would be invisible
  to it.
- RECOMMENDED NEGATIVE CONTROL: a positive control asserting the scanner reports
  `urllib.request.Request(url, method="POST")` and `Request(url, data=b"")`,
  alongside the existing `test_the_scanner_would_notice_one`.

### T-3 `src/campaigns.py:691-709` `CHECKS` as the resume precondition

- CLAIMED GUARANTEE: `orchestrator.resume`'s docstring
  (`src/orchestrator.py:617`) — "Resuming re-checks everything. A pause is not
  undone by forgetting it."
- FAILURE MODE: the 17 checks do not include `eligibility.decide` or any
  suppression read; `src/campaigns.py` never imports `eligibility`. Every check
  can pass while a prospect who replied during the pause is still in the
  campaign. The docstring is the false confidence, and it is load-bearing —
  P0-1 sits directly behind it.
- RECOMMENDED NEGATIVE CONTROL: a test that pauses a campaign, persists an
  unsubscribe for one contact, resumes, and asserts the resume refuses or that
  the contact is excluded.

## RUNTIME VERIFICATION REQUIRED

Ranked. None of these can be settled from source, and none may be settled by
this reviewer.

1. **Does anything running today execute this code at all.** The ~15 loops
   import at process start and do not reload, so every finding above describes
   `b333697`, not the live estate. Compare each loop's process start time
   against the mtimes of the modules it imports, then `git diff` those modules
   for a behavioural change before concluding anything is live.
2. **P0-1 blast radius.** Whether per-lead `EMAIL_STOP_LEAD` had already been
   pushed to EmailBison for anyone who replied during a pause. That decides
   whether the skipped re-check is a latent hole or a live one.
3. **Reverse cross-channel stop.** An email reply stopping a LinkedIn sequence
   at the provider was never measured (`src/providerwrites.py:515-530` says so).
4. **Whether `researchpack`'s Apify actors are still being paid for** despite
   having no production consumer (P1-4) — a ledger read, not a code read.

## TOP 10 FINDINGS

Ordered by production consequence. References only; no new information.

1. **P0-1** — `EMAIL_RESUME` enabled as non-facing: resume skips the suppression
   re-check, the Authorization, the spend gate and the ledger reservation.
2. **T-3** — `orchestrator.resume`'s "re-checks everything" is false; the check
   list contains no suppression read. This is what hid P0-1.
3. **P1-1** — no LLM call is refused at any spend ceiling, and an unknown
   provider writes no ledger row at all.
4. **P1-2** — LinkedIn provider timing is independent of the canonical cadence;
   editing the canonical graph cannot change when LinkedIn sends.
5. **T-1** — the ceiling test proves `check` raises, not that a model call is
   refused.
6. **P1-3** — the static write audit cannot see the transport's own shape; two
   undeclared POSTs are green today.
7. **T-2** — the same test's failure message overstates its guarantee.
8. **P1-4** — `researchpack` is a producer with zero production consumers, and a
   second research store next to `packfacts`.
9. Approval identity is sound and well negative-tested — recorded because "no
   defect found, with the enforcing code cited" is a result, not a blank.
10. The preview cadence divergence is genuinely fixed; preview is a projection.

## SMALLEST FIXES

In the order they should be taken.

1. `src/providerwrites.py:406` — `("email", False, ...)` becomes
   `("email", True, ...)`. Wire the executionguard mint for `EMAIL_RESUME` (this
   is the real work; the flag is one character). Correct the stale prose at
   `:407-409`.
2. `src/orchestrator.py:660-661` — pass `expect_leads` so
   `src/providers/bison.py:1888-1898` can refuse. Correct the "BOTH VERBS ARE
   SEALED" docstring at `:648`.
3. Add the negative control from T-3: pause, suppress, resume, assert refusal.
4. `src/llm.py:275-297` — wrap `complete()` in `spendledger.holding(...)` as
   `src/enrich.py:927` does; let `BudgetExceeded` propagate; narrow the
   `except`; make an unknown provider a named row or a refusal.
5. Add the negative control from T-1: a second `complete()` under an exceeded
   ceiling must raise and must not call `providers.request`.
6. Derive the HeyReach node delays from the canonical `li*` day deltas and
   assert cumulative equality.
7. Extend `CALLS` in `tests/test_nothing_writes_to_a_provider.py` to the
   `Request`-object shape; declare `oidc` and `socketmode` in `ALLOWED`.
8. Decide the canonical research store and either wire `researchpack.build` in
   or retire it.

Reuse over new architecture throughout: every fix above is a flag, an argument,
a `holding(...)` call already used elsewhere, a derivation, or a test. None of
them needs a new module.
