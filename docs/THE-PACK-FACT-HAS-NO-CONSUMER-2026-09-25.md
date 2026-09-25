# The research reaches no email

**Measured 2026-09-25 while building the 503 sample review file.**

    records in the store ................. 1,582
    records carrying rec["evidence"] ......... 4
    contacts carrying evidence ............... 0
    pack rows holding facts ............. 10,957

`cadence.template_vars` builds the opener as:

    line = evidence[0] if evidence else (
        f"I work with {industry} teams on {angle}, and I do not know how "
        f"{company} handles it")

`evidence` is written only by `generate.persona_angle`, which needs a model and
none ships. So `{line}` takes the fallback essentially always, and **no pack
fact reaches any email on any campaign.**

The fallback is honest - it says who we work with and admits what we do not
know, and every value in it is on the record. It is not the incident. But it
is not personalisation either, and the crawl that produced 10,957 fact rows
feeds nothing on the email path.

On the 503 sample: **137 facts across 48 leads, 0 USED, and 45 of the 48 have
a pack that yields a perfectly usable sentence.** The research is there and
extractable. Nothing consumes it.

This is the repository's signature defect - a thing computed correctly that
nothing downstream reads - and the code comment already names it PRODUCT-GAPS
36, including why the earlier version escaped the claim checker: `claims.is_claim`
examines a sentence only when it carries a number, a month or an event word.

**The incident and this are opposite failures.** `work/gencopy.py` DID use pack
facts and used them wrongly, quoting a navigation bar. Production's approved
path does not use them at all.

## The extraction rule, if facts are ever wired in

Every snippet observed opens with the site's navigation strip:

    "Login About Paradigm Leadership Services Recent Work Contact
     The leader in product identity. HEGEMON lights the way for ..."

The usable sentence begins AFTER it. **Taking the head of the snippet is
exactly what produced the incident's quote.** The sample file shows, per fact,
the raw snippet and the sentence extracted from inside it, so the success rate
is visible rather than asserted: 45 of 48.

## Two gotchas this cost, worth not rediscovering

**`providers.allow_writes` is a ContextVar, so a worker thread does not inherit
it.** 48 writes dispatched through `ThreadPoolExecutor` were all refused with
"a mutating provider call with no explicit authorization" while the scope was
open in the parent. `contextvars.copy_context()` does not fix it either - one
Context cannot be entered by several threads at once. The fix is to open the
scope INSIDE the worker.

**`only=` matches URL FRAGMENTS, not function names.** `only=("bison.pause_campaign",)`
refuses everything; `only=("/pause",)` is what works.

## Scraped company names carry branding glyphs

Three of 48 held `\u00ae` or a bare `\u25b2` logo glyph, and the rendered opener
read "I do not know how HUEMOR\u00ae handles it". Stripped in the sample builder;
the general fix belongs wherever pack names are written.
