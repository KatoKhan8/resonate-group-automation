PRIORITY: HARD CANARY GATE — TASK-564

# THE PROVIDER WRITE SURFACE (FRESH AUDIT)

    CLAIM        every path that can mutate a prospect at EmailBison or
                 HeyReach is enumerated, with its enforcement stated
    AUTHORITY    the code at the SHA below, read directly; no empirical
                 provider probes were made (sending.live false, freeze active)
    MEASURED AT  qwen-worker-2-r9 840928f3, 2026-10-03
    STATE        READ-ONLY AUDIT. No patching. Provider writes 0.
                 sending.live false. All Resonate campaigns paused.

Supersedes `PROVIDER-WRITE-SURFACE-2026-09-29.md`. That audit was taken at
ce6715d1 and reported `SUPPORTED` as four verbs. It was already stale: the
tuple held sixteen verbs at the time of this audit, and the import-order
defect it found as finding 1 has since been closed by `KNOWN_PROSPECT_FACING_HOSTS`
seeded at `providers/__init__.py` import time (line ~389).

---

## THE THREE SEEDED FINDINGS

### 1. "`refuse_unauthorized_write` is ROOT-relative and protects nothing
###    from a worktree" — **REFUTED**

`ROOT` (providers/__init__.py:17) is used only for locating `config/.env`.
The write guard itself — `refuse_unauthorized_write` at line 769 — checks
`normalise_method`, `is_prospect_facing(url)`, `is_declared_read` and
`writes_allowed(url)`. None of these consult a filesystem path. Running from
a worktree changes nothing about the guard's logic.

**The real weakness the 09-29 audit found was import-order dependency:**
`_prospect_facing_hosts` was empty until `bison`/`heyreach` were imported.
**That is now CLOSED.** `KNOWN_PROSPECT_FACING_HOSTS` at line ~380 seeds
both hosts at `providers/__init__.py` import time:

    KNOWN_PROSPECT_FACING_HOSTS = (
        "send.resonategroup.co",      # EmailBison
        "api.heyreach.io",            # HeyReach
    )
    for _host in KNOWN_PROSPECT_FACING_HOSTS:
        guard_prospect_facing(_host)

A fresh `import src.providers` now arms the guard without importing either
provider module. The provider modules still call `guard_prospect_facing` for
config-overridden bases; that call is now additive, not load-bearing.

**VERDICT: CLOSED.** The bypass the 09-29 audit named — a scratch script
that hardcodes a URL without importing a provider module — no longer works.

### 2. "An audit agent paused live 487 by importing src and calling through"
###    — **CLOSED for every primitive**

With the import-order fix above, the transport guard at
`refuse_unauthorized_write` fires before the socket on ANY unauthorised
POST/PUT/PATCH/DELETE to either prospect-facing host. The guard is armed at
`providers` import, so every code path that can reach the transport has the
guard active. Opting in requires an explicit act: `RESONATE_PROVIDER_WRITES=1`
or `with providers.allow_writes("<reason>")`. The ContextVar is thread-isolated.

**VERDICT: CLOSED.** The 2026-09-20 incident route is no longer reachable.

### 3. "`_refuse_sequence_gate` has no tenant guard while `offers.py` is
###    single-tenant" — **CONFIRMED, UNCHANGED**

`offers._offers_path()` hardcodes `clients.path_for("productive")` and
`productive-offers.yaml`. `offers.load()` returns Productive's offers
whatever client the campaign belongs to. `bisonfactory._refuse_sequence_gate`
hands those offers to `sequencegate.check` for any tenant.

**Impact today: NONE.** The only client is `productive`, so the ladder
enforced is its own. This is a multi-tenant correctness defect that becomes
a canary blocker when a second tenant exists.

**VERDICT: CONFIRMED. Not a current risk. A future-tenant blocker.**

---

## THE TWO DOORS

The prior audit said `bisonfactory` calls eight provider write functions
directly, bypassing `perform`. That is still true and is documented at
`providerwrites.py:1-15` and `docs/TWO-DOORS-2026-09-16.md`. The two doors
are:

1. **`providerwrites.perform`** — the central door. 16 operations in
   `SUPPORTED`. Requires an `Authorization` for prospect-facing ops, runs
   conditional predicates, ownership checks, the staging-repeat guard,
   readback comparison, ledger reservation and settlement.

