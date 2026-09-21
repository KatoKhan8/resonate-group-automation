#!/usr/bin/env python3
"""Workspaces, users, granular permissions and the audit log.

## What a workspace is

A **hard tenancy boundary**, not a filter. A workspace owns its batches,
companies, contacts, campaigns, approvals, replies, jobs, events and provider
mappings, and nothing but a deliberate super-admin action crosses one.

A workspace is identified by a slug that is also the name of its client config,
so everything a workspace configures independently - ICP rules, personas,
geographies, timezone policy, the verification waterfall, MX policy, research
policy, campaign defaults, provider mappings, Slack routing, approval policy,
daily volume - is already a per-client YAML file and needed no new mechanism.
That is the whole reason this maps onto `config/clients/<slug>.yaml` rather
than inventing a parallel settings store: one place per tenant, already
loaded by `clients.load`, already used by every domain function.

## Roles and permissions

`src/roles.py` holds the *campaign* permission table and keeps doing so - it is
what `orchestrator.decide` asks, and splitting that in two would be exactly the
"second copy of a rule" this codebase keeps refusing. What this module adds is
the layer above it: who is in which workspace, with which role, and which
granular permissions that role carries.

The rule that matters: **a permission is checked at the service boundary, never
in a page.** `require(membership, PERMISSION)` is called by the repo and the
API, so a handler that forgets to check still cannot read another workspace's
rows - there is no unscoped call to reach for.

## Where this is stored

`work/workspaces.jsonl`, through `store`'s own jsonl helpers and lock, like
every other piece of state. Users are a local table with no passwords: this
build has no authentication, and inventing password storage would be a new
place for a secret to live. `WEB-APP.md` describes what replaces it.
"""
import argparse
import json
import os
import re

from . import clients, store

# ------------------------------------------------------------------- roles

SUPER_ADMIN = "super_admin"
WORKSPACE_ADMIN = "workspace_admin"
OPERATOR = "operator"
REVIEWER = "reviewer"
VIEWER = "viewer"

ROLES = (SUPER_ADMIN, WORKSPACE_ADMIN, OPERATOR, REVIEWER, VIEWER)

# ------------------------------------------------------------- permissions
#
# Named for the action rather than the screen, so a new page cannot invent a
# new permission by accident.

WORKSPACE_VIEW = "workspace.view"
WORKSPACE_MANAGE = "workspace.manage"
USERS_MANAGE = "users.manage"

BATCH_CREATE = "batch.create"
BATCH_RUN = "batch.run"

CAMPAIGN_CREATE = "campaign.create"
CAMPAIGN_EDIT = "campaign.edit"
CAMPAIGN_APPROVE = "campaign.approve"
CAMPAIGN_LAUNCH = "campaign.launch"
CAMPAIGN_PAUSE = "campaign.pause"

CONTACTS_VIEW = "contacts.view"
CONTACTS_EXPORT = "contacts.export"

# Writing down something observed about an account. Separate from viewing
# one because it changes what the estate is prioritised on: a signal is not
# a note, it moves an account up somebody's list.
SIGNALS_RECORD = "signals.record"

APPROVALS_REVIEW = "approvals.review"

REPLIES_VIEW = "replies.view"
REPLIES_MANAGE = "replies.manage"

REPORTING_VIEW = "reporting.view"
REPORTING_EXPORT = "reporting.export"

PROVIDER_SETTINGS_VIEW = "provider_settings.view"
PROVIDER_SETTINGS_MANAGE = "provider_settings.manage"

# Operational detail a client-facing viewer must never see: diagnostics, raw
# provider payloads, QA internals, security events.
OPERATIONS_VIEW = "operations.view"

PERMISSIONS = (
    WORKSPACE_VIEW, WORKSPACE_MANAGE, USERS_MANAGE,
    BATCH_CREATE, BATCH_RUN,
    CAMPAIGN_CREATE, CAMPAIGN_EDIT, CAMPAIGN_APPROVE, CAMPAIGN_LAUNCH,
    CAMPAIGN_PAUSE,
    CONTACTS_VIEW, CONTACTS_EXPORT,
    SIGNALS_RECORD,
    APPROVALS_REVIEW,
    REPLIES_VIEW, REPLIES_MANAGE,
    REPORTING_VIEW, REPORTING_EXPORT,
    PROVIDER_SETTINGS_VIEW, PROVIDER_SETTINGS_MANAGE,
    OPERATIONS_VIEW,
)

# A viewer is a *client-facing* role. It sees business outcomes and none of the
# machinery: no diagnostics, no raw payloads, no provider settings, no export
# of contact-level data.
_VIEWER = {WORKSPACE_VIEW, REPORTING_VIEW}

_REVIEWER = _VIEWER | {
    CONTACTS_VIEW, APPROVALS_REVIEW, CAMPAIGN_APPROVE, CAMPAIGN_PAUSE,
    REPLIES_VIEW, OPERATIONS_VIEW,
}

_OPERATOR = _REVIEWER | {
    BATCH_CREATE, BATCH_RUN, CAMPAIGN_CREATE, CAMPAIGN_EDIT,
    CONTACTS_EXPORT, REPLIES_MANAGE, REPORTING_EXPORT,
    PROVIDER_SETTINGS_VIEW,
    # A reviewer reads the estate; an operator changes what it is worked
    # in. Recording a signal is the second of those.
    SIGNALS_RECORD,
}

# An operator runs the machine. A workspace admin also decides who else may,
# and may repoint a provider mapping - which is the pair of powers worth
# keeping apart from the person doing the daily work.
_WORKSPACE_ADMIN = _OPERATOR | {
    WORKSPACE_MANAGE, USERS_MANAGE, PROVIDER_SETTINGS_MANAGE,
}

# Launch is nobody's by default. It is granted deliberately, and in this build
# it is refused at a lower level anyway: `push.run(live=True)` raises.
GRANTS = {
    SUPER_ADMIN: set(PERMISSIONS),
    WORKSPACE_ADMIN: set(_WORKSPACE_ADMIN),
    OPERATOR: set(_OPERATOR),
    REVIEWER: set(_REVIEWER),
    VIEWER: set(_VIEWER),
}


class NotPermitted(PermissionError):
    """The membership does not carry this permission. Nothing happened."""


class NotAMember(PermissionError):
    """This user is not in that workspace.

    Deliberately the same shape as "no such workspace" to a caller: telling
    somebody that a workspace exists but is not theirs is itself a disclosure.
    """


