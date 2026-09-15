# Resonate Group Automation
docs/CONTEXT-RESET-2026-09-15-D.md is the current state: read it first.
Read BUILD-SPEC.md before changing anything. PLAYBOOK.md is the operating
contract: the rules that outrank convenience, including the ones the LLM steps
work to. SLACK-NOTIFICATIONS.md is the same for the notification layer: two
levels, no fallback between them. EMAILBISON-COPY-REQUIREMENTS.md is the
standing contract for email generation: a sequence is one conversation,
same-thread follow-ups use the provider's thread_reply rather than a new
subject every step, no name is ever hardcoded and no greeting may render
empty. ACCOUNT-OUTREACH.md and CADENCE-MODEL.md
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
construction rather than by a flag. RELEASE-CANDIDATE.md is the ninth and
the one to read before deploying anything: three verdicts that are not the
same question, what may be published today and what may not, and why
signing in proving nothing about who somebody is means the demonstration
can go online and the product cannot. PRODUCTION-AUTH.md is the tenth and
answers that last one: an identity provider proves the address, the
membership table decides what it may do, and neither is allowed to learn
the other's job. STREAMING-ARCHITECTURE.md is the eleventh and
the only one about the next scale phase rather than this one: a large TAM
is processed as a stream of accounts rather than a file walked stage by
stage, the first excellent accounts reach a campaign while the long tail
is still being researched, personalisation depth is licensed by evidence
rather than chosen, and campaign performance is never allowed to edit a
safety policy.

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

Durable state: GitHub is the source of truth, 2026-09-15

Set after an unplanned shutdown destroyed a night's terminal state and very
nearly destroyed two completed results. TASK-059's estate outcomes report and
TASK-037's result block existed only as uncommitted files in worktrees. They
were recovered by hand, which is not a plan.

Assume this machine, this session, the Qwen processes, the terminal and every
worktree can disappear between one tool call and the next. The test of durable
state is concrete: **a fresh session on a different computer, with a clone and
the secrets supplied separately, must be able to read the repository and say
what happened and what to do next.** Anything that fails that test is not
state, it is scrollback.

- Commit and push continuously: production code, tests, configuration without
  secrets, CLAUDE.md, QWEN.md, task definitions, task results, architecture
  decisions, provider findings, historical-learning findings, classifier and
  cadence findings, experiment definitions and results, campaign templates,
  quality-gate changes, checkpoints, handoff documents, and any worker result
  that has been reviewed or is waiting for review.
- A finding that exists only in terminal output does not exist. Write it to
  docs/ and push it before moving on.
- The path is worker branch -> commit -> push -> Claude review -> tests and
  gates -> master -> push. Durability is never a reason to push broken work to
  master; it is a reason to push it to its own branch. If work is unfinished,
  valuable, and the machine might die, checkpoint it to the worker branch with
  a commit message that says it is unreviewed.
- `scripts/durable_state.py` regenerates `docs/state/LEDGER.json` and
  `docs/state/QUEUE-MANIFEST.json`. It is DERIVED from the task files and from
  git, never hand-edited, because a ledger somebody has to remember to update
  is a ledger that drifts - and a drifted ledger is worse than none, because
  it is believed. It exits non-zero when a branch holds unpushed work or a
  worktree is dirty. That exit code is a durability alarm, not a crash.
- `scripts/provider_truth.py` writes `docs/state/PROVIDER-CAMPAIGNS.json` by
  asking the providers. A local dry run, a generated sequence, an adapter
  test, a "write passed" line in a handoff - none of those is evidence that a
  campaign exists. Only a provider readback against a real campaign id is.
- `work/` stays gitignored. It is 300 real companies and 92 real contacts and
  it is not ours to publish. The queue is made durable instead by the
  sanitised manifest: counts, stages and a hashed estate fingerprint, enough
  to know whether the estate changed and how much work is in which state, and
  deliberately not enough to rebuild the prospect list.
- Write an autonomous-run checkpoint to docs/ periodically and push it:
  master HEAD, active tasks, completed tasks, pending reviews, blockers,
  production state, provider state, next actions.
- Never commit .env, an API key, a password, a token, a provider credential
  or a temporary credential file. If durable state has to reference a secret,
  store the environment variable NAME and never the value. Scan the staged
  diff before pushing; .gitignore is a guard, not a substitute for looking.

How to work here

