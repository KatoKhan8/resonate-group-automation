# The US cold cohort, free-crawled — merge request

Lane K, 2026-09-25 morning. Branch `worktree-agent-a743eb2e1661cce8f`.
**Not merged, not pushed.** Foundation: lane C's
`docs/MERGE-REQUEST-2026-09-24-RESEARCH-PACKS.md`, whose
`src/researchpack/site.py` this lane RUNS and does not fork.

**Target: lane J's `US-COLD-COHORT-2026-09-25.jsonl` — 12,407 contacts on
10,418 domains.** Repointed at 11:05Z; §0 says why, and it is the most
useful thing in this document.

Read §0, then §1 for the numbers and §2 for the reason not to believe the
good half of them.

**RUN STATUS: IN PROGRESS.** §1 and §2 are INTERIM, measured on the first
867 domains of the repointed walk. §9 carries the final figures.

---

## 0. THE FIRST TARGET WAS WRONG, AND THE OVERLAP WAS FOUR

I was sent at the US slice of `work/qualified-supply.jsonl` — 16,247
domains — and walked 6,219 of them at 10.7 dom/s before the coordinator
corrected the target. The correction is right, and this is how right:

    of the 6,219 domains already crawled, the number that appear in
    lane J's 10,418-domain survivor file is                         4

Not four per cent. **Four.** `scripts/researchpack_us_seed.py` carried those
four rows across; the other 6,215 packs cannot ship, because nothing in this
system holds an address at those domains.

The two files are different populations:

| | rows | unit | has an email? |
| --- | ---: | --- | --- |
| the 09-07 list, as lane J cut it | 12,407 | **contacts** | yes, verified |
| `work/qualified-supply.jsonl` US slice | 16,247 | **domains** | no email field |

They overlap on 1,484 domains — ~9% — and **zero of the 16,247 has a contact
anywhere in `work/queue.jsonl`.** The overlap inside my 6,219 came out at
four rather than the ~9% the file-level figure suggests because my priority
order was "largest `_slice` buckets first", and the biggest buckets
(`Software Development|51_200`) are precisely the part of the supply with no
contacts behind it. **A good ordering against the wrong population makes the
miss worse, not better.**

Both logs are kept. `work/researchpack-us-cold-2026-09-25.jsonl` is the
6,219-row supply walk; it is not wasted if the supply is ever contact-sourced,
and §7 uses it, but nothing in it ships today.

### 0.1 The walk was not stalled

The correction said I had "written nothing since 08:52:29Z". Measured at the
moment it arrived: 6,219 rows, last `retrieved_at` `09:02:40Z`, file mtime
equal to the wall clock to within 0.2 seconds, steady at 10.7 dom/s.
**08:52:29Z is 31 seconds BEFORE this lane's first row**, which is stamped
`08:53:00Z`. The stall was in whatever file was being watched, not in the
walk — this lane writes to production's `work/`, and a worktree has its own,
older one. Said plainly because a lane that quietly accepts a wrong
status report teaches the next reader to distrust the right ones.

---

## 1. FOUR NUMBERS, AND THEY ARE FOUR DIFFERENT QUESTIONS

INTERIM, first 867 of 10,418 domains, shippable-first order (clean domains
before the 2,037 where the estate holds an excluded person; then most
contacts first; then a readable MX):

| | domains | of attempted | **contacts behind them** |
| --- | ---: | ---: | ---: |
| attempted | 867 | | 1,952 |
| refused by `check_url` before any fetch | 0 | | |
| crawled — a classified outcome came back | 867 | 100.0% | 1,952 |
| **with at least one usable fact** | **581** | **67.0%** | **1,305** |
| …of which no opener can be rendered at all | 44 | | |
| **projected to pass copylint rule 1, any angle** | **483** | **55.7%** | **1,092** |
| projected to pass rule 1 under EVERY angle | 470 | 54.2% | 1,066 |

**The contacts column is the one the push reads.** A domain is a unit of
crawling; an address is a unit of sending, and today's ceiling is ~2,500
addresses at 1.98 verification credits each. Lane J's baseline was **179
pushable**, gated on packs rather than on verification.

