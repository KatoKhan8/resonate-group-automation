PRIORITY: HARD CANARY GATE — TASK-564

# THE PROVIDER WRITE SURFACE

    CLAIM        every path that can mutate a prospect at EmailBison or
                 HeyReach is enumerated, with its enforcement stated
    AUTHORITY    the code at the SHA below, read directly; the empirical
                 probes are recorded inline and were run from a fresh process
    MEASURED AT  master ce6715d1, 2026-09-29
    STATE        READ-ONLY AUDIT. No patching. Provider writes 0.
                 sending.live false. Nothing sent by this work.

`work/queue.jsonl` was written by this session's APPROVED run only (the
operator approval stamp), never by this audit. `work/campaigns.jsonl`
sha256 `00B6F103BBDB469F`, unchanged.

---

## THE THREE SEEDED FINDINGS

### 1. "`refuse_unauthorized_write` is ROOT-relative" — **REFUTED, and the
###    real weakness is different and worse to reason about**

It is not path-relative at all. `providers/__init__.py:733` gates on
`normalise_method`, `is_prospect_facing(url)`, `is_declared_read` and
`writes_allowed(url)` — an environment variable and a ContextVar, no
filesystem path anywhere. Running it from a detached worktree changes
nothing about its logic.

**What IS true, measured from a fresh process:**

    from src import providers                      # only this
    providers._prospect_facing_hosts            -> []
    providers.is_prospect_facing(bison_url)     -> False
    providers.refuse_unauthorized_write("POST", bison_url)  -> NOT REFUSED

    from src.providers import bison, heyreach      # now import them
    providers._prospect_facing_hosts
        -> ['api.heyreach.io', 'send.resonategroup.co']
    providers.refuse_unauthorized_write("POST", bison_url)
        -> ProviderWriteRefused

**The guard is armed by IMPORT.** `_prospect_facing_hosts` starts empty and
is populated by each provider module calling `guard_prospect_facing` at
import time. A caller that reaches the transport WITHOUT importing
`bison`/`heyreach` — `providers.request("POST", "https://send.resonate
group.co/api/...")` with a hardcoded URL — passes the host test, returns
early, and opens the socket.

**Reachability today:** every production path imports its provider module by
construction, so the guard is armed on all of them. The exposure is a scratch
script or an audit agent that hardcodes a URL, which is the exact shape of the
2026-09-20 incident this guard was built for. **Classified: REAL, NARROW,
NOT REACHABLE FROM A PRODUCTION ENTRY POINT.** Remediation belongs in its own
task — register the guarded hosts at `providers` import time rather than at
provider-module import time — and is NOT done here.

### 2. "An audit agent paused live 487 by importing src and calling through"
###    — **CLOSED for every primitive that goes through a provider module**

With `bison`/`heyreach` imported, an unauthorised `POST`/`PUT`/`PATCH`/
`DELETE` to either host raises `ProviderWriteRefused` before the socket.
Opting in is explicit and narrow: `RESONATE_PROVIDER_WRITES=1` or
`with providers.allow_writes("<reason>")`. The ContextVar is thread-isolated
on purpose, so a worker thread spawned inside an `allow_writes` block is
refused rather than inheriting it.

The residual is finding 1's route, which does not go through a provider
module at all.

### 3. "`_refuse_sequence_gate` has no tenant guard while `offers.py` is
###    single-tenant" — **CONFIRMED**

`offers._offers_path()` hardcodes `clients.path_for("productive")` and
`productive-offers.yaml`, so `offers.load()` returns Productive's offers
whatever client is being pushed, and `bisonfactory._refuse_sequence_gate`
hands them to `sequencegate.check` for any tenant. One client's approved
ladder is therefore enforced against every client's push.

**Impact on the Rachele canary: NONE.** The client IS `productive`, so the
ladder enforced is its own. This is a multi-tenant correctness defect and a
canary blocker only when a second tenant exists.

---

## THE PRIMITIVES

