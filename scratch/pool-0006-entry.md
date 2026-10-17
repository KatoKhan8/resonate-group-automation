# POOL 0006 — does the live send path bypass the company-fatigue hold?

**Ref**: `93711460` (HEAD of `task-pool-0240-by-attribution-2026-10-17`)
**Brief**: `pool/0006`
**Instrument**: `scratch/pool-0006-scratch/harness.py` (both-answer control) and
`scratch/pool-0006-scratch/census.py` (denominator sweep)

## The one question

> On the refs canary would actually send from, does any send path reach the
> company-fatigue hold, and would an over-fatigued account be refused?

## The three-line answer

1. **The guard is correct.** With fresh (now-relative) dates, `_account_fatigue`
   returns `held:account_fatigue` for an over-fatigued account, and the harness
   reproduces it on both contacts of the same company. The three red tests in
   `tests/test_red_team_tonights_guards.py` are a **stale-date fixture problem**,
   not a defect in the guard — their `2026-09-09` events are 38 days old and the
   7-day rolling window drops every one of them.
2. **The LinkedIn canary's *enrollment* path (`heyreachfactory.ensure_leads`) is
   GATED per lead** — it calls `executionguard.authorize(LINKEDIN_ADD_LEAD)` for
   each contact, which calls `eligibility.decide`, which calls `_account_fatigue`.
   An over-fatigued account is refused *at enrollment*.
3. **The EmailBison path (`bisonfactory._ensure_leads`) is UNGATED** — the code at
   `src/bisonfactory.py:2577` says explicitly: *"`_ensure_leads` calls
   `bison.create_lead` and `bison.attach_leads` directly, bypassing
   `executionguard.authorize()` and every gate it runs"*. The substitute checks
   are collision, killswitch and executionscope. **Fatigue is not among them.**
4. **The activation step is GATED but only for one lead.** Each of
   `scripts/activate_linkedin_canary.py`, `activate_linkedin_cohort.py`,
   `activate_linkedin_cohort_b.py`, `activate_control_campaign_v3.py` and
   `activate_us_cohort_campaign.py` calls `executionguard.authorize` once before
   `heyreach.start_campaign` / `activate_campaign` / `bison.resume_campaign` —
   with a single `(rec, contact)` pair. The authorization is per-lead, but the
   activation is per-campaign. **Leads beyond the one named in the authorization
   have no fresh fatigue check at the moment of activation.**
5. **After activation, the provider sends on its own schedule. There is no
   system-side per-send fatigue re-check.** EmailBison and HeyReach each run
   their own queue; a lead that was under the limit at enrollment can grow past
   it while the provider's scheduler is firing.

## The denominator

Measured at `93711460`, `src/` + `scripts/`:

| class | count | notes |
|---|---:|---|
| direct provider-write sites | 61 | every `bison.<verb>(...)` and `heyreach.<verb>(...)` call |
| REACHABLE-DEFAULT | 56 | can be invoked with no flag, env var or exception lift |
| DEAD / PROBE | 5 | `make_481_inert.py`, `probe_list_staging.py` |
| SEALED | 0 | `LINKEDIN_ADD_LEAD`'s CONDITIONAL predicate is reachable in code, just not true of any live campaign today |
| fatigue CONSULTED at call site | **0** | no call site reaches `eligibility.decide` inside the provider call |
| fatigue CONSULTED in enclosing flow | 6 | `heyreachfactory.ensure_leads` (per lead), 5 activation scripts (once each) |
| fatigue NOT-CONSULTED, REACHABLE | 50 | every other reachable site |
| direct `eligibility.decide` callers | 16 | in `src/` + `scripts/` |
| direct `executionguard.authorize` callers | 10 | the gating entry point |

## The harness control

`scratch/pool-0006-scratch/harness.py` runs both paths against the same
over-fatigued record:

