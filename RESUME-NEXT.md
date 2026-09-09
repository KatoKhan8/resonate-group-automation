# Resume here

> **Read `RESUME-CHECKPOINT.md` first.** It is newer than this file and
> carries the current HEAD, the current suite results, Productive's real
> state and the blockers. This file's figures are from an earlier night and
> are stale; its reasoning still holds.

Written for a session with no memory of how any of this came to be. It
assumes nothing and repeats what matters.

Read this, then `RELEASE-CANDIDATE.md`, then
`FINAL-SYSTEM-INTEGRITY-AUDIT.md`. `PRODUCT-GAPS.md` and
`LIVE-READINESS.md` are the two that stop a claim being made in front of a
client. `AGENTS.md` is an untracked copy of an earlier `CLAUDE.md`; it was
not created by these sessions and is left alone deliberately. It is the
only uncommitted file in the repository and always has been.

---

## Current goal

None in flight. Three missions have completed in sequence: the overnight
release candidate, the demonstration deployment, and production
authentication plus the first live provider reads.

---

## Verified baseline

| | |
| --- | --- |
| HEAD | see `git log -1`; the checkpoint is `114cacf` plus this record |
| Git | clean except untracked `AGENTS.md` |
| Full suite | **4,831 tests, OK** (861s) |
| Mutation audit | **409**, after one was retired for guarding unreachable code. See `PRODUCTION-TRANSITION.md` §4b |
| Live sending | off, by construction |
| Demo | deployed and healthy |

---

## The three things that changed, in order of how much they matter

**1. Productive already has live outreach running.** Read from HeyReach
on 2026-09-02: 42 campaigns in progress, 39 LinkedIn sender accounts,
~160,000 prospects mid-sequence. EmailBison holds 15 campaigns and sends
nothing.

Every pilot plan written before that date assumed a greenfield workspace.
**It is a P1** (`PRODUCT-GAPS.md` §15) and it gates contact selection, not
just pilot size. `PRODUCTIVE-PILOT-PLAN.md` §1 has three ways to close it
and recommends the one that is a conversation rather than a build:
agree a segment Resonate owns exclusively.

**2. Production authentication exists.** OpenID Connect, authorization
code with PKCE, standard library only. `PRODUCTION-AUTH.md`. Demo sign-in
is untouched and unreachable whenever `AUTH_PROVIDER` is set. No real
provider has answered it yet, so it is NEEDS LIVE CONTRACT VALIDATION -
the owner has to create an OAuth client.

**3. Five providers have authenticated and answered.** ContactOut, AI Ark,
EmailBison, HeyReach, Apify - read-only, no credits.
`PRODUCTION-TRANSITION.md` §1. Deliverable still cannot be tested without
spending, and remains the top provider blocker.

---

## What is next, and why in this order

1. **The exclusivity decision.** Which Productive population does Resonate
   own, and which stays with the live HeyReach operation. Nothing else in
   a pilot is safe to design until that is answered, and it is a
   conversation rather than a build.
2. **The OAuth client**, so a real console can go online at all.
   `PRODUCTION-AUTH.md` §5.
3. **The capacity engine and its consumption by strategy.** Deliberately
   not built yet: the true shape was unknown until the reads above, and
   building against a guess was the risk. It is now known - 39 LinkedIn
   sender accounts derivable from `campaignAccountIds`, inbox counts and
   configured limits `UNKNOWN` in both confirmed contracts. Build against
   that, and prove strategy output changes when infrastructure changes.
4. **Deliverable's response shape**, one credit, deliberately.
5. A persistent volume before any instance holds real data.

---

## What tonight changed

Nothing that adds a feature. Four things, all of the same shape - a thing
that was written down and not true.

1. `config.verify()` said "called at startup" and had no caller. Two
   documents described a production fail-closed that had never run.
2. `DEPLOYMENT-PLAN.md` documented `--host 0.0.0.0` as the start command,
   which publishes an unauthenticated console.
