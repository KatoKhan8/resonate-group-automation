"""Per contact, per rule: was every suppression rule asked, and what did it say?

## The question this answers, and the one it refuses to answer

Before CANARY-01 sends, somebody has to be able to say of **each named
contact** that every rule which could exclude them was asked and answered.
Not that the rules exist - they do, and they are good - but that each one was
*put to this person* and gave an answer.

Nothing in this estate produced that. `eligibility.must_not_contact` answers
six questions in one tuple, `suppression.decide` adds five more, `hygiene.check`
adds four, `channels.email_verdict` composes a different subset again, and each
one collapses to a single verdict. A single verdict cannot distinguish the two
states this file exists to keep apart:

    EXCLUDED   the rule was asked and it refused
    UNKNOWN    the rule could not be asked at all

**UNKNOWN IS NOT PASS AND NEVER BECOMES PASS.** A contact with any UNKNOWN
cell is not cleared. That is invariant 0 applied to a cohort: an unreadable
authority means UNKNOWN, and UNKNOWN never becomes PASS, zero, idle, complete
or safe.

## THE AUTHORITY IS CHECKED BEFORE THE RULE, AND THAT IS THE WHOLE DESIGN

Measured 2026-10-16 in `wt-suppression-2026-10-14`:

    agencydnc.load()      ->  {}   with work/agency-dnc.jsonl ABSENT
    agencydnc.lookup(x)   ->  None for every x
    store.load()          ->  0 rows, NO RAISE, with work/queue.jsonl ABSENT
    ingest.load_suppress()->  2 domains, with config/suppress.local.txt ABSENT

So in this tree every contact passes the agency do-not-contact list, and
nothing anywhere says the list was never read. `agencydnc.load`'s own
docstring states it: *"Missing file is empty."* That is a reasonable choice
for a send path which must not take the estate down on a damaged byte - and
it is the wrong answer for a preflight, because a preflight's entire job is
to distinguish "asked and clean" from "not asked".

`src/supervisor.py` already took the opposite decision for the same shape and
wrote down why: *"`campaigns.load()` returns an EMPTY SNAPSHOT when the
registry file is absent - it does not raise. Reading it straight would
therefore turn 'I cannot see the registry' into 'there are no campaigns'."*
It raises `RegistryUnreadable` instead. Nothing does that for the DNC.

**This module does not change any of those readers.** They sit on send paths
and changing one is a gate change. Instead every rule DECLARES the authority
files it needs, `authorities()` reports each one's state by path, and a rule
whose authority is not PRESENT is UNKNOWN before the rule is even called. The
reader keeps its behaviour; the preflight stops being fooled by it.

## Read-only, and it makes no provider call

Every rule needing a provider read is UNKNOWN by declaration, named, with the
read that would answer it. Nothing here enriches, writes, suppresses, enrols
or sends.

## Real addresses do not come from here

This module takes contacts as an argument. It never reads a cohort file and it
never prints one. The addresses live in `resonate-ops/` and in gitignored
paths; the tests use synthetic ones.
"""
import os

from . import store

# ------------------------------------------------------------- the cells

PASS = "PASS"
EXCLUDED = "EXCLUDED"
UNKNOWN = "UNKNOWN"

#: The three answers and the only three. A fourth would be a way to say
#: "probably fine", which is the thing this file exists to refuse.
CELLS = (PASS, EXCLUDED, UNKNOWN)

EXIT_CLEARED, EXIT_EXCLUDED, EXIT_UNKNOWN = 0, 1, 2

# -------------------------------------------------------- the authorities
#
# ONE ROW PER FILE THAT A RULE READS, resolved through the module that owns
# the path - never spelled out here. `test_invariants` fails any module but
# `store` that names a state file, and a second spelling of a path is a
# second thing that can be wrong.

PRESENT, ABSENT, UNREADABLE = "PRESENT", "ABSENT", "UNREADABLE"


def _operator_exclusion_path():
    from . import operatorexclusion
    return operatorexclusion.path()


def _agency_dnc_path():
    from . import agencydnc
    return agencydnc.path()


def _suppress_template_path():
    from . import ingest
    return ingest.SUPPRESS


def _suppress_local_path():
    from . import ingest
    return ingest.SUPPRESS_LOCAL


