# Option A, the free-crawl route, and the sequencing that follows

Operator decisions, Zvonimir, 2026-09-25 ~00:35. Recorded here because both
change what tomorrow does, and because the handoff that set them up got one
thing backwards.

---

## 1. THE TWO DECISIONS

**Option A** on the eleven campaigns lane B found: new campaigns get the
four-step cadence; **485-500 stay three-step**; the 63 stopped leads on
496/497/498 go onto a **new** four-step campaign rather than back onto theirs.
No stored `cadence_steps` row is rewritten and no campaign is left
half-sequenced.

**The free-crawl route for the 128.** Lane D measured that of the 394 records
carrying free-crawl research, **366 (93%) would pass copylint rule 1 today**.
That clears the dominant push blocker with **no Apify spend and no branch
merge**, which also decouples tomorrow's push from the researchpack merge
decision.

---

## 2. THE HANDOFF HAD THE DANGER BACKWARDS, AND IT CHANGES THE ORDER

`PRODUCTION-HANDOFF-2026-09-24-LATE.md` §2 says:

> **The cadence is HALF-APPLIED AND MUST BE FINISHED BEFORE ANY PUSH.** ...
> until all four of these land together, a push fails in a place that does not
> name the cause.

**Measured on master at 5cd5173d, against the real campaign row for 491:**

    configured steps          ['em1', 'em2', 'em3']
    row cadence email keys    ['em1', 'em2', 'em3']
    _sequence_steps(...)      builds 3 steps, no refusal
                              em1 wait 3 / em2 wait 4 / em3 wait 1
                              thread_reply False / True / True

**The current state pushes fine.** The four step-4/step-5 templates sitting in
`src/cadence.py` are unused and break nothing — `_sequence_steps` compares the
CONFIG's keys against the CAMPAIGN ROW's keys, and those agree today.

Fed lane B's four-key config, the same row raises:

    FactoryRefused: `email_sequence.steps` declares ['em1','em4','em5','em2']
    and the cadence's email steps are ['em1','em2','em3']. These must be the
    same keys in the same order.

So **withholding the config is the safe state and landing it is what creates
the refusal.** "Must be finished before any push" is false; the truth is
"must not be landed until the campaigns it breaks are no longer needed."

This matters because the handoff's framing would have had a session land the
config first thing, at which point eleven campaigns — including the 63 stopped
leads' 496/497/498 and campaign 500 — refuse every stage, for no benefit until
the new campaigns exist.

---

## 3. THE ORDER FOR TOMORROW, WHICH FOLLOWS FROM §2

**Do NOT land lane B's config until the step before the push.** Concretely:

1. Confirm free-crawl coverage **on the 128 specifically**. Lane D's 93% is
   across all 394 researched records and is NOT the same question. Lane C has
   been asked for the 128 by name, plus how many of them match no queue record
   at all (lane D found 31% of rendered rows match none). This project's
   recurring failure is a headline number from a stage that had not asked the
   next stage's question — 1,508 exportable that was 114, 19,612 "IN" of which
   two-thirds were under the floor.
2. Crawl the gap, if there is one. That is the critical path, not Apify.
3. Create the new four-step campaigns: Bojan and Jakov, plus one for the 63
   stopped leads, plus a replacement for 500's batch-1b role.
   **Note 501 is taken** — a session consumed it for the stop-test campaign, so
   the pair lands on 502/503.
4. **Then** land lane B's config, when the old campaigns are no longer being
   staged to.
5. Then push the 128 under the gate, with the copylint wiring merged so the
   push refuses anything without a pack fact.

Campaign 500 keeps its three-step provider sequence (steps 4775/4776/4777) and
0 leads. Under option A it is not rebuilt, so it cannot serve batch 1b; it
stays parked rather than deleted, as the previous session left it.

---

## 4. WHAT THIS DOES NOT DECIDE

- The **researchpack merge** — deferred to after lane C reports, by the
  operator. The branch is pushed (`researchpack-four-sources-2026-09-24` @
  `dc33469d`); `origin/master` is untouched at `24acafff`.
- **Rung 3** — drafted per persona by lane D, awaiting approval. It needs
  `{our_company}` and `{capability}`, which do not exist in `src/cadence.py`,
  and a `productive.yaml` change. Lane D declared the dependency rather than
  editing lane B's files, and refused to hardcode "Productive" into shared
  `TEMPLATES` because it would leak into every other client.
- **Whether to merge lane D's copylint at all.** It is correct and proved on
  the real send path, and as things stand it refuses every push this system
  can make. Step 1 above is what makes merging it safe rather than blocking.

---

## 5. RUNG 3 — APPROVED 2026-09-25, WITH ONE CORRECTION TO ITS SHAPE

**Operator approval, Zvonimir, 2026-09-25.** The two lane D drafts in
`docs/MERGE-REQUEST-2026-09-24-COPY-AND-COPYLINT.md` §1.1 and §1.2 are
approved: `economic_buyer` carrying capability `profitability`,
`champion` carrying `budgeting`, both resolving `{capability}` to the
client's own unedited sentence from `productive.yaml` →
`product.capabilities`.