3. The copy experiment screen fell back to `web/demovariants.py`'s planted
   totals whenever a campaign had no `cadence_graph` - which nothing
   writes, so that was every real campaign, always.
4. `WEB_HOST` and `WEB_PORT` were declared, reported by a screen, and read
   by nothing.

Six mutations added, all caught. `Procfile`, `railway.json`,
`requirements.txt` and `.python-version` added, each asserted against the
parser and refusal `main()` itself uses rather than read.

---

## The failure mode this codebase keeps producing

**The system computes the right thing and nothing downstream reads it.**
Fifteen instances found across all missions. Tonight's four were the same
shape one level up: not a value nothing consumed, but a *guard* nothing
called and a *document* describing it anyway.

The two cheap ways to find more, both used tonight:

```
# public functions with no reference anywhere in src/, tests/ or tools/
# 1036 public functions, 16 with zero references
# every os.environ lookup in src/, matched against what consumes it
```

**Before marking anything complete, trace the chain and prove each link is
consumed.** For a guard, that includes: does anything call it, and does
passing it mean what the document says it means. `AUTH_PROVIDER` passed a
check and implemented nothing.

Still open: `campaign["cadence_graph"]` is read by four callers and
written by none (`PRODUCT-GAPS.md` §13).

---

## What is left, none of it blocking a demonstration

1. **Authentication.** The decision above. Everything else on this list is
   smaller than it.
2. **A persistent volume** before any instance holds real data, with
   `QUEUE` pointed at it. One environment variable moves the whole state
   set; a container filesystem is ephemeral and an empty store is a valid
   store, so this fails silently if forgotten.
3. **A screen for cadence experiments.** Every module has a CLI
   (`py -m src.cadencereport --campaign <id>`); none has a page.
4. **Whatever writes `cadence_graph`.** Four readers, no writer.
5. Productive demo fixtures showing an experiment mid-flight, the way
   `web/demovariants.py` does for copy.
6. Adversarial cadence lifecycle cases: an experiment edited mid-flight, a
   record moved between campaigns, an arm whose steps change under
   somebody part-way through.
7. From the prior pilot mission, never reached: `PILOT-READINESS.md`,
   `FIRST-LIVE-VALIDATION-RUNBOOK.md`, `FIRST-PILOT-RUNBOOK.md`.
   `RELEASE-CANDIDATE.md` §8 and §9 now cover most of what those were for.

---

## Invariants that must survive all of it

- Nothing sends. `push.run(live=True)` raises; `tagsync.send` refuses.
  Neither is a flag.
- Production mode does not start, and a non-loopback bind does not start
  unless the estate is fictional. One predicate,
  `security.sign_in_proves_identity()`, and both refusals read it.
- Demo data never reaches a real process. `--demo` is explicit, always.
- Assignment is not exposure. Planned is not confirmed.
- Arm assignment is deterministic and sticky, and the arm must actually
  alter the executed step graph.
- Reply, DNC, positive reply and account hold override experiment
  completion. Safety outranks experimental purity, always.
- Missing evidence is never positive evidence.
- No live sending, no provider mutation, no credit spend, no production
  deployment.

---

## First commands after resume

```
git status --short
git log --oneline -5
py -m unittest tests.test_mutation_anchors -q     # every mutation can fire
py -m unittest tests.test_startup_refusals -q     # what the process refuses
py -m unittest tests.test_deployment_config -q    # and what it ships
py -m src.config                                  # what is configured
py -m src.pilotpath                               # 29 stages, and their tests
```

Full battery, for reference. Do not run the suite and the offline harness
concurrently: they both bind loopback and build demo estates, and one HTTP
test fails intermittently when they overlap. That was diagnosed, not
dismissed.

```
py -m unittest discover -s tests -q     # ~13 min
py -m tests.offline                     # ~15 min
py tools/mutation_audit.py              # ~45 min, 392 mutations
```
