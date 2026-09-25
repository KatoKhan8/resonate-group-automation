# The snippet was the navigation bar

LANE O, 2026-09-25. Packs for the whole US cold cohort, re-crawled at
`SNIPPET_CHARS = 2000`. **10,418 domains / 12,407 contacts, 62 minutes at
K=8, $0.00000, no Apify actor ran.**

## THE ONE-LINE ANSWER

Re-crawling at 2000 characters instead of 400 leaves the same sites, the
same pages and the same 14,524 facts, and changes what a fact CONTAINS. The
whole cohort, one crawl, re-truncated both ways:

| | 400 | 2000 |
|---|---|---|
| menu words per 400 characters | 5.35 | **1.99** |
| rule-1 passes (of 10,418 domains) | 4,463 (42.8%) | 4,926 (47.3%) |
| passes resting on ONE word | 1,475 (33.0%) | **647 (13.1%)** |
| fact-carrying domains offering a quotable span | 3,446 (57.0%) | **5,600 (92.7%)** |
| median anchor a pack-grounded render would carry | 16 | **20** |
| median anchor of the template opener production renders today | 2 | **2** |
| rule 1 passing against the **wrong** company's pack | 70.6% | **91.8%** |
| anchor >= 4 words against the **wrong** company's pack | **0** | **0** |

Two of those rows are the reason this document is longer than one table.
**The pass rate is not the finding and the cap makes rule 1 worse, not
better.** The quotable span is the finding.

## THE CONTROL, AND WHY THE RULE-1 GAIN IS NOT THE HEADLINE

Five times the snippet is five times the chance of an accidental token
match, so a rising pass rate needed a control before it could be reported as
quality. The control is to match each domain's own openers against **a
different domain's pack**. On the 986 domains that carry both:

| | rule 1 vs its own pack | vs somebody else's | anchor >= 4 own | vs somebody else's |
|---|---|---|---|---|
| cap 400 | 878 | **696 (70.6%)** | 20 | **0** |
| cap 2000 | 961 | **905 (91.8%)** | 38 | **0** |

**Rule 1 barely discriminates, and raising the cap makes it worse.** At 400
an opener passes against a stranger's pack seven times in ten. At 2000 it is
more than nine times in ten. The ratio of right-pack to wrong-pack passes
falls from 1.26 to 1.06.

So the 463 domains the cap adds to the rule-1 count are very largely
accident, **and this document does not offer that number as grounding.** It
is the brief's own point measured from the other side: the word tracks the
SIC code, and 10,565 of the 12,407 contacts share one sector. `marketing`
is still the commonest single word behind a pass, 573 times at 400 and 206
at 2000.

**The anchor discriminates perfectly.** A contiguous run of four or more
opener words appears in the right company's pack 20 times at 400 and 38 at
2000, and in the wrong company's pack **zero times at either cap**. A shared
phrase is not vocabulary; it is a quotation or it is nothing.

That is why the honest summary of the cap change is the quotable-span row.
**57.0% to 92.7% is a real gain, because it is a gain in material only the
right company's site could have supplied.** 42.8% to 47.3% is mostly the
gate getting easier to satisfy.

## THE TWO ANCHORS, AND WHY BOTH ARE REPORTED

- **The template anchor** is the anchor of the opener production renders
  today, from `cadence.TEMPLATES["persona_pain"]`. **It is 2 at both caps
  and the cap does not move it, in any batch.** It cannot: that opener is a
  template over sector, angle and company name, and the most a site can
  share with it is the sector word. Raising a snippet cap does not make a
  template quote a website.
- **The grounded anchor** is the length of the span lane H's renderer would
  quote, because its step 1 carries that span verbatim, so the span IS the
  anchor. Median 16 at 400, **20 at 2000**.

Read together they say something precise. **The snippet cap does not improve
today's copy. It removes the reason lane H had to hold most of its leads.**
Lane H held 103 of 128, 52 of them for "no quotable span on any admitted
page" and 31 for "no site page admitted to this pack" - which is what a
400-character navigation bar looks like from the renderer's side. Across
this whole cohort that hold reason collapses:

