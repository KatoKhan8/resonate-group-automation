# P0-A — TASK-425 criterion 2, the SIGNATURE CHAIN, re-measured

**Operator instruction, Zvonimir, 2026-09-28.** Branch `task-p0a-signature-chain`.
Re-test criterion 2 against the **REAL CURRENT mailbox state**, not against the
operator's statement that signatures were added.

    VERDICT: BLOCKED.
    First failed link in chain order:  link 1, OWNER        (66 of 225 mailboxes)
    The decisive, universal failure:   link 4, RENDERED     (225 of 225)
                                       link 5, PROJECTION   (225 of 225)

**The operator's statement is TRUE and it does not unblock criterion 2.**
Signatures are now present at the source of truth for every one of the 222
productive inboxes. The blocker was never only the data: **nothing in the
pipeline has ever read the field.** Filling it at the provider moves link 3 and
leaves links 4 and 5 exactly where they were.

**The single most important number in this document:** across our three live
campaigns the provider's own rendered copy — merge fields resolved, the exact
sending mailbox named on every row — shows **0 of 99 messages carrying that
mailbox's signature, including all 37 that have already been sent.** Measured
at the authority, not inferred from our code. Section 2, link 4.

---

## 0. WHAT CHANGED SINCE THE LAST MEASUREMENT, AND WHAT DID NOT

`TASK-341` (in `REWORK`) concluded **ABSENT AT SOURCE** on 2026-09-26, and the
`TASK-425` artifact on `task-425-one-account-dry-run` (`2d54e274`) recorded
criterion 2 as BLOCKED with "no link of the chain carries a signature".

Both readings were correct when taken and **one half of the first is now
false**. The signature is no longer absent at source. It is
**PRESENT AT SOURCE AND NEVER FETCHED** — a different defect, in a different
place, with a different fix.

Two things about the earlier measurement are worth recording so the next
session does not repeat them:

1. The artifact's `sender_inventory_rows: 0` was measured in a worktree whose
   gitignored `work/` was empty. Production's roster carries **518 rows**,
   225 of them productive mailboxes. A worktree's absent `work/` reads as an
   empty estate. This run used a **COPY** of production's `work/`, never
   production's own files.
2. `TASK-341`'s test, `tests/test_a_step_never_renders_an_empty_signature.py`,
   is three tests **all SKIPPED**. The guard written for this exact blocker
   has never once executed. That is the reason the negative controls in
   section 4 are the deliverable and the verifier is not.

---

## 1. THE SOURCE OF TRUTH, NAMED FROM THE AUTHORITY REGISTRY

Per the canonical authority registry (§0a), the question "what signature does
this mailbox carry" is answered by **the provider's own readback**.

    THE authority       EmailBison `GET /sender-emails`, fully paginated,
                        `email_signature` on each `sender_email` object,
                        via `bison.sender_emails()`
    NOT the authority   our `senderidentity` account row — it has no
                        signature field at all
    NOT the authority   `config/clients/productive.yaml` — no signature field;
                        `mode: client_rep` says the inbox adds it
    NOT the authority   `docs/state/PROVIDER-CAMPAIGNS.json` — a cached read
    NOT the authority   an operator statement that signatures were added

| | |
|---|---|
| CLAIM | Every productive inbox at the provider stores a non-empty `email_signature` |
| AUTHORITY | EmailBison `GET /sender-emails`, 15 pages, `meta.total` 222 reconciled against 222 rows arrived |
| MEASURED AT | 2026-09-28, `scripts/verify_signature_chain.py` |
| STATE | **VERIFIED** |

    meta.total                                222
    rows arrived                              222   (PartialInventory would raise)
    inboxes with a NON-EMPTY signature        222
    inboxes with an EMPTY or NULL signature     0
    distinct signature values                  11
    distinct provider display names            11

The field **discriminates**: 11 names, 11 signatures, one each, no sharing.
That is what makes it evidence about identity rather than an estate-wide
template. Values and names are hashed everywhere in the tooling; no real
signature or real person's name appears in this document or in the code.

---

## 2. THE CHAIN, LINK BY LINK, PER SENDER

Measured by `scripts/verify_signature_chain.py` over **all 225** canonical
productive mailboxes. Deterministic, no LLM anywhere, provider reads only.

