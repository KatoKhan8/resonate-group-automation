# GLM adversarial review: TASK-317-secondbrain

_2026-09-26, file `src/secondbrain.py`_

**1. BYPASS.** The gate is the `TASK_SECTIONS` lookup at line 207. Three ways past it:
- `all_sections(client)` (line 220) is public, takes no task, returns every section. Its only guard against prompt use is the docstring "Not for prompts."
- `TASK_SECTIONS` (line 38) is a mutable module dict: `secondbrain.TASK_SECTIONS["cold_email_writing"] = secondbrain.SECTIONS` then `for_task(...)` returns the whole brain. Nothing freezes it.
- `**scope` (line 199) is accepted and silently discarded — any caller-declared narrowing is unenforced.

Also, the gate doesn't announce what it withheld: the docstring (lines 203–205) promises `missing_sections` metadata on the return value; the implementation returns a bare dict (line 217) with no such key. `cold_email_writing` gets `offers: []` (line 39 → `_offers` line 152) with no signal that data is absent rather than empty.

**2. WHO READS THIS OUTPUT?** Within this file, `for_task` has **zero callers**. The only consumer of anything is `index_html` → `all_sections` (~line 234). If no other module imports `secondbrain.for_task`, this is the INSUFFICIENT_DATA pattern again: a retrieval layer computed and never fed to the email/LinkedIn generators. Verify the importers before trusting it. Second, `index_html`'s docstring (~line 232) claims it "Writes to `work/review/secondbrain-<client>.html`" — it only *returns* a string; there is no write anywhere, and `import os` (line 25) is now unused, which is the corpse of the deleted write. The index page reaches no disk unless an unseen caller writes it.

**3. TEST THAT CANNOT FAIL.**
- Every `source` is the hardcoded literal `"config/clients/productive.yaml ..."` (lines 62, 66, 70, 75, 79, 89, 94, 99, 106, 112, 117, 121, 138, 143, 148, 163, 168, 174, 180) regardless of the `client` argument. A test asserting the source string is constant-vs-constant; it passes for *any* client. It's also a production bug: `for_task("cold_email_writing", "acme")` cites productive.yaml — fabricated provenance.
- `verified=True` default (line 47) and `date=TODAY` (line 51) are stamped unconditionally at retrieval time; assertions on verification or freshness cannot fail and measure nothing.
- `_competitors`, `_offers`, `_learning` return `[]` (125, 152, 184): `assert result["offers"] == []` is green by construction.
- The "Missing Information and Research Priorities" block (~lines 266–281) is hardcoded prose, not derived from `data`. It will keep reporting "no approved campaign offers yet (TASK-318)" after TASK-318 ships, and any test asserting that text appears can never fail.
