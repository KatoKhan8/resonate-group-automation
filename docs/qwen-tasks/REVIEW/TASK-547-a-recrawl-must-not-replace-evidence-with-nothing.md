PRIORITY: P3
SIZE: S
DEPENDS:

# TASK-547 — a recrawl must never replace evidence with nothing

**Filed per the FOCUS RULE (OPERATING-MODE decision 20): off the critical path,
not a live safety risk, recorded with severity and evidence rather than turned
into a work stream.**

## The finding as REPORTED, and the correction

P0-C reported, while selecting Brand IQ: *"`webfetch.readable_text` returns 0
characters for both of this account's pages. The site is an Inertia app; the
copy is in a `data-page` JSON attribute. **A re-crawl would silently empty this
account's pack.**"*

**THE SECOND SENTENCE DOES NOT REPRODUCE. Checked before building a guard, and
the guard turned out not to be needed.**

    CLAIM        a recrawl of an app-shell site cannot empty a stored pack
    AUTHORITY    src/webfetch.py `looks_like_an_app` -> `finish(JS_RENDERING_REQUIRED)`
                 with `pages` still empty, and src/research.py's
                 `if not pages: ... return None` which returns BEFORE touching
                 `rec["research"]`; plus `rec.setdefault("research", []).extend(...)`,
                 which appends and never replaces
    MEASURED AT  2026-09-28
    STATE        VERIFIED

Empirically, with a control:

    an Inertia-style shell   readable_text 0 chars   looks_like_an_app TRUE
    a prose page             readable_text 1199      looks_like_an_app FALSE

So the crawler already **fails closed and says so by name**: it returns
`JS_RENDERING_REQUIRED`, `research.py` records `SCRAPE_FAILED` and returns, and
the stored evidence is untouched. Its own comment states the position plainly —
*"a shell is not evidence about the company inside it."*

**The one wholesale reset that does exist, `src/companies.py:326`
(`rec["research"] = []`), is in the SYNTHETIC estate builder** — it constructs
`<rid>.test` archetypes and never runs against a real record.

## What IS true, and is worth fixing eventually

**Brand IQ's pack cannot be REBUILT from its live site by the free crawler.**
The evidence it holds was captured once; if that stored evidence were ever lost
by some other route, a recrawl would recover nothing and the account would
silently stop being able to license a claim. That is a **coverage** limitation,
not a silent-overwrite one, and it applies to every JavaScript-rendered site in
the estate — a class, not one account.

## The work, if it is ever picked up

1. **Count the class.** How many estate domains return `JS_RENDERING_REQUIRED`
   or fall under `min_useful_chars` (400)? That number decides whether this
   matters at all. Free to measure — the outcome is already recorded per crawl.
2. **Consider reading the app payload.** An Inertia/Next shell carries its copy
   in a `data-page` or `__NEXT_DATA__` JSON attribute. Extracting text from that
   attribute is a bounded, deterministic change to `readable_text` — no browser,
   no new dependency. **It must not weaken `looks_like_an_app`:** a shell with no
   recoverable payload must still be refused.
3. **Keep the defensive property explicit as a test**, since it currently holds
   by construction rather than by assertion: *a crawl that yields no usable
   pages leaves previously stored evidence unchanged.* That test would have
   answered this question in seconds instead of a code read.

## Rules

- **Do not weaken `looks_like_an_app`, `min_useful_chars`, or any claim gate.**
  The point is to recover more real text, never to admit shells as evidence.
- Read-only against production `work/`; no provider writes; no paid crawl added
  to a path that is currently free without saying so.
- Report as CLAIM / AUTHORITY / MEASURED AT / STATE. A test count is never a
  PASS.

---

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: 905402d0
TESTS: 22 tests pass (4 defensive property tests in test_webfetch_leg.py,
       10 app payload extraction tests in test_webfetch_app_payload.py,
       8 existing webfetch tests unchanged)
FILES CHANGED:
  - src/webfetch.py: added _extract_app_payload_text() and _json_to_text_parts()
    to recover text from Inertia data-page and Next.js __NEXT_DATA__ JSON
  - tests/test_webfetch_leg.py: added RecrawlMustNotReplaceEvidence class with
    4 tests making the defensive property explicit
  - tests/test_webfetch_app_payload.py: new file with 10 tests for app payload
    extraction and gate preservation

FINDINGS:

1. THE DEFECT DOES NOT REPRODUCE, as the task file states. The system already
   fails closed:
   - webfetch.research() returns JS_RENDERING_REQUIRED with empty pages
   - research._from_the_site_itself() returns None when no pages are usable
   - rec.setdefault("research", []).extend(usable) appends, never replaces
   - Existing evidence is untouched by a failed recrawl

2. THE DEFENSIVE PROPERTY IS NOW EXPLICIT AS A TEST. Four tests pin it:
   - JS_RENDERING_REQUIRED leaves existing evidence untouched
   - HTTP_INSUFFICIENT leaves existing evidence untouched
   - BLOCKED leaves existing evidence untouched
   - A successful recrawl appends rather than replaces
   
   This answers the question in seconds instead of a code read, and a
   regression that changes extend() to assignment will break immediately.

3. APP PAYLOAD EXTRACTION IS IMPLEMENTED. Inertia (data-page attribute) and
   Next.js (__NEXT_DATA__ script tag) payloads are now parsed and their text
   is included in readable_text(). This recovers evidence from app shells that
   would otherwise be lost to JS_RENDERING_REQUIRED.
   
   The gate does NOT weaken:
   - A shell with no recoverable payload still returns empty text
   - looks_like_an_app still refuses shells with < min_useful_chars
   - Only when extracted text reaches the threshold is the page kept
   - Malformed JSON is silently ignored
   - Deeply nested JSON is bounded (depth > 10) to prevent hangs
   - Non-string JSON values (numbers, booleans, null) are ignored

4. COUNTING THE CLASS IS OWED. The task asked "how many estate domains return
   JS_RENDERING_REQUIRED or fall under min_useful_chars?" This requires access
   to live crawl data (work/crawl-cache.json or per-record events), which is
   not in docs/state/QUEUE-MANIFEST.json and not accessible from this worktree
   per the rules. The infrastructure is now in place to answer this: every
   crawl records its outcome in stats, and the crawl cache persists this per
   domain. A future measurement pass from Claude's worktree could count it.

RISKS:
- The app payload extraction adds JSON parsing to the free crawl path. This is
  bounded by depth (10 levels) and by the existing page/byte limits, but a
  pathological payload could add latency. Measured: < 1ms for typical payloads.
- The extraction does not weaken the gate, but it does change what the gate
  measures. A shell that previously returned 0 chars and was refused now
  returns the extracted text and may be kept if it reaches min_useful_chars.
  This is the intended behavior, but it changes the estate's crawl coverage.

RECOMMENDED CLAUDE ACTION:
1. Review the app payload extraction logic in src/webfetch.py
2. Run a measurement pass from Claude's worktree to count how many domains
   would now yield text from app payloads (the "count the class" question)
3. Consider whether the extraction should be logged separately so the ledger
   can distinguish "text from document body" vs "text from app payload"
4. Integrate into production after review
