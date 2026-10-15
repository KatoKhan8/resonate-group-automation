# The gates `batch_linkedin_push.py` does not go through — TASK 0030 (GLM-C)

2026-10-15. The task's premise, verified against the code, splits in half:

**"`scripts/batch_linkedin_push.py` posts empty `CONNECTION_REQUEST`
messages"** — TRUE. `config/linkedin/productive-standard.json` (lines 92-98)
holds the cloned graph's first node as `nodeType: CONNECTION_REQUEST` with
`payload: {"messages": [""]}`, and `standard_graph()`
(`scripts/batch_linkedin_push.py:285-299`) posts it as read. The emptiness
is by operator instruction — the graph is a step-for-step clone of client
campaign 565765 ("do not shorten it, do not remove steps"), and note-less
connection requests were that campaign's own design. What ships unchecked is
the fact, not an accident.

**"with no gates at all"** — FALSE, and the honest finding is sharper than
the premise. The script has gates (HALT on reply-stop at 407, `--veto-waived`
at 414, TASK-268 identity verification at 424, `providers.allow_writes` at
464, plan-only default, attested seats). What it does not have is **the
per-lead proof the email path requires** — and the gated LinkedIn paths that
hold exactly that proof already exist in this repository and are imported by
nobody in this script.

## The two sanctioned paths the script bypasses

- **`src/heyreachfactory.py` `ensure_leads` (line 1135)** — the
  campaign-level add. Five gates in order, each refusing by name: killswitch
  (1180), suppression/DNC via `eligibility.must_not_contact` per lead
  (1225), account collision (1266), tenant check (1290), unsupported
  sequence (1300). The `LINKEDIN_ADD_LEAD` execution grant is minted at
  1113/1364/1483, and `heyreach.readback_membership` decides the outcome.