**The copy is approved. The deployment shape lane D stated for it is not
possible, and this is measured, not argued.**

Lane D wrote that the pattern becomes `[false, true, true, false, true]` —
"em4 opens a new thread with `SUBJECT_2`, em5 replies into that". Lane B had
already established that the two-thread design is refused. Run against the
real `bisonfactory._sequence_steps` on master, with waits matching the cadence
gaps so no other guard fires first:

    [False, True, True, False, True], em4 carrying {SUBJECT_2}
      -> REFUSED: step 4 is not a thread reply but carries a distinct subject
         ('{SUBJECT_2}' vs opener '{SUBJECT_1}'). Only the opener owns a
         subject; follow-ups must be thread replies referencing the opener's

    [False, True, True, True, True], one subject throughout
      -> BUILT 5 steps, no refusal
         em1 F wait 3 / em2 T wait 4 / em3 T wait 5 / em4 T wait 5 / em5 T wait 1

The invariant is explicit in `bisonfactory.py:288-307`: *"A mixed shape - some
follow-ups threaded, others opening new threads with their own subjects -
violates the invariant and is refused."*

**So the approved five-step shape is `[false, true, true, true, true]`,
every follow-up threaded on the opener's subject.** Rung 3 itself is already
a thread reply carrying `SUBJECT_1`, so rung 3 is not what breaks — lane D's
accompanying assumption about em4 is. Nothing in the approved copy changes.

### 5.1 The consequence for tomorrow's new campaigns, which is not obvious

`bison.set_sequence` **APPENDS and nothing can replace it.** Measured
2026-09-13 on a throwaway campaign: writing one step then another left the
campaign holding both, and a third write of two steps left four, **renumbered
1, 3, 2, 4** - the orders interleave rather than following the writes.

So a campaign created tomorrow at **four** steps **cannot later be given rung 3
cleanly**. Adding it means a second `set_sequence` write, and the ordering is
not the caller's to choose. Two ways forward, and it is an operator call:

- **Build the new campaigns at FIVE steps in one write.** Requires rung 3's
  `{our_company}` and `{capability}` template variables and the config entry to
  exist first — all in `src/cadence.py` and `productive.yaml`, which lane B
  holds. Lane D declared the dependency rather than editing them, and refused
  to hardcode "Productive" into shared `TEMPLATES` because it leaks into every
  other client.
- **Build at four steps now and give rung 3 to the NEXT cohort's campaigns.**
  Today's 128 go out on the four-step cadence; nothing is appended later.

This is the same property that makes option A necessary in the first place, and
it is why campaign 500 cannot be lengthened in place.

---

## 6. THE LINKEDIN HALT IS LIFTED — operator, Zvonimir, 2026-09-25

**Both directions of the cross-channel stop are measured, from PROVIDER
timestamps rather than from our own polling:**

    LinkedIn -> email   7.7 minutes   2026-09-23
    email -> LinkedIn   4m 02s        2026-09-25

The second is today's, and it is the one that had never run. Chain:

    12:19:23Z  email sent to the test identity      provider-confirmed
    12:20:09Z  operator's reply                     provider's own timestamp
    12:20:06Z  reply_received, reply_classified     ingested, record matched
    12:24:10Z  bison.stop_lead      ACCEPTED        reply_watch_loop pid 49396
    12:24:11Z  heyreach.stop_lead   PERFORMED       same loop, same reply
               621824  Pending -> Paused            provider truth

**Timed from 12:20:09Z, not from 12:20:25Z when the watcher noticed it.** The
watcher's own figure was 3m47s and would have been flattering and wrong.

**Four things had to be fixed today for this to run at all**, and each of them
would have produced a passing-looking result that measured nothing:

1. `adapters._custom` read only the top level of a reply row, so `record_id`,
   `contact_key` and `client` were `None` for EVERY EmailBison reply ever
   ingested. Fixed to read `row["lead"]["custom_variables"]`.
2. `leadstop._campaign_of` resolved channel-blind, handing the LinkedIn stop
   the email campaign row.
3. `heyreach_lead_id` has to be `linkedInUserProfile.linkedin_id`. **HeyReach
   support named `linkedInUserProfileId`, and that value 404s.** Three measured
   calls settle it; their own record of the successful one reads
   `leadCampaignStatusMessage: "The workflow was paused manually. (API)"`.
4. The target has to be in a RUNNING status. 620829 could not be reused
   because the validated stop moved it to `Paused`, and a stop against a
   settled lead passes by construction.

**And the audit was lying in both directions until 12:35Z.** The email
read-back was `lambda: {"stopped": True}` against `expected={"stopped": True}`
- a constant identical to the expectation, so it recorded ACCEPTED whatever
the provider did. The LinkedIn read-back returned the raw campaigns LIST
against a dict, so it recorded DRIFTED even when the stop worked. Fixed in
`50ade3b0`; both now ask the provider.

