# Go-Live Checklist

The gate between a working system and one that contacts real people.

This exists to make enabling live sending **hard, deliberate and reversible**.
Every gate below must be signed by a named person on a named date. An unsigned
gate is an unmet gate; there is no "obviously fine" row.

**Current state: nothing on this list is signed. Live sending is disabled.**

`push.run(live=True)` raises `LiveSendNotEnabled`. `slack.post` raises
`SlackPostingNotEnabled` unless `SLACK_LIVE` is set. Those two refusals are the
last line, and this checklist is what precedes taking either of them away.

---

## How to use this

Work top to bottom. A gate that fails stops the process; do not proceed to the
next section on the promise of coming back.

Two people sign each gate in Part D: whoever did the work, and whoever checked
it. The same person cannot be both.

---

## Part A — the build

| # | Gate | Evidence | Signed |
| --- | --- | --- | --- |
| A1 | Full test suite green | `py -m unittest discover -s tests` | ☐ |
| A2 | Network-blocked suite green | `py -m tests.offline` reports "nothing reached off this machine" | ☐ |
| A3 | Mutation audit fully caught | `py tools/mutation_audit.py`, zero MISSED | ☐ |
| A4 | `git status` clean, no mutated source committed | `git status`, `git diff` | ☐ |
| A5 | Version deployed is the version tested | commit SHA recorded here: `________` | ☐ |

---

## Part B — infrastructure

| # | Gate | Evidence | Signed |
| --- | --- | --- | --- |
| B1 | Production database provisioned and migrated | `DATABASE-MIGRATION.md` acceptance checks | ☐ |
| B2 | **A restore from backup has been performed and verified** | restore log; an untested backup is a hope | ☐ |
| B3 | Real authentication in place; demo sign-in refused in production | `APP_MODE=production` and the seeded-user form is absent | ☐ |
| B4 | `python -m src.config --mode production` reports no blockers | command output | ☐ |
| B5 | `SESSION_SECRET` stable across deploys | two deploys, session survives | ☐ |
| B6 | Worker running jobs outside the web process | one job observed | ☐ |
| B7 | Scheduler running, and advancing nothing that sends | scheduler log | ☐ |
| B8 | TLS valid on `app.resonategroup.co` | certificate check | ☐ |
| B9 | Marketing site and existing DNS untouched | `resonategroup.co` resolves as before; MX and TXT unchanged | ☐ |
| B10 | Monitoring and alerting live for the list in `PRODUCTION-READINESS.md` | alert test fired and received | ☐ |

---

## Part C — provider validation

Every row here is a stage of `LIVE-VALIDATION-PLAN.md`. None may be skipped,
and none may be signed on the strength of an offline test.

| # | Gate | Plan stage | Signed |
| --- | --- | --- | --- |
| C1 | Provider reachability confirmed | 1.1 | ☐ |
| C2 | ContactOut people-count confirmed | 1.2 | ☐ |
| C3 | **Deliverable wire contract validated against a live answer** | 2.1 | ☐ |
| C4 | Reoon escalation confirmed | 2.2 | ☐ |
| C5 | Slack auth and channel resolution confirmed | 3.1 | ☐ |
| C6 | First Slack post to a throwaway channel | 3.2 | ☐ |
| C7 | Workspace channel isolation proven with two throwaway channels | 3.3 | ☐ |
| C8 | Slack interaction callback verified, replay refused | 3.4 | ☐ |
| C9 | EmailBison identifiers survive a round trip | 4.2 | ☐ |
| C10 | HeyReach custom fields survive a round trip | 4.3 | ☐ |
| C11 | A real reply ingested, matched, paused and announced | 4.4 | ☐ |

**C3 is the one to be most careful about.** Deliverable's response shape has
never been read from a live answer. Until it has, the verification waterfall's
final step is written against an assumption, and the failure mode is an invalid
address being classified valid - a contact that should have been held becoming
sendable. Do not sign C3 on the basis of one address that verified correctly;
check a known-bad address too. A normaliser that maps everything to "valid"
passes a one-address test.

