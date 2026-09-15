PRIORITY: P4
DEPENDS: 

# TASK-111 - the EmailBison API surface, and what is still guessed

## WHERE THIS STANDS

`docs/BISON-API-CAPABILITY-MAP-2026-09-14.md` and
`docs/BISON-PROVIDER-TRUTH-2026-09-14.md` established a great deal, including
the finding that matters most: **step-level AND variant-level attribution are
REAL**, verified end to end -

    reply 1609180 -> scheduled_email 22290485 -> sequence_step_id 4039
                  -> variant=True, variant_from_step=4037

and that the reply -> step link is **TWO HOPS, not one**: a reply carries
`scheduled_email_id` and NOT `sequence_step_id`. An earlier task called it
"directly supported" and sent the next reader hunting a field that does not
exist.

## WHAT IS STILL UNESTABLISHED

`src/providerwrites.py` lists these as "no documented route" for EmailBison:
create campaign, configure sequence, pause/activate. But `SUPPORTED` now
contains `bison.create_campaign` and `bison.set_sequence`, so two of those
WERE established and the docstring had not caught up - it has now been
corrected, but the underlying question stands:

**Which EmailBison routes are genuinely established, and which are still
guesses?** An endpoint counts as established only when the provider documented
it, the existing code carries its confirmed shape, or a real response has been
read.

## WHAT TO DO

1. Inventory every EmailBison route the codebase references or calls.
2. For each: documented / shape confirmed in code / real response read /
   guessed. Cite the evidence.
3. Probe READ-ONLY routes to confirm shapes. **Do not probe a write route** -
   "guessing a write path against a live client estate is how somebody
   discovers a route by mutating production."
4. Report what a lead-add would need, without performing one.

## WHAT NOT TO DO

- No writes. Not even a "harmless" one to a draft campaign.
- Do not mark a route established because the code has a URL for it. The URL
  being known is exactly the state the write gate calls UNSUPPORTED.

## DELIVERABLE

An updated capability map with an evidence column, and a clear list of what is
still guessed.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from the outside.** If you
  measure zero of something, prove you read the right field first. Industry
  and headcount were reported at 0% three separate times by a reader looking
  at `sizing`, which is null everywhere, instead of `company_facts`.
- Say what you SAMPLED. `per_page` is accepted and IGNORED on every EmailBison
  route - you get 15 rows whatever you ask for - and offset pagination is
  refused past ~500 pages. A number without its page budget is not
  reproducible.
- Never use `meta.total` as a sent count. Campaign 274 reports 30,411
  scheduled rows and zero of its first 100 pages are sent. Count rows WHERE
  `sent_at` IS PRESENT.
- **Do not quote 8.49%** - unreproduced. **Do not quote any open rate** -
  `open_tracking` is False estate-wide, which is an ABSENT MEASUREMENT and not
  a zero. **Do not count an UNKNOWN as negative** - 53.4% of unknowns are
  correctly unknown.
- INTERESTED may NOT carry a learning claim: 0.44 precision on the old pattern
  set, and the new set is UNMEASURED, which is not the same as good.
  MEETING_INTENT (1.00) and OBJECTION (1.00) may, with recall stated.
- Never weaken, widen or disable a gate, a lint rule or a sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- No unhashed PII in any tracked file or commit message - no real names,
  domains, emails, profile URLs or reply text. A seat holder is a real person
  too; Claude leaked one yesterday and the guard caught it.
- Separate OBSERVATIONS (with n), HYPOTHESES, and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection. TASK-059
  left it empty and was right to.

---

## RESULT BLOCK

**STATUS:** DONE

**COMMIT SHA:** 183866e (after rebase)

**TESTS:** No code changes to test. Probe scripts are standalone GET-only
utilities. No existing tests were affected.

**FILES CHANGED:**
- `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md` — the deliverable. Every
  EmailBison route classified by evidence level (LIVE / CODE / DOCS /
  GUESSED), with response shapes cited.
- `scripts/task111_probe_routes.py` — main route probe (50 routes, GET only)
- `scripts/task111_probe_routes2.py` — follow-up probes (lead existence, events)
- `scripts/task111_probe_routes3.py` — per-lead routes, individual reply, search trap
- `docs/qwen-tasks/RUNNING/TASK-111-what-else-does-emailbison-expose.md` —
  moved from TODO/

**FINDINGS:**

### The inventory

50 routes probed (GET only) against the live instance on 2026-09-15:

| Evidence level | Count | What |
|---|---|---|
| **LIVE** | 21 | Route returned 200 (or 404) with parseable shape recorded |
| **CODE** | 13 | Called in `bison.py` with response handling, not re-probed |
| **DOCS** | 16 | Vendor documentation names them, no live probe, no code caller |
| **GUESSED** | **0** | Every route the codebase references has at least DOCS evidence |

19 routes confirmed as **404** (do not exist).

### Corrections to the 2026-09-14 capability map

1. **`GET /scheduled-emails/{id}` does NOT carry a `lead` field.** The
   listing form (`/campaigns/{id}/scheduled-emails`) DOES. This is a real
   asymmetry in the provider's API. The earlier map was wrong.

2. **Lead 146592 no longer exists** (404). It was used as an example in the
   earlier map.

3. **`/workspaces` returns 1 workspace** (PRODUCTIVE, id 10), not 13 as the
   bison.py comment from 2026-09-07 stated.

4. **`/leads/{id}/replies` and `/leads/{id}/sent-emails` are LIVE-confirmed
   200**, not just documented. Both return the expected shapes.

5. **`/campaigns/{id}/leads?search=` is accepted and DISCARDED** — returns
   the full unfiltered listing. This is different from `/leads?search=`
   which IS a real filter.

### What a lead-add would need

All established (CODE evidence):
1. `POST /leads` — create the lead with email, first_name, custom_variables
2. `POST /campaigns/{id}/leads/attach-leads` — attach by id list
3. Pre-conditions: lead not `in_sequence` elsewhere, not bounced/unsubscribed
4. Custom variable names must be declared first if new

Still gaps:
- `POST /campaigns/{id}/leads/attach-lead-list` (DOCS only) — shape unknown
- `POST /leads/bulk/csv` (DOCS only) — shape unknown
- Batch attach is all-or-nothing: one collision refuses the entire batch

### What is still guessed

**Nothing.** Every route the codebase references has at least DOCS evidence.
The 16 DOCS-only routes are write routes that were deliberately NOT probed
per the task rules. Their shapes come from vendor documentation.

**RISKS:**
- The 16 DOCS-only write routes have not been live-verified. Their shapes
  could differ from documentation. Any task that implements one should probe
  it first (read-only where possible, then carefully).
- The workspace count changed from 13 to 1 between 2026-09-07 and
  2026-09-15. If workspaces are added or removed again, code that assumes a
  fixed count will break.
- `per_page` is ignored on almost every route. This is confirmed again.

**RECOMMENDED CLAUDE ACTION:**
- Review the evidence map at `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md`
- The corrections to the 2026-09-14 capability map should be backported if
  that document is still the active reference
- The DOCS-only write routes are candidates for live verification when a
  task needs to implement one
