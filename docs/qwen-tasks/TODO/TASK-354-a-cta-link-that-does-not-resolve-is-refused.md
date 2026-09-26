PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-354 - a CTA link that does not resolve is refused

**Operator decision, 2026-09-26.** Add a lint rule that REFUSES any CTA link that
does not resolve (HEAD 200) at render time.

`config/clients/productive.yaml`'s `booking_link` was
`https://productive.test/get-started/` - a reserved TLD that resolves nowhere - so
every CTA offering a link offered a dead one. **Already fixed in that file** to
`https://productive.io/get-started/`, verified HEAD 200 and GET 200 with no
redirect on 2026-09-26. This task builds the rule so it cannot recur silently.

## Build

    src/copylint.py    MODIFY. New rule, REFUSE class.
    tests/test_a_dead_cta_link_is_refused.py   NEW

Extract every URL a rendered message would put in front of a prospect - the
`booking_link`, any link in a body, any link in a P.S. - and check each resolves.

## The four states, and none of them may collapse into another

This is the whole difficulty. `CLAUDE.md`: *"No silent fallbacks on a safety path.
An `except Exception`, an empty dict, a bare False or an 'unknown' standing in for
confusion will make an unsafe system look healthy. Classify explicitly and fail
closed."*

    200 (or 2xx)              PASS
    4xx / 5xx / DNS failure   REFUSE, rule `cta_link_dead`
    could not be checked      REFUSE, rule `cta_link_unverified` - a DISTINCT
    (no network, timeout)     rule name, never folded into a pass and never
                              folded into `cta_link_dead`
    no link in the message    PASS. A message with no CTA link is not a defect;
                              do not invent a requirement that every message
                              carry one.

**`cta_link_unverified` must be its own rule name.** A transport failure is not a
dead link - the repository has already paid for conflating those two
(`credential_health.py` exists because "a set variable is NOT an authenticated
one" and "a transport failure is NOT a bad key"). An operator seeing
`cta_link_dead` will go and fix a link that is fine.

## The render path must not become network-dependent per lead

- **Cache per distinct URL for the duration of a run.** A 300-lead cohort shares
  one `booking_link`; that is ONE HEAD request, not 300. Check the cache before
  the network, always.
- **Timeout, and a small one.** A render must not hang on a slow host. State the
  timeout you chose and why.
- **Follow redirects**, and report the final URL. A 301 to a 200 is a live link; a
  301 to a 404 is not.
- **Some hosts refuse HEAD.** Fall back to GET and discard the body. Do not
  record a 405 as a dead link.
- **No credentials, no cookies, no custom headers** on these requests. It is a
  liveness check against a public page, nothing more.

## The offline case, which is an operator decision and not yours

If the network is unavailable, every render refuses with `cta_link_unverified`.
That is correct fail-closed behaviour and it will also block a legitimate offline
run.

**Provide an explicit, loud opt-out - not a silent one.** A flag or config key the
operator sets deliberately, which records in the lint output that link checking
was skipped and why. It must be impossible to skip the check without that being
visible in the result. **Do not default it on.** Report under FINDINGS what you
named it, so the operator can accept or rename it.

## Acceptance - RUN each, paste real output

1. The real value passes:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import copylint;\
    print(copylint.check_cta_links(['https://productive.io/get-started/']))"

   Name the real function; the assertion is that a 200 passes.

2. **A dead link REFUSES**, and with `cta_link_dead`. Use a URL guaranteed not to
   resolve - the old `https://productive.test/get-started/` is the honest fixture,
   since `.test` is reserved and can never resolve.

3. **An unreachable check REFUSES with `cta_link_unverified`, NOT `cta_link_dead`
   and NOT a pass.** Simulate the transport failure; assert the rule name. This is
   the assertion that closes the task.

4. **One HEAD per distinct URL.** Count the requests for a 50-lead batch sharing
   one booking_link and assert the count is 1. A rule that fires 50 requests for
   one link will not survive a 300-lead cohort.

5. **The guard is seen to fail:** revert the rule, re-run, confirm the dead-link
   test fails on the old code, restore. Confirm the revert landed (`grep -c`).
   Paste both runs.

6. Re-lint the fifty's existing copy and report the delta. It currently has 15
   copylint refusals; report the new number and name any lead newly refused for a
   CTA link. **Do not modify the fifty's posted, hashed files.**

7. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names). Not a count.