`providerwrites.perform` is the central door: it wraps `_perform` and writes a
spend/audit row on the performed, refused, unverified AND failed paths.
`SUPPORTED` — the operations `perform` will accept — is today
`LINKEDIN_PAUSE`, `EMAIL_PAUSE`, `EMAIL_STOP_LEAD` and `LINKEDIN_STOP_LEAD`.
**Every other primitive below reaches the provider outside that door**, and is
governed by the transport guard, the killswitch and the factory refusals
instead.

    primitive            entry point                      central door  approval  canonical plan  copy/claim gates      suppression        ledger row   scratch-callable  production active
    email create lead    bison.create_lead                NO            no        yes, via       copylint, claims,     via               transport    yes, if bison     YES - the canary
                         (via bisonfactory._ensure_leads)                         derive_bison   lint, sequencegate,   _refuse_colliding  log only     is imported       path
                                                                                  _payload       approval fingerprint  _leads
    email attach lead    bison.attach_leads               NO            no        yes            same as above         same               transport    yes               YES
                         (_ensure_leads)                                                                                                  log only
    email set sequence   bison.set_sequence               NO            no        yes            sequencegate,         n/a                transport    yes               YES (staging)
                         (bisonfactory.stage)                                                    copylint                                 log only
    email create camp.   bison.create_campaign            NO            no        n/a            n/a                   n/a                transport    yes               YES (staging)
    email set limits     bison.set_limits                 NO            no        n/a            n/a                   n/a                transport    yes               YES
    email set schedule   bison.set_schedule               NO            no        n/a            n/a                   n/a                transport    yes               YES
    email update lead    bison.update_lead                NO            no        yes            approval fingerprint  n/a                transport    yes               YES
    email pause          bison.pause_campaign             YES           yes       n/a            n/a                   n/a                FULL row     refused w/o auth  YES
    email resume         bison.resume_campaign            NO*           n/a       n/a            n/a                   n/a                transport    yes               SEALED - operator
                                                                                                                                          log only                       grant required
    email activate       EMAIL_ACTIVATE                   declared      yes       n/a            n/a                   n/a                FULL row     refused           NOT in SUPPORTED
    email stop lead      bison.stop_lead                  YES           yes       n/a            n/a                   n/a                FULL row     refused w/o auth  YES (cross-channel)
    linkedin add lead    heyreach.add_leads_to_campaign   YES           yes       yes, via       copylint, claims,     heyreachfactory    FULL row     refused w/o auth  YES
                         (heyreachfactory)                                        derive_heyreach lint, approval        refusals
    linkedin add to list heyreach.add_leads_to_list       YES           yes       yes            same                  same               FULL row     refused           YES
    linkedin create list heyreach.create_list             YES           yes       n/a            n/a                   n/a                FULL row     refused           YES
    linkedin create camp heyreach.create_campaign         YES           yes       n/a            n/a                   n/a                FULL row     refused           YES
    linkedin set seq.    heyreach.set_sequence            YES           yes       yes            sequencegate          n/a                FULL row     refused           YES
    linkedin add senders heyreach.add_senders             YES           yes       n/a            n/a                   n/a                FULL row     refused           YES
    linkedin set sched.  heyreach.set_schedule            YES           yes       n/a            n/a                   n/a                FULL row     refused           YES
    linkedin pause       heyreach.pause_campaign          YES           yes       n/a            n/a                   n/a                FULL row     refused w/o auth  YES
    linkedin resume      heyreach.resume_campaign         NO*           n/a       n/a            n/a                   n/a                transport    yes               SEALED
    linkedin activate    heyreach.activate_campaign       declared      yes       n/a            n/a                   n/a                FULL row     refused           NOT in SUPPORTED
    linkedin stop lead   heyreach.stop_lead_in_campaign   YES           yes       n/a            n/a                   n/a                FULL row     refused w/o auth  YES
    raw transport        providers.request / _urllib_     NO            no        no             none                  none               refusal log  YES - see          the residual
                         transport                                                                                                        only          finding 1          bypass

`NO*` = not in `SUPPORTED`, so `perform` would refuse it; the function is
nonetheless importable and is governed only by the transport guard.

## WHERE A MISTAKE REACHES A REAL PERSON

1. **`bison.create_lead` / `attach_leads` via `_ensure_leads`.** Outside the
   central door by design and documented as such at `bisonfactory.py:2050`.
   Compensating controls: the workspace killswitch is consulted immediately
   before any lead is created (`sending.live` must be true), collision refusal
   runs against the workspace, and the transport guard still applies. **A lead
   created here is one step from a send.**
2. **`bison.resume_campaign` / `heyreach.resume_campaign`.** Not in
   `SUPPORTED`, so no Authorization object is required by `perform` because
   `perform` is not on the path. A resume on a campaign with rows is a send.
   The 487 grant is recorded as SPENT.
3. **The raw transport (finding 1).** No plan, no gates, no suppression, no
   ledger row beyond a refusal log that does not fire.

## WHAT THIS AUDIT DID NOT ESTABLISH

- Whether `attach_leads`' idempotency holds under a partial failure; not read.
- Whether every HeyReach POST-that-is-a-read is on `READ_ROUTES_ALL`; the
  module documents the class, the list was not enumerated. **UNKNOWN.**
- Scheduling primitives on HeyReach beyond `set_schedule`. **UNKNOWN.**