| link | pass | fail | what fails |
|---|---|---|---|
| 1 owner | 159 | **66** | no owner resolves — neither `sender_id` nor an attestation |
| 2 identity | 145 | **14** | our row names a provider mailbox the inventory does not carry |
| 3 signature | **145** | 0 | of those that get this far, every one resolves a real, non-empty, non-shared signature |
| 4 rendered | **0** | **225** | the rendered final email carries no signature |
| 5 projection | **0** | **225** | the EmailBison projection has no field a signature could travel in |

    senders examined                     225
    senders passing all five links          0
    statuses:  OK 145 · NO_OWNER 66 · NO_PROVIDER_ROW 14

### Link 1 — 66 mailboxes have no owner, and all 66 DO carry a signature

| | |
|---|---|
| CLAIM | 66 of 225 productive mailboxes have no resolvable owner |
| AUTHORITY | `senderownership.resolve_owner` over a copy of production's `senders.jsonl` (518 rows, 192 attestations) |
| MEASURED AT | 2026-09-28 |
| STATE | **VERIFIED** |

All 66 carry a real, non-empty signature at the provider. So the signature
exists and **the system cannot say whose it is.** That is not a smaller
problem than an empty signature: it is the attribution hazard
`scripts/propose_sender_attestation.py` was written to refuse, and
attesting them to close this gap is an operator decision, not a repair.

### Link 2 — the roster and the provider have drifted, both ways

| | |
|---|---|
| CLAIM | 14 canonical rows name mailboxes the provider no longer carries; 11 provider inboxes have no canonical row |
| AUTHORITY | set difference of `provider_account_id` against the provider's `id` |
| MEASURED AT | 2026-09-28 |
| STATE | **VERIFIED** |

    ours not at the provider   14   2738 2742 2743 2908 2909 2912 2913
                                    3427 3428 3429 3432 3433 3434 3436
    at the provider, no row    11

For those 14 the signature is **UNKNOWN, never absent** — a canonical row
pointing at a mailbox that no longer exists must not read as a mailbox with no
signature. The verifier classifies it `NO_PROVIDER_ROW` for that reason, and
control 2b in section 4 is what holds the distinction open.

### Link 3 — PASSES, and it discriminates one-to-one

| | |
|---|---|
| CLAIM | For all 145 mailboxes that resolve an owner and a provider row, the signature is non-empty and belongs to exactly one owner |
| AUTHORITY | provider readback joined to the canonical roster on `provider_account_id` ↔ `id` |
| MEASURED AT | 2026-09-28 |
| STATE | **VERIFIED** |

    OK                                       145
    distinct owners among them                 7
    distinct signatures among them             8
    signatures shared by >1 owner              0

Zero sharing is the load-bearing number. A block used by two humans attributes
neither, so the verifier refuses it — **same value, different sender, is a
FAIL**, which is `TASK-462`'s rule one level down. It does not fire on today's
data because today's data is clean, and the check stays because that is a
property of the data and not of the schema.

### Links 4 and 5 — THE BREAK, and it is structural

| | |
|---|---|
| CLAIM | The rendered final email and the EmailBison projection carry no signature, for every sender, because nothing reads the field |
| AUTHORITY | `email_signature` occurrences in `src/`; the real projection from `sequenceplan.derive_bison_sequence` via `bisonfactory._sequence_steps`; the real lead variables from `bisonfactory._variables_for`; 4,066 real generated bodies in the estate |
| MEASURED AT | 2026-09-28 |
| STATE | **VERIFIED** |

**`email_signature` appears exactly ONCE in all of `src/`** — at
`src/slackagenttools.py:191`, inside a **docstring example**. That is not a
read. Before this branch, no production code had ever fetched the field.

The projection has no field it could travel in, and neither has the lead:

    projection step fields   email_body · email_subject · order · step_key ·
                             thread_reply · wait_in_days
    lead variable names      body_1..body_5 · subject_1 · client ·
                             contact_key · record_id

So link 5 fails **structurally**, independently of any copy: there is no slot.
And link 4 fails because the rendered email is the template composed with those
variables, none of which holds a mailbox's signature.

Measured against real copy rather than one sample, so this is a property of the
estate and not of a fixture:

    queue records scanned                                    1,582
    real generated bodies scanned                            4,066
    bodies carrying a FULL real signature                        0
    bodies carrying even a 5-WORD FRAGMENT of one                0

### Link 4 AT THE AUTHORITY — 99 real queued messages, and none carries it

The measurements above are of our own code. **This one is the provider's.**

`bison.scheduled_emails(campaign_id)` is a GET, and per its own contract it is
*"the only place the RENDERED copy is visible"* — `email_subject` and
`email_body` with merge fields **already resolved**. Each row also carries
`sender_email` as an **object**, including that mailbox's `email_signature`. So
one read answers, per queued message: which mailbox sends this, what will the
recipient actually read, and is that mailbox's own signature in it. That is
links 2, 3 and 4 at the authority, per message.