### 6.1 What the lift does NOT license, measured the same hour

**Not one of the 690 leads in 503/504/505 carries a LinkedIn profile.** Their
rows hold company, domain, email, first_name, location, pack and title. The
09-07 list is addresses and firmographics; no profile URL was ever sourced. So
"cross-channel enrolment, 503/504/505 first" has nothing to enrol them with,
and getting profiles is a DISCOVERY job with its own cost.

**491-498 is the enrollable population: 805 contacts, 805 with a LinkedIn
field.** That is the ceiling and not the number - lane P measured ~30% failing
match validation on a comparable sample (46 refused + 17 unverifiable of 207)
and found candidates already sitting in client LinkedIn campaigns, one in
thirteen at once.

**825 was never available.** Per-seat arithmetic is 779 (7 of 33 seats cannot
take 25) and the rule-respecting figure is 330, because zero seats are
exclusively ours and "unknown is not room" caps a shared seat at 10.

### 6.2 The standing risk a lift does not remove

GLM's review of the account rule: the gate reads `rec["events"]`, and the
store holds **one** `push_marked` against the provider's **2,319** sends.
**131 accounts pass the gate today only because their send history is absent
from the only source the gate reads.** Cross-channel pairs are precisely the
population where that costs a second message to somebody who already replied.
The ledger write-back is the fix and it is the named next engineering item.

---

## 7. THREE DECISIONS, operator Zvonimir, 2026-09-25 afternoon

### 7.1 Batch shape

**Geo + persona are REQUIRED and never merge.** Industry group MAY merge
within a batch when a slice is under **200** contacts, and **the merged
industries are named in the campaign tag**. Slices still under **50** after
that go to a **reservoir** and join the next batch of the same geo + persona.
**Never a campaign under 50** - encoded as a refusal, not a preference.

Why it was needed: slicing on geo x industry x persona gave **41 batches, of
which 22 held <=50 contacts and 15 held fewer than 5**. A one-contact batch is
a campaign per person, which `PRODUCTION-SCALE-POLICY` forbids.

The 1,975 unzonable rows and the 67 rows resolving non-US inside a
US-classified file keep their own slices and are never folded into a placed
one - geo does not merge.

### 7.2 Spend caps become PER PROVIDER

    cheapverifier   total 100,000   per_day 95,000   per_run 10,000
    deliverable     total 500,000   per_day 95,000
    reoon           total 500,000   per_day 95,000
    contactout      no ledger cap
    apify           5,000 $-cents/day, as declared

**The client-level `total` is REMOVED.** A client-level `per_day` of
**200,000** remains as a **sanity ceiling only** - a tripwire against a
runaway loop, not a budget.

**THE SWAP MUST BE ATOMIC.** Removing the client `total` before per-provider
totals are enforced leaves the estate with no lifetime cap at all, and a
200,000/day tripwire does not catch a runaway inside one day. The removal and
the enforcement land in one commit, with a test asserting that a config
carrying **neither** is REFUSED rather than read as unlimited. **A missing cap
must never parse as an unlimited one** - the same class as the empty
expectation `_classify` documents, and as the empty ledger below.

Ground truth at the time of the decision, from the ledger:

    deliverable 8,262 all-time (7,194 today)   reoon 8,236 (7,171)
    contactout 1,562   apify 447   blitz 232   aiark 70
    TOTAL 18,809 all-time, 14,365 today

**And the hazard that makes any of this defeatable:** a paid stage run from an
agent's worktree reads an **empty ledger** - `work/` is gitignored, so a fresh
worktree has no spend history - and `check()` reads that same empty file and
concludes the whole budget is free. Every lane running today could have spent
the balance twice and been told it was within bounds. `LedgerNotCredible`
refuses paid sizing against a ledger with no history; lanes S and T are
coordinating so neither assumes the other checked.

### 7.3 LinkedIn is cold-leads-only

**The 491-498 cohort is PERMANENTLY excluded from LinkedIn.** The client
already runs those people: of 147 swept, **142 are in a client LinkedIn
campaign**, median **eleven** campaigns each, one in nineteen. Our store said
19%; the provider says 98%. Enrolling them would have put a prospect in a
twelfth simultaneous sequence.

LinkedIn supply is therefore **cold leads only**. ContactOut discovery for the
690 runs tomorrow morning, and **every batch carries a LinkedIn URL from
discovery before push**.

**The collision-gate change goes through GLM first.**
`collision.account_policy` STOPs on `anyone_in_sequence` computed with no
regard to WHO, so it refuses a cross-channel pair because of the very person
it is being asked about. That is rule 6 being refused by a gate that predates
it, and it is a live safety gate.

**Carry this into any enrolment:** 63% of the client's HeyReach rows use an
`imp_`-prefixed member id and the stop is validated only on a NUMERIC one. So
`heyreach_lead_id` is read **after** enrolment from `campaign_leads` and its
shape asserted - binding it from the pre-enrolment `lead_profile` call, the
natural place, would store the wrong value for everyone.