| hold | 400 | 2000 |
|---|---|---|
| no quotable span (nothing usable at all) | 573 | **91** |
| page is navigation end to end (2 pages) | 209 | **26** |
| the only quotable spans are not in English | 193 | **34** |

**The cap's real product is 2,154 domains that gained a quotable span where
they had none.** Those are the domains a pack-grounded render can now reach.

## WHY 400 WAS THE WRONG NUMBER

`webfetch.readable_text` returns a page **in reading order**, and a modern
site opens with a menu, a language switcher and a cookie line. At 400
characters the fact was usually that furniture: of the 14,491 facts lane K
captured at 400, **11,719 (80.9%) were navigation-led, and on 4,512 domains
every single fact was.** `copylint.pack_text` then matched rule 1 against a
menu, which is how `software`, `teams` and `services` came to be the words
doing the work.

Lane K probed four caps on 79 domains and the operator took 2000. This lane
did not re-derive that and did not re-litigate it.

**One measurement contradicted itself for a run and is worth stating.**
`navigation_led` is a boolean that fires at three menu words anywhere in a
snippet, so at 2000 characters it fired on 13,613 facts against 11,752 at
400 - while each snippet carried five times the prose. Read as published it
says the change made things worse. **It is not comparable across two caps.**
The comparable statistic is the one lane K's own probe used: density, menu
words per 400 characters, **5.35 down to 1.99**. Both are printed by
`scripts/researchpack_anchor.py`, the boolean labelled as a boolean.

## WHAT THE CAP BOUGHT, DOMAIN BY DOMAIN

Whole cohort, same crawl, re-truncated:

| | domains |
|---|---|
| gained a rule-1 pass | 463 |
| **lost** a rule-1 pass | **0** |
| gained a quotable span where there was none | 2,154 |
| quotable span got longer | 4,363 |
| quotable span got shorter | 448 |
| came off a single-word pass | 1,028 |

Nothing regressed on the measurement that gates a send. The 448 shorter
spans are cases where more text let the span scorer prefer a different,
better-placed sentence.

## THE CROSS-SECTION, PER BATCH, AT 2000

In shippability order, which is lane J's: clean domains before domains where
the estate holds an excluded person, then most contacts first, because one
crawl unlocks every address behind a domain and the binding ceiling today is
addresses, not domains.

| batch | domains | with a fact | rule 1 | resting on one word | median grounded anchor |
|---|---|---|---|---|---|
| 1-2000 | 2000 | 1277 (63.9%) | 1092 (54.6%) | 140 (12.8% of passes) | 20 |
| 2001-4000 | 2000 | 1116 (55.8%) | 873 (43.6%) | 117 (13.4%) | 20 |
| 4001-6000 | 2000 | 1081 (54.0%) | 839 (42.0%) | 112 (13.3%) | 20 |
| 6001-8000 | 2000 | 1084 (54.2%) | 839 (42.0%) | 115 (13.7%) | 20 |
| 8001-10000 | 2000 | 1230 (61.5%) | 1060 (53.0%) | 142 (13.4%) | 20 |
| 10001-10418 | 418 | 254 (60.8%) | 223 (53.3%) | 21 (9.4%) | 21 |
| **all** | **10418** | **6042 (58.0%)** | **4926 (47.3%)** | **647 (13.1%)** | **20** |

**The quality of a pass does not decay down the list.** Single-word passes
sit between 9.4% and 13.7% in every batch and the median anchor is 20 in
every batch. What decays is the hit rate: the first and fifth batches answer
at ~62-64% and the middle at ~54%, which is a property of which sites are up
and not of where they sit in the ranking.

**In contacts: 12,407 attempted, 7,386 behind a domain with a usable fact,
6,182 passing rule 1 at 2000** - against 5,601 at 400.

## SERVE THE UNION. NEITHER LOG ALONE IS COMPLETE

| log | fact-carrying domains | misses that the others have |
|---|---|---|
| the 09-25 calibration run | 609 | 6,058 |
| lane K's 400-char run | 6,057 | **610** |
| this lane's 2000-char run | 6,042 | **625** |
| **union** | **6,667** | - |

