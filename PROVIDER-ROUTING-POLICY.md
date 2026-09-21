# Provider routing policy - ContactOut first

Operator decision, 2026-09-16. This is a PRODUCT priority, not a cost
optimisation, and it outranks any measurement showing another provider to be
cheaper. It does not outrank progressive spend or a qualification gate.

## The order

    1  CONTACTOUT                      first whenever capable
    2  CONTACTOUT CACHE / EXISTING     reuse aggressively
    3  FREE / SELF-HOSTED CRAWLER      incremental public-web evidence
    4  GROK / xAI                      still-missing, current, ambiguous
    5  OTHER PAID PROVIDERS            genuine capability gaps only
    6  CLAUDE                          reasoning and escalation, never bulk

"ContactOut first" means CAPABILITY first: before calling anything else,
establish whether ContactOut supports the requirement. Do not assume the
current adapter represents the whole ContactOut API.

"ContactOut first" does NOT mean ContactOut everything immediately. The
progressive shape is unchanged:

    cheap company capability -> qualification -> free crawler evidence
    -> person discovery once the account qualifies -> contact enrichment for
    SELECTED contacts only -> verification -> other providers for real gaps

Do not enrich five people when two will be contacted. Do not spend contact
credits before the account has the evidence and ICP confidence to justify it.

## Most of this is already built - read it before changing it

`src/waterfall.py` is the canonical routing layer and it already encodes
ContactOut-first with reasoned fallbacks. `waterfall.describe()` prints the
whole policy. Specifically, as of 2026-09-16:

- `contactout_is_first(stage)` is already True for the stages that have a
  ContactOut capability, and `company_information` starts at
  `contactout/company-information-from-domain` at one credit.
- Every fallback step is marked `is_fallback: true` and carries
  `requires_reason` - a CLOSED allowlist of reasons per step. `may_fall_back`
  refuses a fallback with no reason and refuses a reason the stage does not
  name. "We called it anyway" is not a reason.
- The reasons are written as capability statements rather than failures:
  `contactout_no_company_linkedin`, `contactout_no_email_domain`,
  `contactout_missing_company_data`. Each names what came back missing.
- `record_step` writes every call into a per-record ledger, `audit(rec)` reads
  it, and `enrich`'s `spend()` is the only path that may charge.

So the correct work here is surgical addition, NOT a rewrite. A rewrite would
throw away a layer that already does the hard part.

## What is genuinely missing

1. **Grok has no position in the waterfall at all.** `src/providers/xai.py`
   exists with tests and was deliberately kept off the production path;
   `grep -rn "xai" src/` returns only the adapter. Under this policy Grok is
   layer 4 and must be licensed by a ContactOut confirmed miss or unsupported
   capability, never called first.

2. **The failure taxonomy is not explicit.** The policy requires these five to
   be distinguishable, and only the first two may license the next layer:

        CONTACTOUT_CONFIRMED_MISS          may license fallback
        CONTACTOUT_CAPABILITY_UNAVAILABLE  may license fallback
        CONTACTOUT_ERROR                   must NOT license fallback
        CONTACTOUT_TIMEOUT                 must NOT license fallback
        CONTACTOUT_RATE_LIMITED            must NOT license fallback

   The closed allowlist already makes an unnamed reason fail closed, which is
   the right default. What is missing is the taxonomy itself, retry/backoff on
   the last three, and a test proving an error can never be spelled as a miss.

3. **Telemetry.** Required counters, each with the WHY of every escalation:
   `CONTACTOUT_CALLS`, `CONTACTOUT_CACHE_HITS`,
   `CONTACTOUT_CONFIRMED_MISSES`, `CONTACTOUT_ERRORS`, `CRAWLER_CALLS`,
   `GROK_ESCALATIONS`, `OTHER_PROVIDER_ESCALATIONS`.

4. **Crawler position.** The free crawler must come before every paid
   fallback, not just before Grok. `apify-research` currently appears in
   `company_information` and Apify is paid; webfetch is free.

5. **Company-level crawl caching.** Cache at COMPANY level - one crawl per
   company, reused across its contacts. TASK-162 did this for the evidence
   sent into prompts (~2.5 contacts per domain, 66.7% of company context was a
   duplicate of itself); the crawl itself needs the same treatment.

## The measurement this policy overrides, and why it still matters

TASK-185 measured `contactout/company-information-from-domain` across 50
records: **zero ICP verdicts moved, zero criteria resolved.** Geography did not
resolve because the offices returned sit outside the client's include list;
company_type was already PASS wherever any industry was known.

That measurement does not change the policy - the operator has said so
explicitly, and it is a product decision. It does change what we should
conclude from it: **one endpoint was tested, not ContactOut.** The connected
surface includes company search, decision-makers, people search, people
enrich, technology search, email and phone finders, LinkedIn-profile lookups
and job-change signals. The honest reading of TASK-185 is that the endpoint we
happened to call did not answer the ICP question, and the capability audit
(TASK-206) is what establishes whether another ContactOut endpoint does.

## Fallback semantics

A fallback is licensed only after a MEANINGFUL ContactOut outcome. An error, a
timeout and a rate limit are not evidence that ContactOut lacks the data -
retry or back off instead, and never switch providers silently. A confirmed
miss or an unsupported capability may license the next layer, and the reason
must be recorded on the ledger step so the audit can say why.

## Do not pay twice for the same fact

Do not pay Grok to rediscover structured information ContactOut already
returned, and do not crawl the same company once per contact. Provider routing
reflects capability and evidence provenance, not raw API price.

---

## CROSS-CHANNEL SENDER IDENTITY — operator decision, Zvonimir, 2026-09-21

**The email sender and the LinkedIn seat for one prospect need NOT be the
same human.** They are different estates with different identities: the email
estate is 225 mailboxes across 9 attested humans, the LinkedIn estate is 41
seats where the SEAT IS THE IDENTITY, and requiring one person to hold both
would collapse the usable pool to the intersection for no safety gain.

**Within one channel the same human stays on the thread for the whole
cadence.** This is the invariant that does not move. EmailBison already
enforces its half at the provider: once a lead has been sent one campaign
email, the same sender email sends the remaining steps and any follow-up
campaign's mail to that lead. The rule above is that contract stated as
policy, extended to LinkedIn, and it is what `MAX_SENDERS_ONE_CAMPAIGN_MAY_NAME`
protects today by the blunt method of allowing exactly one.

What this does NOT license: changing sender mid-cadence on either channel,
attributing a reply to a human who did not send the message, or treating the
two channels' identities as interchangeable in copy. A message signed by one
human and sent from another's mailbox is the failure this whole module exists
to prevent.
