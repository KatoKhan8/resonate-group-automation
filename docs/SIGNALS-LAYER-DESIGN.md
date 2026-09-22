# Signals layer — design

**FOR REVIEW. BUILD NOTHING UNTIL APPROVED.** Written on branch `infra`
2026-09-22. No code has been written and no task has been dispatched for any
of it.

## OPERATOR DECISIONS — Zvonimir, 2026-09-22

| # | Decision | Effect here |
| --- | --- | --- |
| 1 | **Gojiberry is DROPPED.** No adapter, no design dependency. | §0.2 rewritten, TASK-I withdrawn, `intent` becomes an empty slot |
| 2 | The RGA runbook lives **outside** the repo; being added under `docs/reference/` (3 files). Ignore the Clay and n8n mechanics; take TAM, Signals, refresh-jobs and router. | §6 to be RE-DERIVED against it — **not yet possible, see §0.3** |
| 3 | **`signalrouter.py` confirmed**; `routing.py` keeps its meaning. **Keep half-life decay; never replace it with cliff-edge expiry.** | §1.1, §1.2 and §2.2 now record this as settled |
| 4 | Review tomorrow. **No build until then.** | Unchanged — nothing is dispatched |

### 0.3 §6 IS NOT RE-DERIVED YET, AND WHY

`docs/reference/` **does not exist** on this branch, on `master`, or as
untracked files in any worktree. Checked 2026-09-22 after the decision was
given. The three runbook files have not landed yet.

So **§6 still says what it said** — the list of places I inferred rather than
read. When the files appear I will re-derive §6 against them and mark what
changed, per decision 2. **Nothing else in this document should be treated as
runbook-derived until that pass happens.**

---

## 0. THE TWO THINGS THAT NEEDED SETTLING — both now settled above

### 0.1 I could not find the RGA runbook

The brief says to write this *"from the RGA runbook already in the repo"*.
**There is no document in this repository matching that name**, and the two
terms most distinctive to the brief return **zero hits across every tracked
file**:

    "Gojiberry"                 0 hits  (.md, .py, .yaml, .json)
    "engaged without reply"     0 hits

So this design is built from the adjacent documents that *do* exist, and from
the four modules named in the brief, which all exist. What I used:

    ACCOUNT-INTELLIGENCE.md      what is happening at an account, how fast it
                                 ages, why a priority score is never permission
    STREAMING-ARCHITECTURE.md    TAM as a stream rather than a file walked
                                 stage by stage
    DISCOVERY.md                 discovery as subtraction, weekly refresh
    CONTACTOUT-CAPABILITY-2026-09-16.md   the job-change capability
    ENGAGEMENT-HYGIENE.md        canonical engagement state
    src/{signals,routing,priority,refresh}.py

**If the runbook exists outside the repo, point me at it and I will
re-derive this against it.** Where I have inferred intent rather than read it,
§6 says so.

### 0.2 Gojiberry is DROPPED — operator decision 1

It had no adapter, no `config.VARIABLES` entry and no mention anywhere in the
repository, and it is now formally out of scope. **No adapter, no design
dependency.**

**`intent` remains as an EMPTY SLOT.** The signal type stays defined in the
design with a half-life and a place in the router, and nothing writes it until
an operator names a source. That is deliberate: designing the other four types
around a gap that may be filled later is cheap, and retrofitting a fifth type
into a router that assumed four is not.

**The empty slot must behave like an empty slot, not like a zero.** A signal
type with no collector must be distinguishable from one whose collector ran
and found nothing — otherwise "no intent signal" reads as "no intent", which
is the missing-evidence-as-positive-evidence error CLAUDE.md names. Whatever
consumes signal strength has to treat `intent` as ABSENT rather than as a
weight of 0.

The four that proceed: `job_post`, `new_hire`, `post_engagement`,
`job_change`.

---

## 1. What already exists, honestly mapped

The brief names four modules. All four exist and three do most of what is
being asked. **One does not do what its name suggests.**

| Brief asks for | Module | State |
| --- | --- | --- |
| Append-only signals with expiry and priority per type | `signals.py` (563 lines) | **MOSTLY EXISTS** |
| 60-day re-verify clock | `refresh.py` (502 lines) | **MOSTLY EXISTS** |
| Priority per signal type | `priority.py` (353 lines) | **EXISTS** |
| Router that enrols by signal into a cadence | `routing.py` (293 lines) | **DOES NOT EXIST — see below** |
| Persistent TAM | — | **DOES NOT EXIST** |
| Daily collectors | — | **PARTIAL** (`apify` adapter exists; no collector loop) |
| Monthly job-change sweep | `contactout` adapter | **CAPABILITY EXISTS, SWEEP DOES NOT** |
| "Engaged without reply" segment | — | **DOES NOT EXIST** |

### 1.1 `routing.py` is not the router the brief means

    def plan(rec, segment, verdict, config=None):
        """The persona plan for one company: who, what titles, and how many."""