| | |
|---|---|
| CLAIM | No queued or sent message in any of our three live campaigns carries its own sending mailbox's signature in the provider's rendered body |
| AUTHORITY | EmailBison `GET /campaigns/{id}/scheduled-emails`, paginated, on 487, 489 and 493 |
| MEASURED AT | 2026-09-28 |
| STATE | **VERIFIED** |

    campaign   rows   statuses                     carries its mailbox's signature
    487         20    5 sent · 15 scheduled                  0
    489         15    10 sent · 5 scheduled                  0
    493         64    22 sent · 40 scheduled · 2 stopped     0   (4 rows carry no
                                                                  sender_email at all)
    -----------------------------------------------------------------------------
    total       99    37 ALREADY SENT                        0

**Zero of 99.** Every row's sending mailbox has a non-empty signature at source,
and not one rendered body contains it.

**This is what closes the "the provider appends it at send time" hypothesis as
a criterion 2 pass.** The 37 rows with `status: sent` are real emails that
reached real prospects, and the provider's own record of them carries no
signature either. Whether something is injected later at SMTP time is not
readable through any route this repository has — so it is **UNKNOWN, and UNKNOWN
is never a PASS.**

### What was actually added at the provider, stated plainly

Structure only; no value and no name is printed here or anywhere in the tooling.

    all 11 signatures:  one HTML element, exactly 2 words, 17-23 characters

So each is **a name, not a signature block** — no title, no company, no phone,
no footer. Three consequences, none of them a criticism of the decision, which
is the operator's and the client's alone:

1. It satisfies non-empty at the source, and it **discriminates**: 11 values
   onto 11 display names, one each.
2. It carries nothing that operator decision 10's unsubscribe footer would need.
3. It does not weaken the link-4 measurement. The stored value includes its
   `<p>…</p>` tags, so the match requires the element verbatim and a bare name
   appearing in prose would not produce a false positive. None did, in 99 rows.

### Why "the sending inbox appends it" does not rescue links 4 and 5

The copy engine writes no signature **by design** — `src/copyprompts.py:315`,
`src/copystages.py:311`, and `mode: client_rep` in the client YAML all say the
sending mailbox adds its own. That design is coherent and it is **not a
criterion 2 pass**, for a reason that is about evidence rather than taste:

- the system holds **no representation** of what the sent mail will say. It
  cannot state, before or after a send, which block a given message carried.
- the copy signs nothing, so the body is written for a client rep named
  `Ivan` in the client config while the appended block belongs to one of
  **11 provider display names** — and the canonical roster's productive humans
  are known not to be those names
  (`docs/THE-ROSTER-NAMES-PEOPLE-WHO-DO-NOT-SEND-2026-09-17.md`).
- for the **66 unowned** mailboxes nothing can be attributed at all.

**UNKNOWN is never a PASS.** Under this architecture the honest ceiling for
link 4 is UNKNOWN, and the criterion asks for VERIFIED.

---

## 3. WHAT WAS BUILT, AND WHAT WAS DELIBERATELY NOT

**Built** — `src/sendersignature.py`, the resolution link that did not exist:
mailbox owner → canonical sender identity → the signature stored at the real
source of truth for that exact sender, with six named refusals
(`NO_OWNER`, `NO_CANONICAL_HUMAN`, `NO_PROVIDER_ROW`, `SIGNATURE_ABSENT`,
`SIGNATURE_EMPTY`, `SIGNATURE_AMBIGUOUS`) and **no default, no fallback and no
hardcoded signature anywhere.** Links 1, 2 and 3 are now IMPLEMENTED and
UNIT_TESTED, and measured against the real estate.

**Not built, deliberately.** Closing links 4 and 5 means putting the signature
into the rendered body and the projection, which is `src/generate.py`,
`src/generate_campaign.py` and the `sequenceplan` projection — files this task
was told not to touch, with another agent editing the generator now. It is also
**not obviously the right fix**: if the provider appends the block at send time,
embedding it as well sends it twice. That is an architectural decision about
where the signature is composed, and it belongs to the operator.

**No signature was authored, invented or templated.** What a sender's signature
says is the operator's and the client's decision.

---

## 4. THE NEGATIVE CONTROLS — ALL FIVE FAIL, WITH THE MESSAGE EACH PRODUCED

`tests/test_the_signature_chain_is_verified_per_sender.py`, 14 tests, green.
Placeholder values only; no real signature appears in the file.

