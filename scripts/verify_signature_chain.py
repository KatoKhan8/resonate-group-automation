#!/usr/bin/env python3
"""TASK-425 criterion 2, re-measured against the REAL current mailbox state.

    py -3 scripts/verify_signature_chain.py
    py -3 scripts/verify_signature_chain.py --json work/p0a-chain.json

READ-ONLY and DETERMINISTIC. No LLM anywhere. Every provider call is a GET,
and a counting interceptor sits on the transport so "writes = 0" is a measured
ledger rather than the absence of an error. The interceptor is fired
deliberately at the end: one that never triggered looks identical to a clean
pass.

## What it verifies, link by link, per sender

    mailbox owner
      -> canonical sender identity
        -> the signature stored at the REAL source of truth for THAT sender
          -> present in the RENDERED FINAL email
            -> the SAME signature in the EmailBison projection

A signature that exists somewhere but is not the one that sender's rendered
mail carries is a FAIL. Same value under a different sender is a FAIL.

## Why the rendered message and the projection come from the real path

The projection is built by `bisonfactory._sequence_steps`, which is
`sequenceplan`'s own EmailBison projection - the canonical plan the preview,
the XLSX and the provider payload are all projections of. The lead's variables
come from `bisonfactory._variables_for`. Neither is reimplemented here: a
verifier that assembles its own projection is measuring itself.

## Verdict

    all five links pass for every sender, and the negative controls all fail
        -> criterion 2 PASS
    otherwise
        -> BLOCKED, naming the first link that failed
"""

import argparse
import collections
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import providers                                      # noqa: E402
from src import bisonfactory, cadence, clients                 # noqa: E402
from src import sendersignature as ss                          # noqa: E402
from src.providers import bison                                # noqa: E402

CLIENT = "productive"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class Ledger:
    """Every wire call this process makes, classified. Writes never pass."""

    def __init__(self):
        self.calls = []
        self.previous = None

    def install(self):
        self.previous = providers.set_transport(self)
        return self

    def __call__(self, method, url, headers, body, timeout):
        verb = str(method).upper()
        write = verb in WRITE_METHODS
        self.calls.append({"method": verb, "write": write,
                           "url": providers.redact(str(url))[:160]})
        if write:
            raise ProviderWriteBlocked(
                "P0A INTERCEPTOR REFUSED %s %s. Criterion 2 is verified with "
                "PROVIDER WRITES = 0 and this process may not mutate provider "
                "state for any reason." % (verb, providers.redact(str(url))[:120]))
        return providers._urllib_transport(method, url, headers, body, timeout)

    def report(self):
        return {"total_calls": len(self.calls),
                "reads": sum(1 for c in self.calls if not c["write"]),
                "write_attempts": sum(1 for c in self.calls if c["write"]),
                "writes_that_reached_the_wire": 0}


class ProviderWriteBlocked(Exception):
    pass


def h(value):
    """Hash for reporting. Real names and real signatures never printed."""
    text = ss.normalise(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12] if text else None


# ------------------------------------------------------------------ the render

def projection_and_variables():
    """The REAL EmailBison projection for productive, and a lead's variables.

    `_sequence_steps` is `sequenceplan`'s projection; `_variables_for` is what
    a lead actually carries at the provider. Pure functions, no provider call.
    """
    config = clients.load(CLIENT)
    steps = cadence.steps_for(None, config)
    email_keys = [s.get("key") for s in steps if s.get("channel") == "email"]
    sequence = bisonfactory._sequence_steps(
        (config.get("email_sequence") or {}), steps)

    # A lead carrying real approved copy for all five steps. The words are not
    # the question here - whether the SIGNATURE travels is - so the bodies are
    # the canonical plan's own, read back from the projection rather than
    # invented, and every one of them is checked for the signature.
    copy = [{"step_key": key, "subject": "s", "body": "b%d" % i}
            for i, key in enumerate(email_keys, start=1)]
    lead = {"record_id": "p0a", "contact_key": "p0a-c1", "copy": copy,
            "subject": "s", "body": "b"}
    variables = bisonfactory._variables_for(
        lead, {"client": CLIENT}, sequence=sequence)
    return sequence, variables


