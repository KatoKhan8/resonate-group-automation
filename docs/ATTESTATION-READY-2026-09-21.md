# Attestation — one line each, ready to run.

**NAMES REDACTED 2026-09-21.** This file originally carried mailbox display
names and roster display names in full, and `scripts/pool.sh:116` forbids
exactly that: "Never commit unhashed PII - prospect or seat-holder names".
They are replaced with `<seat:sha256[:12]>`. The real names live only in
gitignored `work/senders.jsonl`. The earlier spelling is still reachable in
this repository's history at commit `39915e4c` - rewriting that is an
operator decision, not one to take unilaterally.

`senderownership.attest` is the only write path for ownership. It takes FIVE
values and refuses on any of them, so the command is prepared here rather than
improvised at the moment of decision.

    attest(workspace, channel, account_id, sender_id, by)

## READ THIS BEFORE PICKING A NAME — the two name sets are disjoint

The attestation packet prints a mailbox `display name` and labels it
**"UNVERIFIED HINT - not ownership evidence, confirm before using"**. That
warning is doing real work here, because the mailbox names and the roster
humans are DIFFERENT SETS OF PEOPLE:

    mailbox display names   <seat:c51dfe238173>, <seat:5c87b064ac71>, <seat:fa56cf5a7010>,
    (from EmailBison)       <seat:9f18f1f2b799>
    roster humans           <seat:556d81ecfe57>, <seat:4cbb4a00fa2a>, <seat:a7c5d4a4a340>,
    (workspace productive)  <seat:0e566427da6c>, <seat:5b41c26bcfb9>, <seat:89fab43150b6>,
                            <seat:cb1ad295d376>

Not one mailbox name appears in the roster. `si.require_sender` enforces it -
verified today:

    'bojan'           REFUSED  UnknownSender: no sender 'bojan' in productive
    '<seat:c51dfe238173>'  REFUSED  UnknownSender: no sender '<seat:c51dfe238173>' ...
    'anna'            ACCEPTED

So `sender_id` is a ROSTER ID, never a mailbox name. The valid set is exactly:

    anna      <seat:556d81ecfe57>            mark      <seat:a7c5d4a4a340>
    john      <seat:4cbb4a00fa2a>          petar     <seat:0e566427da6c>
    sara_s    <seat:5b41c26bcfb9>            sarah     <seat:89fab43150b6>
    tom       <seat:cb1ad295d376>

**This is the question the attestation is actually asking:** which of those
seven humans genuinely operates the mailbox. The mailbox's own display name is
a hint about who it CLAIMS to be, and attesting on that basis would record a
fact nobody checked - which is the one thing ISSUE-010 says must not be done.

## THE CANDIDATES — mailbox id, name hint, health, room

    account_id  provider  name hint (UNVERIFIED)  status      limit  lifetime  bounced  free today
    eb-2736     2736      <seat:c51dfe238173>          Connected      15      1779       12          15
    eb-2737     2737      <seat:5c87b064ac71>          Connected      15      1778        9          15
    eb-2738     2738      <seat:fa56cf5a7010>              Connected      15      1757       13          15
    eb-2739     2739      <seat:9f18f1f2b799>        Connected      15      1768       20          15
    eb-2740     2740      <seat:5c87b064ac71>          Connected      15      1764       19          15

207 of 257 unresolved accounts qualify; these are the five the packet details.
`eb-2736` is 487's current sender and shows 15 of 15 free today.

## THE COMMAND — substitute two values, run one line

    py -3 -c "import sys; sys.path.insert(0,'.'); from src import senderownership as so; print(so.attest('productive', 'email', 'eb-2736', 'anna', 'Zvonimir'))"

Replace `eb-2736` with the mailbox and `anna` with the roster id of the human
who actually operates it. `by` is who is vouching - it is recorded and it is
the question an incident asks first.

Filled in for each candidate, roster id still to be chosen:

    eb-2736   py -3 -c "import sys; sys.path.insert(0,'.'); from src import senderownership as so; print(so.attest('productive', 'email', 'eb-2736', '<ROSTER-ID>', 'Zvonimir'))"
    eb-2737   py -3 -c "import sys; sys.path.insert(0,'.'); from src import senderownership as so; print(so.attest('productive', 'email', 'eb-2737', '<ROSTER-ID>', 'Zvonimir'))"
    eb-2738   py -3 -c "import sys; sys.path.insert(0,'.'); from src import senderownership as so; print(so.attest('productive', 'email', 'eb-2738', '<ROSTER-ID>', 'Zvonimir'))"
    eb-2739   py -3 -c "import sys; sys.path.insert(0,'.'); from src import senderownership as so; print(so.attest('productive', 'email', 'eb-2739', '<ROSTER-ID>', 'Zvonimir'))"
    eb-2740   py -3 -c "import sys; sys.path.insert(0,'.'); from src import senderownership as so; print(so.attest('productive', 'email', 'eb-2740', '<ROSTER-ID>', 'Zvonimir'))"

