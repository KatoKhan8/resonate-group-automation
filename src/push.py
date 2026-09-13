#!/usr/bin/env python3
"""Push preparation. BUILD-SPEC section 5.4, 5.5 and phase 7.

This module prepares. It does not send.

There is no HTTP call to EmailBison or HeyReach anywhere in this build: `--live`
exists as the explicit gate the spec requires, and it refuses with an
explanation rather than performing a send. Everything up to the exact request
payload is built, checked and testable offline.

Two invariants matter more than anything else here:

  1. Nothing reaches a payload without passing lint as a finished email. A
     template is expanded first and the expanded subject and body are what get
     checked, so a template variable cannot smuggle a violation through.

  2. A step is pushed at most once. Identity is
     record:contact:day:channel, persisted on the record, so a retry after a
     crash finds the step already marked and skips it.

  python -m src.push --day 21          what would go where, and why not
  python -m src.push --day 21 --live   refuses: live sending is not built
"""
import argparse

from . import cadence, clients, events, killswitch, lint, pilotcaps, store
from .providers import bison, heyreach

EMAIL = "email"
LINKEDIN = "linkedin"


class LiveSendNotEnabled(RuntimeError):
    """--live was asked for, and this build cannot send. By design."""


def push_id(rec, contact_key, step_key, channel):
    """Stable logical identity for one send. Survives a crash and a restart."""
    return f"{rec['id']}:{contact_key}:{step_key}:{channel}"


def stored_step(rec, contact_key, step_key):
    return ((rec.get("cadence") or {}).get(contact_key) or {}).get(step_key) or {}


def already_pushed(rec, contact_key, step_key):
    """Has this step reached a state it must never leave? Asked before sending.

    Terminal is read from `stepstate`, not spelled out here. The literal
    this replaced was `== "pushed"`, which is the only terminal state
    anything currently writes - so a step recorded as `confirmed` (the
    provider said it went) or `cancelled` (a human or a reply ended it)
    answered False and could be sent a second time.

    Nothing writes those two today. `DATABASE-MIGRATION.md` names
    `stepstate.STATES` as the vocabulary of the status column, and
    `confirmed` is what a provider callback would naturally write, so the
    first thing to produce one would have found this rather than the test
    that now does.
    """
    from . import stepstate

    return stepstate.is_terminal(
        stored_step(rec, contact_key, step_key).get("status"))


def contact_by_key(rec, key):
    return lint.find_contact(rec, key)


def collect(recs, day, client=None, campaign_rows=None):
    """Every step that is eligible today, with the reason anything was skipped.

    A record's campaign decides its cadence: how many steps, on which days,
    and - once an experiment is running - which arm. Resolved here because
    a record does not know its campaign, and what is pushed has to be what
    the campaign says rather than the module constant.

    Deferred import: `campaigns` reaches back into this module for its dry
    run, so importing it at the top would be a cycle.
    """
    from . import campaigns

    ready, skipped = [], []
    # Once, not once per record: this is the quadratic term otherwise.
    paused_set = cadence.paused_domains(recs)
    of_record = campaigns.by_record(campaign_rows)
    for rec in recs:
        if client and rec.get("client") != client:
            continue
        try:
            config = clients.load(rec.get("client"))
        except clients.ConfigError as e:
            skipped.append({"id": rec["id"], "why": str(e)})
            continue

        timeline = cadence.build(rec, config, recs=recs,
                                 paused_set=paused_set,
                                 campaign=of_record.get(rec["id"]))
        if timeline["paused"]:
            skipped.append({"id": rec["id"],
                            "why": f"company paused: {timeline['paused'].get('reason')}"})
            continue

        for contact_key, steps in timeline["contacts"].items():
            contact = contact_by_key(rec, contact_key)
            for step_key, step in steps.items():
                if step["day"] > day:
                    continue
                if already_pushed(rec, contact_key, step_key):
                    # Name the state rather than assuming which one it is:
                    # "cancelled" and "already pushed" are different things
                    # for somebody reading a skip list.
                    state = stored_step(rec, contact_key,
                                        step_key).get("status")
                    skipped.append({"id": rec["id"], "contact": contact_key,
                                    "step": step_key,
                                    "why": f"already {state}"})
                    continue
                if step["status"] != "eligible":
                    skipped.append({"id": rec["id"], "contact": contact_key,
                                    "step": step_key,
                                    "why": step.get("blocked_by") or step["status"]})
                    continue
                ready.append({"record": rec, "contact": contact, "contact_key": contact_key,
                              "step_key": step_key, "step": step,
                              "channel": step["channel"],
                              # Carried so the last gate re-checks against
                              # the sequence this step came from rather
                              # than the module constant.
                              "campaign": of_record.get(rec["id"]),
                              "push_id": push_id(rec, contact_key, step_key,
                                                 step["channel"])})
    return ready, skipped