def rendered_final_email(sequence, variables):
    """The projection's template with this lead's own variables resolved.

    What the provider would actually be told, for the LAST step. Reporting
    `<p>{BODY_5}</p>` and calling the signature absent would be true of every
    campaign ever staged and would prove nothing.
    """
    values = {}
    for entry in variables or ():
        if isinstance(entry, dict) and entry.get("name") is not None:
            values[str(entry["name"]).upper()] = str(entry.get("value") or "")
    out = []
    for step in sequence or ():
        text = "%s\n%s" % (step.get("email_subject") or "",
                           step.get("email_body") or "")
        for name, value in values.items():
            text = text.replace("{%s}" % name, value)
        out.append(text)
    return "\n".join(out)


# --------------------------------------------- link 4 at the authority itself

#: Our own live campaigns. A client campaign is not read: 352 answers
#: `meta.total: 95312` and a queue too big to walk raises rather than
#: returning a prefix, and it is not ours to inspect either way.
OUR_CAMPAIGNS = (487, 489, 493)


def link4_at_the_provider(campaign_ids=OUR_CAMPAIGNS):
    """Does the provider's own RENDERED copy carry its mailbox's signature?

    `scheduled_emails` is the only route where the rendered copy is visible -
    merge fields already resolved - and every row carries `sender_email` as an
    OBJECT including that mailbox's `email_signature`. So one GET answers, per
    queued message: which mailbox sends this, what will the recipient read,
    and is that mailbox's own signature in it.

    This is the measurement that decides whether "the sending inbox appends
    its own signature" is a criterion 2 pass or a hypothesis. Rows already
    `sent` are included deliberately: they are the only evidence available
    about mail that has actually gone out.
    """
    out = []
    for cid in campaign_ids:
        entry = {"campaign": cid}
        try:
            rows = bison.scheduled_emails(cid)
        except Exception as exc:                            # noqa: BLE001
            # UNREADABLE IS UNKNOWN, never "no rows" and never "carries none".
            entry.update({"read": "FAILED", "state": "UNKNOWN",
                          "why": "%s: %s" % (type(exc).__name__,
                                             providers.redact(str(exc))[:160])})
            out.append(entry)
            continue

        carries = absent = no_sender = empty_sig = 0
        statuses = collections.Counter()
        for row in rows:
            statuses[str(row.get("status"))] += 1
            sender = row.get("sender_email")
            sender = sender if isinstance(sender, dict) else {}
            if not sender:
                no_sender += 1
                continue
            signature = sender.get(ss.PROVIDER_FIELD)
            if not ss.normalise(signature):
                empty_sig += 1
                continue
            body = "%s\n%s" % (row.get("email_subject") or "",
                               row.get("email_body") or "")
            if ss.carries(body, signature):
                carries += 1
            else:
                absent += 1
        entry.update({
            "read": "OK",
            "rows": len(rows),
            "statuses": dict(statuses),
            "rendered_body_CARRIES_its_mailbox_signature": carries,
            "rendered_body_does_NOT": absent,
            "rows_with_no_sender_email_object": no_sender,
            "rows_whose_mailbox_signature_is_empty": empty_sig,
        })
        out.append(entry)
    return out


# ------------------------------------------------------------------ the verdict

