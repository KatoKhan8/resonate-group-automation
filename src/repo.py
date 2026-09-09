#!/usr/bin/env python3
"""The persistence seam, and the only place a caller names a client.

## Why this exists

`src/store.py` is the one read/write path to `work/queue.jsonl`, and it is
right as it is. What it does not do is enforce *whose* data a caller may see:
`list_records(client=...)` is a filter a caller may pass, and a filter a caller
may also forget. WEB-READINESS names that gap by name -

    "Client isolation is a filter, not a boundary. Everything reads the one
     work/queue.jsonl. For multi client use, either partition the queue per
     client or enforce the filter in a service layer that never hands a caller
     another client's records."

This is that service layer. Every read goes through a `Repo` that was
constructed for one client and cannot return another client's rows, and every
write refuses a record that does not belong to it. A web request handler cannot
forget the filter, because there is no unfiltered call to reach for.

## Why it is not a database

DATABASE-MIGRATION.md is explicit about when files stop being enough: **when
two processes need to write at once.** That is not today, and doing the
migration tonight would be an irreversible change made without the constraint
that motivates it. What this module does instead is make the migration cheap by
putting every query behind a method, so `FileRepo` can be joined by a
`SqlRepo` later without any caller changing. The method names deliberately read
like the queries a database would run.

The three properties DATABASE-MIGRATION says make the migration cheap - self
contained records, stable idempotency keys, resumable stages - are all still
true, and nothing here weakens them.

## The rule

**A `Repo` is scoped at construction and cannot be widened.** `Repo.for_client`
is the only constructor a request path may use. `admin_repo()` exists for the
CLI and for cross-client reporting, is named so that it is obvious in a diff,
and is refused by the web layer's own tests.
"""
import re

from . import campaigns as campaign_store
from . import clients, store, workspaces

# A client slug is a directory name under config/clients, so it is constrained
# to what a filename may safely be. This is also the path-traversal guard: a
# slug that fails this never reaches the filesystem.
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class UnknownClient(KeyError):
    """No such client, or a slug that is not a slug."""


class CrossClientAccess(PermissionError):
    """A caller reached for an object belonging to somebody else.

    Raised rather than returning None on purpose: an empty result reads as
    "there is nothing there", and the difference between "does not exist" and
    "is not yours" is the difference between a bug and a breach.
    """


def known_clients():
    """Every client with a config file. The only source of valid slugs.

    Read from disk rather than cached: a client added while the server is up
    should be selectable without a restart, and the list is a handful of
    filenames.
    """
    import os
    try:
        names = os.listdir(clients.clients_dir())
    except OSError:
        return []
    return sorted(n[:-5] for n in names
                  if n.endswith(".yaml") and valid_slug(n[:-5])
                  and not n.endswith(".example.yaml"))


def valid_slug(slug):
    return bool(slug and SLUG.match(str(slug)))


