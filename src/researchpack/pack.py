"""Assemble one account's research pack. READ-ONLY, CACHED, COSTED.

    pack = researchpack.build("acme.test")                   # cache only
    pack = researchpack.build("acme.test", live=True,
                              champion="https://.../in/ada")

## DRY RUN IS THE DEFAULT, AS EVERYWHERE ELSE HERE

`CLAUDE.md`: "Dry run is the default for anything that sends. --live is
always explicit." Nothing here sends, but everything here SPENDS, and the
same rule is the right one. `live=False` reads the cache and starts no
actor. A pack built without `live` is still a usable pack - it is the part
that was already paid for.

## COST IS RECORDED AT THE MOMENT OF THE CALL, THROUGH THE ONE LEDGER

`CLAUDE.md`: "Every paid call goes through enrich's `spend()`, which writes
the waterfall ledger. A provider call that skips it is invisible to the
spend audit, and an audit that reports clean because it watched nothing is
worse than none."

`enrich.spend` is a closure over one record and cannot be imported, so this
goes through `spendledger` directly - the module-level API that closure
itself writes through. A run served from cache records NOTHING, because
nothing was bought.

SINCE 2026-09-25 IT ALSO CHECKS, WHICH IT NEVER DID. Recording without
checking made Apify spend visible to the audit and invisible to every
ceiling, so the operator's Apify cap would have been a number nothing
consulted. `run_actor` reserves against the ceiling before the run starts.

## EVERY FACT CARRIES ITS PROVENANCE OR IT IS NOT STORED

See `facts.make`. A pack is worth having because a first line can be traced
back through it, and `src/copylint.py` is the thing that traces.
"""
from .. import spendledger, store
from . import actors as actorspec
from . import cache, facts


class PackRefused(RuntimeError):
    """A pack that cannot be built honestly is refused, never half-built."""


def _items(run_output, limit):
    rows = run_output if isinstance(run_output, list) else []
    return [r for r in rows if isinstance(r, dict)][:limit]


#: Where a row's url, body and date live, across the three actors. Tried in
#: order. Written as data rather than a chain of `or`s so a new actor is a
#: line here and the tests can assert the whole surface.
URL_KEYS = ("url", "postUrl", "link", "jobUrl")
BODY_KEYS = ("text", "description", "title", "content")
DATE_KEYS = ("publishedAt", "postedAt", "date", "datePosted")


def _first(row, keys):
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return None


def _facts_from(name, rows, subject=None):
    spec = actorspec.ACTORS[name]
    out = []
    for row in rows:
        try:
            out.append(facts.make(
                spec["kind"], _first(row, URL_KEYS), _first(row, DATE_KEYS),
                _first(row, BODY_KEYS), subject=subject,
                extra={"actor": spec["actor"]}))
        except facts.UnusableFact:
            # DROPPED, NOT PATCHED. A row with no url or no text cannot
            # support a claim, and inventing either to keep the count up is
            # how an unattributable sentence reaches a client.
            continue
    return out


def _client_config(client):
    """The client's declared ceilings, or `{}` when there are none to read.

    `{}` is "ungoverned" to `spendledger.check`, which is what an
    unattributed run has always been. It is not a licence invented here: a
    client that declares no budget has never had one enforced, and
    `tests/test_a_provider_ceiling_refuses_before_the_call.py` pins that as
    a known, separate gap.
    """
    if not client or client == "unattributed":
        return {}
    try:
        from .. import clients
        return clients.load(client) or {}
    except Exception:                                         # noqa: BLE001
        return {}


def run_actor(name, target, subject=None, client=None, runner=None,
              config=None):
    """One actor run. RESERVES the planned cost before the run starts.

    `runner` is the seam the cassette tests drive: it takes
    `(actor, payload, limit)` and returns the dataset rows. The default
    reaches `providers.apify`'s run lifecycle, which is IMPORTED rather
    than reimplemented - the polling, the timeout and the SSRF posture live
    there and a second copy of them would drift.

    THIS RECORDED AND NEVER CHECKED UNTIL 2026-09-25. Apify spend reached
    the ledger and no ceiling was ever consulted, so a declared Apify cap
    would have been exactly the decoration `per_run` was - a number in a
    config file with no consumer. It now reserves against the ceiling
    before the run starts, so the operator's Apify ceiling is enforced
    rather than reported.

    THE COST HERE IS INTEGER CENTS, NOT CREDITS. `actors.ACTORS[*]["cost"]`
    is money; every other provider writes credits into the same ledger. So
    an Apify ceiling is in cents and a Deliverable ceiling is in credits,
    and the CLIENT-WIDE `per_day` sums the two. See the unit hazard in
    docs/MERGE-REQUEST-2026-09-25-PER-PROVIDER-CEILINGS.md - it is named
    there rather than quietly converted here, because picking a conversion
    rate is not this function's decision to make.
    """
    spec = actorspec.ACTORS[name]
    if spec["needs_session"]:
        raise PackRefused(
            "%s needs a logged-in session; this pack reads public surfaces "
            "only" % name)
    payload = actorspec.build_input(name, target)
    # RESERVED, THEN SETTLED, THEN RUN - AND THAT ORDER IS DELIBERATE.
    #
    # The ceiling is consulted before anything starts, which is the whole
    # point of the change. But the ledger row is still written BEFORE the
    # run rather than after it, because a run that starts and then fails
    # still cost something, and a ledger that records only successes
    # understates spend in exactly the runs worth auditing. `holding()`
    # would have released on an exception and lost precisely those rows,
    # which is right for a per-address verifier call and wrong here.
    hold = spendledger.reserve(
        client or "unattributed",
        config if config is not None else _client_config(client),
        spec["cost"], provider="apify", call=name, unit="cents")
    spendledger.settle(hold)
    rows = (runner or _live_runner)(spec["actor"], payload, spec["limit"])
    return _facts_from(name, _items(rows, spec["limit"]), subject=subject)