2. **`bisonfactory` direct calls** — eight EmailBison primitives that call
   `bison.*` functions directly, bypassing `perform`. Governed by the
   transport guard, the workspace killswitch, factory-level refusals
   (copylint, sequencegate, CTA gate, collision), and (for leads) the
   execution scope.

HeyReach routes ALL writes through `perform`. The gap is EmailBison-only.

---

## THE PRIMITIVES — ONE ROW PER WRITE PATH

### LEGEND

- **central door**: does it go through `providerwrites.perform`?
- **prospect-facing**: can this mutation reach a real person?
- **operator auth**: is an `Authorization` object required?
- **plan-derived**: must the payload derive from a canonical SequencePlan?
- **copy/claim gates**: which gates run before it, by name
- **suppression**: is eligibility/suppression checked?
- **ledger effect**: what row does it write?
- **scratch-callable**: could `import src` + call reach it?
- **production active**: is it reachable from a production entry point today?

### EmailBison primitives

    primitive           entry point                  central  prospect  operator  plan-   copy/claim gates      suppression  ledger       scratch-   production
                                                       door     facing    auth      derived                                           callable   active
    ─────────────────   ─────────────────────────    ───────  ────────  ────────  ──────  ────────────────────   ───────────  ───────────  ─────────  ──────────
    create campaign     bison.create_campaign        YES      NO        YES       NO      none                  n/a          FULL row     YES        YES(staging)
                        via perform                                                                                                     (refused
                                                                                                                                              w/o auth)

    set limits          bison.set_limits             NO       NO        NO        NO      none                  n/a          transport    YES        YES
                        via _ensure_limits                                                                                              log only

    set schedule        bison.set_schedule           NO       NO        NO        YES     none                  n/a          transport    YES        YES
                        via _ensure_schedule                                                                                           log only

    attach senders      bison.attach_senders         NO       NO        NO        NO      none                  n/a          transport    YES        YES
                        via _ensure_senders                                                                                             log only

    ensure variables    bison.ensure_custom_         NO       NO        NO        NO      none                  n/a          transport    YES        YES
                        variables via                                                                                                  log only
                        _ensure_leads

    create lead         bison.create_lead            NO       YES*      NO        YES     copylint, claims,     via          transport    YES        YES
                        via _ensure_leads                                    via      lint, sequencegate,    _refuse_       log only                (canary
                                                                                       approval fingerprint   colliding                path)
                                                                                                                _leads

    attach leads        bison.attach_leads           NO       YES*      NO        YES     same as above         same         transport    YES        YES
                        via _ensure_leads                                                                                              log only

    update lead         bison.update_lead            NO       YES*      NO        YES     approval fingerprint  n/a          transport    YES        YES
                                                                                                                                      log only

    set sequence        bison.set_sequence           YES      NO        YES       YES     sequencegate,         n/a          FULL row     YES        YES(staging)
                        via perform                                                              copylint

    pause               bison.pause_campaign         YES      NO        YES       NO      none                  n/a          FULL row     YES        YES
                        via perform                                                                                                   (refused
                                                                                                                                              w/o auth)

    resume              bison.resume_campaign        YES      YES       YES       NO      none                  n/a          FULL row     YES        SEALED
                        via perform                                                                                                   (operator
                                                                                                                                              grant
                                                                                                                                              required)

    stop lead           bison.stop_lead              YES      NO        YES       NO      none                  n/a          FULL row     YES        YES
                        via perform                                                                                                   (refused
                                                                                                                                              w/o auth)

    activate            EMAIL_ACTIVATE               YES      YES       YES       NO      none                  n/a          FULL row     YES        NOT in
                        via perform                                                                                                   (refused)    SUPPORTED
                                                                                                                                              (declared
                                                                                                                                              but not
                                                                                                                                              enabled
                                                                                                                                              generally)

`YES*` = prospect-facing by nature (creates/modifies a lead that a sequence
acts on), but gated by factory-level controls rather than `perform`'s
Authorization.