def may(role, permission):
    if permission not in PERMISSIONS:
        raise ValueError(f"unknown permission: {permission}")
    return permission in GRANTS.get(role, set())


def permissions_of(role):
    return sorted(GRANTS.get(role, set()))


# -------------------------------------------------------------- the store

def path():
    return os.path.abspath(os.environ.get("WORKSPACES")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "workspaces.jsonl"))


def load():
    return store.read_jsonl(path())


def save(rows, timeout=None):
    with store.lock(timeout, for_path=path()):
        store.write_jsonl(path(), rows)


def transaction(timeout=None):
    return store.file_transaction(path(), timeout)


def new_workspace(slug, name, client=None, created_by="system"):
    """A workspace. Its `client` is the config file that configures it."""
    return {
        "kind": "workspace",
        "slug": slug,
        "name": name,
        # The client config that carries this workspace's ICP rules, personas,
        # verification policy, MX policy, provider mapping and the rest.
        "client": client or slug,
        "created_at": store.now(),
        "created_by": created_by,
        "settings": {},
    }


def new_user(email, name, super_admin=False):
    return {
        "kind": "user",
        "email": str(email).strip().lower(),
        "name": name,
        "super_admin": bool(super_admin),
        "created_at": store.now(),
    }


def new_membership(email, workspace, role):
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    return {
        "kind": "membership",
        "email": str(email).strip().lower(),
        "workspace": workspace,
        "role": role,
        "created_at": store.now(),
    }


def _rows(kind, rows=None):
    return [r for r in (load() if rows is None else rows)
            if r.get("kind") == kind]


def workspaces(rows=None):
    return sorted(_rows("workspace", rows), key=lambda w: w.get("slug") or "")


def workspace(slug, rows=None):
    for row in workspaces(rows):
        if row.get("slug") == slug:
            return row
    return None


def users(rows=None):
    return sorted(_rows("user", rows), key=lambda u: u.get("email") or "")


def user(email, rows=None):
    email = str(email or "").strip().lower()
    for row in users(rows):
        if row.get("email") == email:
            return row
    return None


def memberships(email=None, workspace_slug=None, rows=None):
    email = str(email or "").strip().lower() or None
    out = _rows("membership", rows)
    if email:
        out = [m for m in out if m.get("email") == email]
    if workspace_slug:
        out = [m for m in out if m.get("workspace") == workspace_slug]
    return out


def workspaces_for(email, rows=None):
    """Every workspace this user may enter. A super admin may enter all."""
    rows = load() if rows is None else rows
    person = user(email, rows)
    if person and person.get("super_admin"):
        return workspaces(rows)
    mine = {m["workspace"] for m in memberships(email, rows=rows)}
    return [w for w in workspaces(rows) if w.get("slug") in mine]


def membership_of(email, workspace_slug, rows=None):
    """The membership that authorises this user here, or None.

    A super admin gets a synthetic SUPER_ADMIN membership for any workspace
    that exists. That is the one deliberate way across the boundary, and it is
    named `super_admin` in the audit log every time it is used.
    """
    rows = load() if rows is None else rows
    if workspace(workspace_slug, rows) is None:
        return None
    person = user(email, rows)
    if person and person.get("super_admin"):
        return {"kind": "membership", "email": person["email"],
                "workspace": workspace_slug, "role": SUPER_ADMIN,
                "via": "super_admin"}
    for entry in memberships(email, workspace_slug, rows):
        return dict(entry, via="membership")
    return None


def require_member(email, workspace_slug, rows=None):
    found = membership_of(email, workspace_slug, rows)
    if found is None:
        raise NotAMember(f"no such workspace: {workspace_slug}")
    return found


def require(membership, permission):
    role = (membership or {}).get("role")
    if not role or not may(role, permission):
        raise NotPermitted(
            f"role {role!r} does not carry {permission!r}")
    return True


# ---------------------------------------------------------- the audit log

# ------------------------------------------------------ workspace policy
#
# A workspace's rules live in its client config - a hand-written YAML file with
# comments in it, read by `src/clients.py`. That file is not something a web
# form may rewrite: `clients.py` says why in its own docstring, and the reason
# is that "a misparsed persona cap is a spend, and a misparsed geo is a live
# customer getting cold sequenced". A serialiser that round-trips it would put
# every client's targeting one formatting bug away from being wrong.
#
# So the config stays the baseline, and what a workspace admin changes is an
# *override* stored here, in a file this system already owns and writes
# through `store`. `Repo.config()` merges the two. The client file remains
# readable, diffable and hand-editable; the overrides are audited with a
# before and an after.
#
# ## What may be overridden, and what may not
#
# The allowlist below is the whole surface. A key outside it is refused rather
# than ignored, because a caller who set something and got a 200 has learned
# something false about this system.
#
# Three things are deliberately absent, and each is absent for a reason that
# outranks the convenience of having them here:
#
# **Double verification cannot be turned off.** `required_confirmations` has a
# floor of 2. VERIFICATION.md and PLAYBOOK make two independent confirmations a
# property of the build, not a setting, and a browser form is not where that
# gets renegotiated.
#
# **MX filtering cannot be disabled.** The unknown-provider policy may be moved
# either way - that is a real judgement call about a gateway nobody recognises
# - but switching the filter off entirely is how a Proofpoint tenant gets cold
# emailed, and it is not one click away.
#
# **`allow_review_enrichment` is not here.** It is the flag that lets a company
# which did not qualify on evidence be enriched anyway. /icp says in words that
# widening it is a change to the client config rather than a click on a page,
# and putting it on a form would make that sentence false.

