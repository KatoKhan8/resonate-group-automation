# Slack agent — handoff, 2026-09-24 night

Supersedes `SLACK-AGENT-HANDOFF-2026-09-24.md` and every earlier one.
Written to the test `CLAUDE.md` sets: a fresh session on another machine,
with a clone and the secrets supplied separately, should be able to read
this and say what happened and what to do next.

**Branch `slack-agent` at `ad96c821`, pushed and verified.**
**Master has moved to `33c1b364` and this branch is 69 commits behind it.**
Fetch and merge before anything else — §3a depends on it.

---

## 0. THE LANE DIRECTIVE, AND WHERE THIS SESSION SPENT ITS NIGHT

Operator directive 2026-09-24, valid to 2026-10-01: three lanes,
everything else frozen. **This session is LANE 2 (agent)** and spent the
back half of the night on a **temporary LANE 1 ASSIST**, which is
delivered and described in §1–§2.

The lane 2 queue is frozen mid-flight and is in §3, ready to resume.

---

## 1. THE LANE 1 ASSIST — DELIVERED

Two pieces, a merge request each, both pushed. **Production wires them.**

### 1a. `src/researchpack/` — `5fe4d9e8`, corrected by `ad96c821`

An Apify adapter, read-only, NOT under `src/providers/` (which is
forbidden to this branch; `providers/apify.py` is imported, never edited).

    facts.py    every fact carries source, date and snippet or it is not
                representable. A row that cannot support a claim is
                DROPPED, never padded.
    actors.py   three actors, VERIFIED against the live API. Two are
                "No Cookies", which meets the no-LinkedIn-session rule at
                the actor rather than by hope.
    cache.py    30 days, keyed on DOMAIN AND PROFILE, so an account whose
                champion changed re-buys that champion and not the
                company posts.
    pack.py     dry run is the default; cost goes through
                `spendledger.record` on a run id.

**The actors, as verified 2026-09-24:**

| our name | actor | targetable today |
|---|---|---|
| `company_posts` | `harvestapi~linkedin-company-posts` | **NO** — §2b |
| `open_roles` | `fantastic-jobs~career-site-job-listing-api` | yes |
| `person_posts` | `harvestapi~linkedin-profile-posts` | yes |

### 1b. `src/copylint.py` — `09e16c34`

A BATCH lint. `lint.py` stays the DRAFT lint and this composes it —
`BANNED_PHRASES` and `SUBSTITUTED_PUNCTUATION` are imported, with a test
asserting they are the same object, because a second copy drifts into copy
that passes one lint and fails the other.

Six rules: step 1 opening on nothing the pack supports, a first line shared
by two leads, a company claim carrying a specific no pack fact carries,
fewer than five steps or an empty one, a dash as punctuation, a buzzword.

**Counts, not just a refusal**, and a test asserts clean + dirty reconciles
to the batch size — a count that does not reconcile is one nobody can act
on. A refusal is still a refusal: never widen a rule, regenerate the draft.

**What it cannot do, said in the module and asserted in a test:** it does
not read meaning. "You must be struggling with scale" carries no specific
and passes.

---

## 2. WHAT PRODUCTION MUST DO TO WIRE THEM

### 2a. CALIBRATE THE COST FIGURES — they are placeholders

`ACTORS[*]["cost"]` totalled **36 ledger units** for seven live runs that
cost Apify **$0.0513**. The numbers are invented and the units do not
correspond to anything. Per-account cost means nothing until they are set
against a real invoice, and the spend audit is the thing that suffers.

Measured for reference, from Apify's own `usageTotalUsd`:

    7 runs, 3 accounts, 2 actors      $0.0513 total

### 2b. GIVE `company_posts` A TARGET — the company slug from the jobs actor

`harvestapi~linkedin-company-posts` takes LinkedIn COMPANY urls in
`targetUrls`. **The record store has none: 1,543 records carry ZERO
company-level LinkedIn urls** (1,316 CONTACT-level profile urls do exist,
which is why the other two actors run today).

`actors.targetable(name, record)` refuses rather than aiming a paid run at
a website, and `--only` on the capture script exists for the same reason.

**The cheapest close is already in hand.** The jobs actor returns
`org_linkedin_slug` on every row — `"work-truck-solutions"` on the live
capture. So:

    https://www.linkedin.com/company/<org_linkedin_slug>

feeds `company_posts` for any account that has an open role, at no extra
provider call. Accounts with no open role still need another source.

### 2c. WIRE POINTS

- **S7** reads `researchpack.build(domain, live=True, champion=..., ...)`
  per account and hands the pack to copy generation.
- **The push** calls `copylint.check_batch(leads, packs)` and refuses on
  `report["refused"]`, printing `copylint.report_lines(report)`.

---

## 3. THE FROZEN LANE 2 QUEUE, FOR RESUMING

### 3a. LIFT THE GAG — rules-4 IS LIVE, AND THIS BRANCH DOES NOT HAVE IT

**Verified 2026-09-24 night rather than assumed**, because the morning's
answer was the opposite and master moved underneath it:

    origin/master  src/replies.py:37   VERSION = "rules-4"
    origin/master  src/replies.py:1649 RULE_HASH = "%s+%s" % (VERSION, ...)
    this branch    src/replies.py:30   VERSION = "rules-3"

So the blocker named in every handoff today is **cleared on master** and
this branch is **69 commits behind**. Merging master is the first step of
lifting the gag, not a chore before it.

