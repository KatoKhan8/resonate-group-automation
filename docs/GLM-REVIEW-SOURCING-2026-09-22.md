# GLM adversarial review - sourcing

2026-09-22T18:49:13.770561+00:00. One call per function.

A SECOND OPINION, NOT A VERDICT. Every line below is a lead to check against the code and the tests by hand.

---

## source_agency_supply.run

`glm-5.3`, 112.942s, usage {'prompt_tokens': 1215, 'completion_tokens': 7893, 'total_tokens': 9108, 'reasoning_tokens': 6910, 'cached_tokens': 0}.

## 1. Retry loops — NO FINDING in the shown code

The `while` loop only re-enters `fetch_page` after a successful page (which advances `record["page"]`, sets `done`, or both); `None` breaks out. So no spin and no cursor-stuck walk is constructible here. The 429/backoff logic lives inside `fetch_page`, which I cannot see — if its backoff is unbounded it spins, but that is not derivable from what you've shown. Same for `count_slice`'s failure mode. Unverifiable, not a finding.

## 2. Cursor on 429/402 — re-buy yes, skip no

- **Skip: NO FINDING.** `record["page"] += 1` executes only after a successful fetch + write + flush, and `save_state` follows it. There is no ordering in which the cursor passes a page that was never bought.
- **Re-buy: FINDING.** The provider bills the moment it returns page N. The cursor is advanced two statements later, after the per-row JSON/write loop — the longest part of the page. A kill (OOM, disk stall) anywhere in that window leaves state at page N; resume refetches page N and pays PAGE_SIZE credits again. Output rows are not duplicated (they were flushed to OUT and rebuild `seen`), so the leak is silent: state["credits"] undercounts actual spend by PAGE_SIZE per interruption, and nothing reconciles against the provider's meter.

## 3. Dedupe — FINDING: byte-exact match, no normalization in `run()`

The only guards are `domain in held or domain in seen` on the raw provider string. Concrete input: store holds `acme.com`; provider returns a row with `"domain": "www.acme.com"` → not in either set → written, counted as new. Same class: `Acme.com` vs `acme.com`, punycode `xn--mller-kva.de` vs `müller.de` — any normalization done inside `already_held()`/`collected_domains()` that is not identically applied to `row["domain"]` here (and none is applied here) is a pass-through. Also: no suppression roster is consulted anywhere in `run()`; if suppression is supposed to happen at source time, it is absent from this function.

## 4. False completion and non-402 stops — three findings, this is the worst heading

- **FINDING (slice wrongly marked done, permanent):** `record["page"] * PAGE_SIZE >= (page["total"] or 0)`. Provider returns `{"companies": [...PAGE_SIZE...], "total": null}` → `1 * PAGE_SIZE >= 0` → `done=True`, persisted. A slice with true count C is closed after one page; you lose C − PAGE_SIZE prospects forever and the state says finished. The `or 0` proves the author expects a null total and chose the truncating fallback.
- **FINDING (same class):** `if not companies: done=True`. Input `{"companies": [], "total": 5000}` — one transient empty page (index lag, provider bug) — permanently closes the slice at zero credits and zero rows. Empty is ambiguous between end-of-results and transient failure, and the code cannot tell. Mirror case: a transient `count_slice() == 0` closes the slice before any fetch.
- **FINDING (run-level false success):** `stopped_for` is initialized to `"slices exhausted"` and only overwritten on `BalanceExhausted`. If the provider starts returning ambiguous 403/5xx at 02:00 and `fetch_page` maps them to `None`, every remaining slice breaks on its first fetch, the run ends "cleanly," prints `stopped: slices exhausted`, and `report()` shows totals. Nothing counts broken slices. Operator reads success; the rest of the slice space was never sourced.
- **FINDING (crash halts overnight run, non-402):** `row["domain"]` (KeyError on one malformed row), `page["total"]` as a string (`"5000"` → `int >= str` TypeError), or disk-full on `handle.write` — any of these raises out of the loop, run dies mid-page with the cursor un-advanced, so the resume re-bills that page per §2.