## ALSO SET THE DOMAIN - operator decision, 2026-09-26

`config/clients/productive.yaml` line 4 reads `domain: productive.test`.

**Operator decision: the client's real domain is `productive.io`. Set it.** It is
used for **self-exclusion (never contact anyone @productive.io)** and for
**tenancy**.

**Confirm the code paths BEFORE you set it, and report them.** This is the
load-bearing half of the task: `domain` is read by more than one consumer and a
wrong value here does not fail loudly - it fails by contacting the client's own
staff, or by mis-scoping tenancy.

    py -3 -c "import sys;sys.path.insert(0,'.');import pathlib,re;\
    hits=[(str(f),i+1,l.strip()) for f in pathlib.Path('src').rglob('*.py')\
      for i,l in enumerate(f.read_text(encoding='utf-8',errors='replace').split(chr(10)))\
      if re.search(r'\bdomain\b', l) and ('client' in l or 'config' in l or 'cfg' in l)];\
    [print('%s:%d  %s'%h) for h in hits[:40]];print(len(hits),'candidate sites')"

Then, for each, say whether it is self-exclusion, tenancy, or something else.

**Two things must be true after the change, and both must be TESTED:**

1. **Self-exclusion works on the new value.** An address `@productive.io` is
   refused as a prospect. Prove it fires - and prove the OLD value no longer
   protects anything, since `@productive.test` addresses are now unprotected and
   nothing in the estate should carry one.
2. **Nothing was silently scoped by the old string.** Search the queue and the
   campaign store for `productive.test` and report every occurrence. A record
   whose tenancy was keyed on the placeholder must be reported, **not silently
   rewritten** - rewriting tenancy keys is an operator decision.

    tests/test_the_client_domain_is_never_contacted.py   NEW

**If setting `domain` changes behaviour anywhere beyond self-exclusion and
tenancy, stop and report it** rather than pushing through. The operator named two
consumers; a third is a finding.

## What this task may NOT do

- Do not widen or weaken any existing rule. Do not default the offline opt-out on.
- Do not send a request with credentials, and do not request anything but the
  client's own CTA links.
- Do not modify anything in `config/clients/productive.yaml` other than
  `domain`, which the operator has explicitly asked you to set.
- Nothing sent, nothing activated, no provider call, no model call.

## OPERATOR DECISION 2026-09-26, STANDING — ONE LINK ONLY

**The ONLY prospect-facing link in Productive outreach is
`https://productive.io/get-started/`** (the Resonate-specific link). **No segmented
meeting links, no `book-a-demo`, no other Productive URL, ever, in email or
LinkedIn.**

This SUPERSEDES an earlier instruction in the same session that gave segmented
meeting links by employee count. Those are withdrawn — do not implement them.

Set it as:

    productive.yaml booking_link
    productive-offers.yaml  cta_link on BOTH offers
    productive-offers.yaml  mechanisms.demo.link AND mechanisms.free_trial.link

**Remove `mechanisms.demo.link: https://productive.io/book-a-demo/` and remove any
fallback to it.**

**Add a REFUSE rule: any prospect-facing URL other than
`https://productive.io/get-started/` is refused.** The existing rule for
`productive-web.webflow.io` stays — do not weaken or replace it.

This is an allowlist of exactly one, not a blocklist. A new Productive URL appearing
in copy is refused by default, which is the correct direction for a rule about what
reaches a prospect.

HEAD 200 verification at render time still applies, with the four states already
specified above (`cta_link_dead` / `cta_link_unverified` kept distinct).

Acceptance additions:

- `https://productive.io/get-started/` passes.
- `https://productive.io/book-a-demo/` is **REFUSED** despite returning HEAD 200 —
  resolving is not sufficient; it must be the one allowed URL. This is the
  assertion that proves the allowlist, not the resolver.
- `https://productive-web.webflow.io/...` still refused by the existing rule.
- Grep the repo for `book-a-demo` after the change and report every remaining hit.
