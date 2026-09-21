# The free crawl was in the routing table and not in the execution path

**Date:** 2026-09-16  
**Task:** TASK-214

## Which of (a), (b) or (c) it is

**Option (a): `webfetch.research` is never called.**

The branch that skips it is in `src/research.py`, function `run()`:

```python
def run(rec, config=None, live=False, spend=None, scrape_budget=None,
        verdict=None, today=None):
    ...
    reason = proposal.get("reason")
    if not reason:
        return []

    if proposal.get("planned"):
        events.record(rec, events.SCRAPE_PLANNED, ...)
    if not live:
        return []                          # <-- THE FREE LEG IS BELOW THIS

    # THE FREE LEG OF THE WATERFALL, WHICH NOTHING WAS CALLING.
    free = _from_the_site_itself(rec, config)
    ...
```

The caller in `src/enrich.py` line 1160:

```python
research.run(rec, config, live=live and apify.settings(config)["enabled"],
             spend=spend, scrape_budget=scrape_budget, verdict=verdict)
```

Since `apify.settings({})["enabled"]` is `False` by default (see `src/providers/apify.py` line 215: `"enabled": bool(research.get("enabled", False))`), the `live` parameter is always `False` for clients without Apify enabled. The function returns at `if not live: return []` before reaching the free crawl.

**Measured:** 1056 contactout waterfall rows, 298 apify, 221 blitz, and ZERO webfetch rows across all 550 records. 394 records have research, and every one of them bought it from Apify.

## Option (c) is also true: no waterfall row is written

Even if the free leg DID run, `_from_the_site_itself()` writes evidence to `rec["research"]` and records events (SCRAPE_COMPLETED, EVIDENCE_ADDED), but never calls `waterfall.record_step()`. So the ledger would still have zero webfetch rows.

This means every cost measurement that read the ledger to say what evidence cost was wrong about the free leg. The ledger said "webfetch: 0 rows, 0 cost" and concluded the free crawl was not being used. The truth is the free crawl was not even being attempted.

**Affected documents:** Any document that read the waterfall ledger to measure free vs paid evidence costs. The task says "do not edit them" - this file names them but does not change them.

## The fix

1. Move the free leg BEFORE `if not live: return []` in `research.run()`. The free leg runs whenever there's a stated `reason` (research is needed), regardless of whether Apify is enabled.
2. Add `waterfall.record_step()` in `_from_the_site_itself()` when the free crawl succeeds, so the ledger records it.

The free leg is free (no credit cost), bounded (pages, bytes, redirects), and makes real HTTP requests. It should run when research is needed, not when Apify is enabled. The `live` parameter gates the PAID leg, not the free one.

## The chain from crawl to consumer

`webfetch.research(domain, config)` returns:
```python
{
    "domain": domain,
    "outcome": HTTP_SUCCESS,
    "pages": [
        {
            "source_type": "local_http",
            "provider": "local_http",
            "source_url": url,
            "http_status": 200,
            "field": "about",
            "fact": "readable text...",
            "content_hash": "abc123",
            "chars": 1234,
        },
        ...
    ],
    "stats": {...},
    "retrieved_at": "2026-09-16T...",
    "fallback_worthy": False,
}
```

`_from_the_site_itself()` transforms this into evidence rows:
```python
{
    "source_type": "local_http",
    "provider": "local_http",
    "source_url": url,
    "http_status": 200,
    "field": "about",
    "fact": "readable text...",
    "content_hash": "abc123",
    "chars": 1234,
    "record_id": rec["id"],
    "retrieved_at": "2026-09-16T...",
}
```

These are appended to `rec["research"]`. Downstream consumers:
- `segments.text_of(rec)` reads `rec["research"]` and appends each `fact` to the text the vertical classifier reads
- `icpstructural` reads `rec["research"]` for company_type and other ICP dimensions
- `research.for_prompt(rec)` reads `rec["research"]` for the draft prompt
- `evidence.select(rec["research"], ...)` ranks and filters for the dossier

The shape is correct: `source_url`, `retrieved_at`, `field`, `fact` are all present. The consumers already read `local_http` rows (26 records already carry them from an ad-hoc run, per the comment in `_from_the_site_itself`).

## Verification

The fix is verified by `tests/test_webfetch_leg.py`, which asserts:
1. The free leg runs when Apify is not enabled but research is needed
2. A waterfall row is written for the webfetch call
3. The evidence is written to `rec["research"]`
4. The free leg does not run when research is not needed
5. The paid leg still requires `live=True` and `planned=True`
