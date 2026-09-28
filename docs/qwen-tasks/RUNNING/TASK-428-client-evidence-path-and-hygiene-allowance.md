PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-428 — licensed client evidence lives under `config/clients/productive/`, with a narrow hygiene allowance

**Operator decision, 2026-09-27.** `test_fixture_hygiene` was failing because two
standing instructions collided, and the operator has resolved it rather than
letting either be weakened.

## THE COLLISION

The operator asked that every AI claim trace to stored page text, so
`productive.io/productive-ai` page text and the single CTA link
`https://productive.io/get-started/` were stored in
`config/clients/productive-offers.yaml`. The fixture-hygiene guard forbids a real
client domain in git. Both rules are right; they simply met.

## THE RESOLUTION

**`productive.io` is the CLIENT's own public domain, not a prospect's.** That is the
distinction the guard was missing. So:

1. **Licensed client evidence moves to `config/clients/productive/`.** The stored
   `productive.io/productive-ai` page text and the CTA link live under that path.
2. **The hygiene guard gets a NARROW, DOCUMENTED allowance** for the client's own
   domain, in that path only.
3. **It keeps refusing everything else, everywhere:** every prospect domain, every
   personal name, every email address, every phone number, in any path. The
   allowance is for one client's own public domain in one directory, and nothing
   more.

## ACCEPTANCE — TEST BOTH SIDES, which is the operator's explicit instruction

An allowance that is only tested on the permitted side is how a guard quietly
becomes a hole.

1. The client's own domain in `config/clients/productive/` is ALLOWED.
2. The same client domain OUTSIDE that path is still REFUSED.
3. A PROSPECT domain inside `config/clients/productive/` is REFUSED. The allowance
   is scoped to the client's own domain, not to the directory.
4. A personal name, an email address and a phone number are each REFUSED inside
   `config/clients/productive/`. The allowance covers a domain only.
5. `test_fixture_hygiene` passes without being weakened, and the assertions above
   are new tests rather than relaxations of existing ones.
6. MUTATION: widen the allowance to any domain in that path, and a test must fail.
   MUTATION: widen it to the client domain in any path, and a test must fail.

## WHAT TO BE CAREFUL ABOUT

- `src/offers.py` reads `config/clients/productive-offers.yaml` by path. Moving
  evidence without updating every reader breaks `offers.load()`, which has already
  broken the entrypoint once today. **Validate with `offers.load()` itself, never
  with `yaml.safe_load`** — `clients.parse` is a restricted subset that accepts far
  less, and a permissive validator is what hid that defect.
- Offers A and B are APPROVED at v2. Do not alter any offer record's content,
  `approval_status`, `approved_by` or `approval_history` while moving files.
- Keep the mapping shapes. `clients.parse` supports inline `[a, b]`, nested
  mappings and flat keys; it rejects block lists and folded scalars.
- No send, activate, resume, enrol or attach. Provider writes ZERO. Freeze stands.