**POSITIVE CONTROL FIRST — without it, BLOCKED means nothing.**

    links {owner: T, identity: T, signature: T, rendered: T, projection: T}
    pass True
    "read from sender_email.email_signature for mailbox 1"

**1. WRONG PAIRING** — sender X's mailbox carries sender Y's signature

    FAIL at link `signature`, status SIGNATURE_AMBIGUOUS
    "mailbox '1' stores a signature shared by 2 owners (x, y). A block used by
     more than one human attributes nothing, so it is not this sender's
     signature"

**2. MISSING** — no signature field for that sender at all

    FAIL at link `signature`, status SIGNATURE_ABSENT
    "the provider row for mailbox '1' carries no 'email_signature' field at all"

**2b. MISSING AT SOURCE** — our row names a mailbox the provider has not

    FAIL at link `identity`, status NO_PROVIDER_ROW
    "the source of truth has no mailbox 'a1': our canonical row claims provider
     account '999' and the provider's inventory does not carry it, so its
     signature is UNKNOWN rather than absent"

**3. EMPTY** — the field present and empty (tested as `""`, `"   "`, `"\n\t "`)

    FAIL at link `signature`, status SIGNATURE_EMPTY
    "mailbox '1' stores an empty 'email_signature'. An empty signature is a
     BLOCK, not a signature, and no default is supplied here"

**4. SUBSTITUTED** — another productive sender's signature in its place

    FAIL at link `signature`, status SIGNATURE_AMBIGUOUS
    "mailbox '1' stores a signature shared by 2 owners (x, y) ..."
    and the RIGHTFUL owner is refused too, which is correct: once the block is
    shared it attributes nobody.

**4b. SUBSTITUTED IN THE RENDERED MAIL** — X resolves X's block, mail carries Y's

    FAIL at link `rendered`, status OK
    the signature resolved correctly and the mail does not carry it. A signature
    that exists somewhere but is not the one that sender's rendered mail carries
    is a FAIL, not a pass.

**5. PROJECTION GAP** — the rendered copy HAS it, the projection does not

    FAIL at link `projection`, status OK
    links {owner: T, identity: T, signature: T, rendered: T, projection: F}

A sixth guard, worth naming: `carries(text, "")` returns **False**. `"" in
anything` is True, and reading that as "the signature is present" is exactly
the guard-that-cannot-fail shape this blocker was hiding behind.

---

## 5. THE MUTATION — TWO OF THEM, BOTH CAUGHT

Baseline `sha256(src/sendersignature.py)`
`9f8e3a8d8d01a3864589484694f7bd4a5a8759ab93d420f9b97b1219a8306434`

### Mutation A — break the join key

`CANONICAL_ID_FIELD = "provider_account_id"` → `"account_id"`. Our ids are
`eb-2736`; the provider's are `2736`. Every pairing dissolves.

    file changed, hash moved to d631ae3c0296...
    RESULT: 10 of 14 tests RED.
    The INTENDED check went red: TheVerifierCanPass
      .test_all_five_links_pass_when_the_chain_is_whole
      AssertionError: 'NO_PROVIDER_ROW' != 'OK'
      "our canonical row claims provider account 'a1' and the provider's
       inventory does not carry it"

Red for the **intended reason** — the message names the mutated key (`'a1'`,
the account_id, where `provider_account_id` belonged). **A different guard did
not fire first:** link 1 `owner` still reported `True` in every failing case,
so the owner check did not mask the join.

### Mutation B — a silent fallback instead of a refusal

`provider_row_for` falls back to any mailbox when the id does not match. The
classic wrong-pairing bug, and the one Mutation A could not expose.

    file changed, hash moved to 1d53d49a7f55...
    RESULT: 1 of 14 tests RED — control 2b, and what it produced is the point:
      AssertionError: True is not false
      i.e. chain["pass"] became TRUE for a mailbox the provider does not carry.

A silent fallback manufacturing a PASS. Caught by exactly one test, which is
thin but real coverage, and it is recorded as thin rather than rounded up.

### Restored

    cp baseline -> src/sendersignature.py
    sha256  9f8e3a8d8d01a3864589484694f7bd4a5a8759ab93d420f9b97b1219a8306434
    diff    empty — BYTE-IDENTICAL
    14/14 green again, and the real verifier reproduces BLOCKED at link `owner`

---

## 6. PROVIDER WRITES = 0, WITH THE INTERCEPTOR PROVEN TO FIRE

Per the authority registry, the authority is **the write-interceptor ledger with
the interceptor proven to fire** — never `live=False` and never a zero count
from an interceptor that never triggered.