POLICY_KEYS = {
    # The workspace half of the kill switch. Absence means off, which is
    # what `killswitch.workspace_state` asserts: a workspace created for a
    # demo, where nobody remembers whether the switch was set, must not
    # send. It is a real setting with an audit entry rather than a
    # constant, because "who turned this on, and when" is the first
    # question after an incident.
    #
    # Setting it to `on` sends nothing on its own. The global layer refuses
    # in code and outranks it.
    "sending.live": {
        "label": "Live sending for this workspace",
        "kind": "choice", "choices": ("off", "on"),
        "why": "whether this workspace may send once the build can send at "
               "all. NOTHING ENFORCES THIS YET: the only reader is "
               "`killswitch.workspace_state`, and `killswitch` has no "
               "importer outside its own tests, so setting it off stops "
               "nothing. It is safe today only because the build refuses "
               "to send at all, in code. Wire it into `eligibility` before "
               "that refusal is ever lifted - see PRODUCT-GAPS.md",
    },
    # ---- The ICP. Editable here because a workspace that cannot state who
    # it sells to from the product is a workspace whose first batch is
    # blocked on somebody editing a YAML file, and because the readiness
    # checklist already points at this screen for it.
    #
    # Every one of these *narrows*. `must` is the sentence the ICP scorer
    # reads, the geo lists exclude, and the minimum excludes. None of them
    # can widen who is contactable: verification, suppression, hygiene and
    # approval are all downstream of qualification and none of them is here.
    "market.must": {
        "label": "What this client sells to",
        "kind": "text", "max_length": 200,
        "why": "the sentence qualification is scored against - "
               '"services business that tracks time". Blank means the '
               "market rule is unstated, which the readiness list reports "
               "as missing rather than as everybody",
    },
    "market.size_min_employees": {
        "label": "Minimum employees",
        "kind": "int", "min": 0, "max": 100000,
        "why": "companies smaller than this are not a fit for this client",
    },
    "market.geos": {
        "label": "Markets",
        "kind": "list", "max_items": 40, "max_length": 60,
        "why": "the places this client sells into. A company outside them "
               "is flagged, and whether a flag drops the record is the "
               "next setting. Blank means no geographic rule at all",
    },
    "market.exclude_geos": {
        "label": "Excluded markets",
        "kind": "list", "max_items": 40, "max_length": 60,
        "why": "places this client will not sell into, whatever else "
               "matches",
    },
    # ---- Who at a qualified company gets approached, and how many of them.
    #
    # This one changes who is *selected*, which is more than the rest of
    # this list does, so it is worth being explicit about what still holds
    # after it: a company reaches persona selection only with an ICP
    # verdict, `cap_per_domain` bounds the fan-out at each one, and
    # verification, MX, hygiene, suppression, fatigue and approval are all
    # downstream and untouched. Selecting somebody is not contacting them.
    #
    # An override replaces the client file's personas rather than merging
    # with them, the way every other override on this list replaces the
    # value it names. Half a persona from a form and half from a file is a
    # targeting rule nobody could read in one place.
    "personas": {
        "label": "Personas",
        "kind": "personas",
        "why": "who counts as a decision maker here, how many of each at "
               "one company, and the angles their messages may take. Edited "
               "on its own screen because a persona is four fields rather "
               "than one",
    },
    "market.flag_dont_drop": {
        "label": "An out-of-market company is",
        "kind": "bool", "choices": ("flagged", "dropped"),
        "why": "flagged is the cautious answer: a person decides, and a "
               "wrong geo reading costs a review rather than a company",
    },
    "dm_plan.max_batch_credits": {
        "label": "Batch credit cap",
        "kind": "int", "min": 0, "max": 1000000, "blank_is_none": True,
        "why": "the hard ceiling on what one batch may spend; blank means the "
               "only limit is the per-tier caps, which is a decision rather "
               "than a default",
    },
    "sending.daily_email_volume": {
        "label": "Daily email volume",
        "kind": "int", "min": 0, "max": 500,
        "why": "how many emails a day this workspace will send once sending "
               "is enabled",
    },
    "sending.daily_linkedin_volume": {
        "label": "Daily LinkedIn volume",
        "kind": "int", "min": 0, "max": 200,
        "why": "how many LinkedIn activities a day, once sending is enabled",
    },
    "verification.required_confirmations": {
        "label": "Required confirmations",
        "kind": "int", "min": 2, "max": 3,
        "why": "how many independent verifiers must agree before an address "
               "may be written to. The floor of 2 is a property of this "
               "build, not a setting",
    },
    "email_security.mx_filter.unknown_provider_policy": {
        "label": "Unknown email-security provider",
        "kind": "choice", "choices": ("allow", "block"),
        "why": "what to do with a gateway nobody recognises. Blocking is the "
               "cautious answer and costs reach; allowing is the reachable "
               "answer and costs certainty",
    },
    "slack.approvals_channel": {
        "label": "Approvals channel",
        "kind": "text", "max_length": 80,
        "why": "where an approval request would be posted. Nothing is posted "
               "in this build",
    },

    # ---- Slack routing for this workspace's own channel.
    #
    # The channel lives here rather than in the client config for one reason:
    # it is *per workspace*, and a workspace is the tenancy boundary. Putting
    # it in a shared client file would make "which channel does Productive
    # post to" a question with two possible answers, and the wrong answer
    # sends one client's prospect into another client's room.
    #
    # There is deliberately no default and no inference from the workspace
    # name. A workspace with nothing configured here has no channel, and
    # `notify.destination_for` records that as `unconfigured` rather than
    # falling back to anybody else's.
    "slack.workspace_channel": {
        "label": "Workspace Slack channel",
        "kind": "text", "max_length": 80,
        "why": "where this workspace's positive replies are announced. Blank "
               "means none, and none never means somebody else's",
    },
    # ---- The Slack AGENT's binding for this workspace.
    #
    # DELIBERATELY NOT `slack.workspace_channel`. That key says where this
    # workspace's notifications are POSTED; this one says where a
    # conversational agent may ANSWER about this workspace, and they are two
    # different decisions. A channel can be a good place to receive a
    # positive-reply alert without being a room where somebody may ask the
    # agent anything they like about the client and get an answer.
    #
    # No default and no inference, for the same reason as the channel above:
    # an unbound channel gets generic answers and no client data at all, and
    # "unbound" must never resolve to somebody else's workspace.
    "slack.agent_channel": {
        "label": "Agent channel",
        "kind": "text", "max_length": 80,
        "why": "the channel where the Slack agent answers AS this client. "
               "Blank means the agent answers nothing about this workspace "
               "in any channel, which is the safe default",
    },
    "slack.workspace_users": {
        "label": "Client Slack users",
        "kind": "list", "max_items": 100, "max_length": 20,
        "why": "Slack user ids that are this CLIENT's people. A DM from one "
               "of them is scoped to this workspace. A user listed under two "
               "workspaces is scoped to neither",
    },
    "slack.internal_users": {
        "label": "Resonate Slack users",
        "kind": "list", "max_items": 100, "max_length": 20,
        "why": "Slack user ids on the Resonate team. A DM from one of them "
               "gets internal detail. Everybody else gets client scope or "
               "nothing",
    },
    "slack.notify_positive_replies": {
        "label": "Announce positive replies",
        "kind": "choice", "choices": ("on", "off"),
        "why": "the reason the channel exists. On unless somebody turns it "
               "off",
    },
    "slack.notify_neutral_replies": {
        "label": "Announce neutral replies",
        "kind": "choice", "choices": ("on", "off"),
        "why": "off by default: a neutral reply belongs in the Reply Center "
               "where somebody is already looking, not in an interruption",
    },
    "slack.notify_negative_replies": {
        "label": "Announce negative replies",
        "kind": "choice", "choices": ("on", "off"),
        "why": "off by default, for the same reason as neutral",
    },
    "slack.notify_campaign_milestones": {
        "label": "Announce campaign milestones",
        "kind": "choice", "choices": ("on", "off"),
        "why": "off by default. Campaign operations are Resonate's business "
               "and belong in the global operations channel",
    },
    "slack.notify_reports": {
        "label": "Announce new reports",
        "kind": "choice", "choices": ("on", "off"),
        "why": "off by default. Announces that a report exists; it never "
               "attaches one",
    },
    # ------------------------------------------------- account-aware messaging
    #
    # Whether a message may refer to outreach that has already happened. The
    # labels here are what an operator reads; the keys are what the resolver
    # checks. Nobody configuring a campaign should have to know the word
    # "claim" or the string `outreach.claim_other_dm`.
    #
    # Everything naming a *third party* is off by default. A prospect hearing
    # that we have also been working their CFO has learned how they are being
    # sold to rather than anything about their own problem.
    "outreach.claim_same_contact": {
        "label": "May mention our own earlier message to this person",
        "kind": "choice", "choices": ("on", "off"),
        "why": "on by default. Needs a confirmed touch from the same sender "
               "to the same person; a planned one will not do",
    },
    "outreach.claim_colleague": {
        "label": "May mention a colleague's earlier message to this person",
        "kind": "choice", "choices": ("on", "off"),
        "why": "on by default. Names the colleague whose touch is the "
               "evidence, never a different one",
    },
    "outreach.claim_other_dm": {
        "label": "May mention that we contacted somebody else at the company",
        "kind": "choice", "choices": ("on", "off"),
        "why": "off by default. Being told their colleague was approached "
               "teaches a prospect how they are being sold to",
    },
    "outreach.claim_other_dm_colleague": {
        "label": "May mention a colleague contacting somebody else there",
        "kind": "choice", "choices": ("on", "off"),
        "why": "off by default, for the same reason and one degree further "
               "removed",
    },
    "outreach.claim_other_dm_reply": {
        "label": "May mention that somebody else at the company replied",
        "kind": "choice", "choices": ("on", "off"),
        "why": "off by default. Repeating one person's reply to another is "
               "a disclosure they did not agree to",
    },
    "outreach.claim_referral": {
        "label": "May say who suggested the introduction",
        "kind": "choice", "choices": ("on", "off"),
        "why": "on by default, and only where a referral was recorded with "
               "both people named. Never read out of reply text",
    },
    "outreach.claim_conversation": {
        "label": "May describe an ongoing conversation with a colleague",
        "kind": "choice", "choices": ("on", "off"),
        "why": "off by default. Needs a reply AND an answer to it - a sent "
               "message is not a conversation, and the prospect can check",
    },

    # ------------------------------------------------------------- reply policy
    #
    # What a reply from one decision maker does to the others. Defaults lean
    # towards holding: a hold somebody lifts costs a day, and a message sent
    # into a conversation that had already started cannot be recalled.
    "reply.on_positive": {
        "label": "When somebody replies positively",
        "kind": "choice", "choices": ("continue", "hold", "stop", "review"),
        "why": "holds the whole account by default. Cold-approaching three "
               "colleagues while a conversation is starting reads as one "
               "agency that does not talk to itself",
    },
    "reply.on_negative": {
        "label": "When somebody says they are not interested",
        "kind": "choice", "choices": ("continue", "hold", "stop", "review"),
        "why": "affects that person only by default. One person declining "
               "is not the company declining",
    },
    "reply.on_unsubscribe": {
        "label": "When somebody asks to be removed",
        "kind": "choice", "choices": ("stop", "hold", "review"),
        "why": "stops that person, permanently and immediately",
    },
    "reply.on_account_dnc": {
        "label": "When somebody asks us to stop contacting the company",
        "kind": "choice", "choices": ("stop", "hold", "review"),
        "why": "stops everybody at that company. A company-wide request that "
               "reached only one person is a compliance problem",
    },
    "reply.on_referral": {
        "label": "When somebody points us at a colleague",
        "kind": "choice", "choices": ("continue", "hold", "stop", "review"),
        "why": "holds the referrer by default; activating the referred "
               "contact is a campaign decision",
    },
    "reply.on_wrong_person": {
        "label": "When we wrote to the wrong person",
        "kind": "choice", "choices": ("continue", "hold", "stop", "review"),
        "why": "stops that sequence only. Their colleagues may still be "
               "right",
    },
    "reply.on_left_company": {
        "label": "When a contact has left",
        "kind": "choice", "choices": ("stop", "hold", "review"),
        "why": "nothing more can usefully be sent to that address",
    },
    "reply.on_existing_client": {
        "label": "When they are already a client",
        "kind": "choice", "choices": ("review", "hold", "stop"),
        "why": "somebody needs to know before anything else goes out",
    },

    # ------------------------------------------------------------ pacing
    #
    # How often one person, and one company, may hear from us. These matter
    # more under account-based outreach than they ever did: four
    # independently-correct sequences sharing a recipient is four strangers
    # in two days, and nothing looking at one cadence at a time can see it.
    "fatigue.contact.min_hours_between_touches": {
        "label": "Minimum hours between two touches to one person",
        "kind": "int", "min": 0, "max": 720,
        "why": "counts every sender and both channels, not one sequence",
    },
    "fatigue.contact.max_touches_per_week": {
        "label": "Maximum touches to one person in a rolling week",
        "kind": "int", "min": 1, "max": 50,
        "why": "across every human and channel",
    },
    "fatigue.contact.max_touches_total": {
        "label": "Maximum touches to one person, ever",
        "kind": "int", "min": 1, "max": 200,
        "why": "the whole sequence, not one campaign",
    },
    "fatigue.account.max_active_contacts": {
        "label": "Maximum decision makers worked at once",
        "kind": "int", "min": 1, "max": 20,
        "why": "five people at one company hearing from us in a week is a "
               "blast, however carefully each sequence was paced",
    },
    "fatigue.account.min_hours_between_first_touches": {
        "label": "Minimum hours between opening two people at one company",
        "kind": "int", "min": 0, "max": 720,
        "why": "two openings hours apart reads as a mail merge",
    },
    "fatigue.account.max_touches_per_week": {
        "label": "Maximum touches to one company in a rolling week",
        "kind": "int", "min": 1, "max": 100,
        "why": "every decision maker, every sender, every channel",
    },

    # Report defaults live on the workspace rather than in a browser, so a
    # monthly report does not render differently depending on who pressed the
    # button.
    "reporting.default_template": {
        "label": "Default report template",
        "kind": "choice", "choices": ("executive", "detailed", "internal"),
        "why": "which template the Client Reports screen opens on. Selecting "
               "the internal one here does not let a client-facing role "
               "render it: that is decided per request, against the "
               "operations permission",
    },
    "reporting.default_sections": {
        "label": "Default report sections",
        "kind": "text", "blank_is_none": True,
        "why": "comma-separated section keys, blank for every section the "
               "template offers. A key the template does not offer is "
               "dropped rather than honoured",
    },
}


