# Both P0s are blocked on permission, not on engineering - 2026-09-16

Written by Claude during the overnight autonomous run. Everything below is
read off the code and off provider truth, not remembered.

The objective was EMAILBISON = LIVE/SENDING and HEYREACH = LIVE/SENDING.
Neither can be reached by an engineer acting alone, and after last night the
reason is no longer "the work is not done". The work is done. The permission
does not exist.

---

## THE ONE THING TO READ

`src/providerwrites.py` enumerates every write this system can perform, and
`SUPPORTED` is the tuple that authorizes them. As of this commit:

    AUTHORIZED                          NOT AUTHORIZED
    heyreach.pause                      heyreach.add_lead *
    heyreach.set_sequence               heyreach.create_list
    heyreach.start_empty_for_staging    heyreach.create_campaign
    bison.pause                         heyreach.assign_sender
    bison.stop_lead                     heyreach.set_limits
    bison.create_campaign               heyreach.activate
    bison.set_sequence                  bison.add_lead
                                        bison.assign_sender
                                        bison.set_limits
                                        bison.activate

    * heyreach.add_lead IS in SUPPORTED, and is separately CONDITIONAL on
      `_campaign_is_a_declared_staging_campaign`. See below - that condition
      can no longer be satisfied by any campaign, so the verb is sealed.

Read the columns again and the shape of the blocker is plain. **Every verb
that adds a person, and every verb that starts a campaign, is unauthorized on
both channels.** A campaign can be created and a sequence written onto it.
Nobody can be put in it, and it cannot be started.

That is not an oversight. It is the boundary the system was built to hold, and
`LINKEDIN_ADD_LEAD`'s own comment records what enabling one prospect-facing
route cost to justify.

---

## EMAILBISON - what is finished, and the exact gap

Finished and merged:

- **TASK-159** - the CONTROL sequence, assembled from the audited
  pre-generation templates. `persona_pain -> comparable_proof -> breakup`,
  threading F/T/F on the `thread_reply` boolean, subject carried on the reply
  with "Re:" prepended by the provider. Copy generation stays closed.
- **TASK-167** - that sequence resolved against the real queue. All 17
  contacts render. All 51 step-renderings pass lint. All 51 pass the claims
  gate. 23 fallbacks across 17 contacts, none with more than two. The exact
  staging payload is in `docs/BISON-CONTROL-PAYLOAD-2026-09-16.md`.
- **TASK-170** - in flight as this is written: the pre-write check that reads
  the provider rather than our cache of it, seven checks, fail-closed.

The gap, in one line:

    bison.add_lead and bison.activate are not in SUPPORTED.

So the furthest Bison can go under existing authorization is: a campaign that
exists, carrying the audited CONTROL sequence, holding nobody, unable to send.
That is worth doing and Claude intends to do it once TASK-170 and TASK-174
report. It is not LIVE/SENDING, and no amount of further engineering makes it
LIVE/SENDING.

### And one fact that must be settled first

Campaign **481 is paused, holds 23 leads, has 5 steps and has sent 0**.

`bison.set_sequence` is authorized on stated grounds: *"a sequence written onto
a campaign holding nobody reaches nobody"*. **481 holds somebody.** Writing
CONTROL over it changes what 23 real people would receive, through a route
whose permission was justified on a premise that does not hold for this
campaign.

TASK-174 is characterising the 23 - who they are, when they were added, under
which sequence, whether they overlap the 17, and which of today's gates would
refuse them now. Until it reports, Claude will create a NEW campaign rather
than write over 481, which is the fail-closed reading.

---

## HEYREACH - the staging question is conclusively resolved, both ways

Two provider facts, both measured, and they are not in tension once stated
precisely.

**Campaign-level staging does not exist.** `AddLeadsToCampaign` is refused in
DRAFT; in PAUSED and in FINISHED, adding a lead can ACTIVATE the campaign.
There is no campaign state in which adding a lead is safe.
`CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False` stands, the old
"PAUSED == safe staging" assumption is invalid, and `LINKEDIN_ADD_LEAD` was
resealed so the weaker authorization cannot reach a send-capable write. **That
reseal has not been weakened and must not be.** Its condition
`_campaign_is_a_declared_staging_campaign` now cannot be satisfied by any
campaign, which is why the verb is sealed in practice.