**It routes persona discovery — which people to look for at a company — not
cadence enrolment.** Nothing in `src/` selects a cadence from a signal;
`grep` for `cadence_for` / `select_cadence` / `choose_cadence` returns nothing.

This matters because the brief reads as though the router is a wiring change.
It is a new module.

**SETTLED — operator decision 3: the new module is `signalrouter.py`, and
`routing.py` keeps its meaning.** Do not extend `routing.py` to do cadence
selection and do not rename it. One word meaning two things is how the next
reader picks the wrong one.

### 1.2 `signals.py` already has expiry, and it is better than "expiry"

    half_life(signal_type)     per-type decay, configurable
    weight_at(signal, now)     the signal's weight right now
    is_stale(signal, now)      past usefulness
    derive(rec, workspace)     signals implied by canonical state
    strength(signals, now)     the aggregate

**The brief says "expiry"; the code implements half-life decay**, which is
strictly better — a 40-day-old funding round is weaker than a 3-day-old one
rather than equally valid until it falls off a cliff.

**SETTLED — operator decision 3: half-life decay is KEPT and is NEVER to be
replaced with a cliff-edge expiry.** This is a standing instruction, not a
preference for this design round. A future task that reads "add expiry to
signals" is asking for a regression and should be refused with this
paragraph.

The gap is that new signal *types* need half-lives added, not that the
mechanism is missing. `is_stale` remains useful as a cheap filter for signals
whose weight has decayed below usefulness — that is decay reporting a floor,
not an expiry replacing decay.

Its docstring also states the rule the whole layer hangs on: *"Signals observe
canonical state; they never replace it."*

### 1.3 `refresh.py` is the re-verify clock, at a different cadence

    staleness(rec, today, config, policy)
    candidates(recs, today, ...)
    plan(recs, today, ...)

The brief wants a **60-day re-verify clock**. `refresh.py` already computes
staleness and produces a candidate plan. The gap is likely the *period* and
the *trigger*, not the machinery. **Read `settings(config)` before proposing a
change** — the 60 days may already be configurable and simply unset.

---

## 2. The design

### 2.1 Persistent TAM

Today the estate is the queue: a record exists because somebody sourced it
into a batch. **A TAM is the set of accounts we would work if we had capacity**
— larger than the queue, mostly inert, and re-scored continuously.

    work/tam.jsonl        append-only, one row per account
      domain              canonical, the identity
      first_seen          when it entered the TAM
      source              how it arrived
      icp_verdict         from the existing qualification path
      last_scored         when priority last looked at it
      in_queue            whether it has been promoted to a record

**The TAM is not a second copy of the queue.** It holds the domain and the
verdict; the record holds everything else. The moment it starts holding
contacts it has become a parallel state machine for the same fact, which is
what CLAUDE.md warns produces drift.

A new `STATE_OVERRIDES` entry (`TAM`) so it moves with the rest — the
omission of `QUEUE_DB` this session is the example of what happens otherwise.

### 2.2 Signals: append-only, decayed, per-type priority

Extend `signals.py` rather than replace it. New types, each with a half-life
and a weight:

    job_post           a role we sell into was posted        half-life 30d
    new_hire           a persona-matching hire               half-life 45d
    post_engagement    they posted / we engaged              half-life 14d
    intent             third-party intent (Gojiberry)        half-life 21d
    job_change         a known contact moved                 half-life 90d

**Half-lives are a product decision, not an engineering one.** The numbers
above are a starting proposal and should be argued with before anything reads
them. `priority.py`'s existing `weights(config)` is where per-type priority
already lives.

### 2.3 Daily collectors

One process per source, each writing signals and nothing else:

    collect_job_posts      apify     daily    -> job_post
    collect_new_hires      apify     daily    -> new_hire
    collect_posts          apify     daily    -> post_engagement
    collect_intent         (no source)        -> intent        [EMPTY SLOT, §0.2]

**A collector writes signals and never enrols anybody.** That separation is
the design: the router decides, the collector observes. Collapsing them is how
a scraper ends up able to start a campaign.

Every collector goes through `enrich.spend()` if it costs anything. A provider
call that skips it is invisible to the spend audit, and CLAUDE.md is explicit
that an audit reporting clean because it watched nothing is worse than none.

### 2.4 Monthly job-change sweep

ContactOut `people`/`linkedin` over known contacts, monthly. A move is the
highest-value signal in the set — the person who knew us is now somewhere new,
and both the old and new account become interesting.

**It is also the most expensive**, so it is capped and company-first like
everything else: no paid person-level call before a company reaches an
explicit ICP verdict.

### 2.5 The 60-day re-verify clock

Reuse `refresh.py`. An address verified more than 60 days ago is re-verified
before it is used again, not on a timer for its own sake. **Verification
evidence is paid for** and `refuse_evidence_loss` exists to stop it being
dropped, so re-verification appends rather than replaces.