class NotOverridable(ValueError):
    """A key that is not on the allowlist, or a value outside its range."""


def policy(workspace_slug, rows=None):
    """The overrides recorded for this workspace. Never the client config."""
    entry = workspace(workspace_slug, rows) or {}
    return dict((entry.get("settings") or {}).get("policy") or {})


def coerce_policy(key, raw):
    """One value, checked against its own rule. Raises rather than clamping.

    Clamping would be the friendly thing and the wrong one: somebody who set
    the confirmation count to 1 and got a page saying 2 has been told the
    system does what they asked, and it did not.
    """
    spec = POLICY_KEYS.get(key)
    if spec is None:
        raise NotOverridable(
            f"{key!r} is not a workspace-overridable setting. The list is "
            "deliberately short; anything else is a change to the client "
            "config, made by a person who can see the whole file.")
    text = "" if raw is None else str(raw).strip()

    if spec["kind"] == "int":
        if not text:
            if spec.get("blank_is_none"):
                return None
            raise NotOverridable(f"{spec['label']} needs a number")
        try:
            value = int(text)
        except ValueError:
            raise NotOverridable(f"{spec['label']} must be a whole number")
        if value < spec["min"] or value > spec["max"]:
            raise NotOverridable(
                f"{spec['label']} must be between {spec['min']} and "
                f"{spec['max']}. {spec['why']}")
        return value

    if spec["kind"] == "choice":
        if text not in spec["choices"]:
            raise NotOverridable(
                f"{spec['label']} must be one of "
                f"{', '.join(spec['choices'])}")
        return text

    if spec["kind"] == "bool":
        # Two words rather than a checkbox, because "flagged" and "dropped"
        # say what happens and a ticked box does not. The stored value is a
        # real boolean: the config it merges onto holds one, and a string
        # "false" is true.
        if text not in spec["choices"]:
            raise NotOverridable(
                f"{spec['label']} must be one of "
                f"{', '.join(spec['choices'])}")
        return text == spec["choices"][0]

    if spec["kind"] == "personas":
        return coerce_personas(raw)

    if spec["kind"] == "list":
        # Comma-separated, because that is how the same lists are written in
        # the client file and how somebody pastes a list of countries.
        items = [part.strip() for part in text.split(",")]
        items = [part for part in items if part]
        if len(items) > spec["max_items"]:
            raise NotOverridable(
                f"{spec['label']} takes at most {spec['max_items']} entries")
        for part in items:
            if len(part) > spec["max_length"]:
                raise NotOverridable(
                    f"{spec['label']}: {part[:30]!r} is too long")
        # An empty list and no override are the same thing to every reader
        # of this setting, so they are stored the same way. Keeping both
        # would be two spellings of one state.
        return items or None

    if len(text) > spec.get("max_length", 200):
        raise NotOverridable(f"{spec['label']} is too long")
    return text or None


