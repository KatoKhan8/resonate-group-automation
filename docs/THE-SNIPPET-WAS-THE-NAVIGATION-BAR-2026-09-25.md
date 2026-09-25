# The snippet was the navigation bar

LANE O, 2026-09-25. Packs for the US cold cohort, re-crawled at
`SNIPPET_CHARS = 2000`. **Nothing here spent a cent, nothing here sent, and
no Apify actor ran.**

## THE ONE-LINE ANSWER

Re-crawling at 2000 characters instead of 400 leaves the same sites, the
same pages and the same facts, and changes what the fact CONTAINS. On the
same crawl, re-truncated both ways:

| | 400 | 2000 |
|---|---|---|
| menu words per 400 characters | 5.26 | **2.01** |
| rule-1 passes (of domains) | 49.4% | **54.0%** |
| passes resting on ONE word | 33.5% | **12.3%** |
| fact-carrying domains offering a quotable span | 56.8% | **93.4%** |
| median anchor a pack-grounded render would carry | 16 | **20** |
| median anchor of the template opener production renders today | 2 | **2** |

The last row is the honest one and it is why this document does not stop at
the row above it.

**And one row in that table should not be read as grounding at all.** A
control run afterwards - matching each domain's opener against a DIFFERENT
company's pack - shows rule 1 passing against a stranger's pack 75.7% of the
time at 400 and **93.9%** at 2000. The pass-rate gain is very largely the
gate getting easier to satisfy. The anchor, asked the same way, matches the
wrong company's pack **zero times at either cap.** See the control section
below; it is the most useful thing this lane measured.

## WHY THE ANCHOR AND NOT THE PASS RATE

Rule 1 asks whether any opener token over four characters appears anywhere
in the pack. A dump of a company's prose answers that by accident. Lane K
measured **1,496 of 4,478 passes resting on a single word, `marketing` in
579 of them** - because 10,565 of the 12,407 contacts are Marketing &
Advertising, the opener puts the sector in its first line, and the site says
it back. The word tracks the SIC code. That is the proof it is not research.

Lane H measured the same thing from the other end: before its re-render the
longest contiguous phrase any of 128 openers shared with its own pack was
**three words, and not one reached four**; after, every one was **>= 7**.

So the anchor is the measurement and a pass rate that rises while the anchor
does not has not worked. This lane reports **two** anchors, because reporting
one would be a report that agrees with itself:

- **The template anchor** is the anchor of the opener production renders
  today. **It is 2 at both caps and the cap does not move it.** It cannot:
  the opener is a template over sector, angle and company name, and the most
  a site can share with it is a phrase like the sector name. Raising the
  snippet cap does not make a template quote a website.
- **The grounded anchor** is the length of the span lane H's renderer would
  quote, because its step 1 carries that span verbatim, so the span IS the
  anchor. **This is the one the cap moves, and it moves the other way too:
  the share of fact-carrying domains that offer any quotable span at all
  goes from 56.8% to 93.4%.**

Read together they say something precise. **The snippet cap does not improve
today's copy. It removes the reason lane H had to hold most of its leads.**
Lane H held 103 of 128, 52 for "no quotable span on any admitted page" and 31
for "no site page admitted to this pack" - which is what a 400-character
navigation bar looks like from the renderer's side. On this cohort that hold
reason collapses from 295 domains to 35 in the first 2,048.

## THE CONTROL, AND WHY THE RULE-1 GAIN IS NOT THE HEADLINE

Five times the snippet is five times the chance of an accidental token
match, so the rising pass rate needed a control before it could be reported
as quality. The control is to match each domain's openers against **a
different domain's pack**. On the 313 domains carrying both:

| | rule 1 vs its own pack | vs somebody else's | anchor >= 4 own | vs somebody else's |
|---|---|---|---|---|
| cap 400 | 278 | **237 (75.7%)** | 4 | **0** |
| cap 2000 | 304 | **294 (93.9%)** | 9 | **0** |

**Rule 1 barely discriminates, and raising the cap makes it worse.** At 400
an opener passes against a stranger's pack three times in four. At 2000 it
is fourteen times in fifteen. The ratio of right-pack to wrong-pack passes
falls from 1.17 to 1.03.

So the 94 domains the cap adds to the rule-1 count are very largely
accident, **and this document does not offer that number as grounding.** It
is the brief's own point, now measured from the other side: the word tracks
the SIC code, and 10,565 of the 12,407 contacts share one sector.

