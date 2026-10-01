PRIORITY: P1
SIZE: M
DEPENDS: task-recontact-cold-lead

# TASK-937 — The campaign copy path cannot see `prior_contact`, so cold copy still claims a first touch

Opened as a ramp task by operator decision, 2026-10-01.

## State as measured

`prompts/draft.md` was fixed: `prior_contact` is no longer a boolean. It is three states —
`contacted` / `not_contacted` / `unknown` — and `not_contacted` requires proof on BOTH
channels (every lookup answered, every send history balanced, no undated thread). Membership
without a dated send is `unknown`, not a clean slate. The sentence "you have not met them"
no longer appears anywhere in that file, including in the explanatory prose, and a test
enforces that, because a model could otherwise copy it back.

Two things are still open, and the second is the load-bearing one:

1. `src/generate.py:672` and `:694` still hand a BOOLEAN to the prompt. The prompt now reads
   a boolean as `unknown`, so no false claim is produced — but the genuine first-touch branch
   is unreachable until the caller passes the three-state value plus the dossier.
2. The campaign copy path is still blind. `grep -c prior_contact` is **0** in each of
   `src/copystages.py`, `src/copyprompts.py`, `src/generate_campaign.py`, `src/copylint.py`,
   and `src/copystages.py:388` asserts "FIRST TOUCH SHAPE" unconditionally.

## Task

Give the campaign copy path the same three-state authority, and enforce it in `copylint`.

The lint rule is the load-bearing part: a prompt can be ignored by the model, a lint cannot.

## Acceptance

1. `copylint` refuses copy that asserts a first touch when the state is `contacted`, and also
   when it is `unknown`. Proven by a test that fails before the rule exists.
2. The symmetric control, which is the part that is easy to get wrong: a genuine first contact
   must STILL be allowed to say it is the first contact. Replacing one false claim with
   another false claim is not a fix. Test both directions.
3. `src/copystages.py:388` no longer asserts FIRST TOUCH SHAPE unconditionally; it asserts
   whatever the measured state says, or refuses.
4. `src/generate.py:672` and `:694` pass the three-state value and the dossier. State plainly
   whether the first-touch branch is reachable after your change — before this task it was not.
5. Mutation proof: remove the refusal and a test must go red on EFFECT (the copy that ships),
   not on a message string.
6. READ-ONLY toward providers.

## Context that bounds the urgency

For the bigfish canary this is not a blocker: bigfish classifies COLD with both channels
proven absent from the provider estate, so `not_contacted` is true there and the copy does
not lie. The exposure is every OTHER cold lead and every manually touched one.

Unfixable from our side, and it must be stated in the report rather than designed around: a
HeyReach conversation does not carry a campaign id, so "was this action ours" rests on our own
record — and only 1 of 1,381 contacts in the store carries a `heyreach_campaign_id`. A real
LinkedIn touch of ours that we never recorded reads as manual and would draw a full new cold
sequence.