def verify_before_payload(item, campaign=None, recs=None, config=None):
    """The last gate before a payload exists. Re-checked, never assumed.

    Delegates to src/eligibility.py rather than re-deriving the rules: a second
    copy of "may this go out" is a second thing to get wrong, and the one that
    gets forgotten is always the one guarding the expensive mistake.

    This runs at payload-build time on purpose. Upstream state may have been
    computed minutes ago, or edited by hand, or arrived from a resumed run;
    everything here is recomputed from what it was derived from.
    """
    from . import eligibility

    from . import verification

    rec, contact = item["record"], item["contact"]
    decision = eligibility.decide(
        rec, contact, item["step_key"], channel=item.get("channel"),
        # An item built by `collect` knows which campaign it came from.
        # Without this the last gate rebuilds the default seven-step
        # timeline and judges a four-step campaign's day 8 against it.
        campaign=campaign if campaign is not None else item.get("campaign"),
        recs=recs, config=config,
        # The exact words about to be sent, not a rebuilt copy of them.
        step=item.get("step"))
    if not decision.eligible:
        raise AssertionError(
            f"{item['push_id']}: {decision['verdict']} - "
            + ", ".join(decision["reasons"]))

    # Said twice, on purpose. `eligibility.decide` already asks
    # `verification.is_sendable`, which recomputes - so this cannot fire while
    # that holds. It is here because an EmailBison payload is the last moment
    # anything is cheap to stop, and the confirmation rule is the one this
    # build most recently gained: a future edit that loosened the eligibility
    # path, or a caller that assembled an item by hand, would still meet this.
    # A guard that only exists once is a guard one refactor away from gone.
    if item.get("channel") == EMAIL:
        policy = verification.policy_for(config)
        resolved = verification.resolve(contact, policy)
        count = resolved["confirmation_count"]
        required = resolved["required_confirmations"]
        if count < required:
            raise AssertionError(
                f"{item['push_id']}: refusing to build an EmailBison payload "
                f"for an address with {count} of {required} required "
                f"independent verification confirmations "
                f"({', '.join(resolved['confirmed_by']) or 'none'})")
    return True


def _sender_of(contact, channel):
    """The stored assignment for this contact on this channel, flattened.

    Read off the contact rather than recomputed, because `assignment.ensure`
    stored it and a payload that disagreed with the stored assignment would
    send from an inbox the rest of the system does not think is sending.

    Returns empty rather than raising when nothing is assigned: an unassigned
    contact is a real state, and the launch checklist is where it gets
    refused, not here.
    """
    from . import assignment

    row = assignment.assigned(contact, channel) or {}
    return {
        "sender_id": row.get("sender_id") or "",
        "sender_name": row.get("display_name") or "",
        "sender_account_id": row.get("account_id") or "",
        "provider_account_id": row.get("provider_account_id") or "",
        "sender_address": row.get("address") or "",
    }