Reproduce:

    py -3 scripts/researchpack_us_rule1.py \
      --log work/researchpack-us-cohortJ-2026-09-25.jsonl \
      --s7  work/stage/s7-copy.jsonl \
      --cohort-out work/researchpack-us-cohort-2026-09-25.jsonl

The gap between 100% crawled and 67% packed is the crawler's honesty, not a
failure to try: `HTTP_INSUFFICIENT` is a site that answered and says too
little, and re-reading it changes nothing. The gap between 67% packed and
55.7% rule-1 is §2, and it is the one that matters.

### 1.1 RULE 1 IS MOSTLY A PROJECTION, AND IT IS LABELLED ONE

Of the 10,418 cohort domains, **only 14 seen so far carry a rendered
`s7-copy.jsonl` row.** For the rest there is no opener to lint, so the
number is projected from production's own renderer rather than guessed.

`src/cadence.py` builds step 1 from `TEMPLATES["persona_pain"]` and
`template_vars`, and when a record carries no `evidence` — which is every
record in this system, because `evidence` is written only by
`generate.persona_angle`, which needs a model and none ships — the opener is
fully determined:

    "{first_name}, I work with {sector} teams on {angle_phrase}, and I do
     not know how {company} handles it"

`scripts/researchpack_us_rule1.py` CALLS `cadence.template_vars`,
`cadence.render`, `copylint.first_line`, `copylint.pack_text` and
`copylint._WORD`. It restates none of them: a second copy of the matching
would be a report that agrees with itself and not with the gate.

Which angle a domain gets follows from a contact's title, so every
configured persona/angle pair is rendered and the result is bracketed —
"any angle" and "every angle" above, and the single-word statistic in §2
given for both the thinnest and the richest.

**MEASURED, not projected, on the 14 that do have copy: 7 of 14 pass rule 1,
and 4 of those 7 pass on a single word.** Two of those four words are
`thanks`.

### 1.2 THE GREETING IS A RULE-1 PASS ALL BY ITSELF

`copylint` keeps opener tokens of **more than four** characters.
`template_vars` falls back to `first_name = "there"` when no contact name is
known, and `there` is five characters. **Any site whose prose contains the
word "there" passes rule 1 on the greeting, with nothing about the company
involved.** `thanks`, seen above on real rendered copy, is the same hole
through a different word.

Counted separately and **never** in the headline: the projection drops the
greeting token before matching. Reported because it is a hole in the gate,
not because it helps.

---

## 2. THE SINGLE-WORD WARNING — AND THE WORD IS `marketing` AGAIN

Lane C measured that 54 of 117 UK/EU rule-1 passes (46%) rested on exactly
one distinct word, and that the word was `marketing` in 53 of them.

INTERIM, on this cohort, of the 483 projected passes:

| | thinnest angle | richest angle |
| --- | ---: | ---: |
| rest on exactly ONE distinct word | **164 · 34.0%** | 129 · 26.7% |
| rest on CATEGORY words alone | 153 · 31.7% | 138 · 28.6% |

The single words: **`marketing` 70, `advertising` 9, `project` 6, `across`
5, `media` 3.** The commonest matching words overall: `marketing` 303,
`advertising` 88, `media` 38, `group` 22, `agency` 21, `teams` 18.

**This is lane C's finding, same word, different continent.** And the
supply walk it replaced proves the mechanism rather than the coincidence:
on 3,951 software-heavy supply domains the top single words were `software`
117, `teams` 54, `development` 46. **The word tracks the cohort's SIC code.**
A statistic that moves with the industry classification and not with the
research is not measuring research.

The reason is structural and it is in §1.1: the `{line}` fallback contains
no research at all — it is template text plus the record's own sector and
name. Of course `marketing` matches a marketing agency's website.

**A 55.7% pass rate built like this is the defect, not the fix.**

### 2.1 AND HERE IS WHY THOSE WORDS AND NOT BETTER ONES

`facts.SNIPPET_CHARS` is 400 and `webfetch.readable_text` returns the
document in reading order, so **a fact's snippet is the first 400 characters
of the page — which on a modern site is the navigation bar.**

