# TASK-937 — name the sequencer verbs the two adapters actually share

SIZE: S

From the 2026-10-02 OSS survey (`docs/OSS-SURVEY-2026-10-02.md`, item 2).
Borrowed idea only, no dependency: django-anymail (BSD) gives every email
provider backend the same four-method contract (`build_message_payload`,
`post_to_esp`, `parse_recipient_status`, `esp_name`) off one base class, so
adding a new provider means implementing a known shape rather than starting
from nothing. This task borrows the shape, not the library, using
`typing.Protocol` from the standard library — zero dependency, and a
`Protocol` is structural typing only: it changes nothing at runtime, it is
read by a type checker and by humans.

**SEQUENCED AFTER TASK-273.** TASK-273 (still in `TODO/`, unchanged since
2026-09-23) builds a conformance suite over `src/providers/bison.py` and
`src/providers/heyreach.py` as they exist today, and its own stated goal is
to make every signature mismatch an explicit, named, expected-difference row
rather than a failure. That row list is exactly the input this task needs:
do not start this task until TASK-273 has produced it, because guessing at
which verbs are "really" the same thing before that table exists is how you
write a Protocol that's wrong on day one.

## WHAT IS CONFIRMED TODAY, NOT CARRIED OVER FROM THE OLD SURVEY

No base class, ABC, or Protocol connects the two adapters
(`src/providers/__init__.py`, `bison.py`, `heyreach.py` — checked again,
same result as 09-23). Where verb names coincide, signatures still differ:

    bison.set_sequence(campaign_id, title, steps)       bison.py:1609
    heyreach.set_sequence(campaign_id, sequence)         heyreach.py:2105

    bison.resume_campaign(campaign_id, expect_leads=None,
                           attempts=8, interval=2.0)     bison.py:1876
    heyreach.resume_campaign(campaign_id)                heyreach.py:1630

What the two modules genuinely share is enforced from
`src/providers/__init__.py` and is a transport/safety contract
(`ProviderError`, `request()`, `guard_prospect_facing()`,
`refuse_unauthorized_write()`), not a sequencer one.

## WHAT TO BUILD

A `typing.Protocol` (new, small module — e.g. `src/sequencerprotocol.py`,
outside the `src/providers/` package since that whole package is off-limits
to this task — see FILES FORBIDDEN) naming
**only** the verbs TASK-273's conformance suite confirms are safe to treat as
one signature — do not widen a mismatched pair to make it fit; narrow the
Protocol instead, or split a verb into two named variants
(`set_sequence_ordered` / `set_sequence_keyed`, or whatever reads honestly)
if the two providers' shapes genuinely don't unify. The Protocol is
descriptive and optional — `bison` and `heyreach` modules are not required to
literally declare conformance (`class Bison: ...` subclassing anything); a
runtime `isinstance(x, SequencerProtocol)` check or a static
`reveal_type`/mypy pass against it is enough to prove it describes real
code, not aspirational code.

**This must not change `bison.py` or `heyreach.py` call signatures.** The
Protocol describes what exists; it does not standardize it. Changing either
adapter's actual signature is a separate, larger, riskier task this one does
not authorize.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the
`master` baseline, diffed by test NAME both directions.

Required tests: a test that the Protocol's verb set is a subset of what
TASK-273's own conformance table (once it exists) marks as genuinely shared
rather than merely same-named; a test that neither `bison.py` nor
`heyreach.py`'s actual exported signatures changed (import both, read
`inspect.signature`, compare against a recorded baseline); a test that the
new module imports with zero new dependencies (diff `requirements.txt`
before/after — must be identical).

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