def _live_runner(actor, payload, limit):
    """Start, poll, read. The polling is `providers.apify`'s."""
    from ..providers import apify
    run = _start(actor, payload)
    finished = apify.wait_for(run["id"])
    dataset = (finished or {}).get("dataset_id") or run.get("dataset_id")
    return apify.dataset_items(dataset, limit)


def _start(actor, payload):
    """`apify.start_run` builds the CRAWLER's input and cannot carry ours.

    Posting a run is three lines against helpers that module already
    exports. Re-implementing the POLLING would be the part worth refusing,
    and that is imported above rather than copied.
    """
    from ..providers import apify
    from ..providers import ProviderError, mapping, ok, query, request
    token = apify.key(apify.KEY_VAR)
    status, data = request(
        "POST", query(apify.actor_endpoint(actor, "/runs"),
                      {"token": token, "timeout": apify.RUN_TIMEOUT}),
        {}, payload)
    if not ok(status):
        raise ProviderError("apify start %s: %s" % (actor, status))
    run = mapping(data, "apify start").get("data") or {}
    if not run.get("id"):
        raise ProviderError("apify start returned no run id")
    return {"id": run["id"], "dataset_id": run.get("defaultDatasetId")}


def _label(name, profile):
    return name if not profile else "%s:%s" % (name, profile)


def _profile_key(name, profile):
    """Company actors share the domain key; person actors get their own.

    THE OPERATOR ASKED FOR BOTH KEYS AND THIS IS WHERE THEY DIVERGE. One
    account whose champion changed must re-buy that champion and not the
    company posts, so a person run is cached under the profile and a
    company run under the actor name.
    """
    return profile if name == "person_posts" else name


def build(domain, live=False, champion=None, exec_profile=None, client=None,
          runner=None, now=None, company_url=None, config=None):
    """One account's pack. Cache first, actors only with `live=True`."""
    domain = str(domain or "").strip().lower().lstrip("@")
    if not domain:
        raise PackRefused("a research pack needs a domain")
    now = now or store.now()
    out = {"domain": domain, "built_at": now, "facts": [], "cost": 0,
           "cached": [], "bought": [], "skipped": []}

    wanted = [("company_posts", company_url or "https://%s" % domain, None),
              ("open_roles", domain, None)]
    for profile, url in (("champion", champion), ("exec", exec_profile)):
        if url:
            wanted.append(("person_posts", url, profile))

    for name, target, profile in wanted:
        label = _label(name, profile)
        hit = cache.get(domain, profile=_profile_key(name, profile), now=now)
        if hit:
            out["facts"].extend(hit.get("facts") or [])
            out["cached"].append(label)
            continue
        if not live:
            out["skipped"].append(label)
            continue
        found = run_actor(name, target, subject=profile, client=client,
                          runner=runner, config=config)
        cost = actorspec.ACTORS[name]["cost"]
        out["facts"].extend(found)
        out["cost"] += cost
        out["bought"].append(label)
        cache.put(domain, found, profile=_profile_key(name, profile),
                  cost=cost, now=now)

    out["fact_count"] = len(out["facts"])
    out["by_kind"] = {k: len([f for f in out["facts"] if f["kind"] == k])
                      for k in facts.KINDS}
    # THE PACK SAYS WHAT IT DOES NOT HAVE. A downstream step that reads an
    # empty pack as "nothing to say about them" and one that reads it as
    # "we never looked" write different emails.
    if out["skipped"]:
        out["note"] = ("built without live: %s were not bought, so an absent "
                       "fact here is an unasked question rather than an "
                       "answer" % ", ".join(out["skipped"]))
    return out