AUTHORITIES = (
    {
        "name": "operator_exclusion_register",
        "resolver": _operator_exclusion_path,
        "holds": "every account and address the operator permanently excluded, "
                 "including this estate's own sending addresses",
        "absent_means": "no permanent exclusion can be ruled out for anybody",
    },
    {
        "name": "suppression_template",
        "resolver": _suppress_template_path,
        "holds": "the tracked never-sequence domain template",
        "absent_means": "the tracked half of the domain suppression list is "
                        "unread",
    },
    {
        "name": "suppression_local_roster",
        "resolver": _suppress_local_path,
        "holds": "the real customer never-sequence roster, gitignored",
        "absent_means": "the half of the suppression list that holds real "
                        "customers is unread, and `load_suppress` merges it "
                        "silently - an absent roster contributes nothing and "
                        "says nothing",
    },
    {
        "name": "agency_dnc",
        "resolver": _agency_dnc_path,
        "holds": "everybody who told Resonate directly not to contact them, "
                 "across every workspace",
        "absent_means": "`agencydnc.load` returns {} for a missing file, so "
                        "EVERY contact passes the agency do-not-contact check "
                        "and nothing reports that the list was never read",
    },
    {
        "name": "queue",
        "resolver": store.queue_path,
        "holds": "the records and contacts every person-level and "
                 "account-level rule reads",
        "absent_means": "`store.load()` returns 0 rows without raising, so "
                        "'this person has no history' and 'the history is not "
                        "here' are the same answer",
    },
)

AUTHORITY_NAMES = tuple(a["name"] for a in AUTHORITIES)


def authorities(resolvers=None):
    """Each authority's state, BY PATH. Resolved now, never cached.

    `resolvers` replaces the table's resolvers by name, which is how the
    controls plant a present-and-readable authority set and how one of them
    plants a reader that raises.

    UNREADABLE is a third state and not a flavour of ABSENT: a file that
    exists and cannot be opened is a different incident from one nobody has
    written, and a preflight that merged them would send somebody looking in
    the wrong place.
    """
    resolvers = resolvers or {}
    out = {}
    for entry in AUTHORITIES:
        name = entry["name"]
        resolver = resolvers.get(name, entry["resolver"])
        row = {"name": name, "holds": entry["holds"],
               "absent_means": entry["absent_means"]}
        try:
            path = resolver()
        except Exception as exc:                                # noqa: BLE001
            # A RESOLVER THAT RAISES IS UNREADABLE, NOT ABSENT. The path is
            # unknown, so there is nothing to report but the failure - and
            # reporting it as ABSENT would name no file at all.
            row.update({"path": None, "state": UNREADABLE,
                        "why": "the path could not be resolved: %s: %s"
                               % (type(exc).__name__, exc)})
            out[name] = row
            continue
        row["path"] = path
        try:
            if not os.path.exists(path):
                row.update({"state": ABSENT,
                            "why": "no file at %s" % (path,)})
            else:
                with open(path, "rb") as handle:
                    row["bytes"] = len(handle.read())
                row.update({"state": PRESENT,
                            "why": "%d bytes at %s" % (row["bytes"], path)})
        except OSError as exc:
            row.update({"state": UNREADABLE,
                        "why": "%s could not be read: %s: %s"
                               % (path, type(exc).__name__, exc)})
        out[name] = row
    return out


# -------------------------------------------------------------- the rules
#
# ONE ROW PER RULE THAT CAN EXCLUDE A CONTACT FROM A SEND.
#
# `decides` names the module and function that actually takes the decision,
# so a reader can go and look rather than trust this table. `channel` is
# which path consults it. `needs` is the authorities it reads, and
# `needs_record` / `needs_provider_read` are the two other ways a rule can be
# unanswerable.
#
# `ask` is the real decider, called with a context, returning a REASON STRING
# when the rule refuses and None when it does not. `None` for `ask` means the
# rule has no address-only form and is UNKNOWN by construction here - stated
# rather than omitted, because a rule left out of the table is a rule nobody
# notices is unasked.


def _ask_operator_excluded_address(ctx):
    from . import operatorexclusion
    email = (ctx.get("email") or "").strip().lower()
    if "@" not in email:
        return None
    if operatorexclusion.blocks_address(email):
        return "the operator permanently excluded this address"
    domain = email.rsplit("@", 1)[1]
    if operatorexclusion.blocks_domain(domain):
        return ("the operator permanently excluded %s or a parent of it"
                % (domain,))
    return None