INTERIM, over 1,561 facts on the first 867 cohort domains:

    navigation-led snippets                     1,251   80.1%
    domains where EVERY fact is navigation-led    437   of 581 packed

Counted, not asserted: a snippet is navigation-led when it carries three or
more items of menu furniture (`NAV_WORDS` in the script), and no word on
that list is something a company says about itself. A real one, verbatim:

    "Meet us in Cologne August 26-30, 2026 Book a Meeting For Business
     For CEO For CFO For Startup Founders For GameDev API Integration
     Global Compliance For Contractors Pricing Resources Referral Program
     Blog Free tools Glossary Market Report 2025 ..."

That fact is not *wrong*. It has a source URL, it is on the company's own
domain and `site.on_this_domain` admitted it. It simply **says nothing about
the company**, so matching an opener against it is matching against a menu.

**This is fixable and the fix is not this lane's to make.** It is in
`webfetch._page` / `facts.SNIPPET_CHARS` — raise the cap so the snippet
reaches the prose, or have `readable_text` skip the leading navigation
block. Both belong to lane C and to master. Forking `site.py` to work around
it is what this lane was told not to do, and is what would have hidden the
measurement.

### 2.2 AND THE FIX IS MEASURED, NOT ARGUED — RAISE `SNIPPET_CHARS` TO 2000

A diagnosis nobody tests is a story, and §2.1's leads to a change in shared
code, so the counterfactual was measured first.
`scripts/researchpack_snippet_probe.py` reads 150 seeded cohort domains ONCE
and scores each at four snippet lengths. Nothing is edited, `facts.make` is
not called at a different limit, and identity is still asked through
`site.on_this_domain`. 79 answered with a page on their own domain:

| snippet | passes rule 1 | of passes, on ONE word | menu items per 400 chars |
| ---: | ---: | ---: | ---: |
| **400** (today) | 68 · 86.1% | 18 · 26.5% | **4.16** |
| 1000 | 74 · 93.7% | 14 · 18.9% | 2.16 |
| **2000** | 76 · 96.2% | **8 · 10.5%** | **1.47** |
| 8000 | 76 · 96.2% | 4 · 5.3% | 1.25 |

**400 → 2000 is worth about +10pp of pass rate AND cuts single-word passes
by 60% relative.** It is the rare change that raises a number and makes it
mean more at the same time. 8000 buys nothing further on pass rate and
starts putting paragraphs of somebody else's prose into the pack, which
`facts.py`'s own docstring gives as the reason for a cap at all. **The
recommendation is 2000**, and it is one constant.

The density column is the finding: **the first 400 characters of a page are
three times more menu than the rest of it.** It is given as a density
deliberately — a first version of this probe reported the `navigation_led`
FLAG per length and it ROSE with the limit, 67.9% → 94.9%, which reads as
"longer snippets are more navigational". That is the threshold, not the
prose: the flag asks for three or more menu items and a longer text contains
more of everything. Corrected before it was reported, and recorded here
because the artefact is the kind that survives review.

Its denominator is domains that ANSWERED, so its 86% is not comparable with
the walk's 42% in §1, which counts every attempt.

---

## 3. WHAT THE PUSH CAN ACTUALLY CARRY TODAY

`--cohort-out` writes the packed, rule-1-passing domains as JSONL, ranked
the way the walk is ordered — clean domains first, then most contacts, then
a readable MX — carrying the contact count, the MX status, the fact count
and the grounding words per domain, so lane J's cut and the verifier's
~2,500-address ceiling join against it without re-deriving anything.

**On the honest reading, the pushable number is not the headline.** Of the
483 INTERIM passes, 153 rest on category words alone and 164 on a single
word. Subtracting the single-word passes leaves **319 domains / roughly 720
contacts** whose grounding is more than one word — and even those rest on a
400-character snippet that is 80% navigation.

Three numbers, three questions:

- **1,092 contacts** — what the gate will accept.
- **~720 contacts** — what survives dropping the one-word passes.
- **179** — lane J's pre-crawl baseline, which this replaces.

The push should be sized against the second and reported against the third.

### 3.1 THE SERVED PACK SET IS A UNION, NOT THIS LANE'S CACHE ALONE