### 2.6 The router — `signalrouter.py`, NET NEW

    route(rec, signals, config) -> cadence_name | None, reason

Given an account and its live signals, pick the cadence whose opening premise
matches the strongest signal. A job post routes to the hiring cadence; a job
change routes to the "you've moved" cadence; intent routes to the problem
cadence.

**It selects. It does not enrol.** Enrolment stays behind every gate that
exists today — client approval, collision, verification, account gate,
attestation, caps, `executionguard`. The router is one more input to a
decision those gates already own, and it must not become a second path that
reaches the provider.

**And it may only claim what the event log supports.** `ACCOUNT-OUTREACH.md`
and `CADENCE-MODEL.md` already say a message may only assert what the evidence
carries. A cadence chosen by a job-post signal may reference the hiring; a
cadence chosen by an intent signal may **not** say "I saw you researching X",
because third-party intent is probabilistic and saying so out loud is both
creepy and unfalsifiable.

### 2.7 "Engaged without reply" as a segment

Accounts where we have confirmed exposure — opens, clicks, profile views,
accepted connections — and **no reply**. They are warmer than cold and must
not be treated as replied.

It is a **derived segment, not stored state**: computed from the action ledger
and confirmed touches at read time. Storing it creates a second representation
of engagement that can drift from the ledger, and `ENGAGEMENT-HYGIENE.md`
already names canonical engagement state as the one that counts.

**A positive reply must never be reachable from this segment** — that is
`eligibility`'s existing stop and this segment must sit behind it, not beside
it.

---

## 3. The gaps, as tasks

Not dispatched. Listed in dependency order.

    TASK-A  persistent TAM: work/tam.jsonl, STATE_OVERRIDES entry, append-only,
            domain + verdict only. Refuses to hold contacts.

    TASK-B  new signal types and half-lives in signals.py. Config-driven,
            with the half-life numbers argued rather than assumed.

    TASK-C  collector framework: one entry point per source, writes signals
            only, goes through spend(), cannot enrol.

    TASK-D  apify collectors: job posts, new hires, posts.   DEPENDS: C

    TASK-E  monthly job-change sweep via ContactOut, capped, company-first.
            DEPENDS: B

    TASK-F  60-day re-verify: read refresh.settings() first; this may be
            configuration rather than code.

    TASK-G  signalrouter.py: signal -> cadence selection, behind every existing
            gate, claim-licensed. DEPENDS: B

    TASK-H  "engaged without reply" as a DERIVED segment over the action
            ledger. Must sit behind the positive-reply stop.

    TASK-I  WITHDRAWN. Gojiberry is dropped (operator decision 1). `intent`
            stays an empty slot with a half-life and a router position, and
            nothing writes it until an operator names a source. When one is
            named, the task is a provider adapter with everything that
            entails - credential, cassette, trimmed contract, routing-policy
            position, spend() path - and NOT a collector wiring job.

---

## 4. What this design refuses to do

- **No second state machine for engagement.** §2.7 is derived.
- **No signal may enrol anybody.** §2.3 and §2.6.
- **No claim a signal cannot license.** §2.6.
- **No paid person-level call before a company ICP verdict.** Standing rule.
- **No new path to a provider.** The router feeds the existing gates.
- **Half-life decay is never replaced with cliff-edge expiry.** Operator
  decision 3, standing. §1.2.
- **`intent` is an empty slot, not a zero.** A type with no collector must
  read as ABSENT, never as a weight of 0. §0.2.
- **Intent is not treated as fact.** It is probabilistic, it decays fastest of
  the five types, and it may not be quoted to a prospect.

---

## 5. What it costs, roughly, before anybody approves it

Daily Apify collection over a TAM of a few thousand accounts is the recurring
cost, and it scales with TAM size rather than queue size — **which is the
point and also the risk**. A TAM of 20,000 accounts collected daily is a very
different bill from 1,000.

**Cap before fanning out.** The existing rule — people-count is free,
everything else burns credits — applies unchanged, and the TAM makes it easier
to forget because the accounts are inert until they are not.

No numbers here because I have not measured them. **That is a gap, not an
omission**, and it should be measured before TASK-D is dispatched.

---

## 6. Where I inferred rather than read

Named, because §0.1 means more of this than usual:

- **Half-lives in §2.2** are proposed, not derived from anything.
- **The 60-day clock** is taken from the brief; `refresh.py`'s current period
  has not been checked against it.
- **Cadence names in §2.6** are illustrative — I have not checked which
  cadences exist in `cadencelibrary.SEQUENCES` against which signals.
- **"Engaged without reply"** is my reading of a term that appears nowhere in
  the repo. If it has a specific existing meaning, this section is wrong.
- **Gojiberry's shape** — API, auth, data model, pricing — is entirely
  unknown. §0.2.

**Approve the shape, not the numbers.** The numbers need a pass with the
runbook in hand.
