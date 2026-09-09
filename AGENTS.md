# Resonate Group Automation
Read BUILD-SPEC.md before changing anything. PLAYBOOK.md is the operating
contract: the rules that outrank convenience, including the ones the LLM steps
work to. SLACK-NOTIFICATIONS.md is the same for the notification layer: two
levels, no fallback between them. ACCOUNT-OUTREACH.md and CADENCE-MODEL.md
cover account-based orchestration: the account is the unit of outreach, and a
message may only claim what the event log supports. OPERATOR-PLAYBOOK.md is
the workflow those rules govern; PRODUCT-INVENTORY.md says what exists.
PRODUCT-GAPS.md says what deliberately does not, so nobody discovers a gap in
front of a client, and MANUAL-REVIEW.md says what a person still has to check
because no assertion can reach it. ENGAGEMENT-HYGIENE.md covers the third
layer: canonical engagement state, what a new list is checked against before
anybody spends a credit on it, and what the providers are told afterwards.
COPY-EXPERIMENTS.md covers the fourth: five variants per message step, how a
contact is assigned to one, and why the evaluator refuses to call a winner
from four replies against three. ACCOUNT-INTELLIGENCE.md covers the fifth:
what is happening at an account, how fast that ages, why a priority score
is never permission to write, and what the campaign brief may assemble
without asserting anything of its own. GTM-STRATEGY.md covers the sixth:
what was decided about how a workspace is worked, what that rested on, and
why the decision log enforces nothing. DISCOVERY.md covers the seventh:
why discovery is a subtraction rather than a search, which known accounts
a weekly refresh is worth spending on, what the client review file may not
be trusted about, and why a cohort of three accounts is told to say
nothing. LIVE-READINESS.md is the eighth and the one to read before
promising anything: every capability with one strict classification, where
a fixture is never a live-validated integration and sending is BLOCKING by
construction rather than by a flag.

Rules

- work/queue.jsonl holds record state and work/campaigns.jsonl holds campaign
  state. Those two files are the only state. Touch both through src/store.py,
  never directly. A campaign is not a record: it has no domain and no contacts,
  so it gets its own file rather than a row that fails every record invariant.
- Provider modules return trimmed dicts, never raw payloads.
- No email is generated for an unverified address. No draft ships without passing lint.py.
- Never widen a lint rule to make a draft pass. Regenerate the draft.
- Dry run is the default for anything that sends. --live is always explicit.
- Never delete a queue record. Drop it with a reason.
- Costs are real: people-count is free, everything else burns credits. Cap before you fan out.
- Company first. No paid person-level call before a company reaches an explicit
  ICP verdict, and rejected, review and unknown all mean zero person credits.
- Every paid call goes through enrich's `spend()`, which writes the waterfall
  ledger. A provider call that skips it is invisible to the spend audit, and an
  audit that reports clean because it watched nothing is worse than none.
- Missing evidence is never positive evidence, and score and confidence are
  different questions. A guessed timezone is worse than a missing one.