# A persona name is a key in the client config and an identifier in every
# report that groups by it. Lower case, because `classify` compares against
# the config's own keys and two personas differing only in case are one
# persona with a typo.
PERSONA_NAME = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
ANGLE_NAME = re.compile(r"^[a-z][a-z0-9_]{1,20}$")

MAX_PERSONAS = 8
MAX_TITLES = 40
MAX_ANGLES = 10
MAX_CAP = 10


def coerce_personas(raw):
    """The whole persona set, checked before any of it is stored.

    Structural, not cosmetic. A title list is what `classify` matches a
    contact against, so an empty one is a persona that can never select
    anybody - which is not an error a person would see until a batch came
    back with nobody in it. It is refused here instead.

    Returns None for an empty set, so "no personas" has one spelling and
    the readiness list keeps reporting it as missing.
    """
    # The one place that decides an empty set is no override at all. A
    # second check at the caller would reach the same answer and neither
    # could then be removed by a mutation and caught by a test.
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise NotOverridable("personas must be a set of named personas")
    if len(raw) > MAX_PERSONAS:
        raise NotOverridable(f"at most {MAX_PERSONAS} personas")

    out = {}
    for name, body in raw.items():
        key = str(name or "").strip().lower()
        if not PERSONA_NAME.match(key):
            raise NotOverridable(
                f"{name!r} is not a usable persona name. Lower case "
                "letters, digits and underscores, starting with a letter.")
        body = body or {}
        titles = [str(t).strip()[:80] for t in (body.get("titles") or [])]
        titles = [t for t in titles if t]
        if not titles:
            raise NotOverridable(
                f"{key} needs at least one title. A persona with none can "
                "never select anybody, and nobody would find that out "
                "until a batch came back empty.")
        if len(titles) > MAX_TITLES:
            raise NotOverridable(f"{key}: at most {MAX_TITLES} titles")

        try:
            cap = int(body.get("cap_per_domain") or 1)
        except (TypeError, ValueError):
            raise NotOverridable(f"{key}: the cap must be a whole number")                 from None
        if not 1 <= cap <= MAX_CAP:
            raise NotOverridable(
                f"{key}: the cap must be between 1 and {MAX_CAP}. It is how "
                "many people at one company this persona may put into a "
                "sequence.")

        angles = {}
        for angle, phrase in (body.get("angles") or {}).items():
            angle_key = str(angle or "").strip().lower()
            if not ANGLE_NAME.match(angle_key):
                raise NotOverridable(
                    f"{key}: {angle!r} is not a usable angle name")
            text = " ".join(str(phrase or "").split())[:200]
            if not text:
                raise NotOverridable(
                    f"{key}: the angle {angle_key} has nothing to say")
            angles[angle_key] = text
        if len(angles) > MAX_ANGLES:
            raise NotOverridable(f"{key}: at most {MAX_ANGLES} angles")

        entry = {"titles": titles, "cap_per_domain": cap}
        if angles:
            entry["angles"] = angles
        out[key] = entry
    return out