**The anchor discriminates perfectly.** A contiguous run of four or more
opener words appears in the right company's pack 4 times at 400 and 9 at
2000, and in the wrong company's pack **zero times at either cap**. A shared
phrase is not vocabulary; it is a quotation or it is nothing.

This is why the honest summary of the cap change is the quotable-span row
and not the pass-rate row. 56.8% to 93.4% is a real gain because it is a
gain in material that only the right company's site could have supplied.
49.4% to 54.0% is mostly the gate getting easier to satisfy.

## WHY 400 WAS THE WRONG NUMBER

`webfetch.readable_text` returns a page **in reading order**, and a modern
site opens with a menu, a language switcher and a cookie line. At 400
characters the fact was usually that furniture: of the 14,491 facts lane K
captured at 400, **11,719 (80.9%) were navigation-led, and on 4,512 domains
every single fact was.** `copylint.pack_text` then matched rule 1 against a
menu, which is how `software`, `teams` and `services` came to be the words
doing the work.

Lane K probed four caps on 79 domains. The operator took 2000. This lane did
not re-derive that and did not re-litigate it.

**One measurement here contradicted itself for a run and is worth stating.**
`navigation_led` is a boolean that fires at three menu words anywhere in the
snippet, so at 2000 characters it fired on 94.1% of facts against 83.5% at
400 - while each snippet carried five times the prose. Read as published it
says the change made things worse. It is not comparable across two caps, and
the comparable statistic is the one lane K's own probe used: **density, menu
words per 400 characters, which falls 5.26 to 2.01.** Both are printed by
`scripts/researchpack_anchor.py`, the boolean labelled as a boolean.

## WHAT THE CAP BOUGHT, DOMAIN BY DOMAIN

On the first 2,048 domains, same crawl, re-truncated:

| | domains |
|---|---|
| gained a rule-1 pass | 94 |
| **lost** a rule-1 pass | **0** |
| gained a quotable span where there was none | 477 |
| quotable span got longer | 957 |
| quotable span got shorter | 94 |
| came off a single-word pass | 238 |

Nothing regressed on the measurement that gates a send. The 94 shorter spans
are cases where a longer snippet let the span scorer prefer a different,
better-placed sentence.

## THE CROSS-SECTION, PER BATCH

Reported in shippability order, which is lane J's: clean domains before
domains where the estate holds an excluded person, then most contacts first,
because one crawl unlocks every address behind a domain and the binding
ceiling today is addresses.

First 2,048 domains / 3,145 contacts, at 2000:

| batch | domains | with a fact | rule 1 | resting on one word | median grounded anchor |
|---|---|---|---|---|---|
| 1-1000 | 1000 | 669 (66.9%) | 602 (60.2%) | 59 (9.8% of passes) | 20 |
| 1001-2000 | 1000 | 606 (60.6%) | 485 (48.5%) | 76 (15.7%) | 20 |

In contacts: **3,145 attempted, 2,020 behind a domain with a usable fact,
1,763 passing rule 1.** The full run is still walking and the final table
replaces this one.

## THE THINGS THAT COULD HAVE GONE WRONG AND WHAT WAS DONE ABOUT THEM

**The ledger.** The brief asks for it verified by hash before and after.
Ninety seconds into the crawl the sha256 had already moved, and it was not
this lane: 10 rows of `reoon` and `deliverable` email verification from
another live lane, and by the next check 3,572 rows had become 3,694. Lane
K's whole-file hash was sound because lane K had the estate to itself for
thirteen minutes; lanes M, N and P are live now, so the same check reports
their correct behaviour as this lane's spend. The assertion was narrowed to
one this lane can own and `scripts/researchpack_ledger_guard.py` checks it:
**no Apify row appeared while this lane ran.** The last Apify row in the
ledger is still 2026-09-24T23:18:47Z. The free path reaches no billable call
at all - `spendledger.record` has exactly one caller, `run_actor`, and
nothing in this lane calls it.

**Apify, and a hazard this lane did not touch.** No actor ran. The standing
ruling holds - site content from our own free crawler, Apify runs LinkedIn
only - and `apify~website-content-crawler` is still absent from
`actors.ACTORS`. Yesterday `open_roles` bought 93 runs and covered one
account; nothing here repeats that. **But the ceiling is still unchecked on
master:** `researchpack.pack.run_actor` calls `spendledger.record` and never
`spendledger.check`, so a live pack build on master can spend past the
budget. Lane C has already written the fix - `_may_spend` calling
`spendledger.check` before the run - and it is on lane C's branch, unmerged.
This lane left `pack.py` alone rather than write a second version of
somebody else's fix, but the gap is real on master today and it is only
invisible because nothing is currently buying.