def emailbison_rows(items):
    rows = []
    for item in items:
        if item["channel"] != EMAIL:
            continue
        verify_before_payload(item)
        rec, contact, step = item["record"], item["contact"], item["step"]
        parts = (contact.get("name") or "").split()
        rows.append({
            **_sender_of(contact, EMAIL),
            "email": contact["email"],
            "first_name": parts[0] if parts else "",
            "last_name": " ".join(parts[1:]),
            "company": rec.get("company", ""),
            "title": contact.get("title", ""),
            "subject": step.get("subject", ""),
            "body": step.get("body", ""),
            "record_id": rec["id"],
            # Same reason as the LinkedIn side: the adapter reads both back and
            # neither was ever sent, so a reply named a company and never a
            # person.
            "contact_key": item["contact_key"],
            "client": rec.get("client", ""),
            "push_id": item["push_id"],
        })
    return rows


def heyreach_rows(items):
    rows, seen = [], set()
    for item in items:
        if item["channel"] != LINKEDIN:
            continue
        verify_before_payload(item)
        rec, contact, step = item["record"], item["contact"], item["step"]
        profile = contact["linkedin"]
        if profile in seen:
            continue                     # never the same profile twice in one push
        seen.add(profile)
        parts = (contact.get("name") or "").split()
        rows.append({
            **_sender_of(contact, LINKEDIN),
            "linkedin_url": profile,
            "first_name": parts[0] if parts else "",
            "last_name": " ".join(parts[1:]),
            "company": rec.get("company", ""),
            "title": contact.get("title", ""),
            "note": step.get("note", ""),
            "record_id": rec["id"],
            # Carried so the provider payload can name the person as well as
            # the company. `adapters._heyreach_event` reads both back off an
            # inbound conversation, and until now neither was ever sent.
            "contact_key": item["contact_key"],
            "client": rec.get("client", ""),
            "push_id": item["push_id"],
        })
    return rows


def payloads(items, bison_campaign_id=None, heyreach_campaign_id=None,
             linkedin_account_id=None, campaign_id=None,
             heyreach_sequence=None):
    """The exact request bodies phase 7's sender would post. Nothing is sent.

    `heyreach_sequence`, when given, is that campaign's live node graph and no
    payload is built if its copy needs a variable this push does not supply.
    It is a parameter rather than a fetch because this function is pure and
    every test depends on that; the live read belongs to the caller, which is
    what makes the check just-in-time rather than a stale snapshot. Passing
    nothing checks nothing, which is why `run()` is where the fetch is owed -
    a default that silently skipped the gate would be worse than no gate,
    since it would look checked.

    The two providers have separate campaign ids and they are not
    interchangeable. An earlier version took a single `campaign_id` and handed
    it to both, so a HeyReach payload carried an EmailBison campaign - which
    would either 404 or, far worse, add LinkedIn leads to whatever campaign
    happened to have that id. `campaign_id` is still accepted so existing
    callers keep working, but only as the EmailBison one.

    The LinkedIn *account* is a third thing again: which inbox sends, not which
    campaign receives. Passing a campaign id where an account id belongs is the
    same class of mistake, so it has its own parameter.
    """
    email_rows = emailbison_rows(items)
    linkedin_rows = heyreach_rows(items)
    bison_id = bison_campaign_id or campaign_id
    # Before the body exists, not after. A refusal must leave nothing that
    # looks postable behind it.
    #
    # The return value was discarded here. `refuse_unsupported_sequence`
    # raises on an unknown variable and RETURNS the hazards it cannot decide -
    # the Bison handoff among them - and throwing those away meant the one
    # fact that decides whether a LinkedIn push is LinkedIn-only was computed,
    # returned, and dropped without being logged or stored. It is carried out
    # in the payload now, under `linkedin`, so a caller cannot fail to have
    # been told.
    sequence_verdict = None
    if heyreach_sequence is not None and linkedin_rows:
        hazards = heyreach.refuse_unsupported_sequence(
            heyreach_sequence, rows=linkedin_rows,
            campaign_id=heyreach_campaign_id)
        proven, why = heyreach.linkedin_only(heyreach_sequence)
        sequence_verdict = {
            "linkedin_only": proven,
            "why": why,
            "hazards": [{"what": what, "detail": detail}
                        for what, detail in hazards],
        }
    elif linkedin_rows:
        # No sequence was fetched, so nothing is known about what this campaign
        # would actually send. Stated rather than left absent: an unfetched
        # sequence and a clean one must not look the same to a reader.
        sequence_verdict = {
            "linkedin_only": False,
            "why": ("no sequence was supplied, so what this campaign would "
                    "send is unknown - `push.payloads` was called without "
                    "`heyreach_sequence`"),
            "hazards": [],
        }
    return {
        "emailbison": {
            "endpoint": bison.leads_endpoint(bison_id or "<bison-campaign-id>"),
            "method": "POST",
            "body": bison.build_leads(email_rows),
            "count": len(email_rows),
        },
        "heyreach": {
            "endpoint": heyreach.add_leads_endpoint(),
            "method": "POST",
            "body": {"campaignId": heyreach_campaign_id,
                     "accountLeadPairs": heyreach.build_lead_pairs(
                         linkedin_rows, linkedin_account_id or 0)},
            "count": len(linkedin_rows),
            # Whether this campaign is provably LinkedIn-only, and why. None
            # when there are no LinkedIn rows at all.
            "sequence": sequence_verdict,
        },
        # Which humans and which accounts this push would involve. Not part of
        # either request body - it is what the preview and the audit read, so
        # that "who would this go out as" is answerable without unpicking two
        # different providers' payload shapes.
        "senders": sender_summary(email_rows, linkedin_rows),
    }