`scripts/verify_signature_chain.py` installs a counting interceptor on
`providers.set_transport`, the transport chokepoint in front of
`refuse_unauthorized_write`. Every wire call is classified; write verbs are
recorded and raised, never forwarded.

    before the deliberate firing   total 23 · reads 23 · write attempts 0
    deliberate PATCH to /sender-emails/signatures/bulk:
      FIRED: "P0A INTERCEPTOR REFUSED PATCH .../sender-emails/signatures/bulk"
    after                          total 24 · reads 23 · write attempts 1
                                   writes that reached the wire 0

The 23 reads are one workspace-binding GET, 15 `sender-emails` pagination GETs
and 7 `scheduled-emails` GETs across campaigns 487, 489 and 493.

| | |
|---|---|
| CLAIM | This task performed zero provider writes |
| AUTHORITY | the interceptor ledger, with the interceptor fired deliberately and observed refusing |
| MEASURED AT | 2026-09-28 |
| STATE | **VERIFIED** |

Also verified: the verifier **fails closed on an unreadable authority.** Run
without a credential file it prints *"the source of truth cannot be read, so the
signature state is UNKNOWN — and UNKNOWN is never a PASS"* and exits 2, rather
than reporting zero signatures.

### The killswitch, and a trap found while verifying it

The killswitch was not touched and the freeze stands — but the first read of it
from this worktree was **right for the wrong reason**, and that is worth
recording because it is invariant 0's "absence under a guessed identifier".

    worktree, before copying work/workspaces.jsonl
      {'sending': False, 'why': 'no such workspace: productive'}

    same worktree, with a COPY of production's workspaces.jsonl
      {'sending': False, 'why': 'sending.live is off for productive'}

**Identical `sending: False`, two completely different causes.** The first is
the guard failing closed on a workspace it cannot find; only the second is the
freeze. A session verifying the freeze from a fresh worktree gets the
reassuring value and no freeze behind it. Read `why`, never `sending` alone.

| | |
|---|---|
| CLAIM | `sending.live` is off for `productive`; the freeze stands |
| AUTHORITY | `killswitch.workspace_state('productive')`, read against a copy of production's `workspaces.jsonl`, with `why` inspected |
| MEASURED AT | 2026-09-28 |
| STATE | **VERIFIED** |

---

## 7. THE LADDER

| link | rung |
|---|---|
| 1 mailbox owner | IMPLEMENTED · UNIT_TESTED · measured against the real roster — **66 of 225 fail** |
| 2 canonical sender identity | IMPLEMENTED · UNIT_TESTED — **14 of 225 fail** |
| 3 signature at the source of truth | IMPLEMENTED · UNIT_TESTED · **LIVE_VALIDATED** against the provider's own readback — passes for all 145 that reach it |
| 4 present in the rendered final email | **ABSENT** — no implementation, zero production readers, and **refuted at the provider**: 0 of 99 queued/sent messages carry it |
| 5 same signature in the projection | **ABSENT** — no field in the projection or the lead |

Criterion 2 as a whole: **BLOCKED**. Not `INTEGRATION_TESTED`, because links 4
and 5 have nothing to integrate.

---

## 8. WHAT WOULD MAKE CRITERION 2 PASS

Not a relaxation of the criterion — the standing instruction is to change the
system to meet it. Three things, in order, and the first is the operator's:

1. **Decide where the signature is composed.** Provider-appended (then the
   system must record and be able to read back which block a message carried)
   or system-composed (then the body carries it and the provider must not
   append it twice). Links 4 and 5 cannot be built before this is answered,
   and it is not a decision for whoever runs the verifier.
2. **Close link 1.** 66 mailboxes need an owner.
   `scripts/propose_sender_attestation.py` already produces the proposal, with
   the near-duplicate, no-canonical-row and unhealthy hazards flagged rather
   than resolved. A person confirms; nothing is backfilled.
3. **Reconcile link 2.** 14 canonical rows point at mailboxes that are gone
   and 11 provider inboxes have no row.

Then re-run `py -3 scripts/verify_signature_chain.py`. It reports PASS only
when all five links hold for every sender, and section 4 is the evidence that
it is capable of saying either word.

---

## 9. HOW TO REPRODUCE

    py -3 scripts/verify_signature_chain.py --env <path>/config/.env
    py -3 -m unittest tests.test_the_signature_chain_is_verified_per_sender -v

The verifier needs production-shaped canonical state. **Point `SENDERS` or
`QUEUE` at a COPY of production's `work/`, never at production's own files** —
a worktree's own `work/` is absent or stale, and a client probe there resolves
unbound and reads as an empty estate. That is how the earlier measurement came
to report a sender inventory of zero rows.