### HeyReach primitives

    primitive           entry point                  central  prospect  operator  plan-   copy/claim gates      suppression  ledger       scratch-   production
                                                       door     facing    auth      derived                                           callable   active
    ─────────────────   ─────────────────────────    ───────  ────────  ────────  ──────  ────────────────────   ───────────  ───────────  ─────────  ──────────
    pause               heyreach.pause_campaign      YES      NO        YES       NO      none                  n/a          FULL row     YES        YES
                        via perform                                                                                                   (refused
                                                                                                                                              w/o auth)

    start empty         heyreach.start_campaign      YES      NO        YES       NO      none                  n/a          FULL row     YES        YES
                        via perform,                                        via
                        CONDITIONAL                   conditional

    set sequence        heyreach.set_sequence        YES      NO        YES       YES     sequencegate          n/a          FULL row     YES        YES

    create list         heyreach.create_list         YES      NO        YES       NO      none                  n/a          FULL row     YES        YES

    create campaign     heyreach.create_campaign     YES      NO        YES       NO      none                  n/a          FULL row     YES        YES
                        via perform,                                        via
                        CONDITIONAL                   conditional

    add lead to list    heyreach.add_leads_to_list   YES      NO        YES       YES     copylint, claims,     via          FULL row     YES        YES
                        via perform,                   via      lint, approval     factory
                        CONDITIONAL                   conditional                        refusals

    add lead to camp    heyreach.add_leads_to_       YES      YES       YES       YES     copylint, claims,     via          FULL row     YES        YES
                        campaign via perform,         via      lint, approval     factory
                        CONDITIONAL                   conditional                        refusals

    add senders         heyreach.add_senders         YES      NO        YES       NO      none                  n/a          FULL row     YES        YES
                        via perform

    remove senders      heyreach.remove_senders      NOT in   NO        n/a     NO      none                  n/a          n/a          YES        NOT in
                        SUPPORTED                                                                                                        SUPPORTED

    stop lead           heyreach.stop_lead_in_       YES      NO        YES       NO      none                  n/a          FULL row     YES        YES
                        campaign via perform                                                                                           (refused
                                                                                                                                              w/o auth)

    resume              heyreach.resume_campaign     NOT in   YES       n/a     NO      none                  n/a          transport    YES        SEALED
                        SUPPORTED                                                                                       log only

    activate            heyreach.start_campaign      YES      YES       YES       NO      none                  n/a          FULL row     YES        YES
                        via perform,                  via                                                             (refused
                        CONDITIONAL                   conditional                                                    w/o auth)
                                                                                                                       for non-
                                                                                                                       canary

    set schedule        NOT in SUPPORTED             NOT in   NO        n/a     NO      none                  n/a          n/a          YES        NOT in
                                                                                                                                        SUPPORTED

### Raw transport

    primitive           entry point                  central  prospect  operator  plan-   copy/claim gates      suppression  ledger       scratch-   production
                                                       door     facing    auth      derived                                           callable   active
    ─────────────────   ─────────────────────────    ───────  ────────  ────────  ──────  ────────────────────   ───────────  ───────────  ─────────  ──────────
    raw HTTP            providers._urllib_           NO       YES       NO        NO      none                  none         refusal log  YES        the
                        transport                                                                                                        only        residual
                                                                                                                                        via         bypass
                                                                                                                                        declared
                                                                                                                                        reads

---

## WHAT CHANGED SINCE THE 09-29 AUDIT

1. **SUPPORTED grew from 4 to 16 verbs.** The prior audit listed
   `LINKEDIN_PAUSE, EMAIL_PAUSE, EMAIL_STOP_LEAD, LINKEDIN_STOP_LEAD`.
   The current tuple adds: `EMAIL_RESUME, EMAIL_CREATE_CAMPAIGN,
   EMAIL_SET_SEQUENCE, LINKEDIN_SET_SEQUENCE, LINKEDIN_ADD_LEAD,
   LINKEDIN_START_EMPTY_FOR_STAGING, LINKEDIN_ADD_LEAD_TO_LIST,
   EMAIL_ASSIGN_SENDER, EMAIL_ACTIVATE, LINKEDIN_CREATE_CAMPAIGN,
   LINKEDIN_ACTIVATE, LINKEDIN_CREATE_LIST`.

2. **Import-order guard CLOSED.** `KNOWN_PROSPECT_FACING_HOSTS` seeds both
   hosts at `providers/__init__.py` import time. The scratch-script bypass
   the 09-29 audit named no longer works.