def sender_summary(email_rows, linkedin_rows):
    """Who would send what, grouped by human and by provider account."""
    out = {}
    for channel, rows in ((EMAIL, email_rows), (LINKEDIN, linkedin_rows)):
        people = {}
        for row in rows:
            key = row.get("sender_id") or "unassigned"
            bucket = people.setdefault(key, {
                "sender_id": row.get("sender_id") or None,
                "sender_name": row.get("sender_name") or None,
                "rows": 0, "accounts": set()})
            bucket["rows"] += 1
            if row.get("sender_account_id"):
                bucket["accounts"].add(row["sender_account_id"])
        out[channel] = sorted(
            ({**b, "accounts": sorted(b["accounts"])} for b in people.values()),
            key=lambda b: (-b["rows"], b["sender_id"] or ""))
    return out


def record_prepared(recs, ready):
    """Note that a step was prepared, once, whatever the run is repeated.

    The id is derived from the push identity, so a second dry run of the same
    day does not double count.
    """
    marked = 0
    by_id = {rec["id"]: rec for rec in recs}
    for item in ready:
        rec = by_id.get(item["record"]["id"])
        if rec is None:
            continue
        entry = events.record(rec, events.PUSH_PREPARED,
                              contact_key=item["contact_key"],
                              channel=item["channel"], step=item["step_key"],
                              push_id=item["push_id"],
                              id=f"{item['push_id']}:prepared")
        marked += 1 if entry else 0
    return marked