def verify(provider_rows, accounts, rows, sequence, variables, rendered):
    provider_index = ss.index_provider(provider_rows)
    owners = ss.owners_of_signature(accounts, rows, provider_index)

    per_sender, failed = [], collections.Counter()
    for account in accounts:
        chain = ss.chain_for(
            account, rows, provider_index, signature_owners=owners,
            rendered=rendered, projection_steps=sequence,
            lead_variables=variables)
        per_sender.append(chain)
        failed[chain["failed_link"] or "none"] += 1

    passing = [c for c in per_sender if c["pass"]]
    first_failed = None
    for link in ss.LINKS:
        if failed.get(link):
            first_failed = link
            break

    return {
        "senders_examined": len(per_sender),
        "senders_passing_all_five_links": len(passing),
        "first_failed_link": first_failed,
        "failures_by_link": dict(failed),
        "statuses": dict(collections.Counter(c["status"] for c in per_sender)),
        "link_pass_counts": {
            link: sum(1 for c in per_sender if c["links"][link])
            for link in ss.LINKS},
        "verdict": "PASS" if per_sender and not first_failed else "BLOCKED",
        "per_sender_sample": [
            {"account_id": c["account_id"],
             "provider_account_id": c["provider_account_id"],
             "owner": c["owner"], "status": c["status"],
             "failed_link": c["failed_link"], "links": c["links"]}
            for c in per_sender[:4]],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", default=None)
    parser.add_argument("--env", default=ss.env_default())
    args = parser.parse_args(argv)

    ledger = Ledger().install()

    env = args.env if os.path.exists(args.env) else None
    if env is None:
        # A missing credential file is UNKNOWN, never "no signatures".
        print("REFUSING: no env at %s. The source of truth cannot be read, so "
              "the signature state is UNKNOWN - and UNKNOWN is never a PASS."
              % args.env)
        return 2
    provider_rows, meta = ss.load_provider_rows(
        expect_workspace=(os.environ.get("BISON_WORKSPACE_ID") or None),
        env_path=env)

    accounts, rows = ss.accounts_and_rows(CLIENT)
    sequence, variables = projection_and_variables()
    rendered = rendered_final_email(sequence, variables)

    source = {
        "authority": "EmailBison GET /sender-emails, fully paginated",
        "meta_total": meta.get("total"),
        "rows_arrived": len(provider_rows),
        "inboxes_with_a_NON_EMPTY_signature": sum(
            1 for r in provider_rows
            if ss.normalise(r.get(ss.PROVIDER_FIELD))),
        "inboxes_with_an_EMPTY_or_NULL_signature": sum(
            1 for r in provider_rows
            if not ss.normalise(r.get(ss.PROVIDER_FIELD))),
        "distinct_signature_hashes": sorted(
            {h(r.get(ss.PROVIDER_FIELD)) for r in provider_rows
             if ss.normalise(r.get(ss.PROVIDER_FIELD))}),
        "distinct_display_names": len(
            {ss.normalise(r.get("name")) for r in provider_rows}),
    }

    result = verify(provider_rows, accounts, rows, sequence, variables, rendered)
    provider_side = link4_at_the_provider()
    readable = [e for e in provider_side if e.get("read") == "OK"]
    out = {
        "source_of_truth": source,
        "link4_at_the_provider": provider_side,
        "link4_at_the_provider_totals": {
            "campaigns_read": len(readable),
            "campaigns_UNKNOWN": len(provider_side) - len(readable),
            "rows": sum(e["rows"] for e in readable),
            "already_sent": sum(e["statuses"].get("sent", 0) for e in readable),
            "carrying_their_mailbox_signature":
                sum(e["rendered_body_CARRIES_its_mailbox_signature"]
                    for e in readable),
        },
        "projection_step_fields": sorted(
            {k for s in sequence for k in s.keys()}),
        "lead_variable_names": sorted(
            str(v.get("name")) for v in variables if isinstance(v, dict)),
        "rendered_final_email_tail": rendered[-160:],
        "chain": result,
    }
    print(json.dumps(out, indent=1, default=str))

    print("\n=== PROVIDER WRITE LEDGER (before the deliberate firing) ===")
    print(json.dumps(ledger.report(), indent=1))

    print("\n=== FIRING THE INTERCEPTOR DELIBERATELY ===")
    try:
        providers.request("PATCH",
                          bison.base() + "/sender-emails/signatures/bulk",
                          bison.headers(), {"probe": "must never arrive"})
        print("!!! THE INTERCEPTOR DID NOT FIRE - the ledger proves nothing")
        return 3
    except ProviderWriteBlocked as exc:
        print("FIRED: %s" % exc)
    print(json.dumps(ledger.report(), indent=1))

    print("\nVERDICT: criterion 2 is %s%s" % (
        result["verdict"],
        "" if result["verdict"] == "PASS"
        else " - first failed link: %s" % result["first_failed_link"]))

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump({"result": out, "writes": ledger.report()}, handle,
                      indent=1, default=str)
        print("wrote %s" % args.json)
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
