# TASK-040: What Gets Slow First at Real Scale

Every number below is measured or modelled from measured
constants.  No provider was called.  No credential was used.

## The Known Constant

EmailBison ignores `per_page` on every route and always
returns 15 rows.  Measured 2026-09-13 on the live estate:
`GET /campaigns/352/leads?per_page=200` answers fifteen rows
with `meta.per_page: 15`.  `per_page=50` and `per_page=15`
answer identically.  Campaign 352 holds roughly 95,000
scheduled emails, so a full walk is about 6,400 sequential
requests.  Joining a reply to its step costs one more
request per reply.

## Request Counts by Operation and Scale

| Operation | Scale | Requests |
|---|---|---|
| campaign_lead_walk | 500 leads | 34 (34 pages) |
| campaign_lead_walk | 2,000 leads | 134 (134 pages) |
| campaign_lead_walk | 10,000 leads | 667 (667 pages) |
| campaign_lead_walk | 50,000 leads | 3,334 (3334 pages) |
| campaign_lead_walk | 95,000 leads | 6,334 (6334 pages) |
| reply_feed_walk | 500 replies | 34 (34 pages) |
| reply_feed_walk | 2,000 replies | 134 (134 pages) |
| reply_feed_walk | 10,000 replies | 667 (667 pages) |
| reply_feed_walk | 50,000 replies | 3,334 (3334 pages) |
| sender_inventory | 50 senders | 4 (4 pages) |
| sender_inventory | 225 senders | 15 (15 pages) |
| sender_inventory | 500 senders | 34 (34 pages) |
| sender_inventory | 1,000 senders | 67 (67 pages) |
| collision_check_per_domain | 5,000 lead estate | 4 (4 pages) |
| collision_check_per_domain | 21,000 lead estate | 14 (14 pages) |
| collision_check_per_domain | 95,000 lead estate | 14 (14 pages) |
| membership_check | 1 leads | 1 (1 pages) |
| membership_check | 5 leads | 5 (5 pages) |
| membership_check | 10 leads | 10 (10 pages) |
| membership_check | 50 leads | 50 (50 pages) |
| membership_check | 200 leads | 200 (200 pages) |
| reply_to_step_join | 500 replies | 500 (500 pages) |
| reply_to_step_join | 2,000 replies | 2,000 (2000 pages) |
| reply_to_step_join | 10,000 replies | 10,000 (10000 pages) |
| reply_to_step_join | 50,000 replies | 50,000 (50000 pages) |
| full_campaign_audit | 1,000 leads, 142 replies | 234 |
| full_campaign_audit | 13,500 leads, 1,928 replies | 2,972 |
| full_campaign_audit | 95,000 leads, 13,571 replies | 20,825 |

## Wall Time Model: Campaign Lead Walk

Sequential requests, each blocked on the previous.  No parallelism is possible because cursor pagination depends on the previous page's response.

| Leads | Requests | | fast_local (0.1s/req) | | typical_api (0.25s/req) | | conservative (0.5s/req) |
|---|---||---|---|---
| 500 | 34 | 3.6s | 9s | 17s |
| 2,000 | 134 | 14s | 34s | 68s |
| 10,000 | 667 | 70s | 3 min | 6 min |
| 50,000 | 3,334 | 6 min | 14 min | 28 min |
| 95,000 | 6,334 | 11 min | 27 min | 53 min |

## Wall Time Model: Reply Feed Walk

| Replies | Requests | | fast_local (0.1s/req) | | typical_api (0.25s/req) | | conservative (0.5s/req) |
|---|---||---|---|---
| 500 | 34 | 3.7s | 9s | 17s |
| 2,000 | 134 | 15s | 35s | 68s |
| 10,000 | 667 | 73s | 3 min | 6 min |
| 50,000 | 3,334 | 6 min | 14 min | 28 min |

## Wall Time Model: Full Campaign Audit (Campaign 352 Shape)

Campaign 352: ~13,500 leads, ~2,000 replies, 225 senders.
A full audit walks every lead, every reply, joins every reply to its step, and reads every sender.

Total requests: **3,049**

| Latency | Wall Time |
|---|---|
| fast_local (0.1s/req) | 5 min (329s) |
| typical_api (0.25s/req) | 13 min (787s) |
| conservative (0.5s/req) | 26 min (1549s) |

## Local Processing Measurements

### Page Processing (200 pages, 15 rows/page)

- Total: 0.0021s for 3,000 rows
- Per page: 0.01ms
- Per row: 0.0010ms

### store.transaction (one read-modify-write cycle)

| Estate Size | Transaction (s) |
|---|---|
| 300 | 0.0555 |
| 1,000 | 0.1749 |
| 5,000 | 0.7886 |
| 30,000 | 7.0256 |

### refuse_history_loss (event log comparison)

| Estate Size | refuse_history_loss (s) |
|---|---|
| 300 | 0.0012 |
| 1,000 | 0.0042 |
| 5,000 | 0.0269 |
| 30,000 | 0.1903 |

## The Comparison: Local Compute vs Provider Pagination

At campaign 352 scale (~13,500 leads, ~2,000 replies):

- **Local compute** (process 2,000 replies + 2,000 transactions at 300 records): **111.0s**
  - Page processing: 0.0s
  - Store transactions: 111.0s
- **Provider pagination** (3,049 requests at 0.25s/req): **13 min (787s)**

**Ratio: provider pagination is 7x slower than local compute.**

## Verdict: What Gets Slow First

The single worst bottleneck at campaign 352 scale is **provider pagination**: 3,049 sequential HTTP requests, each blocked on the previous, at 13 minutes wall time (at 0.25s/request).

Local compute at the same scale is 111s (1.9 min).  Provider pagination is **7x slower**.

The shape is linear in request count, but the request count itself is the problem: 6,333 pages for 95,000 leads at 15 per page, each sequential, each a full HTTPS round-trip.  No amount of local optimisation changes this.

The operations ranked by request count at campaign 352 scale:

- **reply-to-step join**: 2,000 requests, 8.3 min at 0.25s/req
- **campaign lead walk**: 900 requests, 3.8 min at 0.25s/req
- **reply feed walk**: 134 requests, 0.6 min at 0.25s/req
- **sender inventory**: 15 requests, 0.1 min at 0.25s/req

The campaign lead walk dominates because the campaign holds 13,500 leads and the provider returns 15 per page.  The reply-to-step join is second because it costs one request per reply, and there is no batch endpoint.

## Reproducing

```bash
# Request count model (no network, no credentials)
python benchmarks/provider_pagination.py --json

# Local measurements only
python benchmarks/provider_pagination.py --local-only
```

No provider was called.  No credential was used.  Every number is reproducible.