def mark_pushed(rec, contact_key, step_key, push_identity, at=None, day=None,
                sent=None):
    """Persist that one logical step has been sent. Through store, never around it.

    The sender travels onto the event, and that is not bookkeeping. A later
    step may say "my colleague Anna emailed you", and `src/touch.py` will only
    allow it if the confirming event names Anna. Reading the *current*
    assignment instead would let a reassignment rewrite history and put the
    wrong name in front of a prospect - so who sent it is recorded at the
    moment it is sent, and never looked up again.

    The variant travels for the same reason and had not been travelling.
    `account.touches` reads `variant_id` off the event and says attribution
    depends on it; `variants.journey_of` filters on it; `results_from`
    counts exposures from that journey. Nothing wrote it, so every journey
    was empty, every tally was `{}`, and every experiment reported
    INSUFFICIENT_DATA whatever had been sent - which looks exactly like a
    working evaluator waiting for volume.

    `sent` is the step as it went out. Passing it is how the copy that was
    actually sent gets recorded rather than the copy the record holds now:
    a variant edited after the fact would otherwise re-label a message
    nobody sent, and pool two wordings under one id.
    """
    cad = rec.setdefault("cadence", {}).setdefault(contact_key, {})
    step = cad.setdefault(step_key, {})
    step["status"] = "pushed"
    step["push_id"] = push_identity
    step["pushed_at"] = at or store.now()
    channel = push_identity.rsplit(":", 1)[-1]

    contact = next((c for c in rec.get("contacts") or []
                    if c.get("key") == contact_key), None)
    sender = _sender_of(contact, channel) if contact else {}
    carried = sent if sent is not None else step

    store.log(rec, "pushed", f"{push_identity}")
    # `at` reaches the event, not only the step. It was applied to
    # `step["pushed_at"]` and dropped here, so the step said when the
    # caller sent it and the event said when this ran - and the event is
    # what `account.touches` reads, which is what attribution and exposure
    # both count from. A backfill or a replay wrote today's date onto every
    # touch it recreated.
    # WHY THIS MESSAGE, PINNED TO THE MESSAGE.
    #
    # The persona, the angle and the evidence the copy was built from all
    # live on the CONTACT, and the next generation overwrites them. So the
    # questions this system exists to answer - which personas reply, which
    # angles work, which evidence creates a reply - were being asked of
    # whatever the contact happened to say later, not of what was sent.
    #
    # That is not a reporting inconvenience. Read at send time it is a
    # measurement; read afterwards it is a guess that looks like one, and
    # `outcomes` was correctly reporting those dimensions as INFERRED. Every
    # send made before this is permanently unattributable.
    #
    # Same reasoning as the sender and the variant two lines below, both of
    # which had to learn it first.
    decision = (contact or {}).get("personalization") or {}
    events.record(rec, events.PUSH_MARKED, contact_key=contact_key,
                  at=at,
                  channel=channel, step=step_key,
                  push_id=push_identity, id=f"{push_identity}:pushed",
                  day=day if day is not None else step.get("day"),
                  sender_id=sender.get("sender_id") or None,
                  account_id=sender.get("sender_account_id") or None,
                  persona=(contact or {}).get("persona") or None,
                  angle=carried.get("angle") or (contact or {}).get("angle")
                  or None,
                  evidence_ids=list(decision.get("selected_evidence_ids")
                                    or []) or None,
                  evidence_level=decision.get("level") or None,
                  variant_id=carried.get("variant_id") or None,
                  variant_style=carried.get("variant_style") or None,
                  variant_version=carried.get("variant_version"))
    return step


def _pilot_config(recs, client):
    """The client config the caps are read from, or {} if it cannot be read.

    A config that fails to load must not quietly raise the ceiling: `{}` means
    pilot mode on and the ceiling applies, which `pilotcaps.enabled` documents
    as the one forgetting that costs nothing.
    """
    slug = client or (recs[0].get("client") if recs else None)
    if not slug:
        return {}
    try:
        return clients.load(slug)
    except Exception:
        return {}