```
=== over-fatigued, GATED path ===
  contact: a  verdict: held  reasons: ['held:account_fatigue']  classified: GATED
  contact: b  verdict: held  reasons: ['held:account_fatigue']  classified: GATED

=== over-fatigued, UNGATED path ===
  contact: a  result: {'sent': True, 'reason': None}  classified: UNGATED
  contact: b  result: {'sent': True, 'reason': None}  classified: UNGATED

=== classifier discriminates ===
  GATED path    : GATED  (the hold was consulted)
  UNGATED path  : UNGATED  (the hold was bypassed)
  PASS: the instrument prints both answers

=== the specific finding ===
  _account_fatigue on over-fatigued contact a: held:account_fatigue
  _account_fatigue on over-fatigued contact b: held:account_fatigue
```

With now-relative dates, the guard works, it sees both contacts of the same
company, and the classifier prints the opposite answer for the bypassing path.

## Why the three tests are red (and what that does and does not mean)

`TheFatigueHoldCannotBeSidestepped` in
`tests/test_red_team_tonights_guards.py` uses:

```python
"at": "2026-09-09T10:00:00+00:00"
```

for every event. The 7-day window is measured from `store.now()`, which on
2026-10-17 is 38 days later. `_within_week` drops every touch as outside the
window, and `account_check` reports 0 recent touches. The guard is doing
exactly what it claims to do; the test data is not "recent".

That is a **fixture problem**, not a guard defect. With the same record shape
and now-relative dates, the guard returns `held:account_fatigue` (the harness
proves it). The fix is to make the dates dynamic, not to weaken the assertion.

The brief forbids changing the guard or its tests. This entry names the
cause and leaves the code alone.

## The risk that survives

The brief asked whether an over-fatigued account would be refused. The answer
is **channel-dependent**:

- **LinkedIn (HeyReach) enrollment through `heyreachfactory.ensure_leads`**: yes,
  refused — `authorize` runs the fatigue check per lead.
- **EmailBison enrollment through `bisonfactory._ensure_leads`**: no, not asked —
  the code documents the bypass.
- **Activation of either channel**: yes, asked — but only for one lead. The
  other members of the audience ride on the activation decision made for
  somebody else.
- **Per-send, after activation**: no — the provider sends on its own schedule
  and this system does not re-check.

An account that was under the limit at enrollment, grew past it while the
provider's scheduler was firing, and was enrolled through EmailBison rather
than HeyReach, would not be stopped by anything in this codebase. That is the
surviving risk.

## OPERATOR

The brief's question is a measurement. Three operator calls fall out of it:

1. **`bisonfactory._ensure_leads` bypasses `executionguard.authorize`.** The
   code's own comment at `src/bisonfactory.py:2577` names the bypass. The
   substitute checks (collision, killswitch, executionscope) are real but do
   not include fatigue. Whether to wire `authorize` in, or to add an explicit
   `fatigue.account_check` call, is an operator call.
2. **Activation authorizes one lead and starts the whole campaign.** Each of
   the five activation scripts mints a single `Authorization` for one
   `(rec, contact)` pair and then calls `perform(LINKEDIN_ACTIVATE)` or
   `bison.resume_campaign`. The other members of the audience are not
   fatigue-checked at activation time. Whether that is acceptable, or whether
   activation should be per-lead, is an operator call.
3. **The three red tests in `test_red_team_tonights_guards.py`.** The guard is
   correct and the fixture is stale. The brief forbids fixing this in-line;
   flagging it so a later lane can repair the fixture under a separate brief
   is the minimal operator-visible action.

None of these are wiring a guard, changing a gate or lifting a refusal — they
are decisions about whether the canary may proceed with the defect open.

## Files

- `scratch/pool-0006-scratch/harness.py` — both-answer control
- `scratch/pool-0006-scratch/census.py` — the denominator sweep
- `scratch/pool-0006-scratch/census.out` — raw census output at `93711460`