Lane J marks **128 cohort domains** (179 contacts) as already carrying a
pack fact. This lane packs **73 of those 128** and gets nothing at all for
the other **55** — those 55 were packed by an earlier pass whose facts came
from sources this lane does not run, and their sites defeat the free
crawler today.

So the pack set a push should serve is
`researchpack-us-cohortJ-cache-2026-09-25.json` **plus** the three
pre-existing caches in §7, not this lane's file alone. Serving only this
lane's cache would silently un-pack 55 domains that were already ready.

### 3.2 WHY THE COHORT'S SINGLE WORD IS `marketing`

**10,565 of the 12,407 contacts are `Marketing & Advertising`** — 85% of
the cohort, one industry. `template_vars` puts `{sector}` in the opener, so
the opener says "marketing" about a marketing agency and the agency's own
website says it back. That is the whole mechanism, and it is why lane C saw
the identical word on a UK/EU cohort of the same shape, and why the
abandoned supply walk — software-heavy — showed `software` instead.

---

## 4. K, AND THE EVIDENCE FOR IT

**K = 48.** Measured, not inherited from lane C's K=8.

Disjoint 300-domain windows per K — because `webfetch.robots_allows` caches
per domain and the OS caches DNS, so re-running one window at a higher K
measures the warm cache and calls it concurrency:

| K | 300 domains in | rate |
| ---: | ---: | ---: |
| 12 | 68.7s | 4.364 dom/s |
| 24 | 54.8s | 5.477 dom/s |
| **48** | **42.0s** | **7.139 dom/s** |
| 64 | 40.6s | 7.385 dom/s |
| 96 | 36.6s | 8.196 dom/s |

An earlier 40-domain sweep is in the commit history and is NOT the basis for
the choice: at that size one slow domain moves the makespan more than K
does, and the rates came back non-monotonic (K=8 3.08, K=16 1.99, K=24 3.78,
K=32 1.99). The 300-domain windows are the measurement.

48 takes 96% of 64's rate and 87% of 96's for a third to half the concurrent
sockets, and the curve is flat past it. **Per-host concurrency is 1 at every
K**: one worker owns one domain end to end, so the politeness bound a
crawler actually owes a site is respected however high K goes. Robots is
asked per domain either way, and no bound in `webfetch.settings` was changed
— the run prints them: 6 pages, 512KB/page, 10s request, 45s domain, 3
redirects, robots respected.

**Observed live: 10.7 dom/s on the supply walk and 11.3 dom/s on the
cohort**, half again the calibration. 10,418 domains in about 15 minutes,
against lane C's single-threaded rate of roughly six hours for the same set.

---

## 5. $0.00, AND THE LEDGER THAT PROVES IT

- **`work/spend-ledger.jsonl` is byte-identical before and after.**
  sha256 `64baeef9050a5fdd06865466778edd15449ea5761c54e6c17157f1ddf877bbb2`,
  599,901 bytes, mtime `2026-09-24T23:18:47Z` — lane C's last row.
  **Zero rows dated 2026-09-25.** Re-verified in §9.
- **No Apify call was made.** `src/providers/apify` is imported for
  `check_url` alone, which is a pure URL-safety function that starts no run
  and needs no token. `build_input("site_content", ...)` cannot be reached
  from here; lane C deleted the actor.
- Every row in both logs carries `"provider": "local_http", "usd": 0.0`, and
  `pack_one` **raises** if the site source ever reports a non-zero cost
  rather than recording it.
- No provider write, no EmailBison call, no HeyReach call, no write to
  `work/queue.jsonl` or `work/campaigns.jsonl`. Lane J's cohort file is
  **read only**.

---

## 6. THE SSRF GATE THE FREE PATH DID NOT HAVE, AND IT FIRED ON REAL DATA

`apify.check_url` is this repository's SSRF posture — scheme, credentials,
port, loopback names, internal suffixes, private and reserved addresses, and
DNS resolution of the host. **It guards the Apify input path only.
`webfetch.research` never calls it.** `webfetch` has its own bounds (https
only, `same_domain`, bounded redirects, robots, byte/page/wall caps) but it
does not ask whether a domain resolves into RFC1918.