3. **`require_resonate_os_campaign` added.** Every `perform` path — both
   prospect-facing and staging — now refuses unless the destination is a
   ledger-recorded Resonate OS campaign. Internal Resonate campaigns are
   never touched. Unknown campaigns are refused. This runs BEFORE the
   transport, BEFORE the authorization is spent.

4. **`EMAIL_ACTIVATE` and `LINKEDIN_ACTIVATE` are in SUPPORTED**, each
   CONDITIONAL on a single named campaign. The prior audit said "NOT in
   SUPPORTED" for activate; that was wrong even then.

---

## WHERE A MISTAKE REACHES A REAL PERSON

Ranked by blast radius, most dangerous first:

1. **`bison.create_lead` + `bison.attach_leads` via `_ensure_leads`.**
   Outside the central door by design. Compensating controls: workspace
   killswitch (`sending.live` must be true), execution scope
   (`executionscope.require`), collision refusal against the workspace,
   copylint, sequencegate, approval fingerprint, blank-render check, and
   the transport guard. **A lead created here is one step from a send.**
   The killswitch and scope are the meaningful gates; the transport guard
   is the backstop.

2. **`bison.update_lead` via `_ensure_leads`.** Rewrites custom variables
   carrying approved copy onto an existing lead. Outside `perform`. Gated
   by approval fingerprint check and the transport guard. **An incorrect
   update puts wrong words on a lead that is already attached.**

3. **`bison.resume_campaign`.** In `SUPPORTED` as `EMAIL_RESUME`, goes
   through `perform`, requires an Authorization. A resume on a campaign
   holding leads is a send. The 487 grant is SPENT. Current grants:
   `productive-email-control-v3` (campaign 485 replacement) and
   `productive-email-us-cohort-v1` (second cohort).

4. **`bison.set_limits`, `bison.set_schedule`, `bison.attach_senders`,
   `bison.ensure_custom_variables`.** Outside `perform`. Staging only —
   none of these directly sends — but a wrong cap or schedule on a
   campaign that is later activated determines how many people receive
   messages and when.

5. **The raw transport.** A `providers.request("POST", url, ...)` call
   that bypasses both `perform` and the provider modules' `_post`/`_write`
   helpers. Governed only by the transport guard. The import-order fix
   means the guard is now armed for any caller that imports `providers`,
   which is every path that can reach the transport.

---

## WHAT THIS AUDIT DID NOT ESTABLISH

- Whether `attach_leads`' idempotency holds under partial failure. UNKNOWN.
- Whether every HeyReach POST-that-is-a-read is on `READ_ROUTES_ALL`. The
  module documents the class; the complete list was not enumerated. UNKNOWN.
- Whether `heyreach.set_schedule` exists as a primitive. The route
  `/campaign/UpdateSchedule` is deliberately NOT on `WRITE_ROUTES` because
  there is no read route to verify it. NOT IMPLEMENTED.
- The exact set of campaigns covered by each `CONDITIONAL` predicate at the
  moment of this audit. The predicates read provider state live; the answer
  changes moment to moment.

---

## THE ENFORCEMENT LAYERS, IN ORDER

For a write that goes through `perform`:

    1. `require_supported`         — operation is in SUPPORTED
    2. Authorization check         — genuine object, right channel, right op
    3. `_require_approved_words`   — fingerprint covers the copy
    4. `require_conditional_       — campaign state at the provider
       permission`
    5. `require_resonate_os_       — destination is ours, not internal
       campaign`
    6. `authorization.spend()`     — one token, one write
    7. Ledger reservation check    — ATTEMPTED state must exist
    8. `revalidate`                — re-check suppression, eligibility
    9. Transport                   — the actual write
   10. Readback                    — read provider state back
   11. Classify                    — ACCEPTED / DRIFTED / UNKNOWN
   12. Touch record                — confirmed touch before ledger settle
   13. Ledger settle               — SENT / UNRESOLVED

For a write that bypasses `perform` (bisonfactory direct calls):

    1. Factory refusals            — copylint, sequencegate, CTA, collision
    2. Workspace killswitch        — `sending.live` must be true
    3. Execution scope             — `executionscope.require` (leads only)
    4. Transport guard             — `refuse_unauthorized_write`
    5. Provider-module allowlist   — `WRITE_ROUTES` / `_allow`

The second list is shorter and does not include approval fingerprint,
readback, ledger reservation, or touch recording. That is the gap the
two-door document names.