**List-level staging does exist, and it was found, not invented.** TASK-158
established the schema HeyReach does not document:

    POST /list/AddLeadsToListV2
    {"listId": <id>,
     "leads": [{"profileUrl": "...", "firstName": "...", "lastName": "..."}]}

`firstName` and `lastName` are REQUIRED, and the provider **silently drops**
any lead missing either, returning `addedLeadsCount: 0, updatedLeadsCount: 0,
failedLeadsCount: 0` with HTTP success. Twelve other body shapes were probed
and all returned 0/0/0 - the route had looked broken for a day because a 200
with 0/0/0 is the provider refusing, not accepting. The previous code sent
`linkedInUrl`, a field that does not exist on this route.

Proven against the provider: one real lead added to list **940797**, readback
`totalCount: 1`, correct profile URL. That list is attached to no campaign and
can send nothing. TASK-165 then designed the full path with 42 tests.

So the answer to the overnight question is:

    LIST STAGING IS SUPPORTED BY THE PROVIDER AND SAFE WHILE THE LIST IS
    UNBOUND. Adopting "ADD_TO_CAMPAIGN == ACTIVATION" is NOT necessary.

The gap, in one line:

    there is no verb for it, therefore there is no permission for it.

`providerwrites.py` has no constant for adding a lead to a list. TASK-172 is
specifying the verb and its condition - ours, our tenant, attached to NO
campaign, asserted from a provider read taken at the moment of the write - and
is under explicit instruction to leave the permission **OFF**.

### What that condition can and cannot promise

It cannot promise that the list stays unbound. A list unbound at the moment of
the write can be attached to a campaign a second later by anyone with provider
access, and attaching it makes every lead in it a lead in a campaign. Campaign
599020 already has list 933603 attached, so "a list we created" was never the
safety property - "attached to nothing, checked now" is.

---

## THE DECISIONS THAT ARE YOURS

Each of these is a new irreversible authorization. Claude has not taken any of
them and will not.

1. **Enable `bison.add_lead`.** Prospect-facing. Puts people into an email
   campaign. Needed for any email send, ever.
2. **Enable `bison.activate`.** Prospect-facing. Starts sending.
3. **Enable the new list-staging verb** (TASK-172 will have specified it, left
   off). Not prospect-facing while its condition holds: an unbound list sends
   nothing. This is the cheapest of the three to say yes to and the one that
   unblocks the LinkedIn path to a gated canary.
4. **Campaign 481 and its 23 leads.** Reuse, leave alone, or resolve. Blocks
   nothing if a new campaign is created instead, but somebody must eventually
   say what those 23 are for.
5. **Whether the 17-contact email canary should be 10.** Seven of the 17 carry
   `persona=None` and therefore receive the champion persona's finance angle
   regardless of their actual role. Configured behaviour, passes every gate,
   and precisely the shape of thing that `docs/LEADS-ARE-BLOCKED-2026-09-14.md`
   found fails a human read. Claude's recommendation is the 10 whose angle is
   their own. Reversible either way.
6. **The PII leak in git history** - a sender's real name, pushed at `abae39b`,
   scrubbed at `ca53cb5`, still in history. A rewrite remains yours. Unchanged
   from the previous checkpoint, recorded so it is not forgotten.

Items 1 and 2 are what stand between this system and EMAILBISON = SENDING.
Item 3 is what stands between it and a gated one-lead HeyReach canary.

---

## WHAT DID NOT GET WEAKENED

Stated explicitly because the objective was LIVE and the temptation runs one
way. No gate, threshold, cap, lint rule, sender limit or ICP rule was relaxed
overnight. Nothing was added to `SUPPORTED` or `CONDITIONAL`. The
`LINKEDIN_ADD_LEAD` reseal is intact. No provider write of any kind was
performed by Claude. The one provider write that happened all night was
TASK-158's single lead into unbound list 940797, which is what proved the
schema, and it can send nothing.

`work/queue.snapshot.jsonl` is stale and disagrees with live state - it reports
`icp_status: NONE` for all 550 records while the runner reports 35 verified.
TASK-171 is establishing which artefact is authoritative. **Do not measure the
funnel from that file until it reports.**
