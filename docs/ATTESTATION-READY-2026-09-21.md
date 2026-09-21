# Attestation — one line each, ready to run. Nothing attested.

`senderownership.attest` is the only write path for ownership. It takes FIVE
values and refuses on any of them, so the command is prepared here rather than
improvised at the moment of decision.

    attest(workspace, channel, account_id, sender_id, by)

## READ THIS BEFORE PICKING A NAME — the two name sets are disjoint

The attestation packet prints a mailbox `display name` and labels it
**"UNVERIFIED HINT - not ownership evidence, confirm before using"**. That
warning is doing real work here, because the mailbox names and the roster
humans are DIFFERENT SETS OF PEOPLE:

    mailbox display names   Bojan Rendulic, Bernarda Vrbat, Ivan Mamic,
    (from EmailBison)       Kresimir Simicic
    roster humans           Anna Novak, John Adeyemi, Mark Weber,
    (workspace productive)  Petar Horvat, Sara Simic, Sarah Lindqvist,
                            Tom Ricci

Not one mailbox name appears in the roster. `si.require_sender` enforces it -
verified today:

    'bojan'           REFUSED  UnknownSender: no sender 'bojan' in productive
    'Bojan Rendulic'  REFUSED  UnknownSender: no sender 'Bojan Rendulic' ...
    'anna'            ACCEPTED

So `sender_id` is a ROSTER ID, never a mailbox name. The valid set is exactly:

    anna      Anna Novak            mark      Mark Weber
    john      John Adeyemi          petar     Petar Horvat
    sara_s    Sara Simic            sarah     Sarah Lindqvist
    tom       Tom Ricci

**This is the question the attestation is actually asking:** which of those
seven humans genuinely operates the mailbox. The mailbox's own display name is
a hint about who it CLAIMS to be, and attesting on that basis would record a
fact nobody checked - which is the one thing ISSUE-010 says must not be done.

## THE CANDIDATES — mailbox id, name hint, health, room

    account_id  provider  name hint (UNVERIFIED)  status      limit  lifetime  bounced  free today
    eb-2736     2736      Bojan Rendulic          Connected      15      1779       12          15
    eb-2737     2737      Bernarda Vrbat          Connected      15      1778        9          15
    eb-2738     2738      Ivan Mamic              Connected      15      1757       13          15
    eb-2739     2739      Kresimir Simicic        Connected      15      1768       20          15
    eb-2740     2740      Bernarda Vrbat          Connected      15      1764       19          15

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