def _ask_operator_excluded_company(ctx):
    from . import operatorexclusion
    domain = (ctx.get("domain") or "").strip().lower()
    if not domain:
        return None
    if operatorexclusion.blocks_domain(domain):
        return ("the operator permanently excluded the company domain %s or a "
                "parent of it" % (domain,))
    return None


def _ask_suppressed_domain(ctx):
    from . import ingest
    domain = (ctx.get("domain") or "").strip().lower()
    if not domain:
        return None
    if domain in ingest.load_suppress():
        return "%s is on the never-sequence domain list" % (domain,)
    return None


def _ask_agency_dnc(ctx):
    from . import agencydnc
    hit = agencydnc.lookup({"email": ctx.get("email"),
                            "linkedin": ctx.get("linkedin")})
    return hit or None


RULES = (
    # ---- answerable from an address and a tracked register
    {"name": "operator_exclusion_address",
     "decides": "operatorexclusion.blocks_address / blocks_domain, reached "
                "from eligibility._operator_excluded",
     "channel": "both",
     "needs": ("operator_exclusion_register",),
     "ask": _ask_operator_excluded_address,
     "about": "this person's own mailbox is at a permanently excluded "
              "address or domain - the check that caught our own 225 sending "
              "addresses passing as recipients"},
    {"name": "operator_exclusion_company",
     "decides": "operatorexclusion.blocks_domain, reached from "
                "eligibility._operator_excluded",
     "channel": "both",
     "needs": ("operator_exclusion_register",),
     "ask": _ask_operator_excluded_company,
     "about": "the company is permanently excluded"},
    {"name": "suppression_domain_list",
     "decides": "eligibility._suppressed via ingest.load_suppress",
     "channel": "both",
     # BOTH HALVES. `load_suppress` merges the tracked template with the
     # gitignored roster and reports neither, so a missing roster makes this
     # rule unanswerable even though the template is right there.
     "needs": ("suppression_template", "suppression_local_roster"),
     "ask": _ask_suppressed_domain,
     # `load_suppress` UNIONS the two files, so whichever half is on disk can
     # still fire - see the asymmetry note in `evaluate`.
     "fires_on_partial": True,
     "about": "the company is on the never-sequence domain list"},
    {"name": "agency_dnc",
     "decides": "agencydnc.lookup, reached from eligibility._suppressed",
     "channel": "both",
     "needs": ("agency_dnc",),
     "ask": _ask_agency_dnc,
     "about": "this person told Resonate directly not to contact them, in "
              "any workspace"},

    # ---- need the queue record, and say so
    {"name": "client_suppressed_drop",
     "decides": "eligibility._suppressed, the `drop_reason` branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "the client suppressed this record"},
    {"name": "client_own_domain",
     "decides": "eligibility._client_own_domain",
     "channel": "email", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "the address is at the client's own domain - their staff, "
              "never a prospect"},
    {"name": "record_state",
     "decides": "eligibility._record_state",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "dropped, or in an unshippable state. Whether `held` and "
              "`drafted` block a send is recorded as UNSETTLED in the "
              "approval sheet's own note, and enforced in code regardless"},
    {"name": "contact_flags",
     "decides": "eligibility._replied, the flag branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "unsubscribed, suppressed, stopped or paused on the contact"},
    {"name": "contact_reply_event",
     "decides": "eligibility._replied, the event branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "this person replied; their sequence is answered"},
    {"name": "account_suppressed",
     "decides": "eligibility._paused, the account suppression branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "the company asked not to be contacted"},
    {"name": "account_review_open",
     "decides": "eligibility._paused, the open-review branch",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "a human review is open on this account"},
    {"name": "account_paused",
     "decides": "eligibility._paused via cadence.pause_state",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "the account is paused by reply policy"},
    {"name": "account_reply_log",
     "decides": "suppression.decide step 2 via account.replies",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "a reply recorded against the contact but not flagged on it is "
              "still a reply"},
    {"name": "bounce_history",
     "decides": "channels._bounced, and bouncepolicy.decide for the "
                "hard/soft split",
     "channel": "email", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "this address has already bounced. Keyed to the CONTACT, not "
              "the account"},
    {"name": "mx_and_verification",
     "decides": "channels.email_verdict via mx.allows_email and the client's "
                "verification policy",
     "channel": "email", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "the address cannot receive mail, or is not verified to this "
              "client's policy. No email is generated for an unverified "
              "address"},
    {"name": "hygiene_workspace_history",
     "decides": "hygiene.check step 2 via hygiene.index",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "we have worked this person before, by strong identity"},
    {"name": "hygiene_account_history",
     "decides": "hygiene.check step 3",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "we have worked this company before"},
    {"name": "client_approval_register",
     "decides": "hygiene.check step 0 via clientapproval.is_suppressed",
     "channel": "both", "needs": ("queue",), "needs_record": True,
     "ask": None,
     "about": "the client removed this domain from a snapshot: permanent, "
              "per workspace, and no re-sourcing brings it back"},

    # ---- need a provider read this task may not make
    {"name": "hold_active_sequence",
     "decides": "suppression.decide, HOLD_ACTIVE_SEQUENCE",
     "channel": "both", "needs": (), "needs_provider_read": True,
     "ask": None,
     "about": "they are in an active sequence somewhere, on any channel, "
              "belonging to anyone"},
    {"name": "hold_recent_touch",
     "decides": "suppression.decide, HOLD_RECENT_TOUCH "
                "(hold_after_last_touch_days, default 30)",
     "channel": "both", "needs": (), "needs_provider_read": True,
     "ask": None,
     "about": "a last touch inside the window holds, whoever made it"},
    {"name": "hold_total_sends",
     "decides": "suppression.decide, HOLD_SEND_VOLUME "
                "(hold_above_total_sends, default 10)",
     "channel": "both", "needs": (), "needs_provider_read": True,
     "ask": None,
     "about": "more than the configured lifetime sends holds for manual "
              "review"},
    {"name": "cooling_90_days",
     "decides": "suppression.decide, `cooled` from thresholds()['cooling_days']",
     "channel": "both", "needs": (), "needs_provider_read": True,
     "ask": None,
     "about": "the operator-confirmed 90 days. It LIFTS the volume hold "
              "rather than imposing one, and it is computed from the same "
              "provider last-touch this file may not read"},
)

RULE_NAMES = tuple(r["name"] for r in RULES)


# ------------------------------------- rules expected and NOT found in code
#
# "A rule you cannot locate in code does not exist for this purpose. Say
# which ones you expected and did not find." - TASK-0170.
#
# These are DECLARED somewhere this project treats as authority and have no
# implementation on any path that could exclude a contact from a send. They
# are not in `RULES` because a row there implies something asks it; they are
# here because the gap is the finding.
#
# Each one is pinned by a test, in BOTH directions: if an implementation
# appears, the test fails and the entry has to be deleted rather than
# quietly outliving its own gap.

RULES_EXPECTED_BUT_NOT_FOUND = (
    {
        "name": "internal_campaign_membership",
        "declared_in": "CLAUDE.md standing rule 2 and docs/OPERATING-MODE.md: "
                       "\"anyone with a lead row in 327/328/352 is NOT CLEAN "
                       "for outreach, whoever owns them\", and UNKNOWN means "
                       "do-not-touch and members NOT CLEAN",
        "what_exists": "providerwrites carries the three-state classifier - "
                       "RESONATE_OS / RESONATE_INTERNAL / UNKNOWN_OWNER - and "
                       "it governs provider WRITES TO A CAMPAIGN",
        "what_is_missing": "nothing in eligibility, suppression, hygiene or "
                           "channels asks whether this CONTACT holds a lead "
                           "row in an internal or unknown-owner campaign. A "
                           "member of 327, 328 or 352 passes every rule in "
                           "RULES above",
        "would_need": "a provider read of each internal and unknown-owner "
                      "campaign's lead rows, then a rule on the enrol path",
    },
    {
        "name": "ninety_day_no_contact",
        "declared_in": "the operator's confirmed 90-day cooling rule, carried "
                       "in suppression.DEFAULTS as cooling_days: 90",
        "what_exists": "cooling_days=90 is real and is consulted - but it "
                       "LIFTS the volume hold, it does not impose a hold. The "
                       "recency hold is hold_after_last_touch_days, default "
                       "30",
        "what_is_missing": "no rule refuses a contact BECAUSE they were "
                           "contacted within 90 days. A contact touched 45 "
                           "days ago passes the recency hold and the cooling "
                           "window does not re-impose it",
        "would_need": "an operator decision on which of the two the 90 days "
                      "is, and then either a threshold change or a new rule. "
                      "It is a one-line config change if the answer is 90, "
                      "and this file must not guess",
    },
    {
        "name": "self_send_exclusion_as_its_own_rule",
        "declared_in": "the task's own list of rules to enumerate",
        "what_exists": "it IS implemented, in two places: the estate's own "
                       "225 sending addresses are entries in the operator "
                       "exclusion register, and eligibility._client_own_domain "
                       "refuses an address at the client's own domain",
        "what_is_missing": "nothing, but it is not where a reader would look "
                           "and it is not one rule. Named here so a future "
                           "audit does not conclude it is absent and add a "
                           "third implementation",
        "would_need": "nothing. This entry is a pointer, not a gap",
    },
)

EXPECTED_NOT_FOUND_NAMES = tuple(r["name"]
                                 for r in RULES_EXPECTED_BUT_NOT_FOUND)

def production_work():
    """Where production `work/` actually is, which is NOT this tree's.

    `store.PRODUCTION_WORK` resolves against the CALLING tree's root, so a
    preflight run from any worktree resolves the queue to that worktree's own
    empty `work/` - and `store.load()` answers 0 rows without raising. That
    is the same per-tree resolution that made six concurrent suite runs
    serialise nothing, and CLAUDE.md names the one path that is identical
    from the main checkout and from every worktree:
    `git rev-parse --path-format=absolute --git-common-dir`.

    Reported, never read. A RELATIVE answer from git is refused rather than
    resolved, because `abspath` would resolve it against the caller's cwd and
    reintroduce the per-tree path this function exists to escape.
    """
    import subprocess

    try:
        done = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except Exception as exc:                                    # noqa: BLE001
        return None, "git could not be asked: %s" % (type(exc).__name__,)
    out = (done.stdout or "").strip()
    if done.returncode != 0 or not out:
        return None, "git refused: %s" % ((done.stderr or "").strip()[:160],)
    if not os.path.isabs(out):
        return None, "git answered a relative path (%r); refusing to resolve "                     "it against this tree's cwd" % (out,)
    return os.path.join(os.path.dirname(out), "work"), "from --git-common-dir"


#: What would answer each unanswerable class, named once rather than per row.
WHAT_WOULD_ANSWER = {
    "queue": "a read of the canonical queue - `store.load()` against the "
             "production work/ directory, which this task's boundaries "
             "forbid",
    "provider_read": "one fully paginated EmailBison and HeyReach read of "
                     "every campaign's lead and send rows for these "
                     "addresses, which this task's boundaries forbid",
}


def evaluate(contact, state=None, channel="email"):
    """One contact's row: a cell per rule, plus whether they are cleared.

    THE ORDER IS THE POINT. The authority is checked before the rule, so a
    rule whose list is not on disk is UNKNOWN rather than silently clean -
    see this module's docstring for the `agencydnc` measurement that makes
    that necessary.
    """
    state = authorities() if state is None else state
    cells = {}
    for rule in RULES:
        if rule.get("channel") not in ("both", channel):
            cells[rule["name"]] = {
                "cell": PASS, "why": "not consulted on the %s path" % channel,
                "not_applicable": True}
            continue
        missing = [name for name in rule["needs"]
                   if state.get(name, {}).get("state") != PRESENT]
        if missing:
            why = "; ".join(
                "the %s authority is %s - %s"
                % (name, state.get(name, {}).get("state", "UNDECLARED"),
                   state.get(name, {}).get("why", "not in the table"))
                for name in missing)
            # AN EXCLUSION FOUND ON A PARTIAL READ IS STILL AN EXCLUSION, and
            # a rule that did NOT fire on one has still not been answered.
            #
            # `bounce_stop_7day` states the same asymmetry one layer down and
            # it is `senderheadroom`'s: a PASS needs a complete read and a
            # STOP does not. Here: the tracked suppression template is on
            # disk while the real customer roster is absent, so a domain
            # found on the template is excluded whatever the roster says,
            # and a domain absent from the template proves nothing.
            if rule.get("fires_on_partial") and rule.get("ask"):
                try:
                    reason = rule["ask"](contact)
                except Exception as exc:                        # noqa: BLE001
                    reason = None
                    why += ("; and the readable half raised %s: %s"
                            % (type(exc).__name__, str(exc)[:120]))
                else:
                    why += ("; the readable half WAS asked and did not fire, "
                            "which is not an answer about the missing half")
                if reason:
                    cells[rule["name"]] = {
                        "cell": EXCLUDED,
                        "why": "%s - found on the readable half, so the "
                               "missing one cannot change it" % reason}
                    continue
            cells[rule["name"]] = {"cell": UNKNOWN, "why": why}
            continue
        if rule.get("needs_provider_read"):
            cells[rule["name"]] = {
                "cell": UNKNOWN,
                "why": "needs a provider read: %s"
                       % WHAT_WOULD_ANSWER["provider_read"]}
            continue
        if rule.get("needs_record") and not contact.get("record"):
            cells[rule["name"]] = {
                "cell": UNKNOWN,
                "why": "needs this contact's queue record: %s"
                       % WHAT_WOULD_ANSWER["queue"]}
            continue
        ask = rule.get("ask")
        if ask is None:
            # DECLARED UNANSWERABLE, which is not the same as unasked. A rule
            # with no address-only form and all its authorities present still
            # has nothing to go on here, and saying so by name is the whole
            # value of the row.
            cells[rule["name"]] = {
                "cell": UNKNOWN,
                "why": "this rule has no form that can be evaluated without "
                       "a record or a provider read"}
            continue
        try:
            reason = ask(contact)
        except Exception as exc:                                # noqa: BLE001
            # A RULE THAT RAISED DID NOT PASS. Broad because one rule's
            # failure must not stop the other twenty being asked, and safe
            # because the direction is UNKNOWN - which clears nobody.
            cells[rule["name"]] = {
                "cell": UNKNOWN,
                "why": "the rule raised %s: %s"
                       % (type(exc).__name__, str(exc)[:200])}
            continue
        if reason:
            cells[rule["name"]] = {"cell": EXCLUDED, "why": reason}
        else:
            cells[rule["name"]] = {"cell": PASS, "why": "asked, did not fire"}

    excluded = sorted(n for n, c in cells.items() if c["cell"] == EXCLUDED)
    unknown = sorted(n for n, c in cells.items() if c["cell"] == UNKNOWN)
    return {
        "key": contact.get("key"),
        "name": contact.get("name"),
        "company": contact.get("company"),
        "email": contact.get("email"),
        "domain": contact.get("domain"),
        "channel": channel,
        "cells": cells,
        "excluded_by": excluded,
        "unknown_on": unknown,
        # CLEARED NEEDS EVERY CELL. Not "no exclusion found" - an exclusion
        # not found by a rule that never ran is not an absence of exclusions.
        "cleared": not excluded and not unknown,
        "verdict": (EXCLUDED if excluded else
                    UNKNOWN if unknown else PASS),
    }


def assess(contacts, state=None, channel="email", control_rows=None):
    """The whole table, the three totals and one verdict.

    THE THIRD TOTAL IS THE ONE THAT MATTERS: not-cleared-because-UNKNOWN. It
    is the number most likely to read zero because the instrument cannot see,
    so it is computed from the rows rather than from an absence of problems.
    """
    state = authorities() if state is None else state
    control_rows = list(control_rows or [])
    rows = [evaluate(c, state=state, channel=channel) for c in contacts or []]
    cleared = [r for r in rows if r["cleared"]]
    excluded = [r for r in rows if r["excluded_by"]]
    unknown = [r for r in rows if not r["excluded_by"] and r["unknown_on"]]
    bad_controls = [c for c in control_rows if not c.get("ok")]

    # ORDER: a broken instrument outranks a finding, because a table whose
    # controls did not hold does not support either answer.
    if bad_controls:
        verdict, code = UNKNOWN, EXIT_UNKNOWN
    elif excluded:
        verdict, code = EXCLUDED, EXIT_EXCLUDED
    elif unknown:
        verdict, code = UNKNOWN, EXIT_UNKNOWN
    elif rows:
        verdict, code = PASS, EXIT_CLEARED
    else:
        # NO CONTACT IS NOT A CLEAN COHORT. An empty table is an instrument
        # that was handed nothing, and reporting it as cleared is the exact
        # shape of every defect this lane has been fixing.
        verdict, code = UNKNOWN, EXIT_UNKNOWN

    out = {
        "rows": rows,
        "authorities": state,
        "controls": control_rows,
        "controls_ok": not bad_controls,
        "channel": channel,
        "totals": {"contacts": len(rows), "cleared": len(cleared),
                   "excluded": len(excluded),
                   "not_cleared_because_unknown": len(unknown)},
        "verdict": verdict,
        "exit_code": code,
    }
    out["sentence"] = sentence(out)
    return out


def sentence(assessment):
    """The one line at the top of the report. Never a tick.

    It says cleared-or-not FIRST and why, because a reader who stops after
    one sentence must not stop on a number that looks like a pass.
    """
    totals = assessment["totals"]
    if assessment["verdict"] == PASS:
        return ("CANARY-01 IS CLEARED TO SEND on the %s path: all %d contact(s) "
                "passed every rule, every authority was readable and every "
                "control held."
                % (assessment["channel"], totals["cleared"]))
    parts = []
    if totals["excluded"]:
        parts.append("%d EXCLUDED by a rule that fired" % totals["excluded"])
    if totals["not_cleared_because_unknown"]:
        parts.append("%d NOT CLEARED because at least one rule could not be "
                     "asked at all" % totals["not_cleared_because_unknown"])
    if not assessment["controls_ok"]:
        parts.append("the controls did not hold, so this table proves nothing")
    if not totals["contacts"]:
        parts.append("no contact was assessed, which is not a clean cohort")
    return ("CANARY-01 IS NOT CLEARED TO SEND on the %s path: %d cleared of "
            "%d; %s. UNKNOWN is not a pass."
            % (assessment["channel"], totals["cleared"], totals["contacts"],
               "; ".join(parts)))


# ------------------------------------------------------------- the controls
#
# Three, every run. Without the third the table could be all-EXCLUDED and
# still look rigorous; without the second it is the B7 instrument - clean
# because it never managed to ask anything.
#
# SYNTHETIC ADDRESSES ONLY. Reserved domains, planted into temporary
# authority files, so a control never touches a real roster and a real
# address never enters this module's own data.

_CONTROL_SUPPRESSED = "blocked-control@example.test"
_CONTROL_CLEAN = "clean-control@example.invalid"


def _planted_state(tmpdir, raising=()):
    """Every authority PRESENT in a temporary directory.

    `raising` names authorities whose resolver raises instead, which is how
    control 2 plants a store read that cannot be done.
    """
    resolvers = {}
    for entry in AUTHORITIES:
        name = entry["name"]
        if name in raising:
            def _boom(_name=name):
                raise OSError("planted control: %s cannot be read" % _name)
            resolvers[name] = _boom
            continue
        path = os.path.join(tmpdir, name + ".planted")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("# planted by preflight.controls\n")
        resolvers[name] = (lambda _p=path: _p)
    return authorities(resolvers=resolvers)


def controls():
    """The three, as rows. `ok` is False the moment one disagrees."""
    import tempfile
    import shutil

    from . import agencydnc, operatorexclusion

    out = []
    tmp = tempfile.mkdtemp(prefix="rga-preflight-control-")
    try:
        # 1. A PLANTED SUPPRESSED ADDRESS SHOWS EXCLUDED WITH ITS REASON.
        #
        # Planted into a real agency-DNC file through `agencydnc.add`, so the
        # control exercises the real fingerprinting and the real lookup
        # rather than a stub that would agree with anything.
        dnc = os.path.join(tmp, "agency-dnc.jsonl")
        try:
            agencydnc.add("email", _CONTROL_SUPPRESSED, file_path=dnc)
            state = _planted_state(tmp)
            state["agency_dnc"] = authorities(
                resolvers={"agency_dnc": lambda: dnc})["agency_dnc"]
            with _using(agencydnc, "path", lambda: dnc):
                row = evaluate({"key": "control-1",
                                "email": _CONTROL_SUPPRESSED,
                                "domain": "example.test"}, state=state)
            cell = row["cells"]["agency_dnc"]
            observed = [cell["cell"], bool(cell["why"])]
        except Exception as exc:                                # noqa: BLE001
            observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc)]
        out.append({
            "control": "a planted suppressed address shows EXCLUDED with its "
                       "reason",
            "planted": "%s added to a temporary agency-DNC file through "
                       "agencydnc.add" % _CONTROL_SUPPRESSED,
            "expected": [EXCLUDED, True],
            "observed": observed,
            "ok": observed == [EXCLUDED, True]})

        # 2. A PLANTED CONTACT WHOSE STORE READ RAISES SHOWS UNKNOWN, AND THE
        #    RUN EXITS NON-ZERO.
        try:
            state = _planted_state(tmp, raising=("queue",))
            row = evaluate({"key": "control-2", "email": _CONTROL_CLEAN,
                            "domain": "example.invalid",
                            "record": {"id": "r"}}, state=state)
            whole = assess([{"key": "control-2", "email": _CONTROL_CLEAN,
                             "domain": "example.invalid",
                             "record": {"id": "r"}}], state=state)
            # THE AUTHORITY'S OWN STATE IS IN THE OBSERVATION, not only
            # the cell. Without it this control passed with the gate
            # deliberately blinded to PRESENT, because `record_state` has no
            # address-only form and came out UNKNOWN for a different reason -
            # a different guard firing first, which is the trap CLAUDE.md
            # names. Measured while writing TASK-0170's test file.
            observed = [state["queue"]["state"],
                        row["cells"]["record_state"]["cell"],
                        whole["exit_code"]]
        except Exception as exc:                                # noqa: BLE001
            observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc), None]
        out.append({
            "control": "a planted contact whose store read raises shows "
                       "UNKNOWN and the run exits non-zero",
            "planted": "the queue authority's resolver raising OSError",
            "expected": [UNREADABLE, UNKNOWN, EXIT_UNKNOWN],
            "observed": observed,
            "ok": observed == [UNREADABLE, UNKNOWN, EXIT_UNKNOWN]
                  and observed[-1] != 0})

        # 3. A PLANTED CLEAN CONTACT SHOWS PASS.
        #
        # The one the other two cannot stand in for: without it an instrument
        # that answered EXCLUDED or UNKNOWN to everything would pass both.
        try:
            empty_dnc = os.path.join(tmp, "empty-dnc.jsonl")
            with open(empty_dnc, "w", encoding="utf-8", newline="\n") as h:
                h.write("")
            excl = os.path.join(tmp, "empty-exclusions.jsonl")
            with open(excl, "w", encoding="utf-8", newline="\n") as h:
                h.write("")
            supp = os.path.join(tmp, "empty-suppress.txt")
            with open(supp, "w", encoding="utf-8", newline="\n") as h:
                h.write("")
            state = _planted_state(tmp)
            for name, path in (("agency_dnc", empty_dnc),
                               ("operator_exclusion_register", excl),
                               ("suppression_template", supp),
                               ("suppression_local_roster", supp)):
                state[name] = authorities(
                    resolvers={name: (lambda _p=path: _p)})[name]
            operatorexclusion.forget()
            with _using(agencydnc, "path", lambda: empty_dnc), \
                    _using(operatorexclusion, "path", lambda: excl), \
                    _suppress_paths(supp, supp):
                row = evaluate({"key": "control-3", "email": _CONTROL_CLEAN,
                                "domain": "example.invalid"}, state=state)
            answerable = [name for name in ("operator_exclusion_address",
                                            "operator_exclusion_company",
                                            "suppression_domain_list",
                                            "agency_dnc")]
            observed = [row["cells"][n]["cell"] for n in answerable]
        except Exception as exc:                                # noqa: BLE001
            observed = ["RAISED", "%s: %s" % (type(exc).__name__, exc)]
        finally:
            operatorexclusion.forget()
        out.append({
            "control": "a planted clean contact shows PASS on every rule that "
                       "can be asked",
            "planted": "%s against present, empty, readable authority files"
                       % _CONTROL_CLEAN,
            "expected": [PASS, PASS, PASS, PASS],
            "observed": observed,
            "ok": observed == [PASS, PASS, PASS, PASS]})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for row in out:
        row["ok"] = bool(row["ok"])
    return out


class _using:
    """Swap one module attribute for the duration of a block.

    Local rather than `unittest.mock`, because this runs in production code
    and `mock` is a test dependency. Restores the original even on a raise.
    """

    def __init__(self, module, name, value):
        self.module, self.name, self.value = module, name, value

    def __enter__(self):
        self.previous = getattr(self.module, self.name)
        setattr(self.module, self.name, self.value)
        return self

    def __exit__(self, *exc):
        setattr(self.module, self.name, self.previous)
        return False


class _suppress_paths:
    """`ingest.SUPPRESS` and `SUPPRESS_LOCAL` pointed at planted files."""

    def __init__(self, template, local):
        self.template, self.local = template, local

    def __enter__(self):
        from . import ingest
        self.ingest = ingest
        self.previous = (ingest.SUPPRESS, ingest.SUPPRESS_LOCAL)
        ingest.SUPPRESS, ingest.SUPPRESS_LOCAL = self.template, self.local
        return self

    def __exit__(self, *exc):
        self.ingest.SUPPRESS, self.ingest.SUPPRESS_LOCAL = self.previous
        return False