With tens of thousands of strings arriving from sourcing files that is worth
closing, so every domain is gated before the crawler sees it. **The function
is imported and called, never edited. Nothing was widened. No allowlist was
touched.**

It refused a real supply domain on the live walk:

    zendrive.com  ->  UNSAFE_URL
    "zendrive.com resolves to the private address 0.0.0.0"

A dead or parked domain, and `0.0.0.0` means "this host" to a `connect()` on
most stacks. `webfetch` alone would have tried it.

### 6.1 One refusal in thousands is also what an inert gate looks like

So it is driven and asserted on rather than admired.
`scripts/researchpack_us_guardcheck.py` calls **`pack_one` itself**, not a
copy, with loopback names, internal suffixes, `127.0.0.1`, `10.0.0.7`,
`192.168.1.1`, the cloud metadata address `169.254.169.254`, `[::1]`, an
off-port host and credentials in the host field — and replaces the crawler
with one that **raises if it is ever reached**, so a refusal that did not
happen fails loudly instead of passing quietly. Each case asserts WHY it was
refused, so a case refused by a different guard than the one it exists to
prove also fails. `example.com` is in the set for the opposite reason: a
gate that refuses everything proves nothing.

**One expectation was wrong and the GUARD was right.** `[::1]` was expected
to fail as "no host in url"; `urlsplit` parses the brackets as an IPv6
literal and it is refused as the loopback address it actually is. The
expectation was corrected to what the guard proves.

`site.on_this_domain` is asked the same way, including
`acme.com.evil.net` — the suffix attack the check exists for — and both
fail-closed cases. Exit 0.

---

## 7. WHAT I RE-MEASURED IN THE BRIEF, AND WHERE IT DIFFERS

The lane rests on "zero of the sourced domains carry a research pack" and
"the 439 we have packed are disjoint from the supply", so it was re-measured
rather than inherited — `scripts/researchpack_us_gap.py`.

| | measured |
| --- | ---: |
| domains with ≥1 fact in the three **servable caches** | 137 |
| domains **named** by any research artefact in `work/` | 178 |
| …of those, in `qualified-supply` | 105 |
| …of those, **in the US supply slice** | **0** |

Lane J's own file agrees from the other side: **179 of its 12,407 contacts
carry `readiness.research_pack_fact: true`** and the rest do not.

**The operational claim holds exactly.** Two details in the brief do not:

- **The 439 is not reproducible from `work/`.** Most research artefacts
  there are run REPORTS (`summary`/`packs`/`charges`), not caches a pack
  build can be served from. The three cache-shaped files carry 137 domains
  with facts; the union of every artefact, reports included, is 178.
- **The packed set is not disjoint from the supply.** 105 of the 178 are in
  `qualified-supply`. All UK/EU, which is why the US number is still zero
  and why nothing about the plan changes.

`researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json` was **never opened** —
the script skips it by name and says so in its output.

---

## 8. FILES

    scripts/researchpack_us_crawl.py       the walk: priority, K, SSRF gate, JSONL
    scripts/researchpack_us_rule1.py       the four numbers, contacts, single-word
    scripts/researchpack_us_gap.py         §7, the claim the lane rests on
    scripts/researchpack_us_guardcheck.py  §6.1, the guards driven and asserted
    scripts/researchpack_us_seed.py        §0, the four rows carried across
    docs/MERGE-REQUEST-2026-09-25-US-PACK-CRAWL.md

Under `work/` (gitignored, new, named for this lane):

    work/researchpack-us-cohortJ-2026-09-25.jsonl       THE crawl log
    work/researchpack-us-cohortJ-cache-2026-09-25.json  THE servable cache
    work/researchpack-us-cohort-2026-09-25.jsonl        ranked, packed, rule-1
    work/researchpack-us-rule1-2026-09-25.json          the report as JSON
    work/researchpack-us-cold-2026-09-25.jsonl          the abandoned supply walk
    work/researchpack-us-CALIBRATION.jsonl              §4

