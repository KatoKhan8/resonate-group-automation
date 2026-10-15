# THE ONE AUTHORISED PROVIDER READ — `GET /sender-emails`, 2026-10-15

TASK 0180 (pilotcaps). Authorisation: operator, 2026-10-15 23:00, **one
endpoint, fully walked, read-only.** The first authorised provider read in this
system's history. It is spent and does not carry forward.

    measured tree   wt-pilotcaps-2026-10-14   (CRLF)
    measured SHA    7a2890022e45b9830f2798f1f4afdb77e8bce3a9
    branch          task-pilotcaps-enforcer-2026-10-14

**No address, surname or signature string appears in this file.** Mailboxes are
provider ids and owners are px values, the convention
`CANARY-01-ALLOWLIST-2026-10-15.md` uses and for the same reason: the roster
surnames are on `tests/test_fixture_hygiene.py`'s `FORBIDDEN_NAMES`, which
scans every tracked `.md`. The clear-text form of this result is
`resonate-ops/FINDING-the-one-authorised-read-2026-10-15.md`; the response
bytes and the instrument are beside it, outside git, because they carry
addresses.

## THE ANSWER

**Criterion 7's string comparison is MET.** The provider spells the pool's
owner identically in `name` and in `email_signature`, on all ten pool
mailboxes and both reserves, and the approved bodies sign the byte-identical
string:

    px(provider `name`)             =  px-fc7d1255b8a3
    px(provider `email_signature`)  =  px-fc7d1255b8a3
    px(the bodies' sign-off line)   =  px-fc7d1255b8a3     EQUAL

    px(the allowlist's "ivan" group label)  =  px-75ee916b9999   stale

Every one of those 24 strings is **pure ASCII** — `str.isascii()` true, zero
codepoints above 127 — so NFC and NFD are the same bytes and the comparison
carries no normalisation question at all.

**And it is settled by id identity, not by the name**, which is the stronger
proof: a matching string could still be a different person's mailboxes.

    allowlist "ivan", px-75ee916b9999, 13 ids:
        2738 2741 2745 2748 2750 2751 2757 2760 2763 2766 2772 2775 2778

    distinct live signature-owner px values holding ANY of those 13 ids:  ONE
        px-fc7d1255b8a3 holds 12 of 13 (2738 has left the estate)

Of the two readings the audit could not separate, **reading 1 is proven**: the
same mailboxes under an edited signature. The allowlist's px *label* is stale;
the pool is not drawn from outside the allowlist. Both allowlist gates pass on
the allowlist's own authority — all ten ids are on it, and all ten are present
and `Connected` in the current estate.

### The ten `sender_email_ids` — the field the attach payload lists as UNKNOWN

    [2763, 2760, 2751, 2750, 2778, 2772, 2748, 2745, 2741, 2775]

    reserve, not in the pool:  2757, 2766

All twelve: `Connected`, `daily_limit` 15, `warmup_enabled` true,
`type` `google_workspace_oauth`, one owner px, one signature string. There are
exactly twelve rows for that local-part in the estate — the ten plus the two
reserves.

### Why the drift was on one group only, which is what looked wrong

**Not one owner name in the live estate contains a non-ASCII byte.** Eight of
the eleven live owner px values are *unchanged* from the allowlist:

    px-387dd1f77205   61    allowlist "kresimir"    MATCH
    px-19834114d0e7   41    allowlist "bernarda"    MATCH
    px-494dc227d91e   17    fictitious              MATCH
    px-c82dcaabaec1   17    fictitious              MATCH
    px-7513d195dfb1   17    fictitious              MATCH
    px-fc7d1255b8a3   12    the pool — allowlist has px-75ee916b9999
    px-894888e9f1c3    6    allowlist "bojan"       MATCH
    px-2f1dd920a186    5    no allowlist group
    px-d065203e066c    3    no allowlist group
    px-40bfd9825a08    1    no allowlist group
    px-e7b9ecb0a51e    1    no allowlist group

So this was never an estate-wide diacritic convention that changed. The
2026-09-21 fixture held **one** person's signature with a diacritic while every
colleague's was already plain, and that one signature has since been
normalised. That is why `px-fc7d1255b8a3` appeared in no group and nowhere in
the fixture's histogram.

## THE READ, AND THE FENCE THAT KEPT IT NARROW

    13 requests, every one:  GET https://send.resonategroup.co/api/sender-emails?page=N
    N = 1..13,  no body,  all 200
    rows 181,  meta.total 181,  meta.per_page 15,  meta.last_page 13

    sha256 of the 13 bodies concatenated in page order
        2c928a2652fd2c414976f83dfb8bddd5701e4dbdbfbb20b1512c8470a9107439

`len(rows) == meta.total == 181` is what makes the walk provably **complete**
rather than merely long. Per-page digests are in the artifact.

The authorisation was enforced **in code**, at `src.providers`' transport seam:
any method that is not GET, any path whose leaf is not `sender-emails`, and any
request carrying a body is refused **before it leaves the process**. Three
negative controls ran first and the instrument will not make the live read
unless all three refuse:

    POST /api/sender-emails          REFUSED_BY_FENCE
    GET  /api/campaigns              REFUSED_BY_FENCE
    GET  /api/campaigns/499/senders  REFUSED_BY_FENCE

The fence's own recording is the evidence of narrowness: 13 observed, 13
allowed, 0 refused during the read, one path, one method. A positive self-check
guards the reader — an empty recording reports "the fence never observed the
transport", never "only one call was made".

No credential was read, printed or logged. `headers` is the only argument that
could carry one and the fence drops it.

### `scripts/email_sender_estate.py` is NOT usable under this authorisation

The attach payload names it as "the one tool". It is not.
`active_campaign_senders()` walks `/campaigns` and then
`/campaigns/{id}/senders` for **every ACTIVE campaign** — further endpoints,
and one was authorised. The fence refuses both, which is why they are two of
the three controls. It also could not have answered the question: `--json`
hashes the owner name and neither mode prints `email_signature`.

### Two walks were made, not one

Run 1 completed all 13 pages and then lost every byte to an `AttributeError`
in its own post-processing — `providers._urllib_transport` returns the response
**text**, not the parsed dict the fixture `Wire` in
`tests/test_a_page_is_not_an_inventory.py` returns — and it wrote its artifact
only at the end. Nothing survived, so the question was still unanswered and the
same read-only route was walked again with the capture appended and `fsync`ed
**inside** the fence, the moment each page arrives.

The lesson is this repository's own: **a once-authorised read whose artifact
depends on the rest of the script being correct is not durable.**

## THE DEFECT THAT MATTERS MORE THAN THE ANSWER

`tests/test_every_body_is_signed_by_the_pools_owner.py:534` — the test gated
behind `B7_LIVE_ESTATE=1`, the one this approval was meant to unblock — **passes
while seeing nothing.**

    sig_html = (row.get("signature") or row.get("Signature") or "")
    m = re.match(r"<p[^>]*>([^<]+)</p>", sig_html.strip())

Two independent defects, either sufficient alone:

1. The provider's field is **`email_signature`**. `signature` and `Signature`
   are absent from all 181 rows — measured by key-set intersection over every
   row, not inferred.
2. The regex requires `<p>text</p>` with no intervening tag. The real signature
   holds a `<br>` between the owner and the company, so `[^<]+` stops there and
   `</p>` never follows. **Given even the correct field it matches zero of 181.**

Either way `name` is empty on every row, every row counts `no-owner`,
`mismatch` is 0, and `assertEqual(mismatch, 0)` holds **vacuously**.

Proven by replaying the 13 captured page bodies through
`providers.set_transport` with `B7_LIVE_ESTATE=1`, at **zero** further provider
cost, in this lane's own integration tree `cc112ae60`:

    test_the_live_estate_classifies_under_the_same_ladder ... ok
    Ran 26 tests — OK (expected failures=4)

    replayed rows=181  meta.total=181
      as the test reads it   (row['signature'])       : {'no-owner-or-unparsed': 181}
      as the provider holds  (row['email_signature']) : {'named': 181}

The replay transport refuses any URL it holds no capture for, so that run could
not have reached the network even had the code asked for something else.

**Had the approval been spent by simply setting that variable, criterion 7
would have been recorded MET on an instrument that never looked at an owner
name.** This is `existence is not function` in the instrument for the very
criterion the authorisation was granted for — and worse than the usual form,
because the field it reads is one rename from the field that exists, so the
code looks right.

**Not fixed here**: another lane's file, and this task's scope is the read.
Owner: GLM lane. The fix is the field, the regex, and — the load-bearing part —
a **positive control**, so the next version cannot pass by seeing nothing.
Note that once it reads the real field it goes **RED, correctly**: 12 match,
169 mismatch, 0 no-owner.

## CRITERION 7 — VERDICT: STILL NOT MET, FOR ONE REMAINING REASON

The brief states the string comparison "is the whole of criterion 7". **That
premise does not survive the criterion's own wording.** Criterion 7 is *"One
owner across the **attached** pool"*; nothing is attached and no campaign
exists. `docs/CANARY-01-EXIT-CRITERIA-AUDIT-2026-10-15.md` §7 is explicit that
the green pool test is "the offline stand-in for the per-campaign pool check",
and that the per-campaign form "does not exist and cannot be run". This read
does not create it.

Three reasons have become one:

    allowlist membership of the pool's owner    WAS UNKNOWN     ->  RESOLVED
    provider spelling vs the bodies' spelling   WAS UNKNOWN     ->  EQUAL
    the per-campaign pool check                 DOES NOT EXIST  ->  UNCHANGED

The four `expectedFailure` facts stay red and this read turns none green: the
estate attests **eleven** owner px values, not one, and 0 of 181 mailboxes own
the signature they are made to send because 169 belong to somebody other than
the pool's owner. Those are facts about the **estate**; criterion 7's wording is
about the **pool**. That distinction is the markers' standing argument and today
does not change it.

**NOT MET. The remaining blocker is construction, not a question**: wire the
existing green pool primitive to a campaign id, with a test that goes RED on
two owners and RED on a foreign signature. Owner: GLM lane.

## PROVIDER vs EXPORT — the provider wins, and barely has to

Export `sender-estate-export-2026-10-15b.csv`, sha256 reproduced as
`07f4c67144d3566356136ac9d3aa7f86d4be5d43ac3bf8cf4df3d3c65b881cca`.

    row set              181 vs 181, matched by address.  only-in-provider 0, only-in-export 0
    Name                 0 of 181 differ
    Status               0 of 181 differ
    Signature            0 of 181 differ
    Daily Sending Limit  0 of 181 differ
    Bounces              0 of 181 differ
    Opens                0 of 181 differ
    Emails Sent         10 of 181 differ    +2 to +5, all on one owner's rows
    Replies              1 of 181 differ    one row, 3 -> 4

**No disagreement.** Eleven moved values in two monotonic lifetime counters, on
mailboxes belonging to one owner who has been sending since the export — drift,
not contradiction. **Not one of the ten pool mailboxes moved by a single send
or bounce**, so the attach payload's bounce ranking stands on live bytes.

The disagreement the audit found was always between the **provider and the
allowlist**, and it is settled above in the provider's favour.

Estate totals, live: **181 rows, 179 `Connected`, 2 `Not connected`, 175,271
lifetime sends, 1,771 bounces (1.01%), Opens 0 on all 181, `daily_limit` 15 on
all 181.** Criterion 6's figures reproduce; its 175,237 is the export's and the
live number is 34 higher from the same eleven rows. Neither `Not connected`
mailbox is in the pool or the reserve.

## WHAT THE READ CONTRADICTS IN OUR OWN DOCUMENTS

Named, not reconciled silently.

1. **The five "display misspelled, signature correct" mailboxes.** The
   allowlist places 2910, 3425, 3426, 3430, 3435 inside the 71-id kresimir
   group on the grounds that only the display name is wrong. The provider says
   **both** fields carry the misspelling, so under the allowlist's own owner
   authority those five are `px-2f1dd920a186` — **not an allowlist group** —
   and the kresimir group is **50** live ids, not 71.
2. **Three UNDECIDED groups now resolve to a name, one is gone.**
   `px-898fe4fd21fe` 12 ids → 3 live, one owner px;
   `px-523053400694` 1 id → 1 live; `px-a0e6d43e8d90` 11 ids → **0 live**. One
   of the four remaining attested humans appears nowhere in the live estate.
3. **2782 was excluded as having no owner; it has one now** — the empty
   signature has been filled since the fixture. **2742 has left the estate.** So
   the allowlist's "No owner — 2" category is now zero rows: one named, one
   departed.
4. **Eleven mailboxes the fixture has never seen**: ids **4276–4286**, all one
   owner px, all `created_at` 2026-09-23 — two days after the fixture. Under
   allowlist gate 2 they are **UNDECIDED-by-absence and excluded**, which is
   correct, and they are the largest block of new capacity in the estate.
5. **"`per_page` accepted and ignored" was not exercised.**
   `bison.sender_emails` sends only `page`; `per_page` appears in none of the 13
   query strings. The 15-per-page figure is the provider's default, confirmed by
   `meta.per_page` on every page. The claim may be true; this read is not
   evidence for it.
6. **`sender_emails` returns the rows UNTRIMMED** — 24 keys in, 24 keys out,
   zero dropped, measured by set difference. CLAUDE.md's standing rule is
   "Provider modules return trimmed dicts, never raw payloads", and
   `imap_server`, `imap_port`, `smtp_server`, `smtp_port` reach every caller.
   Low severity, real, and a rule the repository states about itself.

## THE RESPONSE SHAPE — so the next task need not discover it

Envelope `{data, links, meta}`; `links` = `{first, last, next, prev}`;
`meta` = `{current_page, from, last_page, links, path, per_page, to, total}`.

Row keys, all 24 present on all 181 rows — none optional, none dropped:

    bounced_count  created_at  daily_limit  email  email_signature
    emails_sent_count  id  imap_port  imap_server  interested_leads_count
    name  smtp_port  smtp_server  status  tags  total_leads_contacted_count
    total_opened_count  total_replied_count  type  unique_opened_count
    unique_replied_count  unsubscribed_count  updated_at  warmup_enabled

**ABSENT, and each absence costs something:**

- **No owner, creator, user, team, tenant or workspace field.** The only `*_at`
  keys are `created_at` and `updated_at`. The campaign record's blind spot,
  again, on the sender record: **ownership of a mailbox is not a provider fact
  and cannot be made one.** `src/senderownership.py`'s reason to exist is
  confirmed by measurement, and the signature string stays the only owner
  authority the provider offers.
- **No campaign membership and no campaign count** — zero keys containing
  "campaign". So **`glm-c/0150`'s check, "confirm none of the ten is already in
  another ACTIVE campaign before attaching", is NOT answerable from this
  endpoint.** The export's `Campaigns Count` column has no API counterpart
  here; the export is a UI join. That check needs `GET /campaigns` plus
  `GET /campaigns/{id}/senders` per ACTIVE campaign, and **those were not
  authorised** — the fence refused them as controls. It is the next
  authorisation to request, and the standing shared-estate rule of 2026-10-15
  23:45 depends on it.
- **No per-day or today's usage.** `emails_sent_count` is lifetime, as
  documented, so the forward book cannot be built from this endpoint alone.
- **No bounce rate** — derived from `bounced_count / emails_sent_count`.
- **No plain-text signature.** `email_signature` is HTML and the owner is the
  first text node of the first `<p>`, which the defect above is the cautionary
  tale about parsing.

## OPERATOR DECISIONS — recorded, not waited on

1. **Regenerate the allowlist's `ivan` px to `px-fc7d1255b8a3`** and
   `tests/fixtures/sender-estate-2026-09-21.json` **from this read's artifact**,
   not from a new call — the bytes and their digest are on disk. Fold item 4
   above into the same commit so the allowlist and the fixture are never
   separately stale again. Owner: GLM lane.
2. **The attestation that binds the pool's owner has left the estate.** The
   allowlist binds that group to a roster human through the recorded attestation
   on **eb-2738**, and 2738 is the one of the 13 ids no longer present. The
   twelve survivors carry one identical signature, so the group is internally
   coherent — but the single mailbox tying that name to an attested human can no
   longer be read, so the chain cannot be re-verified from provider data. The
   one item here that is a decision rather than a measurement.
   **Recommendation: re-attest on a surviving mailbox — 2763 is the pool's
   lowest-bounce member — before the first send, in one sentence naming the id.**
   Not a reason to call the pool unclean; a reason not to leave the only binding
   on a departed row.
3. **Authorise `GET /campaigns` + `GET /campaigns/{id}/senders`**, ACTIVE set
   only, fully walked, read-only. Without it, "is one of our ten already in
   somebody else's active campaign" is UNKNOWN, and UNKNOWN is not a pass.
4. **Do not set `B7_LIVE_ESTATE=1` until the defect above is fixed.** Today it
   returns `ok` from an instrument that sees nothing.
5. The five misspelled mailboxes are wrong in **both** fields. Correcting them
   is a provider write to mailboxes shared with campaigns that are not ours —
   the write edits no campaign, but it changes what those campaigns send.
   **Recommendation: report to the client, do not edit.** Consistent with the
   2026-10-15 23:45 standing rule.

## SCOPE

No write of any kind. Nothing attached, staged or assigned. No endpoint other
than `/sender-emails`, enforced by the fence with three refused controls as
evidence. **`src/providers/*` was never opened**: the function surface came from
`tests/test_a_page_is_not_an_inventory.py`, which documents the
`providers.set_transport` seam and the `(rows, meta)` contract, and from `dir()`
on the package — the fence is installed through the public seam. No push or
merge to master. No other lane's worktree was written to; this lane's own
integration tree ran read-only under `-B` and its HEAD was not moved.

**The authorisation is spent and is not carried forward.** Item 3 is a request
for a new one, not a use of this one.
