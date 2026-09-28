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