def set_policy(workspace_slug, updates, actor="system"):
    """Apply a set of overrides, or none of them. Returns (before, after).

    All or nothing on purpose: a half-applied policy is a workspace running
    under rules nobody chose.
    """
    checked = {key: coerce_policy(key, value) for key, value in updates.items()}
    before, after = {}, {}
    with transaction() as rows:
        for i, row in enumerate(rows):
            if row.get("kind") != "workspace" or row.get("slug") != workspace_slug:
                continue
            settings = dict(row.get("settings") or {})
            current = dict(settings.get("policy") or {})
            before = dict(current)
            current.update(checked)
            # A key set back to None is removed rather than stored as null,
            # so "no override" and "overridden to nothing" stay distinct.
            current = {k: v for k, v in current.items() if v is not None}
            after = current
            settings["policy"] = current
            rows[i] = dict(row, settings=settings)
            break
        else:
            raise NotOverridable(f"no such workspace: {workspace_slug}")

    changed = {k: {"from": before.get(k), "to": after.get(k)}
               for k in set(before) | set(after)
               if before.get(k) != after.get(k)}
    if changed:
        record(actor, workspace_slug, "workspace.policy_changed",
               resource_type="workspace", resource_id=workspace_slug,
               before={k: v["from"] for k, v in changed.items()},
               after={k: v["to"] for k, v in changed.items()},
               reason="changed from the workspace settings screen")
    return before, after


def apply_policy(config, overrides):
    """Merge overrides onto a client config. Returns a new dict.

    Dotted keys, walked and copied rather than mutated: the config object
    handed back by `clients.load` is shared, and writing through it would make
    one workspace's override everybody's.
    """
    if not overrides:
        return config
    merged = _deep_copy(config or {})
    for key, value in overrides.items():
        if key not in POLICY_KEYS:
            # Ignored rather than raised: a key that was valid when it was
            # written and has since been removed from the allowlist should
            # stop applying, not stop the workspace loading.
            continue
        parts = key.split(".")
        node = merged
        for part in parts[:-1]:
            child = node.get(part)
            node[part] = dict(child) if isinstance(child, dict) else {}
            node = node[part]
        node[parts[-1]] = value
    return merged


def _deep_copy(value):
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_copy(v) for v in value]
    return value


def audit_path():
    return os.path.abspath(os.environ.get("AUDIT")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "audit.jsonl"))


# Nothing in an audit entry may be a secret. `metadata` is for identifiers,
# counts and status words; a test asserts no credential-shaped string reaches
# this file.
def record(actor, workspace_slug, action, resource_type=None, resource_id=None,
           before=None, after=None, reason=None, metadata=None):
    """Append one durable, human-readable audit entry."""
    entry = {
        "at": store.now(),
        "actor": actor,
        "workspace": workspace_slug,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "before": before,
        "after": after,
        "reason": reason,
        "metadata": metadata or {},
    }
    path_ = audit_path()
    with store.lock(for_path=path_):
        rows = store.read_jsonl(path_)
        rows.append(entry)
        store.write_jsonl(path_, rows)
    return entry


def audit(workspace_slug=None, limit=200, action=None):
    """The audit log, newest first.

    `action` narrows *before* the limit, which is the whole point of having
    it. A caller that reads 5,000 rows and filters afterwards is not asking
    "what refusals are there", it is asking "what refusals are among the
    last 5,000 things that happened" - and since refusals are rare next to
    routine writes, that number falls towards zero as a workspace gets
    busier. `notify.history` already filters in this order.
    """
    rows = store.read_jsonl(audit_path())
    if workspace_slug:
        rows = [r for r in rows if r.get("workspace") == workspace_slug]
    if action:
        rows = [r for r in rows if r.get("action") == action]
    return list(reversed(rows))[:limit]


def audit_total(workspace_slug=None, action=None):
    """How many there are, as opposed to how many were shown."""
    rows = store.read_jsonl(audit_path())
    if workspace_slug:
        rows = [r for r in rows if r.get("workspace") == workspace_slug]
    if action:
        rows = [r for r in rows if r.get("action") == action]
    return len(rows)


# ------------------------------------------------------------- bootstrap

class ClientTaken(RuntimeError):
    """Another workspace is already configured by this client file."""


def ensure(slug, name=None, client=None, created_by="system"):
    """Create a workspace if it is not there. Returns it either way.

    Refuses a client file another workspace already claims, and that is a
    tenancy guard rather than tidiness. Records, campaigns and jobs are
    scoped by `repo.client`; the audit log, senders, notifications, reports
    and drafts are scoped by `repo.workspace`. Two workspaces sharing one
    client would therefore share every record and every campaign while
    keeping separate audit trails - each tenant seeing the other's
    companies, and neither log saying so.

    Nothing in the product could produce it: `api.create_workspace` passes
    the slug as the client and refuses a config file that already exists.
    A hand-edited table could, and this is where that stops.

    The audit entry is written after the transaction closes, not inside it:
    the log is a separate file with its own lock, and taking a second lock
    while holding the first is how a deadlock gets built.
    """
    created = None
    with transaction() as rows:
        found = workspace(slug, rows)
        if found:
            return found
        wanted = client or slug
        taken = [w for w in workspaces(rows)
                 if (w.get("client") or w.get("slug")) == wanted]
        if taken:
            raise ClientTaken(
                f"workspace {taken[0].get('slug')!r} is already configured "
                f"by client {wanted!r}. Two workspaces sharing one client "
                "share every record and campaign in it.")
        created = new_workspace(slug, name or slug, client, created_by)
        rows.append(created)
    record(created_by, slug, "workspace.create", "workspace", slug,
           after=created.get("name"))
    return created


def add_user(email, name, super_admin=False, actor="system"):
    created = None
    with transaction() as rows:
        found = user(email, rows)
        if found:
            return found
        created = new_user(email, name, super_admin)
        rows.append(created)
    record(actor, None, "user.create", "user", created["email"],
           metadata={"super_admin": bool(super_admin)})
    return created