These govern how the work is done. The rules above govern what the system
may do, and none of what follows may be traded against them: simplicity
never buys a weakened guard, and tenancy, RBAC, canonical identity,
confirmed-history semantics, claim licensing, suppression, DNC,
positive-reply protection, approval, pre-send recheck, kill switches,
volume caps, provider boundaries, auditability and the no-live-action
restriction outrank every preference below.

- Read the implementation before changing it. Find the real execution
  path, the convention already in use, the assumption you are about to
  make, and the smallest change that satisfies the actual requirement -
  then decide how you will know it worked. This repository already has an
  architecture. Do not invent one from the prompt.
- Existence is not function. A model, table, config key, route, adapter,
  report, fixture, test or paragraph of documentation proves nothing on
  its own. The recurring defect here is a thing computed correctly that
  nothing downstream reads - an evaluator reported INSUFFICIENT_DATA
  forever because nothing wrote the field it read, which is
  indistinguishable from an evaluator waiting for volume. For anything
  execution-critical, trace the whole chain and prove every link is
  consumed: input, canonical state, decision, consumer, execution,
  confirmed event, outcome, reporting.
- Prefer canonical state to a second representation of it. Before adding
  state, ask what already holds this truth. Workspace, account, contact,
  sender, campaign, cadence, variant, approval, confirmed touch, reply,
  suppression, engagement and evidence each have one, and a parallel
  state machine for the same fact is how the two drift.
- Smallest robust solution. No speculative features, no abstraction with
  one caller, no configuration nobody asked for, no wrapper around a
  wrapper, no rewrite where a surgical fix works. New modules, concepts,
  state, config, persistence formats and dependencies each have to earn
  their place; where two designs are equally correct, ship the simpler.
- Surgical changes. Every changed line should answer to the task or to a
  bug its verification exposed. Do not reformat, rename or refactor what
  you were not sent to change, and delete only what your own change
  orphaned. Unrelated debt goes into PRODUCT-GAPS.md, not into the diff.
- Make the request falsifiable before writing code. Not "implement
  cadence experiments" but "assign an account deterministically to an
  arm, prove the arm changes the executed step graph, and prove a reply
  after step three stops later steps and is reported as three confirmed
  exposures". For a bug: reproduce, test, fix, verify, attack the test,
  regress. For a feature: state the invariant, trace the existing path,
  make the minimum change, test that it is consumed, test that it fails,
  regress.
- Test behaviour, not the text of the source. Assert on the import graph
  or on what a function returns. Searching source for words produces a
  test that fails when somebody writes a comment, which has happened
  repeatedly here. A red test is not proof by itself: when you break a
  guard deliberately, confirm that the intended test failed, that it
  failed for the intended reason, and that a different guard did not fire
  first.
- A failing test is a question about the system, not an obstacle. Ask
  which it is - fixture, assumption, disconnected consumer, wrong
  canonical model, stale state, wrong identity, wrong tenancy, swallowed
  exception, or a real bug - and fix the smallest root cause. Never
  weaken a check to make it pass. "Never widen a lint rule to make a
  draft pass" above is one instance of that general rule.
- No silent fallbacks on a safety path. An `except Exception`, an empty
  dict, a bare False or an "unknown" standing in for confusion will make
  an unsafe system look healthy. Classify explicitly and fail closed.
- Decide, do not ask, for local reversible work. Name the uncertainty,
  look for the answer in the repository, take the most conservative
  reading, record the assumption where it is material, implement, verify,
  continue. Never ask whether to continue, commit, run the tests or fix
  something. Ask only where the unresolved decision involves an
  irreversible external action - production deployment, destructive data
  mutation, real provider state, real sending, real credit spend - or
  credentials with no fixture path, or business semantics ambiguous
  enough that guessing would build the wrong product.
- Read `git diff` and `git status` before every commit. Is every changed
  file intentional? Did tooling rewrite something? Is generated output
  being committed? Is there formatting churn that is not yours?
- Never stage or commit while mutation tooling is running, and never
  `git add -A` anywhere near it. This repository has committed mutated
  source once. Afterwards: wait for completion, verify restoration,
  inspect the diff, inspect the status, stage the exact files, commit.
- Verify in isolation. `unittest discover` and `tests.offline` both bind
  loopback and build demo estates; run back to back they still overlap
  during teardown, and one HTTP test fails intermittently. Leave a gap
  between them. An intermittent failure is diagnosed - alone, as a class,
  and in an isolated full run - never dismissed.
- Stop when the goal is met. Validate, record the result, commit safely,
  take the next queued mission. If nothing meaningful is queued, report
  the boundary. Do not invent work to fill the remaining context.