class Repo:
    """Everything a caller may ask, already scoped to one client.

    `client=None` means unscoped, and only `admin_repo()` builds one of those.
    """

    def __init__(self, client=None):
        if client is not None and not valid_slug(client):
            raise UnknownClient(f"not a valid client slug: {client!r}")
        self.client = client
        # Set by `for_user`. A repo without a membership carries no
        # permissions; see `require`.
        self.workspace = client
        self.membership = None
        self.actor = None

    # ------------------------------------------------------------- scoping

    @classmethod
    def for_client(cls, slug):
        """A repo scoped to a client config, with no membership behind it.

        The CLI's constructor. A request path must use `for_user` instead, so
        that the tenancy boundary is a membership rather than a slug somebody
        typed into a URL.
        """
        if not valid_slug(slug):
            raise UnknownClient(f"not a valid client slug: {slug!r}")
        if slug not in known_clients():
            raise UnknownClient(f"no such client: {slug}")
        return cls(slug)

    @classmethod
    def for_user(cls, email, workspace_slug):
        """The constructor every request path uses.

        Two things happen here and neither is optional. The workspace has to
        exist, and this user has to be a member of it - a super admin included,
        who gets a membership that says `super_admin` so the crossing is named
        in the audit log rather than invisible.

        `NotAMember` is raised for both "no such workspace" and "not yours",
        deliberately: telling a caller that a workspace exists but belongs to
        somebody else is itself a disclosure, and the handler turns both into
        the same 404.
        """
        if not valid_slug(workspace_slug):
            raise workspaces.NotAMember(
                f"no such workspace: {workspace_slug!r}")
        membership = workspaces.require_member(email, workspace_slug)
        entry = workspaces.workspace(workspace_slug)
        repo = cls((entry or {}).get("client") or workspace_slug)
        repo.workspace = workspace_slug
        repo.membership = membership
        repo.actor = email
        return repo

    # ------------------------------------------------------- permissions

    def require(self, permission):
        """Every service call that needs a permission asks here.

        A repo built by `for_client` has no membership and carries no
        permissions: the CLI is trusted by being the CLI, and a *request* path
        that somehow got hold of one is refused rather than waved through.
        """
        if self.membership is None:
            raise workspaces.NotPermitted(
                "this repository has no membership behind it, so it carries "
                "no permissions; a request path must use Repo.for_user")
        workspaces.require(self.membership, permission)
        return True

    def may(self, permission):
        if self.membership is None:
            return False
        return workspaces.may(self.membership.get("role"), permission)

    def role(self):
        return (self.membership or {}).get("role")

    def audit(self, action, resource_type=None, resource_id=None, **kw):
        """One durable entry, attributed to this user, this workspace, and the
        membership they are acting under.

        The role and `via` are carried because without them a super admin
        working inside somebody else's workspace writes an entry shaped
        exactly like one the workspace's own admin wrote. `membership_of`
        mints `via: super_admin` for that crossing and it stopped there -
        nothing reached the log, and no entry anywhere recorded the crossing
        itself. Reconstructing "this was an outsider" then means joining
        against the membership table, which stops working the moment somebody
        is legitimately added to that workspace. `for_user`'s own docstring
        says the crossing is named in the audit log; this is what makes that
        true.
        """
        metadata = dict(kw.pop("metadata", None) or {})
        membership = self.membership or {}
        for name in ("role", "via"):
            if membership.get(name) and name not in metadata:
                metadata[name] = membership[name]
        return workspaces.record(self.actor, self.workspace, action,
                                 resource_type, resource_id,
                                 metadata=metadata or None, **kw)

    def config(self):
        """The client config, with this workspace's overrides merged onto it.

        The client file is the baseline and stays hand-written; the overrides
        are the handful of settings a workspace admin may change from the
        settings screen, stored beside the workspace rather than written back
        into a YAML file with comments in it. See `workspaces.POLICY_KEYS`.

        A CLI repo gets the same merge. That is deliberate: if the web layer
        and the CLI read different rules for the same client, one of them is
        wrong and nobody can tell which. An override is the workspace's policy,
        not the browser's, and a batch run from a terminal is run under it too.
        """
        if not self.client:
            return {}
        # Named rather than inferred. This is the one caller that knows
        # which workspace it is reading for, and saying so is both faster
        # and correct in an estate where a client file is shared.
        return clients.load(self.client, workspace=self.workspace)

    def _mine(self, rec):
        return self.client is None or (rec or {}).get("client") == self.client

    def _guard(self, rec, what):
        if rec is None:
            return None
        if not self._mine(rec):
            raise CrossClientAccess(
                f"{what} belongs to another client and is not readable here")
        return rec

    # --------------------------------------------------------------- reads

    def records(self, state=None, lane=None, batch=None):
        """Every record this client owns, filtered where asked."""
        rows = [r for r in store.load() if self._mine(r)]
        if state:
            rows = [r for r in rows if r.get("state") == state]
        if lane:
            rows = [r for r in rows if r.get("lane") == lane]
        if batch:
            rows = [r for r in rows
                    if r.get("batch") == batch or r.get("batch_id") == batch]
        return rows

    def record(self, record_id):
        """One record, or a refusal. Never another client's."""
        return self._guard(store.get(record_id), f"record {record_id!r}")

    def contact(self, record_id, contact_key):
        rec = self.record(record_id)
        if rec is None:
            return None, None
        for contact in rec.get("contacts") or []:
            if contact.get("key") == contact_key:
                return rec, contact
        return rec, None

    def batches(self):
        """Batch ids this client owns, with their record counts."""
        counts = {}
        for rec in self.records():
            key = rec.get("batch") or rec.get("batch_id")
            if key:
                counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    def campaigns(self):
        rows = campaign_store.load()
        return [c for c in rows
                if self.client is None or c.get("client") == self.client]

    def campaign(self, campaign_id):
        for row in campaign_store.load():
            if row.get("campaign_id") == campaign_id:
                return self._guard(row, f"campaign {campaign_id!r}")
        return None

    def stats(self):
        return store.stats(self.records())

    # -------------------------------------------------------------- writes

    def save_records(self, records):
        """Write back. Refuses anything that is not this client's.

        The whole queue is rewritten, so the rows this repo cannot see have to
        be carried through untouched - which is exactly what a per-client
        partition or a `WHERE client = ?` would do for free later.
        """
        for rec in records:
            if not self._mine(rec):
                raise CrossClientAccess(
                    f"refusing to write record {rec.get('id')!r}: "
                    "it belongs to another client")
        by_id = {r["id"]: r for r in records}
        with store.transaction() as rows:
            for i, existing in enumerate(rows):
                if existing["id"] not in by_id:
                    continue
                if not self._mine(existing):
                    # The record was re-tenanted while we held it.
                    #
                    # The id was popped only inside this branch, so a row that
                    # had moved to another client was left in `by_id` and then
                    # appended - two rows sharing one id, the live one and our
                    # stale shadow of it. `store.append` refuses a duplicate
                    # id; `store.transaction` does not. And because
                    # `store.get` finds the other client's row first, the
                    # writer could not read back its own write.
                    #
                    # A re-tenanting is a transfer, not a fork. Refuse and let
                    # the caller re-read.
                    raise CrossClientAccess(
                        f"record {existing['id']!r} now belongs to another "
                        "client: re-read before writing")
                rows[i] = by_id.pop(existing["id"])
            rows.extend(by_id.values())

    def _owns_record(self, record_id):
        """Is this record id one of ours? Absent counts as not ours.

        A campaign may not claim a record that does not exist either: an id
        that is merely absent today is an id somebody else may be given
        tomorrow.
        """
        for row in store.load():
            if row.get("id") == record_id:
                return self._mine(row)
        return False

    def save_campaign(self, campaign):
        """Upsert one campaign, leaving every other client's rows alone."""
        if not self._mine(campaign):
            raise CrossClientAccess(
                "refusing to write a campaign belonging to another client")
        # And the records it claims, not only the client field on the row.
        #
        # This checked whose campaign it was and never which records it
        # listed, while `campaigns.by_record` is unscoped - so a campaign
        # owned by one client could list another client's records, and those
        # records would then run its step graph. A record already in its own
        # campaign became ambiguous instead: `by_record` maps a record in two
        # campaigns to `None`, `eligibility._campaign` returns immediately on
        # `None`, and freeze, pause, rejection and approval staleness all stop
        # applying to it. One client could quietly detach another's records
        # from their own campaign, and the row that did it is invisible to
        # them.
        theirs = [rid for rid in (campaign.get("record_ids") or [])
                  if not self._owns_record(rid)]
        if theirs:
            raise CrossClientAccess(
                "refusing a campaign that claims %d record(s) belonging to "
                "another client" % len(theirs))
        with campaign_store.transaction() as rows:
            for i, existing in enumerate(rows):
                if existing.get("campaign_id") == campaign.get("campaign_id"):
                    if not self._mine(existing):
                        raise CrossClientAccess(
                            "a campaign with this id belongs to another client")
                    rows[i] = campaign
                    break
            else:
                rows.append(campaign)
        return campaign


def admin_repo():
    """Unscoped. For the CLI and cross-client reporting only.

    Named so that its use is obvious in a diff and greppable in a review. The
    web layer has a test asserting no request handler calls it.
    """
    return Repo(None)
