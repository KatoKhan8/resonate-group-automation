# TASK-967 — the copy path still passes the old boolean, and the new authority has no caller

Found by GLM in the first multi-part review, 2026-10-02, and verified in the
source before being accepted. It is A45(a) and it is why
`task-one-os-authority` does not merge.

## The measurement

    src/generate.py:672   block["prior_contact"] = bool(claims.prior_contact(rec, contact))
    src/generate.py:694   block["prior_contact"] = bool(claims.prior_contact(rec, contact))

and `claims.may_claim_first_contact` — the predicate that exists to license the
first-touch branch — has **ZERO callers** anywhere in `src/` or `scripts/`.

The branch's own prompt file says so in its own words:

> "A caller that passes `bool(claims.prior_contact(...))` is passing the OLD
> boolean, derived from a local event log that holds one confirmed touch in
> 1,582 records; read it as `unknown` per the rule above **until that caller is
> changed**."

So the authority ships and the defect it exists to close is held shut by prompt
prose. That is this repository's signature failure — a thing computed correctly
that nothing downstream reads — and the prompt even documents its own
workaround.

## WHY THIS IS NOT A TWO-LINE FIX, measured

`claims.prior_contact_state(rec, contact, dossier)` returns `CONTACTED` /
`NOT_CONTACTED` / `PRIOR_CONTACT_UNKNOWN`, and its docstring is explicit:
**NOT_CONTACTED REQUIRES PROOF ON BOTH CHANNELS**, every lookup must have
succeeded, and one unreadable channel is enough to make the answer UNKNOWN.

Called with no dossier it returns `PRIOR_CONTACT_UNKNOWN` — for everybody. So
simply swapping the call makes every contact UNKNOWN, the first-touch branch is
never licensed, and em1 can never open as a first contact. That is CORRECT
fail-closed behaviour and it is also useless on its own.

**The real fix is wiring `collision.recontact_dossier` into the copy path**, and
that is a PROVIDER READ per contact during generation. Its consequences have to
be decided, not discovered:

- cost and latency: one or two provider reads per contact, inside a generation
  loop that already retries up to ten times per message;
- caching: the dossier is provider truth and ages — how long may one be reused
  inside a campaign build, and who says so;
- failure: an unreadable dossier is UNKNOWN, which blocks the first-touch
  branch. For a cold estate with 872 records carrying neither provider id, that
  is most of it. **That is the finding, not a bug** — but it has to be reported
  as a number before it is enforced, or generation will simply stop.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); from src import generate, claims; import inspect; src=inspect.getsource(generate); assert 'bool(claims.prior_contact(' not in src, 'the copy path still passes the old boolean'; print('OK the boolean is gone from the copy path')"
```

```
python -c "import sys,subprocess; sys.path.insert(0,'.'); out=subprocess.run(['git','grep','-n','may_claim_first_contact','--','src/','scripts/'],capture_output=True,text=True,encoding='utf-8').stdout; callers=[l for l in out.splitlines() if 'def may_claim_first_contact' not in l and '/claims.py' not in l]; assert callers, 'may_claim_first_contact still has no caller outside claims.py'; print('OK callers:', len(callers)); [print('   ', c) for c in callers[:5]]"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import claims; s=claims.prior_contact_state({'id':'x','contacts':[]}, None); assert s == claims.PRIOR_CONTACT_UNKNOWN, 'no dossier must be UNKNOWN, never NOT_CONTACTED: '+str(s); print('OK fail-closed without a dossier:', s)"
```

### NEGATIVE CONTROL

Commands 1 and 2 fail today — the boolean is at `generate.py:672` and `:694`,
and the new predicate has no caller. Command 3 PASSES today and is the guard
that the fix must not relax: if a later change makes a missing dossier read as
`NOT_CONTACTED`, every cold-looking contact becomes a licensed first contact,
which is the failure the three states exist to prevent. **A fix that makes
commands 1 and 2 pass while breaking command 3 is a worse state than today.**

Command 1 reads source text, which this repository forbids as a rule; the
exception is argued rather than hidden — the defect IS a line of source, and the
assertion is written so that any rewrite which stops passing a boolean satisfies
it.

## The report this task must produce before it enforces anything

**How many of the 1,381 contacts can get a readable dossier at all**, measured
rather than estimated — 872 records carry neither a `bison_lead_id` nor a
`heyreach_lead_id`, so the answer is already known to be far from all of them.
Enforcing UNKNOWN without that number in hand would stop generation and look
like a regression.

## Files

`src/generate.py`, `src/claims.py` if the signature needs it,
`src/collision.py`'s dossier if the wiring exposes a gap, and tests with
mutations for each of the three states.

## Not in scope

The rest of `task-one-os-authority`, which is finished and waiting on this. The
role ladder and the copy gates (TASK-964).
