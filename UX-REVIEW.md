# UX Review Checklist

For your manual pass after Mission 4.1. Ordered by what changed most.

## Start it

```
py -m src.web --demo
```

**http://127.0.0.1:8765** — sign in by picking a person. No password.

| Sign in as | Role |
| --- | --- |
| `root@resonate.test` | SUPER_ADMIN — every workspace, admin consoles |
| `admin@productive.test` | WORKSPACE_ADMIN |
| `ops@productive.test` | OPERATOR — most screens are built for this role |
| `review@productive.test` | REVIEWER |
| `client@productive.test` | VIEWER — the client |
| `ops@contactout.test` | operator in ContactOut, **reviewer** in Productive |

---

## Review in this order

### 1. Global Dashboard — `/global` as `root@`
Every workspace you may enter, aggregated. Note the new type scale and the
warmer ground: the previous palette was a navy admin theme.

### 2. Productive workspace — `/` as `ops@productive.test`
The operator's first screen. The Slack panel names this workspace's channel
and nothing about the operations channel.

### 3. Account Outreach View — `/outreach/account/demo-acme` ★
**The flagship screen, and the one to spend most time on.**

Acme Ltd: three decision makers, four humans, two channels, one reply, one
referral.

Look at:
- **the account timeline** — one column of what happened, interleaving touches,
  the reply and the referral, rather than three tables to merge by eye
- **John Smith** — heard from Anna (email) and Petar (LinkedIn), replied
  positively, referred us to Sarah. Open him from `/contacts` for the same
  interleaving one person at a time: every touch, his reply, what the policy
  did about it and any date he named, in one column with an arrow saying
  which way each line went
- **Sarah Jones** — Mark emailed her (confirmed); Sara's LinkedIn touch is
  **planned**, and the screen says so
- **"What a message here may say"** on each contact — every claim, allowed or
  refused, each with its reason

The specific thing to check: on Sarah, "Colleague handoff" is **refused** with
*"Sara Simic has no confirmed touch to this contact"*. That planned LinkedIn
message is exactly the fabrication the model exists to prevent.

### 4. Contact Outreach View — `/outreach` as before
The campaign-wide contact list, unchanged in shape. `/outreach/accounts` is the
new account-first list.

### 5. Cadence Builder — `/outreach/cadence`
Switch the template dropdown to **Account-based multi-DM**. Look for:
- branches with their conditions in words ("if the connection request was
  accepted")
- two email humans and two LinkedIn humans in one graph
- a node marked *not on the default path* — a branch nobody can see is a
  branch nobody reviews
- the validation panel

Then try **LinkedIn heavy** — 13 nodes, a 21-day wait, and a second profile
taking over.

### 6. Campaign Builder — `/campaigns/new`
Unchanged this mission. Still dense; see rough edges below.

### 7. Account Dossier — `/companies/demo-acme`
The older company view, for comparison with §3.

### 8. Reply Center — `/replies`
### 9. Approval Center — `/approvals`
Both unchanged this mission.

### 10. Reporting — `/reporting`
Eighteen dimensions, every rate with its numerator and denominator.

### 11. Report Editor — `/reporting/editor` ★
**The second flagship.**

Create a draft: template **Resonate Outbound Performance Report**, period
`2026-07-01 to 2026-07-31`.

Then look at:
- the narrative blocks, pre-filled with **deterministic** seeded prose and
  marked *Suggested* until you edit them
- the **Counted** panel on the right — read-only figures, with the sentence
  "recounted every time the report renders, so an edit above cannot change
  one"
- section checkboxes
- **Next month** — Scale / Test / Stop / Follow up

Edit the summary, save, and watch the version go up. The previous version is
kept.

### 12. Generated Monthly PDF — Export PDF from the editor
Twenty sections. Check:
- your edited summary is in it
- the counted figures are still counted
- **Meetings says "Not tracked"** with the reason
- LinkedIn says acceptance is never inferred if there is no provider data
- Sender Performance says "No ranking" and shows sample sizes

### 13. Client Viewer — sign in as `client@productive.test`
They can generate their own executive report. **Internal Operations Report is
not offered**, and forging it returns the executive one.

### 14. Slack Admin — `/admin/slack` as `root@`
Unchanged and still working. Posts made: 0.

---

## Try to break it

1. `/outreach/account/<a ContactOut record id>` as a Productive operator → 404,
   no contact names in the body
2. `/reporting/editor?draft=<another workspace's draft>` → 404
3. As the VIEWER, POST `template=internal` → you get the executive report, not
   a refusal
4. Find a claim shown as allowed with no reason beside it
5. Find a number in a report with no denominator

---

## Rough edges — stated so you needn't hunt

**Resolved since Mission 4:** suppression and search now exist; system health
and onboarding exist; the client report is no longer a one-shot PDF.

**Still open:**

- **The campaign builder still does not use the cadence graph.** `/campaigns/new`
  builds the old linear cadence; the graph is visible at `/outreach/cadence`
  and validated, but the two are not yet joined. A campaign cannot yet *store*
  a branching cadence, only preview one.
- **The contact outreach view is unchanged.** §24 of the brief asked for it to
  be rebuilt alongside the account view; the account view came first and the
  contact view still shows the old per-step layout.
- **Fatigue is advisory, not yet wired into campaign QA.** `fatigue.check()`
  exists and is shown on the account screen; QA does not call it yet.
- **The reply classifier does not create referral edges.** It now reads
  them: a reply handing somebody on is classified `referral` and records what
  it said, and the task centre asks a person to resolve it. Turning "Sarah
  handles this" into an edge is still nobody's job but an operator's —
  deliberately, because a name is not an identity.
- **The design pass is tokens and shell, not every screen.** The palette,
  type scale, tables and panels changed everywhere; individual dense screens
  (campaign builder, diagnostics) have not been reworked.
- **The public Resonate site was not reachable from this build**, so the
  design language came from the brief's description rather than the site
  itself. `DESIGN-SYSTEM.md` §0 lists what to check against the real site.
- No screen-reader pass. Semantics, contrast and focus are built to; nobody
  has tested with an actual reader.

---

## What I could not do, and why

The brief refers to founder-supplied reference materials:

- **HeyReach cadence exports** (§28) — not in the repository. The node
  vocabulary comes from the brief's own list and from what the HeyReach
  adapter demonstrably supports. Two node types the brief names (post
  reaction, withdraw connection request) are present but marked unvalidated
  and **blocked at validation**, because nothing here proves the provider does
  them.
- **Greenfield / Productive / Nextoria reference reports** (§30) — not in the
  repository. The monthly template's structure comes from §32's own section
  list.

If you can supply either, the right next step is to widen the vocabulary and
the report structure against them rather than to assume.