- **`src/liststaging.py` `stage_lead` (line 249)** — the list-level add,
  which is exactly this script's shape (unbound list + `add_leads_to_list`):
  `validate_lead_row` (261), live `assert_list_safe` (262), then
  `providerwrites.perform(LINKEDIN_ADD_LEAD_TO_LIST, ...)` (323-331) with an
  ACCEPTED/DRIFTED/UNKNOWN readback. Its own comment (281-301, "THE WRITE
  GOES THROUGH THE DOOR, NOT ROUND IT") records that calling the transport
  directly skips `require_supported`, the action ledger, the spend ledger,
  the killswitch, and the staged-already idempotency check — a bypass found
  once before, 2026-09-16, TASK-186.

`scripts/batch_linkedin_push.py:494-499` calls `heyreach.add_leads_to_list`
directly. The script's imports (63-65) name neither `heyreachfactory` nor
`liststaging` nor `providerwrites` nor `killswitch`.

## The enumeration

Email-path call sites are in `src/bisonfactory.py` (the `stage()` /
`_ensure_leads` chain). The third column is where the same gate is held on
the sanctioned LinkedIn paths. The fourth is the line in
`scripts/batch_linkedin_push.py` where it is absent.

| # | Gate | Email path | Sanctioned LinkedIn holder | Absent in the push script |
|---|------|-----------|---------------------------|---------------------------|
| 1 | Per-lead suppression / DNC | `_ensure_leads` collision+suppression 2371-2374 | `heyreachfactory.py:1217-1231` (Gate 2, `eligibility.must_not_contact`) | `enrolled_leads()` 107-129 selects on URL + no `campaign_id_linkedin` only (117-121); nothing per-lead before 494 |
| 2 | Killswitch workspace sending | 2392-2396 | `heyreachfactory.py:1179-1184`; inside `providerwrites.perform` (`liststaging.py:281-301` names it) | no killswitch consult anywhere; imports 63-65 |
| 3 | Campaign-scoped execution grant | `executionscope.require(EMAIL_ADD_LEAD)` 2411-2422 | `heyreachfactory` 1113/1364/1483 (`LINKEDIN_ADD_LEAD`); `liststaging` 323-331 (`LINKEDIN_ADD_LEAD_TO_LIST`) | 494-499 reaches the transport with no `providerwrites`/`executionscope` call |
| 4 | Account collision (estate) | 2371-2374 | `heyreachfactory.py:1233-1288` (Gate 3) | nothing between selection and 494 |
| 5 | Approved copy | `_certified_copy` 1483-1588 + missing-copy refusal 2338-2351 | `merge_sequence_copy` refuses missing fallback copy (`config/clients/productive.yaml:409`) | `standard_graph()` 285-299 posts the clone as-read; the `[""]` message ships with no approval, lint, or certification |
| 6 | Dry-run-record refusal | 2334 | `heyreachfactory.py:1172-1174` | absent from 107-129 |
| 7 | Tenant / workspace binding | 187-196 (`bison.bound_workspace`) | `heyreachfactory.py:1290-1298` (Gate 4, `check_tenant`) | no expected-workspace or org-unit comparison in the write loop |
| 8 | Unsupported claims / variable fill | 2336 | `heyreachfactory.py:1300-1303` (Gate 5) | absent |
| 9 | Readback + idempotency | `_find_or_create` 198, pre-attach re-read 2553-2561, `_readback` 228 | `liststaging` readback 182-244 + `perform`'s staged-already; `heyreachfactory` `readback_membership` | the add at 494-499 is never read back; `heyreach.lists()` is read only for name reuse (443-452); the report's `leads` count (511) is rows asked, not rows confirmed |
| 10 | Daily-volume cap refusal | `_ensure_limits` 212 | — (client-side pacing only) | absent as a refusal; PACE=0.4s (460) is rate, not volume |
| 11 | Schedule-window refusal | `_ensure_schedule` 213 | — | absent |
| 12 | Stop-before-leads + re-read | `_ensure_stopped` 225, 2553-2561 | — | DRAFT creation 501-502 is a partial analogue (a DRAFT sends nothing); no re-read before attach |
| 13 | Copy lint / sequence gate / CTA gate | 122 / 154 / 165 | copy gates in `_plan` | absent; `verify_leads` 424 is profile identity, not copy |
| 14 | Veto window as timestamp | `batch1_push.py:84-103` (`--veto-closed` ISO) | — | only `--veto-waived` (414) |

`verify_leads` (TASK-268, script 419-439) deserves its own line of honesty:
it is a real gate the **email** path does not have — the provider-resolved
profile's surname/company/location must match the record, fail-closed. It is
identity proof, not contact permission, and it is not a substitute for any
row above.

The five-step lead classification (CLAUDE.md permanent rule 2,
BLOCKED/ON-HOLD/STARI/COLD/UNKNOWN) has no enforcement module in this
vocabulary anywhere under `src/` (grep for `STARI`: no matches). On this
path it is policy prose with no code behind it; the code-enforceable
per-lead proof is rows 1-4 above.

## The failing test, and its mutation proof

`tests/test_the_linkedin_push_needs_per_lead_proof.py` asserts the required
behaviour at the seam the module owns — the push set `enrolled_leads()`
builds: a lead the per-lead proof refuses (unsubscribed contact;
suppressed-account contact) is never enrolled, and a clean contact still is.
The clean-contact control is load-bearing: a gate that refused everything
would pass the refusal assertions alone.

Measured 2026-10-15 on branch `task-glm-c-2026-10-14`:

- **RED as committed**: 2 failures, both the intended reason — the refused
  contact keys are present in the enrolled set. The clean control passes,
  which is the proof that the failure is the gate's absence and not a
  fixture or import error, and that no other guard (HALT, `verify_leads`)
  fired first — neither is in `enrolled_leads()`'s path.
- **Mutant**: five lines wired into `enrolled_leads()` consulting
  `channels.linkedin_verdict(record, contact)` — the canonical per-lead
  verdict (`src/channels.py:210`: operator-excluded, unsubscribed,
  suppressed, duplicate, canonical URL). Result: 3/3 pass, clean control
  included. The test detects the gate and only the gate.
- **Reverted**: `git diff` on the script empty afterwards; the RED restored
  with the same two intended failures.

The task forbids wiring the gate in, so the mutant is not committed — the
red test and this document are the deliverable. The script was never run;
no LinkedIn call was made (the test imports the module and patches
`src.campaigns.load` / `src.store.load`; no `heyreach` network function is
invoked).

## UNKNOWN, and the authority that would settle it

Whether `heyreach.add_leads_to_list` self-gates internally cannot be
determined here: the standing rules of this lane forbid reading
`src/providers/*`. The authority is `src/providers/heyreach.py` itself, read
under a task that names it. Committed circumstantial evidence says it does
not: `liststaging.stage_lead` routes the same transport through
`providerwrites.perform` explicitly and documents (281-301) exactly what a
direct call skips — which would be redundant if the transport self-gated —
and `docs/CANARY-GATE-REPORT-2026-09-16.md:324` treats `ensure_leads` as
"the campaign-level path", i.e. a different, gated route to a similar write.