**AND THE GAG IS ALREADY PARTLY LIFTED HERE.** `fcced109` moved
`CLIENT_CHANNEL_GAG` to sit AFTER the change-request intake, so a client
asking us to change something reaches the operator again. **Answers are
still gagged.** That was an operator decision and a real loosening; the
revert is one block move and is documented at the block, with
`tests/test_the_gag_stops_the_answer_not_the_request.py` pinning both
halves.

What remains for a full lift: merge master, confirm
`replyverdict.positive_confirmed` is non-zero now that `RULE_HASH` exists,
and move the 2d block out of `_respond` — then the latency question
returns, because a 132-second turn was one of the three faults that caused
the gag and client p95 is **37.8s** against a 30s target (§5).

### 3b. REPLY-ENGINE DRAFTS IN `#replies-productive`

Not started. It is the other half of lane 2 and nothing in this branch
touches it yet.

### 3c. THE MONDAY REPORT LOOP — PRODUCTION'S, AND UNSTARTED

The dry run is done and the machinery is sound (`9175243c`): preview
07:30, window, post 08:00, `already_done`, a stop holds, an anonymous stop
is refused, a late tick refuses to post.

**NOTHING HAS STARTED THE LOOP.** It is in `start_monitors.MONITORS` as
`weekly-report` now and `--status` says `weekly-report NEVER`. Adding it to
the table does not start it. First real Monday is **2026-09-28** and lane
3 cuts over that same night after 23:00 Zagreb, so it needs starting on the
current host for Monday morning and confirming on the new one after.

### 3d. STILL FROZEN, HERE FOR OCTOBER

- The latency increment: `slack-agent-latency-parked` at `3c5c0528`.
  **Wired and unmeasured** — no replay has run against it, which was the
  operator's own condition. Two pieces worth separating when it thaws: the
  "reasoning-heavy" definition the catalogue does not actually contain,
  and the plan/answer timing, which is instrumentation rather than a
  latency change.
- The missed-mention sweep. Two constraints when it thaws:
  `work/slack-history/` holds credential-shaped strings (8 `sk-` keys, 4
  Slack tokens, 6 `password:` values — counts only, `work/` is gitignored),
  so **redact at READ**; and the archive predates the agent, so a sweep
  that does not window to the agent's own lifetime reports every pre-agent
  mention as a missed one.
- Item 5's 10-vs-7 day promise window, which is an argument to
  `slackpromises.scan(window_days=...)`, not a build.

---

## 4. THE SEVEN APIFY PREMISE CORRECTIONS — FOR THE REGISTER

Every one was a plausible guess that the live runs disproved. They are
listed together because the pattern is the finding: **this package was
written entirely from assumptions about an API nobody here had ever
successfully called**, and seven of them were wrong.

1. **The three actor ids did not exist.** `apify~job-listings-scraper`,
   `apify~linkedin-company-posts-scraper` and
   `apify~linkedin-profile-posts-scraper` all answer **404** on
   `GET /acts/<id>`; `apify~website-content-crawler` answers 200. The real
   ones are in §1a.
2. **`proxyConfiguration` is not universal.** All three declare no
   required fields. The blanket rule was inherited from the website
   crawler, which does require it, and was never true here.
3. **`timeRange: "Last 30 days"` is rejected.** Exact error:
   `400 invalid-input: Input is not valid: Field input.timeRange must be
   equal to one of the allowed values: "1h", "24h", "7d", "6m"`. Now `6m`.
4. **The input field names were invented.** `companyUrl` / `companyDomain`
   / `profileUrl` are really `targetUrls` and `domainFilter`, from each
   actor's published input schema.
5. **`linkedinUrl` is the permalink field**, and its absence from the url
   map dropped **all nine** real profile posts as unusable — reported as
   "0 facts", which reads as *this person has nothing to say*. With it, 7
   of 9 are usable.
6. **`postedAt` is an OBJECT, not a string.** `str(value)[:10]` would have
   stamped the literal `{'timestam` on a fact as its date. It was invisible
   only because correction 5 was dropping every row first.
7. **Without `postedLimit` the actor returns a profile's whole history.**
   The capture came back with posts from **February 2020**. A six-year-old
   post is not a hook. Now `6months`, from the actor's own enum.

### 4a. And one that was ours rather than Apify's

**The spend ledger booked six rows for runs that never existed**, because
cost was recorded before the POST and the 404s therefore charged nothing
real. It now records on a run id, which is when Apify starts charging. A
ledger that overstates is no better than one that understates.

### 4b. What this says about the cassettes

`tests/fixtures/cassettes/00-researchpack.json` now carries the REAL actor
ids, input field names and row structure, with every VALUE replaced — the
real rows named a real company, its domain and a real person. A test
asserts none of them survived, because `test_fixture_hygiene` only knows
the domains somebody already added to its list.

The first version of that file was hand written to a guessed schema and
said so honestly, and it was still wrong in six of the seven ways above.
**Saying a fixture is invented does not make it harmless.**

---

## 5. THE NUMBERS THAT CARRY OVER

    full suite, this branch          82 failures (136 at the pre-merge tip)
    client p50 / p95                 25.4s / 37.8s  against 15s / 30s
    turns over 82s                   0 of 33, from 11 of 21 answered
    the remaining latency            ~21s of every turn is answer
                                     composition - one model call

`scripts/suite_verdict.txt` is TRACKED and written by whichever checkout
runs the suite. The copy in git is another machine's. Do not read it as
this branch's verdict.