## WHAT ONE ATTESTATION DOES AND DOES NOT UNLOCK

It moves `HUMAN_IDENTITY_ATTESTED` off zero for that mailbox, so the allocator
can propose it. It does NOT move the second cap: `executionguard._sender_for`
enforces `MAX_SENDERS_ONE_CAMPAIGN_MAY_NAME = 1`, so one campaign still draws
from one mailbox. Both caps are why ISSUE-010 reads zero twice over. The arity
half is TASK-239's successor, not this.

Verify after running:

    py -3 -c "import sys; sys.path.insert(0,'.'); from src import senderownership as so; print(so.attestation_for('productive','email','eb-2736'))"

---

# RECORDED 2026-09-21T12:02:10Z — five attestations, on the operator's wording

The roster had to be populated first, and that is the finding worth keeping.
`require_sender` refused every mailbox name, and not because the people are
unknown to the business: the seven roster humans are seeded by
`src/web/demoaccount.py` and `src/web/demosenders.py`. **The productive roster
held DEMO PERSONAS and no real Productive staff at all.** So these are the
first real humans in it, created with `team="outbound"` and
`colleague_language=None`, which every caller treats as "not permitted" until
somebody decides otherwise.

    eb-2736 -> bojan       eb-2737 -> bernarda     eb-2738 -> ivan
    eb-2739 -> kresimir    eb-2740 -> bernarda

2737 and 2740 are ONE human with two inboxes, exactly as the operator stated,
and the model agrees: the unit email can attribute is a human, not a mailbox.

Readback, `scripts/sender_pool_census.py`:

                                BEFORE   AFTER
    HUMAN_IDENTITY_ATTESTED          0       5
    SAFE_FOR_PRODUCTIVE              0       5
    MAX SAFE SENDER POOL             0       1

The pool is 1 rather than 5 because it is the MINIMUM of two independent
limits and only one of them moved. `MAX_SENDERS_ONE_CAMPAIGN_MAY_NAME = 1`
still holds, so ONE CAMPAIGN MAY NAME ONE MAILBOX - but there are now five
eligible mailboxes, so **up to five campaigns may run in parallel, one per
attested mailbox.** That is what the operator asked for and it is now
possible; it was not this morning.

Identity only. No push, no enrollment, no campaign write was performed.

## THE NEXT BATCH — and one thing that must be resolved before it

202 unattested mailboxes remain, and they belong to only **12 humans**. Four
are already attested and hold 121 of those mailboxes between them, so
attesting more of THEIR inboxes adds eligible mailboxes without adding people.

**RESOLVE THIS BEFORE ATTESTING ANY OF IT.** Two display names differ by a
single letter:

    <seat:9f18f1f2b799>   57 mailboxes   ALREADY ATTESTED as `kresimir`
    <seat:2eb42b5b5a48>    5 mailboxes   UNATTESTED

The second is the first spelled without one `i`. Either it is a typo on five
mailboxes and they belong to an already-attested human, or they are two
different people and attesting them together would record a false ownership -
the one thing this module exists to prevent. **It is not guessable from the
estate and it is not being guessed.**

Best unattested mailbox per NEW human, by free-today headroom:

    3926  <seat:e8f2b3c7ae55>  Connected  lifetime  316  bounced  6  free 15
    3737  <seat:a1f4d2e90c3b>  Connected  lifetime  431  bounced 11  free 15
    3736  <seat:7b9c5e1d8a24>  Connected  lifetime  513  bounced  3  free 15
    3735  <seat:3d8a6f4b2c91>  Connected  lifetime  510  bounced  3  free 15
    2913  <seat:c7e1a9b53f68>  Connected  lifetime 1797  bounced 16  free 15
    2910  <seat:2eb42b5b5a48>  Connected  lifetime 1741  bounced 15  free 15  <- the one-letter case
    2782  <seat:f4b8d3a61e72>  Connected  lifetime 1777  bounced 13  free 15
    2769  <seat:9a2c7e5b4d81>  Connected  lifetime 1788  bounced 11  free 15

Real names for these are in gitignored `work/senders.jsonl` and in the
provider; ask and they are read back to you, they are simply not committed.