**The SSRF gate.** Lane K's gate is kept exactly as written: every domain
goes through `providers.apify.check_url` with `resolve=True` before the
crawler sees the string, imported and called rather than edited, and no
allowlist was widened.

**Identity.** Asked three times now and fail-closed each time -
`webfetch.same_domain` during the crawl, lane C's `site.on_this_domain` when
the fact is made, and lane C's `is_this_company` against `source_url` when
the fact becomes servable. The third refused **0 of 15,760** facts, which is
the control: the counter is supposed to stay at zero, and if it moves, two
authors have stopped agreeing about identity.

**The quarantined cache.** `researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json`
is refused **by name** in `researchpack_union_cache.py`, so a caller who
passes it gets an error rather than a pack.

**Redaction.** `scripts/researchpack_redact_check.py` checks a file against
the entire cohort - every domain, contact key, local-part, company name,
surname and LinkedIn slug - before it is committed, with a self-test that
has a control. It found four false-positive defects in itself before it
found anything in a document, and it was red-teamed with a file naming one
real domain, company and contact key: refused, exit 1, all three found.
Every tracked file this lane wrote is clean.

## SERVE THE UNION. NEITHER LOG ALONE IS COMPLETE

Lane J marks 128 cohort domains as already packed, from
`work/researchpack-us-CALIBRATION.jsonl`. Merging the logs measures the real
one-sided loss and it is larger than 128: **lane K's 400-character run
carries 6,057 fact-carrying domains and misses 488 that the calibration log
holds.** A site that answers at 09:40 can be down at 11:10 and it runs both
ways, so a push served from either log alone gets a smaller cohort than this
system has actually researched.

Precedence in the union is **by cap, not by clock**: a later log wins only
where it carries facts, so a domain that answered before and timed out on
the re-crawl keeps its pack instead of losing it; and the 2000-character log
outranks the 400-character ones for the same domain, because the cap is the
whole reason for re-crawling.

## CARRY THIS FORWARD: `published_at` IS NULL BY DESIGN

**Every site fact has `published_at": null` and this is correct.** A crawled
page carries no publication date worth trusting, and stamping one would make
every site fact read as published today - which is how a four-year-old page
becomes "they just announced". Source and snippet are **per fact**; the date
is **`retrieved_at` at pack level**, written on every cache entry.

The QA spec asks for "source, date and snippet" per fact. **Read literally,
per fact, that check refuses every one of the facts this cohort has** - all
14,491 at 400 and all of the re-crawl. It has to read the date at pack
level. This is not a gap to fill by inventing dates; it is a spec that has to
name the level it reads at.

## THROUGHPUT, AND THE ONE DECISION NOT TAKEN

The operator's decision was 8-way and the run is 8-way. Measured on this
estate, for the record rather than as an argument: K=8 sustains **2.6
domains/sec**, so 10,418 domains take about **70 minutes**. Lane K measured
**13.0 dom/s at K=48**, which is the same work in 13. A four-way sample
taken from disjoint windows mid-list came out 1.08 / 1.69 / 4.31 / 2.95
dom/s at K=8/16/32/48 - noisy at n=60 and not a basis for overriding a
decision. Per-host concurrency is 1 at every K by construction, because one
worker takes one domain end to end.

**8-way finishes today, so nothing was changed.** If tomorrow's push wants
the whole 12,407 re-crawled inside a coffee break rather than inside an
hour, K=48 is measured, free and politeness-neutral - that is a question for
the operator, not an assumption for this lane.

## WHAT RUNS

    scripts/researchpack_us_crawl.py      lane K's, byte-identical
    scripts/researchpack_us_rule1.py      lane K's, byte-identical
    scripts/researchpack_anchor.py        the anchor, per batch, per cap
    scripts/researchpack_union_cache.py   the union, identity-checked
    scripts/researchpack_ledger_guard.py  did THIS lane spend anything
    scripts/researchpack_redact_check.py  does this file name anybody

`anchor_run` and `grounded_fact` are lane H's, materialised from lane H's
git blob at run time and the sha printed. `site.py` and `actors.py` are lane
C's, the same way. `pack_text`, `first_line` and `_WORD` are production's
`copylint` - the gate itself. Nothing here restates another lane's matching,
because a second copy of it would be a number that agrees with this
document and not with the system.

The only change to `src/` is one constant and its reasoning:
`researchpack.facts.SNIPPET_CHARS`, 400 to 2000. The 21 researchpack tests
pass and none of them pinned 400.
