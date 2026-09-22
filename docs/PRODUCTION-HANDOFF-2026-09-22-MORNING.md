# Production handoff — 2026-09-22 morning

Written for a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-21-NIGHT.md`**, whose headline — 151 leads
enrolled and nothing able to send — is no longer true. Both channels are
live.

---

## 1. THE HEADLINE: BOTH CHANNELS ARE SENDING

**EmailBison 491-498 are ACTIVE**, holding 151 leads, with 243 scheduled
rows the provider planned itself.

    camp  human      leads  queue  first send          window
    491   kresimir      34     68  2026-09-22 13:03Z   America/New_York
    492   bernarda      30     59  2026-09-22 13:55Z   America/New_York
    493   ivan          20     20  2026-09-24 13:20Z   America/New_York
    494   fran          12     23  2026-09-22 14:13Z   America/New_York
    495   tomislav      26     44  2026-09-22 13:02Z   America/New_York
    496   bojan          9      9  2026-09-24 08:10Z   Europe/London
    497   jakov          7      7  2026-09-24 08:33Z   Europe/London
    498   luka          13     13  2026-09-24 07:09Z   Europe/Zagreb

13:02Z is 09:00 in New York — the provider is scheduling inside each
cohort's own window.

**33 HeyReach campaigns are IN_PROGRESS**, 613724-613761, one per attested
seat, carrying 151 leads across 33 lists and the cloned Productive standard
graph. **Connection requests sent: 0. Accepted: 0. Replies: 0.**

**ENROLLED IS NOT SENT, AND ENROLLED IS NOT REQUESTED.** Starting a LinkedIn
campaign does not issue 151 requests: each seat works its own four or five
leads at ten a day, and the graph decides the rest — three hours to the first
message on the accepted branch, five days between messages, five days before
each profile view.

## 2. CAPACITY: 2,310 IS A CAP, 1,470 IS TODAY

**Size batches against the forward book, not against the mailbox count.**
This is the rule to carry forward and it has already cost one wrong number.

154 attested mailboxes × 15 = 2,310, and that assumes every mailbox is free
every day. They are not. The forward book, walked 2026-09-21T18:50Z,
complete, covering every campaign that can book a mailbox (327, 328, 352,
481, 487, 489):

    camp  human      mailboxes  09-22  09-23  09-24  09-25
    491   kresimir          63     48     48     48     48
    492   bernarda          47     30     29     29     29
    494   fran              12     11     11     11     11
    495   tomislav          11      7      7      7      7
    493   ivan              13      2      0      0      0
    496   bojan              5      0      0      0      0
    497   jakov              2      0      0      0      0
    498   luka               1      0      0      0      0

    98 mailboxes with room today × 15 = 1,470 first steps actually available

That table also answers why four campaigns wait for the 24th: every campaign
sending today has mailboxes with room today and every campaign waiting has
none. Not the window — 498 is the Zagreb cohort and opened earliest. Not the
planner. It is 327/328/352 holding those inboxes at their 15/day limit.
jakov has two attested mailboxes and luka has one.

`docs/WHY-FOUR-CAMPAIGNS-WAIT-FOR-THE-24th-2026-09-22.md` has the full
reasoning, including what the walk does NOT prove.

## 3. SUPPLY

    S5 verification   FINISHED. 9,140 decided: verified 6,534, held 1,658,
                      accept_all_uncleared 601, unknown 148, invalid 199.
    S7 copy           850 rendered, 21 held - all 21 for no company name.
    re-engagement     973 REENGAGE, 37 REVIVE, 379 UNKNOWN, 17 ACTIVE,
                      9 NEVER. READ-ONLY. Nothing enrolled.

S5 finishing is the biggest supply change since last night: 6,534 verified
against 4,161 twelve hours ago.

## 4. WHAT MERGED

    TASK-241  arity      90bd119b + 490f6f58. Capacity 120 -> 2,310 cap.
    TASK-244  export cycle, S1 suppression per client
    TASK-245  nightly sourcing that stops at candidates
    TASK-246  learning tags
    Slack agent Phase A  live, answering, readbacks proven against the
                         production work/ directory

**Phase B is NOT merged.** `docs/MERGE-REQUEST-SLACK-AGENT-PHASE-B.md` is
waiting, and the operator's instruction is explicit: do not bind any client
channel yet.

## 5. KEYS WERE ROTATED, AND EVERY MONITOR SURVIVED IT

EmailBison, HeyReach and Slack tokens were rotated overnight. Verified by
name, never by value:

    CONTACTOUT_TOKEN  BLITZ_API_KEY  AIARK_KEY  BISON_KEY  HEYREACH_KEY
        all AUTHENTICATION_VERIFIED
    REOON_KEY  DELIVERABLE_KEY
        configured, unverified BY DESIGN - their only endpoints cost a credit

**Zero 401s and zero 403s in any watcher log**, so no monitor is running on a
dead key. The Slack bot token was re-smoke-tested: `ts 1790014855.313029`.

## 6. MAILBOX 3437

**Excluded from every new batch** and already held out of wave 2 by the 2%
bounce stop, at 2.14% lifetime over 8,947 sends. **489 runs its five leads to
completion on it** — that is the operator's decision, not an oversight.

Four other mailboxes are held for the same reason: 3760 (2.29%), 3743
(2.08%), 3761 (3.53%), 3947 (2.68%).

**The 7-day stop is NOT yet measured from our own ledger.** Every number
above is LIFETIME, which `sender_emails()` gives and which is a different
question. Building that from the action ledger is one of the next three
actions below.

## 7. THE NEXT THREE ACTIONS

1. **Batch 3, sized to the forward book.** Supply is 850 rendered plus
   whatever S5's finished output clears; capacity is 1,470 today, not 2,310.
   Dual-channel from the start: email plus HeyReach on fresh unbound lists
   using the cloned graph. Stats, 15-minute veto, push. Report per-campaign
   first-step capacity AND backlog days.
2. **Merge Slack agent Phase B** per its merge request, restart the loop,
   post "Phase A+B live". Bind no client channel.
3. **The 7-day bounce stop, from our own action ledger.** Every stop checked
   so far is lifetime. The grant's rule is seven days, and only our ledger
   can answer it per mailbox.

## 8. MONITORS

    86848   bison_mailbox_utilisation --interval 300
    19236   reply_watch_loop --interval 300
    95760   notify_deliver_loop --interval 60
    89640   bison_watch_loop --campaign 487 --interval 180
    105276  bison_watch_loop --campaign 489 --interval 180
    92332   heyreach_watch_loop --interval 300
    110384  digest_loop --interval 300
    105124  slack_agent_loop          (a DIFFERENT session owns this file)

S5 has finished and is no longer running. Restart bare. **Never under
`timeout`.**

**The batch campaigns have no watcher.** 491-498 and the 33 LinkedIn
campaigns are sending with nothing tailing them the way 487 and 489 are
tailed. That is the largest observability gap right now.

## 9. WHAT MUST NOT BE RE-DERIVED

- **A status the provider returns on the happy path is a state, not an
  anomaly.** `STARTING` on HeyReach and `launching` on EmailBison were both
  reported as unclassifiable while the campaigns were running. Both
  classifiers now carry them; success is still only `IN_PROGRESS`/`active`.
- **`campaign_leads` reads ZERO on a DRAFT whose bound list holds people.**
  The audience materialises at start. `expect_leads` must come from the list.
- **A HeyReach list is PERMANENT** - no delete endpoint - and list names cap
  at 50 characters. `add_leads_to_list` takes INTERNAL rows and refuses
  provider-shaped ones.
- **A graph read from the provider is not a graph you can post back.**
  `sequence_for_write` strips the provider's `conditionalNode: END`
  normalisation; it has existed since 2026-09-16 for this exact round trip.
- **The cloned standard's three `SEND_LEAD_TO_BISON` nodes are dropped** as
  ENDs that keep their own 3/3/5-day waits, because they were pinned to the
  client's campaigns 417 and 418 and HeyReach validates that reference.
- **Client approval, collision and verification all run against the CLIENT's
  policy**, not the defaults. The approval gate read the default policy until
  2026-09-21 and approved 168 leads under roles the client had dropped.