# What the sign-in path writes to the audit log. Named here rather than
# spelled out at each call site, because `bootstrap_super_admin` below reads
# them back and two spellings of one action is a bootstrap that silently
# finds nothing.
IDENTITY_PROVED = "auth.identity_proved"
IDENTITY_REFUSED = "auth.identity_refused"
BOOTSTRAP_ACTION = "auth.bootstrap"


class BootstrapRefused(RuntimeError):
    """The first administrator cannot be created from what was supplied."""


def proved_addresses(limit=1000):
    """Addresses an identity provider has actually proved, newest first.

    Read from the audit log, which is the only place a *verified* identity
    is recorded. That is the whole point: an address in an environment
    variable is somebody's claim, and this system does not accept claims.
    An address that appears here has completed a real authorization code
    exchange - state, nonce, audience, expiry, `email_verified` and domain
    all checked - and was then refused because no user row existed for it.
    """
    seen = []
    for row in audit(limit=limit):
        if row.get("action") != IDENTITY_PROVED:
            continue
        actor = (row.get("actor") or "").strip().lower()
        if actor and actor not in seen:
            seen.append(actor)
    return seen


def bootstrap_super_admin(email, workspace_slug, workspace_name=None,
                          client=None):
    """Create the first administrator, once, from an identity already proved.

    The chicken-and-egg of a fresh production deployment: nobody can sign
    in because no user exists, and no user can be created because signing
    in is how you reach the screen that would create one. Something has to
    break the circle, and the only question is what it is allowed to trust.

    **It trusts the audit log, not its own argument.** `email` selects
    which proved identity to promote; it cannot conjure one. An address
    that has never completed a Google sign-in against this deployment is
    refused, so setting the variable to somebody else's address grants
    nothing until that person authenticates - at which point they are the
    one who proved it.

    **It is inert the moment it has worked.** Any user existing at all
    means this returns None and touches nothing, so it cannot be used to
    add a second administrator, to re-promote a demoted one, or to escalate
    after the fact. That is also why there is no "force": a bootstrap that
    can run twice is an administrative back door with a polite name.

    Everything it does goes through the ordinary auditable primitives -
    `add_user`, `ensure` - and it writes its own entry naming the address,
    the workspace and the fact that SUPER_ADMIN was granted.
    """
    existing = users()
    if existing:
        return None

    email = str(email or "").strip().lower()
    if not email:
        raise BootstrapRefused("no address was named")

    proved = proved_addresses()
    if email not in proved:
        raise BootstrapRefused(
            f"{email} has never proved itself against this deployment. "
            "Sign in through the identity provider first - the refusal is "
            "expected and is what records the proof - then bootstrap. "
            + (f"Addresses that have: {', '.join(proved)}" if proved
               else "No address has completed a sign-in yet."))

    if not workspace_slug:
        raise BootstrapRefused(
            "a workspace is required: a super admin with none cannot enter "
            "the console, and nothing in the application creates one")

    # Fail before writing anything if the client config is absent, rather
    # than leaving a workspace whose every screen raises.
    from . import clients

    client = client or workspace_slug
    try:
        clients.load(client)
    except Exception as e:                             # noqa: BLE001
        raise BootstrapRefused(
            f"workspace {workspace_slug!r} needs config/clients/{client}.yaml "
            f"and it could not be read: {e}")

    person = add_user(email, email, super_admin=True, actor="bootstrap")
    space = ensure(workspace_slug, workspace_name or workspace_slug, client,
                   created_by="bootstrap")
    record("bootstrap", space["slug"], BOOTSTRAP_ACTION, "user", email,
           reason="first administrator, from an identity proved by the "
                  "configured identity provider",
           metadata={"super_admin": True, "workspace": space["slug"]})
    return {"email": person["email"], "workspace": space["slug"],
            "super_admin": True}


# ------------------------------------------------------------ invitations
#
# The gap this fills, and why it is a separate kind of row.
#
# `assign` refuses an address with no user row, and the reason in its
# docstring is right: "a membership row pointing at nobody is a row that
# grants a permission to whoever registers that address next". So an
# administrator could not give somebody access until that person had
# already signed in and been turned away - which is a workflow nobody
# would design on purpose.
#
# An invitation is the missing state. It is *not* a membership: it grants
# nothing, appears in no permission check, and is invisible to
# `membership_of`. It is a standing instruction that says what to do if a
# particular address is ever proved by the identity provider, and it is
# only ever read by `consume_invitations`, after the proof.
#
# Kept in `workspaces.jsonl` alongside users, workspaces and memberships,
# because it is the same question - who may be here - and a second file
# would be a second place for that answer to live.

PENDING = "pending"
ACCEPTED = "accepted"
REVOKED = "revoked"

# No expiry. It would be a second thing to get wrong and a background job
# to run, and an invitation that grants nothing until an identity provider
# proves the address is not a credential lying around. Revocation is the
# control that matters and it is immediate.


class RoleNotAssignable(ValueError):
    """A role that this form is not allowed to hand out."""


def normalise_email(value):
    """One definition, used by the invite and by the consumer.

    An invitation is matched against what a provider proved, so the two
    sides must normalise identically or an invitation silently never
    matches - or worse, matches something it should not.
    """
    return str(value or "").strip().lower()


def new_invitation(email, workspace, role, invited_by):
    return {
        "kind": "invitation",
        "email": normalise_email(email),
        "workspace": workspace,
        "role": role,
        "invited_by": normalise_email(invited_by),
        "status": PENDING,
        "created_at": store.now(),
        "consumed_at": None,
        "subject": None,
    }


def invitations(workspace_slug=None, email=None, status=None, rows=None):
    found = _rows("invitation", rows)
    if workspace_slug:
        found = [i for i in found if i.get("workspace") == workspace_slug]
    if email:
        email = normalise_email(email)
        found = [i for i in found if i.get("email") == email]
    if status:
        found = [i for i in found if i.get("status") == status]
    return found


def assignable_roles():
    """Every role a workspace form may hand out.

    `SUPER_ADMIN` is absent and that is the point: it is an account-level
    fact on the user row, not a workspace role, and nothing reachable from
    inside a workspace may grant it.
    """
    return tuple(r for r in ROLES if r != SUPER_ADMIN)