Lane J flagged 128 cohort domains as already packed. The real one-sided loss
is five times that: **lane K's run alone misses 610 fact-carrying domains,
and this lane's alone misses 625.** A site that answers at 09:40 can be down
at 11:10 and it runs both ways, so a push served from any single log gets a
smaller cohort than this system has actually researched. The union serves
**6,667 domains and 16,056 facts** - 610 more domains than the best single
log.

Precedence is **by cap, not by clock**: a later log wins only where it
carries facts, so a domain that answered before and timed out on the
re-crawl keeps its pack instead of losing it; and the 2000-character log
outranks the 400-character ones for the same domain, because the cap is the
whole reason for re-crawling. Of the 6,667 served, 6,042 come from the
2000-char run, 481 from the calibration run and 144 from lane K's.

**The union file is proven servable rather than assumed so.** The writer
ends by pointing `RESEARCH_PACK_CACHE` at what it just wrote and asking
production's own `researchpack.cache.get` for an entry at
`<domain>::site_content` - the key lane C's `build` asks for - and checks
facts present, cost 0, pack-level `retrieved_at` present, every
`published_at` null, every fact carrying a source and a snippet. With the
control that matters: a domain not in the file must come back `None`,
because without it the check passes for a reader that returns something for
every string.

## CARRY THIS FORWARD: `published_at` IS NULL BY DESIGN

**Every site fact has `published_at: null` and this is correct.** A crawled
page carries no publication date worth trusting, and stamping one would make
every site fact read as published today - which is how a four-year-old page
becomes "they just announced". Source and snippet are **per fact**; the date
is **`retrieved_at` at pack level**, written on every cache entry.

The QA spec asks for "source, date and snippet" per fact. **Read literally,
per fact, that check refuses every fact this cohort has** - all 14,524 of
them, at either cap. It has to read the date at pack level. This is not a
gap to fill by inventing dates; it is a spec that has to name the level it
reads at.

## THE THINGS THAT COULD HAVE GONE WRONG

**The ledger.** The brief asks for it verified by hash before and after.
Ninety seconds into the crawl the sha256 had already moved, and it was not
this lane. By the end **12,822 rows had been appended - 6,402 `reoon` and
6,420 `deliverable` address verifications from other live lanes.** Lane K's
whole-file hash was sound because lane K had the estate to itself for
thirteen minutes; lanes M, N and P are live now, and the same check would
have reported their correct behaviour as this lane's spend. An alarm that
fires on somebody else's correct behaviour is an alarm nobody reads twice.

So the assertion was narrowed to one this lane can own, and
`scripts/researchpack_ledger_guard.py` checks it: **no Apify row appeared
while this lane ran.** The last Apify row in the ledger is still
`2026-09-24T23:18:47Z`, unmoved across 62 minutes. The free path reaches no
billable call at all - `spendledger.record` has exactly one caller,
`researchpack.pack.run_actor`, and nothing in this lane calls it. The
crawler's own belt-and-braces check, which raises if the free crawl ever
reports a cost, never fired: **$0.00000 over 10,418 domains.**

**Apify, and a hazard this lane did not touch.** No actor ran. The standing
ruling holds - site content from our own free crawler, Apify runs LinkedIn
only - and `apify~website-content-crawler` is still absent from
`actors.ACTORS`. Yesterday `open_roles` bought 93 runs and covered one
account; nothing here repeats that. **But the ceiling is still unchecked on
master:** `researchpack.pack.run_actor` calls `spendledger.record` and never
`spendledger.check`, so a live pack build on master can spend past the
budget. Lane C has written the fix - `_may_spend` calling `spendledger.check`
before the run - and it is unmerged on lane C's branch. This lane left
`pack.py` alone rather than write a second version of somebody else's fix,
but the gap is real on master today and is only invisible because nothing is
currently buying.

**The SSRF gate.** Lane K's gate is kept exactly as written: every domain
goes through `providers.apify.check_url` with `resolve=True` before the
crawler sees the string, imported and called rather than edited, and no
allowlist was widened. **0 domains were refused on this run** - lane K's run
refused one that resolved to `0.0.0.0`, and the gate staying quiet on a
second pass is the expected result, not evidence it is absent.