**Unverifiable from shown code, not scored:** whether `fetch_page` actually requests `PAGE_SIZE` (if it requests less, the done-check fires early — another silent truncation), and where suppression actually runs.

## source_agency_supply.fetch_page

`glm-5.3`, 95.66s, usage {'prompt_tokens': 823, 'completion_tokens': 6919, 'total_tokens': 7742, 'reasoning_tokens': 5881, 'cached_tokens': 128}.

Scope note first: only `fetch_page` is shown. Everything about what the caller does with `None`, and when the cursor is persisted, is unseen — I flag dependence where it matters rather than guessing.

## 1. Retry loops

**In-function: bounded, arithmetic checks out.** With `RATE_LIMIT_BACKOFF = (60,120,240)`, `(0,)+B` yields attempts 0–3; `attempt == len(B)` fires exactly once, on the final iteration, after its 240s sleep has already been paid. Max 4 provider calls, 420s sleep per `fetch_page` entry. The 429 loop cannot spin inside this function.

**Run-level: yes, it can walk forever with a frozen cursor — two constructions.**

- **Continuous 429** (e.g., provider daily quota hit at 01:00): every `fetch_page` burns 7 minutes and returns `None`. Cursor never moves, no slice exhausts, `BalanceExhausted` never raises. The run spends the remaining 7 hours sleeping in 420s chunks, buys zero pages, and never terminates. Cost: the entire night's wall clock, plus 4 log lines per page attempted.
- **403-as-credit-refusal misclassified.** You state 403 is "ambiguous." If `is_balance_exhausted` only matches 402/`payment` and `is_rate_limit` only matches 429, then a 403 body of `"insufficient credits"` falls into the generic branch: print, return `None` — **one attempt, no backoff, no raise**. The operator's designated run-stopper is the one branch whose predicate is uncertain, and the failure mode is not "stop," it's "spin forever printing errors." Overnight cost: unbounded loop, zero output, log file growth into GBs if stdout is redirected. This is the single worst constructible input; verify `is_balance_exhausted` against your real 403 body today.

## 2. Cursor corruption on 429/402

**In-function: NO FINDING.** `fetch_page` writes no state; it cannot corrupt the cursor. 429 retries don't rebill — the provider refused the call.

**The only constructible double-pay** is outside this function's control but inside this function's window: SIGKILL (OOM killer at 03:00) while `company_search` is in flight and the provider has already billed the page. Response discarded, caller persists nothing, resume re-requests the same page. Cost: ≤1 credit per kill event. If a watchdog restarts on OOM in a loop, that's 1 credit per restart.

Skip/re-buy on resume is entirely a function of the unseen caller's ordering of (fetch → persist companies → persist cursor). Not attackable from what's here.

## 3. Dedupe

**NO FINDING.** This function contains no dedupe logic and no domain handling. Case/whitespace/subdomain/encoding questions are unanswerable from this code; don't accept a review that claims otherwise from this snippet.

## 4. Stop-paths other than 402/403

**Zero retries for non-429 errors — inverted robustness.** A 429 gets `len(B)+1` attempts; a transient `ReadTimeout`, connection reset, or HTTP 500 gets **one attempt, then `None`**. Concrete input: one dropped TCP packet on page 7 of a slice at 02:00. That page is lost for the entire run. At 1% transient-error rate over 5,000 pages, that's ~50 pages of companies never sourced, silently, on the happy path.

**`None` is overloaded, and the worst outcome hides in it.** `None` means "rate-limited out," "other provider error," and — depending on the SDK — possibly "empty page / end of slice." If `company_search` returns `None` for pages past the end, the collision is forced: a persistent 429 at page N is byte-identical to end-of-slice. Then the caller either (a) marks the slice done with pages N+1… unbought — the looks-like-success failure you named as worst — or (b) freezes the cursor and the run never terminates for that slice. Which one happens is decided in the caller, but `fetch_page` guarantees the caller cannot distinguish them. That's a design defeat even if the caller is perfect.

**Minor, stated for completeness:** the trailing `return None` after the loop is dead code in all reachable paths (final-attempt 429 returns inside the loop). Harmless today; it silently swallows any future edit that makes the loop exit without returning.