**Nothing in `src/` was touched.** `src/researchpack/site.py` is lane C's and
is loaded from its own git blob at run time — blob
`225f4354418419b20c5b9bd1ca15015ab6ded17e`, printed by every run — rather
than copied into this branch, because a copy in `src/` is a fork somebody
later edits. `src/webfetch.py` and `src/researchpack/facts.py` are
byte-identical on master and on lane C's branch (`git rev-parse` on both
agrees: `f322fe06…` and `b6fbe7c9…`), so those are imported normally.

The **cache** is written in `src/researchpack/cache.py`'s own shape — keyed
`domain::site_content`, with `retrieved_at`, `facts` and `cost: 0` — so
`RESEARCH_PACK_CACHE` can be pointed straight at it. `cache.put` itself is
deliberately not used for the walk: it loads and rewrites the whole cache per
entry, which is O(n²) over ten thousand domains. **Only domains with at
least one fact get an entry**: an entry with an empty `facts` list is a
30-day promise that a domain has been researched, and it has not.

---

## 9. FINAL FIGURES

*Written when the walk ends. Until then §1, §2 and §3 are INTERIM on the
first 867 domains.*

---

## 10. WHAT REMAINS UNVERIFIED

1. **Rule 1 is projected, not measured**, for all but the handful of cohort
   domains that carry rendered s7 copy. §1.1.
2. **The projection assumes the `{line}` fallback.** If S7 is ever made to
   render step 1 FROM the pack — the real fix for §2, and lane H's and
   production's code rather than this lane's — every number in §1 and §2 is
   void and must be re-measured, not adjusted.
3. **`facts.published_at` is `null` on every site fact**, by lane C's
   deliberate design: a crawled page carries no publication date worth
   trusting, and stamping `retrieved_at` there would make every fact read as
   published today. The acceptance bar asks for source, date and snippet:
   source and snippet are on the fact and were checked on **every** one of
   them; **the date is `retrieved_at` at PACK level, not `published_at` on
   the fact.** Said plainly rather than left for a reader to discover.
4. **Lane J's cohort is taken on report.** This lane read its file and did
   not re-derive the provider readback, the 28,118-lead estate walk or the
   exclusion cuts behind it. Its own `exclusions.unsubscribed` and
   `exclusions.linkedin_any_channel` are recorded as NOT_READABLE /
   NOT_JOINABLE, which is absence of the binding and not evidence of none —
   that caveat travels with every number here.
5. **Coverage is this estate's and this crawler's.** 67% on US marketing and
   advertising firms is not a web-wide rate, and `HTTP_INSUFFICIENT` is a
   property of the sites rather than a crawler failure.
6. **The 30-day cache TTL is still untested against reality**, unchanged
   since the pilot.
7. **`pack_one` classifies an unexpected crawler exception as
   `RESEARCH_FAILED` and records the exception text.** Classified rather
   than swallowed, and the count is in the outcomes table — but a genuine
   crawler bug would land in that bucket beside real network failures.
8. **The full suite was not run by this lane.** Nothing in `src/`,
   `config/` or `tests/` changed, so there is no import path from this work
   to any test and the five scripts are new files with no importer.
   `scripts/suite_verdict.txt` was not touched — lane C's §9 explains why
   two lanes each merging their own verdict is how a stale one comes to
   exist.

---

## 11. HOW TO MERGE THIS

Branch `worktree-agent-a743eb2e1661cce8f`, branched from master at
`24acafff` — the same base as lane C's. Master has moved since, so
`git diff master..HEAD` will show deletions of files this branch simply
predates. **Those are not deletions this branch makes.**

Five new scripts and one new doc. **No file in `src/`, `config/` or
`tests/` is touched at all**, so this merges without interacting with lane
B's cadence files, lane D's `packfacts`/copylint, lane G's account rule,
lane H's re-render, lane I's re-engagement or lane J's cohort cut.

It does **not** depend on lane C's branch being merged: `site.py` is read
from lane C's blob at run time and every run prints the sha. If lane C
merges, nothing here changes. If lane C's `site.py` is ever edited, this
lane's runs keep pointing at the old blob by sha until `LANE_C_SITE`'s
constant is updated — stated because it is a real staleness hazard, not
hidden.