**Identity.** Asked three times and fail-closed each time -
`webfetch.same_domain` during the crawl, lane C's `site.on_this_domain` when
the fact is made, and lane C's `is_this_company` against `source_url` when
the fact becomes servable. The third refused **0 of 16,056** facts, which is
the control: the counter is supposed to stay at zero, and if it ever moves,
two authors have stopped agreeing about identity. Unverifiable is not a pass.

**The quarantined cache.**
`work/researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json` - 50 of whose 71
job rows belonged to a different company - is refused **by name** in
`researchpack_union_cache.py`, so a caller who passes it gets an error
rather than a pack.

**Redaction.** `scripts/researchpack_redact_check.py` checks a file against
the entire cohort - 77,586 distinct strings: every domain and domain stem,
contact key, email local-part, company name, surname, LinkedIn url and slug
- before it is committed, with a self-test that has a control. It found four
false-positive defects in itself before it found anything in a document, and
it was red-teamed with a file naming one real domain, company and contact
key: refused, exit 1, all three found. Every tracked file this lane wrote is
clean. Hits are reported as kind and length only, because printing the value
is the same leak one step removed.

This matters more than it looks. The anchor report's own
`single_word_top` - the list of words rule 1 matched on - contains one-word
company names on this cohort, because a one-word brand whose site says it
back is exactly what a single-word pass is. **That list is a leak that looks
like a statistic** and it stays in `work/`, which is gitignored.

## THROUGHPUT, AND THE ONE DECISION NOT TAKEN

The operator's decision was 8-way and the run was 8-way: **10,418 domains in
3,740 seconds at 2.721 dom/s.** Lane K measured **13.0 dom/s at K=48** - the
same work in 13 minutes instead of 62. A four-way calibration on disjoint
mid-list windows came out 1.08 / 1.69 / 4.31 / 2.95 dom/s at K=8/16/32/48,
noisy at n=60 and not a basis for overriding anything. Per-host concurrency
is 1 at every K by construction, because one worker takes one domain end to
end.

**8-way finished inside the hour, so nothing was changed and nothing needed
asking.** If a future re-crawl of the full 12,407 wants to fit in a coffee
break rather than an hour, K=48 is measured, free and politeness-neutral -
that is a question for the operator, not an assumption for a lane.

## WHAT RUNS

    scripts/researchpack_us_crawl.py      lane K's, byte-identical
    scripts/researchpack_us_rule1.py      lane K's, byte-identical
    scripts/researchpack_anchor.py        the anchor, per batch, per cap,
                                          with the wrong-pack control
    scripts/researchpack_union_cache.py   the union, identity-checked,
                                          proven servable
    scripts/researchpack_ledger_guard.py  did THIS lane spend anything
    scripts/researchpack_redact_check.py  does this file name anybody

`anchor_run` and `grounded_fact` are lane H's, materialised from lane H's
git blob at run time and the sha printed. `site.py` and `actors.py` are lane
C's, the same way. `openers_for` and `rule1_tokens` are lane K's, imported
from lane K's own file. `pack_text`, `first_line` and `_WORD` are
production's `copylint` - the gate itself. Nothing here restates another
lane's matching, because a second copy of it would be a number that agrees
with this document and not with the system.

The only change to `src/` is one constant and its reasoning:
`researchpack.facts.SNIPPET_CHARS`, 400 to 2000. `fact_id` hashes
`clean(snippet, 200)` with an explicit limit, so a re-crawled page keeps its
id and a draft that cited it still traces. The 21 researchpack tests pass
and none of them pinned 400.

## WHAT A PUSH CAN CARRY

`work/laneO-shippable-2026-09-25.jsonl`: **4,926 domains passing rule 1 at
2000**, in lane J's shippability order, each row carrying its contact count,
MX status, fact count, `retrieved_at`, matched words, `rests_on_one_word`
and both anchors. `work/laneO-union-cache-2026-09-25.json`: **6,667 domains,
16,056 facts**, keyed `<domain>::site_content`, ready for
`RESEARCH_PACK_CACHE`.

Neither is a permission to send. `anchor_grounded` on a row is the number
worth reading before rendering: **0 means there is nothing on that site
worth quoting, and a rule-1 pass on that row is a category word.**