**Not a finding:** `except Exception` correctly does not catch `KeyboardInterrupt`/`SystemExit`; SIGINT during `time.sleep` propagates cleanly.

## source_agency_supply.already_held

`glm-5.3`, 109.274s, usage {'prompt_tokens': 792, 'completion_tokens': 8639, 'total_tokens': 9431, 'reasoning_tokens': 7614, 'cached_tokens': 128}.

Only `already_held()` is in evidence. The loop, retry policy, cursor persistence, and slice-completion logic that questions 1, 2, and half of 4 target were not provided — I will not guess at them. Here is what the shown function actually admits.

## 1. Retry loops — NO FINDING

No retry, cursor, or loop exists in this function. What settles it: the page-fetch retry policy (attempt cap, backoff ceiling) and the slice-walk termination condition. Lethality ranking to check when you have the loop: an infinite 429 retry is a *hang* that bills nothing on refused requests. The paying defects would be (i) cursor advanced past a page on repeated 429, slice then marked done — pages never bought, silent early finish; (ii) cursor saved before the paid call and the call re-issued after a crash — same page re-billed. Both live in unseen code.

## 2. Cursor corruption — NO FINDING on the cursor itself; one chain partially constructible

The chain: if the loop writes the store in place non-atomically, the kill-mid-page you posit produces a truncated store file. On resume, the shown except path **prints a warning and continues** with only the prefix that parsed. Arithmetic: a store of N records truncated at record k leaves N−k domains invisible to dedupe for the entire unattended run; each is re-emitted when its slice returns it. Suppression survives (separate union), so the cost is mass duplicate funnel entries and duplicate downstream outreach, not credits. Conditional on write atomicity (unseen); the continue-on-corruption behavior is shown.

## 3. Dedupe gaps — four constructible, one reframe

**F1 — store failure is downgraded, contradicting the function's own docstring.** The docstring says missing any of the three sources is a double-buy; the code hard-stops only for suppression and warn-and-continues for the estate store. Input: any exception from `store.load()` — the truncated-after-mid-write-kill file from §2 is the expected producer. The warning is read ~8h after the damage.

**F2 — no canonicalization beyond `strip().lower()`.** Pairs that pass unchanged on both sides and compare unequal: suppression `"acme.com"` vs returned `"www.acme.com"`; `"acme.com"` vs `"acme.com."`; `"bücher.de"` vs `"xn--bcher-kva.de"`; and scheme-bearing roster rows (`"https://www.acme.com"`) are inert entries that never match anything. Which fires depends on provider output format — one real response and one roster row settles it.

**F3 — `candidatelist.domains_already_known()` is unioned raw.** If it ever returns `"Acme.com"` or `" acme.com"`, that element sits in `held` forever unmatched — the entire candidate-list source silently inert. One unnormalized element is the test.

**F4 — snapshot staleness (needs call site).** If `already_held()` is called once at run start, domains written to the store *during* the run are invisible to it: slice A sources `acme.com` at 00:10, slice B returns it at 03:00, emitted twice.

**Set-build order: no defect.** Union is commutative and the final comprehension only drops empties. Not attackable.

**Cost reframe:** with per-return billing and no server-side exclusion, *no* dedupe outcome changes credit spend — dedupe is post-purchase filtering. The payable double-buy lives in page re-request (§2), not here. Here the cost is the docstring's other fear: suppressed domains walked back into the funnel (F2) and duplicate entries (F1/F4).

**Guard-void check:** if `ingest.load_suppress()` returns `[]` on a missing/renamed file instead of raising, the hard stop is dead code. One-line test on `ingest`.

## 4. Stops other than 402/403

- Loud, by design: suppression unreadable → raise.
- Loud, unguarded: any exception from `candidatelist.domains_already_known()` terminates the run — pre-spend if called at startup, with a traceback. Fails safe, but it is a third stop reason.
- The dangerous direction present in this function is the *inverse* of what you asked: a condition that should stop and doesn't (F1). **No silent break or falsely-completed slice is constructible from this code** — that logic isn't in it.

To attack 1, 2, and the silent-stop case of 4: send the paginate/retry loop, the cursor save/load, the slice-completion write, and the call site of `already_held()`.