def invite(email, workspace_slug, role, actor="system"):
    """Pre-authorise an address. Grants nothing until a provider proves it.

    Returns a small result the screen can speak from - `invited`,
    `already_pending`, `already_member`, `role_changed` - rather than
    raising for the ordinary outcomes, because "this person is already in
    this workspace" is an answer and not an error.

    Idempotent. Inviting the same address twice leaves one invitation, and
    inviting at a different role updates the one that is there rather than
    stacking a second standing instruction nobody can see.
    """
    email = normalise_email(email)
    if not email or "@" not in email:
        raise ValueError(f"not an email address: {email!r}")
    if role not in assignable_roles():
        raise RoleNotAssignable(
            f"{role!r} cannot be granted from a workspace. Assignable: "
            + ", ".join(assignable_roles()))
    if workspace(workspace_slug) is None:
        raise NotAMember(f"no such workspace: {workspace_slug}")

    # Somebody who is already here does not need an invitation; they need
    # their role set, which is what `assign` is for.
    if user(email) is not None:
        for entry in memberships(email, workspace_slug):
            if entry.get("role") == role:
                return {"outcome": "already_member", "email": email,
                        "role": role}
            assign(email, workspace_slug, role, actor=actor)
            return {"outcome": "role_changed", "email": email, "role": role}
        assign(email, workspace_slug, role, actor=actor)
        return {"outcome": "added", "email": email, "role": role}

    created = None
    outcome = "invited"
    with transaction() as rows:
        for entry in rows:
            if (entry.get("kind") == "invitation"
                    and entry.get("email") == email
                    and entry.get("workspace") == workspace_slug
                    and entry.get("status") == PENDING):
                if entry.get("role") == role:
                    outcome = "already_pending"
                else:
                    entry["role"] = role
                    outcome = "pending_role_changed"
                created = entry
                break
        else:
            created = new_invitation(email, workspace_slug, role, actor)
            rows.append(created)
    record(actor, workspace_slug, "invitation." + outcome, "invitation",
           email, after=role)
    return {"outcome": outcome, "email": email, "role": role,
            "created_at": created.get("created_at")}


def revoke_invitation(email, workspace_slug, actor="system"):
    """Withdraw a pending invitation. Immediate, and the only control needed.

    Revoked rather than deleted: "this was offered and taken back" is a
    different fact from "this never happened", and the audit log should be
    able to tell them apart.
    """
    email = normalise_email(email)
    changed = False
    with transaction() as rows:
        for entry in rows:
            if (entry.get("kind") == "invitation"
                    and entry.get("email") == email
                    and entry.get("workspace") == workspace_slug
                    and entry.get("status") == PENDING):
                entry["status"] = REVOKED
                changed = True
    if changed:
        record(actor, workspace_slug, "invitation.revoked", "invitation",
               email)
    return changed


def consume_invitations(email, subject=None, rows=None):
    """Turn every pending invitation for a *proved* address into membership.

    **Only ever call this with an address an identity provider has just
    proved.** It is the one place an invitation becomes access, and it
    trusts its argument completely - which is safe exactly once: when the
    caller is `/auth/callback`, after state, nonce, issuer, audience,
    expiry, `email_verified` and the domain fence have all passed.

    The demo sign-in must never reach it. Typing an address into a form is
    the thing invitations exist to *not* be, and `_establish` takes an
    explicit `proved` flag rather than inferring it from a subject that a
    provider might omit.

    Matching is on the exact normalised address and nothing else. Not the
    domain, not a prefix, not a display name: an invitation for
    `tina@example.com` is not claimable by `tina+x@example.com` or by
    anybody else at `example.com`.

    Only the invited workspace is activated. An invitation to one workspace
    says nothing about any other.
    """
    email = normalise_email(email)
    pending = [i for i in invitations(email=email, status=PENDING, rows=rows)]
    if not pending:
        return []

    if user(email) is None:
        add_user(email, email, super_admin=False, actor="invitation")

    activated = []
    for entry in pending:
        # Through `assign`, so a membership is created the one way
        # memberships are created, with its own audit entry.
        assign(email, entry["workspace"], entry["role"],
               actor="invitation:" + normalise_email(entry.get("invited_by")))
        activated.append({"workspace": entry["workspace"],
                          "role": entry["role"]})

    with transaction() as rows_:
        for entry in rows_:
            if (entry.get("kind") == "invitation"
                    and entry.get("email") == email
                    and entry.get("status") == PENDING):
                entry["status"] = ACCEPTED
                entry["consumed_at"] = store.now()
                entry["subject"] = subject

    for done in activated:
        record(email, done["workspace"], "invitation.accepted", "invitation",
               email, after=done["role"],
               metadata={"subject": subject} if subject else None)
    return activated


class NoSuchUser(KeyError):
    """A membership was requested for somebody who does not exist."""


def assign(email, workspace_slug, role, actor="system"):
    """Put a user in a workspace with a role. Idempotent on (user, workspace).

    The user has to exist. A membership row pointing at nobody is a row that
    grants a permission to whoever registers that address next, and there is
    no good reason for one to be creatable by a typo in a form.
    """
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    if user(email) is None:
        raise NoSuchUser(f"no such user: {email}")
    with transaction() as rows:
        for entry in rows:
            if (entry.get("kind") == "membership"
                    and entry.get("email") == str(email).strip().lower()
                    and entry.get("workspace") == workspace_slug):
                before = entry.get("role")
                entry["role"] = role
                record(actor, workspace_slug, "membership.assign", "user", email,
                       before=before, after=role)
                return entry
        entry = new_membership(email, workspace_slug, role)
        rows.append(entry)
    record(actor, workspace_slug, "membership.invite", "user", email,
           after=role)
    return entry


def remove(email, workspace_slug, actor="system"):
    removed = None
    with transaction() as rows:
        keep = []
        for entry in rows:
            if (entry.get("kind") == "membership"
                    and entry.get("email") == str(email).strip().lower()
                    and entry.get("workspace") == workspace_slug):
                removed = entry
                continue
            keep.append(entry)
        rows[:] = keep
    if removed:
        record(actor, workspace_slug, "membership.remove", "user", email,
               before=removed.get("role"))
    return removed


def settings_of(slug):
    """The client config that configures this workspace."""
    entry = workspace(slug)
    if entry is None:
        raise NotAMember(f"no such workspace: {slug}")
    try:
        return clients.load(entry.get("client") or slug)
    except Exception:
        return {}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.workspaces",
                               description=__doc__)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    rows = load()
    payload = {
        "workspaces": workspaces(rows),
        "users": users(rows),
        "memberships": memberships(rows=rows),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    for entry in payload["workspaces"]:
        print(f"  {entry['slug']:<16} {entry['name']}")
        for m in memberships(workspace_slug=entry["slug"], rows=rows):
            print(f"      {m['email']:<32} {m['role']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
