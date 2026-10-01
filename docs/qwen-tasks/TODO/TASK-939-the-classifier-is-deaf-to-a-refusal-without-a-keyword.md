PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-939 — A refusal without a keyword is read as `unknown` (measured 2026-10-01)

Opened from a measurement, not a review. Everything below was reproduced against the
committed classifier on branch `task-reply-classification-clean` @ 36445185, whose
`RULE_HASH` is `rules-4+400872bcd6e6` — the same hash in the regenerated artifact filename,
so this is committed behaviour and not a stale pre-fix run. `__pycache__` was wiped and the
module was imported the way production imports it (`from src import replies`).

## The defect, minimal and isolated

| input | verdict |
|---|---|
| `"remove me"` / `"DNC"` / `"Stop"` / `"unsubscribe"` | `unsubscribe 0.95` |
| `"remove"` (alone, any casing) | `unknown 0.0` |
| `"No needs, thanks."` | `automated 0.85` — a human refusal read as an autoresponder |
| `"we don't need help"` / `"Sorry no opp for you"` | `unknown 0.0` |

The bare imperative `remove` has no pattern, while `remove me` does. `"No needs, thanks."`
is worse than unclassified: it is affirmatively mislabelled `automated`, which is the class
we use to mean "no human wrote this".

## What it costs on real rows

Measured across all 899 readable replies: 82 change verdict under the new rules. The gain is
real — 56 new removal verdicts (44 `unknown→unsubscribe`, 9 `negative→unsubscribe`,
3 `not_relevant→unsubscribe`). But 16 replies LOSE a verdict into `unknown 0.0` with empty
evidence, and all 16 of those people are on NO list afterwards (0 of 16 are covered by
another reply from the same person).

The stripper is NOT the cause: it correctly preserved the human text in all 17 rows checked.
The cause is a missing rule.

Compliance exposure, the worst row first:
- reply 1603100, lead 146868, campaign 352. The entire human content of the reply is the
  single word `remove`. Verdict `unknown 0.0`. The person is not on the DNC list.
- reply 1590488 `"No needs, Bojan. Thanks."` → `unknown` (was on the list, now is not)
- reply 1605004 `"no"` → `unknown`
- reply 1604711 `"Thanks but we don't need help !"` → `unknown`
- reply 1565865 `"we won't be needing the platform ... at this time"` → `unknown`
- reply 1602466 `"Sorry no opp for you"` → `unknown`
- reply 1602062 `"I don't I'm afraid - my apologies!"` → `unknown`
- reply 1567859 `"I'll keep <product> in mind should our needs change"` → `unknown`
- reply 1582130 polite negative → `unknown`
- reply 1608534 `"You pulled up my profile where? I'm not a project manager."` → `unknown`

Commercial exposure — these are live opportunities nobody can see:
- reply 1609203 `"Glad to talk with you. Set up an on line meeting or call me at <tel>"`
  → `unknown 0.0`. Was `referral`.
- reply 1608929 asks which system we use for this outreach → `unknown 0.0`. Was `positive`.
- reply 1511779 `"our team are already exploring options with you guys"` → `unknown 0.0`.

A verdict that was previously correct and is now lost:
- reply 1592702, an Inbox Zero autoresponder → `unknown 0.0`. `automated` was right.

## Why the earlier audit did not catch this

The 432-row audit measured the NEGATIVE-AND-DNC subset, where `unknown` genuinely falls
41 → 8. These 16 rows fall INTO `unknown` from outside that subset, so the audit's
denominator could not show them. Both numbers are true. Any future rules change must be
measured on the full reply corpus, not on the subset the rules already select.

## Acceptance

1. A bare `remove` (and the same family: `remove.`, `Remove`, `REMOVE`, `remove us`,
   `take me off`) yields a removal verdict, proven by a test that fails before the change.
2. `"No needs, thanks."` is not `automated`. Decide explicitly what it IS and defend it;
   `unknown` is an acceptable answer only if a human review queue actually receives it.
3. A keyword-free refusal (`"Sorry no opp for you"`, `"we don't need help"`) reaches a named
   class or a named review queue. It must not silently become `unknown 0.0`.
4. The three commercial rows (1609203, 1608929, 1511779) reach a class a human will look at.
5. Re-run the full 899 and report the directional table again. Acceptance is: no row loses a
   verdict into `unknown` without being named in the report and justified one by one.
6. READ-ONLY toward providers. No DNC list is merged as part of this task — the regenerated
   355-row list is awaiting an operator decision separately.

## Warning

`src/replies.py` is a send-path file and `task-reply-classification-clean` is awaiting a
merge decision. Do not merge this fix into that branch's pending decision; keep it separate
so the operator can judge the two independently.