---

## Part D — the client

Not technical, and the part most likely to be skipped.

| # | Gate | Evidence | Did | Checked |
| --- | --- | --- | --- | --- |
| D1 | The client has agreed to outreach being sent on their behalf | signed agreement | ☐ | ☐ |
| D2 | Sending domains are owned by, or delegated by, the client | DNS records | ☐ | ☐ |
| D3 | SPF, DKIM and DMARC pass on every sending domain | authentication report | ☐ | ☐ |
| D4 | Sending domains warmed | warm-up record | ☐ | ☐ |
| D5 | LinkedIn profiles belong to real, consenting people | named list | ☐ | ☐ |
| D6 | Every sender persona corresponds to a real person | named list | ☐ | ☐ |
| D7 | The client's Slack channel id is confirmed **by the client** | written confirmation, not a guess from the name | ☐ | ☐ |
| D8 | Unsubscribe and suppression handling agreed | written | ☐ | ☐ |
| D9 | A named person is on call for replies | rota | ☐ | ☐ |

D6 deserves a sentence. This system sends as a named human and writes
cross-channel copy in their voice - "my colleague Anna emailed you earlier this
week". If Anna is not a real person who agreed to this, that sentence is a
fabrication sent to a stranger, and no amount of engineering discipline
elsewhere makes it acceptable.

---

## Part E — the campaign

Per campaign, every time. Not once.

| # | Gate | Signed |
| --- | --- | --- |
| E1 | QA passed, no BLOCK verdicts | ☐ |
| E2 | Every contact double-verified, or held | ☐ |
| E3 | MX and email-security screening applied | ☐ |
| E4 | Suppression list applied | ☐ |
| E5 | Sender capacity sufficient for the planned volume, using known limits only | ☐ |
| E6 | Cadence reviewed in the outreach preview, by a person | ☐ |
| E7 | Cross-channel references check out against confirmed touches | ☐ |
| E8 | Approval recorded with a current fingerprint | ☐ |
| E9 | The approver holds `campaign.approve` in that workspace | ☐ |

---

## Part F — enabling it

Only after A through E are complete and signed.

1. **Announce it.** A named person, a named time, a named campaign.
2. **One campaign.** Not a workspace, not a batch of campaigns. One.
3. **Smallest useful volume.** Ten contacts, not the segment.
4. Enable sending for that campaign only.
5. Watch for one full working day: deliveries, bounces, replies, unmatched
   events, Slack notifications, job failures.
6. Stop, and review, before the second campaign.

### The stop condition

Turn sending off immediately, without discussion, if any of these occur:

- a message goes to a contact who was held, suppressed or paused
- a reply is attributed to the wrong contact or the wrong company
- a positive reply reaches the wrong workspace's Slack channel
- copy references a touch that did not happen
- the reply poller stops and nobody is notified
- a bounce rate above the agreed threshold
- anything nobody can explain within an hour

"We will look at it after this batch finishes" is not a response to any of
these. The pause is cheap; the alternative is not.

---

## Part G — after

| # | Gate | Signed |
| --- | --- | --- |
| G1 | First-day review held, findings written down | ☐ |
| G2 | Everything in Part F step 5 observed and accounted for | ☐ |
| G3 | Rollback rehearsed at least once | ☐ |
| G4 | This checklist updated with what it failed to anticipate | ☐ |

G4 is not ceremonial. The first live campaign will find something this document
did not think of, and the value of writing it down is entirely in the second
campaign.

---

## Sign-off

Live sending may be enabled only when every gate above carries two signatures.

| Role | Name | Date |
| --- | --- | --- |
| Engineering | | |
| Operations | | |
| Client-facing owner | | |

**Nothing on this page is signed. Live sending remains disabled.**
