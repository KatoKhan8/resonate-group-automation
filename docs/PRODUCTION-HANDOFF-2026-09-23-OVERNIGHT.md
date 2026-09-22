# Production handoff — 2026-09-23 overnight

For a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-22-EVENING.md`.**

---

## 1. THE THING TO READ FIRST: A RUN REPORTED SUCCESS AND WAS NOT

The overnight sourcing walk printed `stopped: slices exhausted`. **It had not
exhausted them.** `stopped_for` was initialised to that string and overwritten
only on a credit refusal, so any other ending printed a clean finish.

Worse, and measured rather than inferred: **CANADA WAS NEVER SOURCED.** Nine
Canada slices closed as DONE on page one at 0-7 credits with 1,000-8,600
people behind them on the free count, because **ContactOut company-search does
not honour `location=Canada`** - it returns `total=2` and the rows it returns
are SPANISH AND INDIAN companies. `hq_only` is not the cause: with it off,
`total=5`, still no Canadian row. The same query for the United States returns
1,258 and genuinely American rows.

**So the "ContactOut honours industry, size and geo" finding is qualified**: it
holds for the geos actually measured - UK, Germany, US - and NOT for Canada. A
filter that silently returns another country's companies is worse than one
returning nothing. Three geos were generalised to twenty.

All three defects are fixed in `4854964b`. **The 48,017 domains collected are
unaffected and still good** - this is about what is MISSING.

**The GLM adversarial review found this** (`docs/GLM-REVIEW-SOURCING-2026-09-22.md`),
which is the argument for dispatching it against anything that spends unattended.

## 2. WHERE THE SOURCING LANDED

    48,017 distinct domains · 177,535 credits · 395 of 400 slices done

    bucket      credits      new   yield  cr/domain  slices
    51_200       38,564   17,761   46.1%       2.2   98/100
    201_500       9,632    4,079   42.3%       2.4  100/100
    501_1000      3,205    1,368   42.7%       2.3  100/100
    11_50       126,134   24,809   19.7%       5.1   97/100

**`11_50` took 71% of the spend for 52% of the domains.** The three bands that
clear the 20 floor by construction all land at 2.2-2.4 credits per qualified
domain; the straddling band costs 2.2x that. Walking it last was worth ~126k
credits of deferred risk. **Whether to keep buying it is the operator's open
decision** and this table is what it rests on.

Five slices sit at page 401 - they hit `MAX_PAGES_PER_SLICE`, not exhaustion.
Three have 270k-326k people behind them. Resumable.

## 3. WHAT IS RUNNING

    124716  learning_walk_replies      lock held, NOT complete
    126468  qualify_sourced_supply     S3 -> MX -> collision over the 48,017
    109640  slack_agent_loop           restarted onto Phase D1
    118944  slack_history.py --loop    21 channels, #racuni excluded
    + the 12 production watch loops, unchanged pids

**The learning walk DIED once tonight** - `HttpTimeout` after 25s at 1,895
pages, silently, leaving no lock. Restarted from its cursor. That is why its
monitor now watches pid liveness and page-stall, not just the completion flag.

### Monitors armed (harness task ids, not OS pids)

    b6geb19vh  learning walk: complete | pid death | pages stalled 10 min
    bo300xeg3  hard stops + loop count | AND the check itself breaking
    b7bpmfwwc  batch pacing: approved/drafted/queued rising
    bu7uu7xkj  qualify pipeline: completion or death

`b2fzh611l` (sourcing) has fired and ended.

## 4. THE HARD STOP CAN GO BLIND, AND NOW SAYS SO

`scripts/hard_stop_check.py` did not exist when a monitor was first armed
against it - **it would have reported nothing for ever, and silence from a
hard-stop monitor is indistinguishable from safety.** It exists now.

Then campaign 491 passed 40 pages and `scheduled_emails` refused, so the check
went blind on the largest campaign. `scheduled_emails` now takes an explicit
`cap` and **still refuses past whatever cap it is given** - the property is the
refusal, not the number 40. A campaign that cannot be read is reported BLIND,
including in `--quiet`, which exits non-zero. A campaign we could not read is
not a campaign with no bounces.

Live: 96 mailboxes, **no hard stop tripped**, 0 spam, 0 unsubscribed. Three
mailboxes are UNDEFINED under the 20-send denominator and held out of NEW
enrollment: 1/6, 1/4, 1/5. **UNDEFINED IS NOT PASS.**

## 5. MERGED TODAY

    93d432bb  hard stop can read 491; artifacts redacted
    028230c9  qualification pipeline
    4854964b  the three false-completion fixes
    f077dcbc  slack-agent Phase D1
    b99ae7b9  milestones off for productive
    c56800ae  POST /company/search named in the read-only allow-list

**Phase D1 is live** and the loop was restarted onto it - a merge is not a
deploy. Only D1 had a merge-request doc; D2's content appears to be in
`4af4f982` with no doc, so it was not merged under a label it does not carry.

**Replies re-run through the new classifier: 0 positive of 14**, so nothing
routes to #productive-resonate-outbound. 4 out_of_office, 3 negative, 3
not_relevant, 1 assistant_redirect, 1 automated, 2 unclassified.

## 6. NOT DONE

1. **The 50-row sample** to #resonate-os once the qualify pipeline finishes -
   then that track STOPS for operator approval before anything reaches the
   client.
2. **The supervisor adoption (C6 / TASK-263)** in the no-send window, after
   23:00 and before 07:00: merge its merge request, move monitors under it ONE
   AT A TIME starting with the least critical, never two instances of one,
   then post `--status` showing all UP.
3. **Canada re-run** once a location token the provider honours is found.
   Do not simply retry - it returns the same two Spanish companies.
4. **The five page-401 slices**, if the supply is wanted.
5. Cleared supply into batches under the 7-day pacing rule; AU ninth campaign;
   the 289 US re-engagement leads. Stats, 15-minute veto, push.
6. The learning doc, automated-vs-human first, once the walk completes.
7. The 90k walk. Infra merge requests as they arrive. Digest 07:00,
   briefing 07:15.

## 7. THE PATTERN UNDER TONIGHT

Three separate things reported success while not working: a hard-stop monitor
with no script behind it, a sourcing run that printed "exhausted" over
unwalked slices, and a reply walk that died leaving its own state looking
healthy. **Every one was caught by asking what the failure would look like, and
noticing it would look exactly like the success.**

The GLM review is worth reading in full before touching the spender. It also
names two findings not yet fixed: a page re-bought when the process is killed
between the provider billing and the cursor advancing, and byte-exact domain
dedupe with no normalisation.