def run(day=21, live=False, client=None, campaign_id=None, linkedin_account_id=None):
    """Dry run by default. Nothing is sent, and nothing is marked as sent."""
    if live:
        raise LiveSendNotEnabled(
            "live push is not implemented in this build. Phase 7 ships preparation "
            "only: payloads, eligibility, pause and idempotency. No code here can "
            "reach EmailBison or HeyReach.")
    recs = store.load()
    ready, skipped = collect(recs, day=day, client=client)
    prepared = payloads(ready, bison_campaign_id=campaign_id,
                        linkedin_account_id=linkedin_account_id)
    # What this batch would consume, against the pilot ceiling. `pilotcaps`
    # had no importer at all outside its own tests - `require` was documented
    # as "the gate a runner would call" and no runner called it - so the
    # ceilings were arithmetic nobody consulted.
    #
    # Reported here and enforced by the sender, for a reason worth stating
    # because the first attempt got it wrong. Refusing the batch at
    # preparation time was tried and is incorrect twice over. `day` is a
    # cadence day and not a calendar day, so the count in one run is not the
    # quantity `email_per_day` limits; and preparation is not the constrained
    # resource - a prepared payload costs nothing until something sends it.
    # Enforcing on a mis-mapped quantity is worse than not enforcing, because
    # it produces a refusal somebody will learn to route around.
    #
    # The honest enforcement point is the sender, counting real sends against
    # a real calendar day. `pilotcaps.require` is that gate and is deliberately
    # left for it. See PRODUCT-GAPS.md.
    plan = {"email_per_day": prepared["emailbison"]["count"],
            "linkedin_per_day": prepared["heyreach"]["count"]}
    caps = pilotcaps.check(plan, _pilot_config(recs, client))
    return {"live": False, "day": day, "ready": ready, "skipped": skipped,
            "payloads": prepared, "caps": caps,
            # Reported, not enforced here, and the distinction is the point.
            # `killswitch` had no importer outside its own tests, so
            # `sending.live` was a real setting with an audit entry that
            # stopped nothing. Enforcement belongs to whatever sends, which is
            # why `killswitch.require` exists and why this run cannot call it:
            # every layer would refuse - correctly, the build cannot send - and
            # a dry run that refuses itself prepares no payload for anyone to
            # review. So the verdict travels with the preparation instead, and
            # an operator can see which layers would stop this before anything
            # is enabled rather than discovering it on the day.
            "sending": killswitch.state(
                workspace=(recs[0].get("client") if recs else None)),
            "counts": {"email": prepared["emailbison"]["count"],
                       "linkedin": prepared["heyreach"]["count"],
                       "skipped": len(skipped)}}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.push")
    p.add_argument("--day", type=int, default=21)
    p.add_argument("--client")
    p.add_argument("--campaign")
    p.add_argument("--sender-account", type=int)
    p.add_argument("--live", action="store_true",
                   help="explicit gate; this build refuses and explains why")
    a = p.parse_args(argv)

    if a.live:
        print("REFUSED: live push is not implemented in this build.")
        print("Phase 7 prepares payloads only. Nothing here can send.")
        return 2

    result = run(day=a.day, client=a.client, campaign_id=a.campaign,
                 linkedin_account_id=a.sender_account)
    print(f"DRY RUN, day {a.day}. Nothing sent.\n")
    print(f"EmailBison: {result['counts']['email']} lead(s) would be added to "
          f"{result['payloads']['emailbison']['endpoint']}")
    for row in result["payloads"]["emailbison"]["body"]["leads"]:
        print(f"  {row['email']:<36} {row['custom_variables']['subject'][:44]}")
    print(f"\nHeyReach: {result['counts']['linkedin']} profile(s) would be added to "
          f"{result['payloads']['heyreach']['endpoint']}")
    for pair in result["payloads"]["heyreach"]["body"]["accountLeadPairs"]:
        lead = pair["lead"]
        print(f"  {lead['profileUrl']:<52} {lead['customUserFields'][0]['value'][:40]}")
    if result["skipped"]:
        print(f"\nnot pushed ({len(result['skipped'])}):")
        for s in result["skipped"]:
            where = s["id"]
            if s.get("contact"):
                where = f"{where}:{s['contact']}:{s.get('step')}"
            print(f"  {where:<44} {s['why']}")
    print("\nadd --live to push. This build refuses: preparation only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
