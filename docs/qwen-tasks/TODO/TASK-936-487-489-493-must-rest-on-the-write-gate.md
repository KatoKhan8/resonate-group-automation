PRIORITY: P1
SIZE: M
DEPENDS: task-internal-campaign-guard

# TASK-936 — Campaigns 487/489/493 must rest on the write gate, not on three external conditions

Opened by operator decision, 2026-10-01: "487/489/493 na write gateu: zasebni zadatak,
otvori ga, ne sad."

## The standing assumption that was wrong

It was believed that 487/489/493 are untouchable. Measured on d98c83ce with a transport and
readback that raise if touched — so the evidence is effect, not log — `bison.resume` and
`bison.assign_sender` PASS ownership for all three and reach transport today.

What actually holds them is three conditions, none of which is the write gate:
- the killswitch
- `sending.live=false`
- stale approvals

The internal-campaign guard (`config/internal-campaigns.txt`, default REFUSE, read on every
call with no cache) deliberately says nothing about them, because they are `resonate_os`
rather than a client tenant.

So the rule "do not touch 487/489/493" currently rests on three things that can each be
changed independently of the write path, by someone who is not thinking about these three
campaigns at all.

## Task

Make the protection a property of the write gate, so that flipping `sending.live`, clearing
the killswitch, or refreshing an approval does not by itself make these three writable.

## Acceptance

1. A table of effect, not of log, for every verb that can reach these campaigns: with the
   killswitch off, `sending.live=true`, and a fresh approval, each verb is still REFUSED by
   the gate. Prove it with a transport that raises on contact.
2. The refusal names the campaign and the reason. A refusal that cannot name its destination
   is the hole this is meant to close.
3. A negative control that actually works: remove the protecting line and the same write
   reaches transport again. Without this the test proves nothing.
4. Deleting the guard call breaks tests on EFFECT, not only on message text.
5. State explicitly whether the mechanism is the same list as `config/internal-campaigns.txt`
   or a second one. If it is a second list, say why one list cannot serve both, because two
   lists that can disagree is the defect class this repo keeps rediscovering.
6. READ-ONLY toward providers.

## Known adjacent hole, do not fix here, but do not pretend it is closed

`src/bisonfactory.py` has eight calls that go to the bare provider, bypassing `perform`:
`set_limits`, `set_schedule`, `attach_senders`, `ensure_custom_variables`, `update_lead` (x2),
`create_lead`, `attach_leads`, `pause_campaign`. In `scripts/` the bypassers are
`batch_linkedin_push.py` (4 calls), `batch_activate.py`, `linkedin_activate.py`,
`make_481_inert.py`, `resume_487.py`, `batch_linkedin_reconcile.py`, `probe_list_staging.py`.
A gate on `providerwrites.perform` does not cover any of them. Name in your report which of
these can reach 487/489/493.
