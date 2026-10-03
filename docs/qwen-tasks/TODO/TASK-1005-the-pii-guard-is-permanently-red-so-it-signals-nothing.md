# TASK-1005 — the roster-domain guard carries 54 standing hits, so a new leak cannot make it fail

Measured 2026-10-03, while removing two leaks I had just written myself.

## Measured

`tests/test_fixture_hygiene.TestNoRealDataAnywhereInGit.test_no_real_client_prospect_or_roster_domain`
scans every tracked file for `FORBIDDEN_DOMAINS`. Today:

    total hits: 56
    in files written today (mine): 2
    pre-existing: 54, across 54 files

The 54 include **`config/clients/productive.yaml`** and
**`config/clients/productive-offers.yaml`** — a client config naming its own
client, which is the file's entire purpose — plus `docs/DEFECT-MAP-2026-10-02.md`,
`docs/HANDOFF-2026-09-30-CANARY.md`, `docs/HANDOFF-2026-09-30-PRODUCTION.md`
and fifty others.

**So the guard is permanently red, and a new leak changes nothing about its
verdict.** It is one of the five standing names the merge reference carries, so
the name-set rule — correctly — does not charge a branch for it. The result is
that the one check whose job is to stop real client and prospect data entering
git **cannot signal that real client data has entered git.**

That is the argument the verifier's own test module already makes about a
different check, in its own words: *"a broken check that always cries wolf is
more dangerous than no check, because it spends the credibility the check
needs."* This is that, on the PII path.

## The proof that it matters, from today

Two files I wrote and committed carried the client's domain — one of them in
the very row explaining that the domain is on the roster. **Nothing failed.**
The guard was already red, the merge gate correctly ignored a baseline name,
and the leak was found only because another lane read the file and told me.
That is the ninth instance in two days of a check reintroducing what it
forbids, and the first where the guard that should have caught it was
structurally unable to.

## What to do

1. **An explicit, narrow allowlist of legitimate namings**, with a reason per
   entry: a client config must name its client; a handoff that records an
   incident names the campaigns involved. `names_the_test_identity_on_purpose`
   already exists in that module for exactly this shape — extend the pattern
   rather than inventing a second one.
2. **Everything outside the allowlist is a hit, and the guard goes GREEN.**
   Only then does a new leak turn it red, which is the only state in which it
   is a guard at all.
3. **The allowlist is the thing reviewed**, not the hit list. A file added to
   it is a decision with a sentence attached; a file that quietly stops
   appearing is the defect this task is about.
4. Then **remove the name from the merge baseline**, and re-measure the
   reference — five standing names become four, and a branch that greens it
   must not be charged with the disappearance.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); from tests.test_fixture_hygiene import corpus, FORBIDDEN_DOMAINS; hits=[(p,d) for p,t in corpus() for d in FORBIDDEN_DOMAINS if d in t.lower()]; allowed=[h for h in hits if h[0].startswith('config/clients/')]; assert hits, 'the corpus reader found nothing at all - this command is reading the wrong thing and would pass vacuously'; assert len(hits)==len(allowed), 'the guard still carries %d hit(s) outside config/clients/, so it cannot go green and cannot signal a new leak: %s'%(len(hits)-len(allowed), sorted({h[0] for h in hits if h not in allowed})[:6]); print('OK every remaining hit is an allowlisted client config:', len(allowed))"
```

```
python -c "import sys; sys.path.insert(0,'.'); import tests.test_fixture_hygiene as m; names=[n for n in dir(m) if 'allow' in n.lower() or 'purpose' in n.lower() or 'exempt' in n.lower()]; assert names, 'nothing in the module expresses an exemption, so the allowlist is implicit and unreviewable'; print('OK the exemption is explicit:', names)"
```

### NEGATIVE CONTROL

**Command 1 fails today**, naming the files outside `config/clients/` that
still hit — 54 of them. Its first assertion is the control that the corpus
reader works at all: a reader pointed at the wrong tree finds nothing and would
otherwise report a clean guard, which is the exact failure this task exists to
end. It cannot be satisfied by emptying `FORBIDDEN_DOMAINS` either, because a
corpus with no hits at all fails that first assertion.

Command 2 refuses an implicit allowlist. A guard made green by deleting the
check reads identically to one made green by fixing the leaks, and the only
difference visible from outside is whether the exemption is written down.

**Command 2 PASSES today, and that is a finding rather than a half-done task.**
The module already carries `HYGIENE_EXEMPT`, `names_the_test_identity_on_purpose`,
`ALLOWED_PHONES` and a whole `TestTheExemptionStaysNarrow` class — the mechanism
exists and is already policed for narrowness. So this work is to USE it for
roster domains, not to build it, which makes the task smaller than it reads.
The command stays because it is what catches a future fix that greens the guard
by weakening the check instead of by writing the exemption down.

## Files

`tests/test_fixture_hygiene.py`, the 54 files that carry a hit, and the merge
baseline once it is green.

## Not in scope

The other four standing names in that module. Each is its own measurement and
`test_every_email_address_is_on_a_reserved_domain`,
`test_no_linkedin_url_with_real_vanity_name` and
`test_no_real_person_or_client_named` may well have the same shape — worth
checking with the same method, not assuming it.
