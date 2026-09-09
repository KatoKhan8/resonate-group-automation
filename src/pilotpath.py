#!/usr/bin/env python3
"""The path a real company takes, and what stands behind each step of it.

## Why this is code and not a document

A document describing the pipeline is accurate on the day it is written.
This is the same description with the parts a machine can check: every
stage names the test modules that cover it, and a test asserts those
modules exist. A stage whose coverage is deleted stops being a claim and
starts being a failure.

It is also the answer to a question that had no single answer: *what,
exactly, has to work for twenty companies to go through this safely.* That
was spread across nine documents and the heads of whoever wrote them.

## What each field means, and why these fields

    canonical   where the truth lives after this stage. Named by its
                module rather than by a path: every state file is
                overridable by environment, `store` is the only module
                allowed to name one, and a literal path here would be
                both a second name for it and wrong under a test harness
    decision    what is being decided, in the words somebody would use
    failure     what it looks like when this stage goes wrong - not an
                exception name, the operational shape of the failure
    idempotent  the key that makes running it twice safe, or None with a
                reason. `None` here is a real answer for a pure read
    tenancy     what stops this stage crossing a workspace
    tests       the modules that cover it, checked to exist
    live        what has never been exercised against a real counterpart

`live` is the field that decides whether a pilot can send. Everything else
can be green while that column is full, and a summary that reported one
without the other is how a fixture becomes a promise.

## It asserts nothing about quality

A stage listed here with tests is a stage somebody wrote tests for. That
is not the same as a stage that is correct, and this module does not claim
otherwise. What it can prove is the absence of the cheaper failure: a
stage nobody covered at all.
"""
import argparse
import importlib.util
import json

# Live validation classes, matching LIVE-READINESS.md so the two cannot
# drift into different vocabularies.
NONE_NEEDED = None
READ = "live read validation required"
WRITE = "live write validation required"
BLOCKING = "blocking: refused in code, not by a flag"

# A pure read decides nothing and stores nothing, so running it twice is
# safe by construction. Spelled out rather than left blank: an empty
# idempotency field reads as an oversight.
PURE_READ = "pure read: no state written, safe to repeat"


def stage(name, canonical, decision, failure, idempotent, tenancy, tests,
          live=NONE_NEEDED, note=None):
    return {"stage": name, "canonical": canonical, "decision": decision,
            "failure": failure, "idempotent": idempotent, "tenancy": tenancy,
            "tests": tuple(tests), "live": live, "note": note}


STAGES = (
    stage("workspace",
          "the workspace table, through workspaces",
          "which tenant is this, and may this user act in it",
          "a user acts in a workspace they do not belong to",
          "workspace slug",
          "Repo.for_user is the only constructor; 404 rather than 403",
          ("test_workspaces", "test_repo", "test_web_security")),

    stage("import",
          "the record queue, through store",
          "which rows become records, and which are refused",
          "a malformed CSV half-imports and nobody knows which half",
          "batch id plus row identity",
          "the batch carries the workspace; upload writes through Repo",
          ("test_ingest", "test_import_contacts", "test_web_app")),

    stage("normalize",
          "the record, at write time",
          "what this domain and this mailbox actually are",
          "two spellings of one company become two companies",
          "deterministic: the same input normalises identically",
          "no cross-record read",
          ("test_ingest", "test_dedupe")),

    stage("dedupe",
          "the record queue, through store",
          "is this the same company, or the same person",
          "five people at one company import as one company and four losses",
          "strong identity: normalised mailbox, canonical profile URL, "
          "provider lead id. A name is never identity",
          "duplicates are only sought within the workspace",
          ("test_dedupe", "test_duplicates", "test_import_contacts")),

    stage("history and hygiene",
          "the engagement index, plus the record's own events",
          "have we dealt with this company or person before",
          "a new list quietly re-contacts somebody who asked us to stop",
          "hashed identity per workspace",
          "the engagement index is per workspace; agency DNC is global "
          "by design and hashed",
          ("test_hygiene", "test_hygiene_lifecycle", "test_client_review")),

    stage("ICP",
          "record.qualification.verdict",
          "is this company in the client's ICP, or does a person decide",
          "a review verdict is read as a rejection, or as a pass",
          "deterministic from the record and the client config",
          "the client config is the workspace's",
          ("test_icp", "test_qualify_resume", "test_icp_review")),

    stage("account",
          "the record, plus its event log",
          "what is true of this company as a whole",
          "an account-level fact is derived per contact and disagrees "
          "with itself",
          PURE_READ,
          "account.graph reads one record",
          ("test_account_outreach", "test_account_policy")),

    stage("contact and decision maker",
          "record.contacts",
          "who at this company is worth writing to, and in what order",
          "a contact is created without an identity and cannot be "
          "addressed to a provider",
          "contact key derived from strong identity",
          "contacts live on the record",
          ("test_personas", "test_dedupe", "test_import_contacts")),

    stage("enrichment",
          "record.contacts and the waterfall ledger",
          "what is missing, and is it worth a credit",
          "credits are spent on a company nobody qualified",
          "spend() writes the ledger; a repeat run re-reads the cap",
          "enrichment runs per record, within the batch's workspace",
          ("test_enrich", "test_waterfall", "test_contactout_first"),
          READ),

    stage("email verification",
          "contact.verification.evidence",
          "may this mailbox be written to at all",
          "a provider failure is read as valid",
          "one entry per provider per address; re-decided from evidence",
          "verification is per contact on a scoped record",
          ("test_verification", "test_double_verification", "test_mx"),
          READ),

    stage("segment",
          "record.qualification.segment_key",
          "which companies are one group, and why",
          "one campaign is four stories wearing one name",
          "deterministic from the record",
          "segmentation reads scoped records",
          ("test_icp", "test_campaigns", "test_request_scale")),

    stage("account intelligence",
          "the signal store, plus derived first-party signals",
          "what is happening there, and how much of it is still true",
          "a signal is read as permission to mention it",
          "stored signals are append-only and identified per row; "
          "first-party signals are derived and never stored",
          "signals carry their workspace and are loaded per workspace",
          ("test_signals", "test_observations")),

    stage("campaign",
          "the campaign store, through store",
          "which accounts, which cadence, which senders",
          "a campaign includes an account that may never be written to",
          "campaign id",
          "campaigns.load is filtered by the caller's workspace",
          ("test_campaigns", "test_campaign_e2e", "test_web_campaign_builder")),

    stage("playbook",
          "the campaign, plus playbooks.recommend at read time",
          "which approach fits this account",
          "a playbook is applied to an account whose signals do not "
          "support it",
          PURE_READ,
          "reads one scoped record",
          ("test_playbook", "test_playbooks")),

    stage("sender assignment",
          "contact.sender_assignment",
          "which human writes to this person, on which channel",
          "a message goes out from an inbox nobody thinks is sending",
          "sticky: an assigned channel is skipped entirely on re-run",
          "senders are per workspace; a sender outside it is refused",
          ("test_sender_identity", "test_senders", "test_web_senders")),

    stage("variant",
          "contact.variant_assignment and the touch event",
          "which of five copies this person gets",
          "a page refresh moves somebody from A to D",
          "assignment is derived and persisted, never re-rolled",
          "experiments and learning are per workspace",
          ("test_variants", "test_learning")),

    stage("context pack",
          "assembled at read time from scoped records",
          "why these companies, why now, what has already been said",
          "a planned touch is described as contact that happened",
          PURE_READ,
          "built from repo.records(), never widened",
          ("test_contextpack", "test_context_history")),

    stage("claim licensing",
          "the event log for our claims; evidence rows for theirs",
          "what a message is allowed to assert",
          "\"my colleague Anna emailed you\" when Mark sent it",
          PURE_READ,
          "claims resolve against one scoped record",
          ("test_account_outreach", "test_observations",
           "test_cross_channel_copy", "test_evidence_ageing")),

    stage("message QA",
          "the draft on the record, re-linted at read time",
          "is this draft shippable, and does it claim only what is "
          "supported",
          "a rule is widened to let a draft through",
          "deterministic from the record and the step",
          "QA reads one scoped record",
          ("test_lint", "test_qa", "test_campaign_qa", "test_coherence")),

    stage("approval",
          "record.cadence[contact][step].approval and the campaign",
          "has a human agreed to this exact text",
          "an edit after approval ships unreviewed",
          "fingerprint of the content; an edit invalidates it",
          "approval is recorded against a scoped record",
          ("test_approve", "test_orchestration", "test_web_approval_audit")),

    stage("provider payload",
          "built at read time; nothing is stored",
          "what would be posted, to which provider campaign",
          "a HeyReach payload carries an EmailBison campaign id",
          "push id: record:contact:step:channel",
          "payloads are built from scoped records",
          ("test_push", "test_transport", "test_wire_contracts"),
          WRITE),

    stage("pre-send recheck",
          "re-derived from primary state at payload time",
          "may this specific step still go out, right now",
          "a reply that arrived after approval does not stop step four",
          "the decision is a pure function of current state",
          "the record is already scoped when it arrives here",
          ("test_eligibility", "test_push", "test_reply_transitions")),

    stage("confirmed send",
          "the record's event log",
          "did this actually reach the prospect",
          "a prepared payload is counted as a send",
          "push id; the event is written once per logical step",
          "events live on the scoped record",
          ("test_push", "test_events", "test_cross_channel"),
          BLOCKING,
          "push.run(live=True) raises. There is no code path to either "
          "provider; this is not a flag"),

    stage("reply ingestion",
          "the record's event log",
          "did somebody answer, and which of our messages",
          "one reply is counted twice, or matched to the wrong person",
          "the provider's own event id",
          "the payload names the client; an ambiguous one is refused "
          "rather than guessed",
          ("test_replies", "test_transport", "test_transport_e2e"),
          READ),

    stage("classification",
          "the reply event, plus the policy decision",
          "what did they actually say",
          "a classifier misreads a message and outreach continues",
          "derived from the stored reply; re-running changes nothing",
          "classification reads one scoped record",
          ("test_replies", "test_reply_transitions", "test_account_policy")),

    stage("hold, pause and suppression",
          "record.paused, record.suppression, the suppression file",
          "who must not be written to now, and who never again",
          "a pause is applied to one contact and the company keeps going",
          "state is idempotent: applying the same outcome twice is one "
          "pause",
          "suppression files are per workspace; agency DNC is hashed",
          ("test_account_policy", "test_hygiene", "test_web_pause_replies")),

    stage("Slack",
          "the notification outbox",
          "who needs to know, in which channel",
          "a client's room learns about another client",
          "notification id derived from the occurrence",
          "routing is per workspace with no fallback between levels",
          ("test_notify", "test_notify_pipeline", "test_slack",
           "test_slack_route", "test_interactions"),
          WRITE),

    stage("provider tag sync",
          "the provider tag outbox",
          "what the providers should be told about this contact",
          "canonical state is changed to match what a provider accepted",
          "workspace, record, contact, provider",
          "rows carry their workspace and are filtered on read",
          ("test_tagsync",),
          BLOCKING,
          "tagsync.send refuses unconditionally: no tag endpoint on "
          "either provider has been validated"),

    stage("reporting",
          "derived at read time from the event log",
          "what actually happened, with the denominator",
          "approved is counted as sent",
          PURE_READ,
          "every report is built from scoped records",
          ("test_reporting", "test_client_reports", "test_web_analytics")),
)

REQUIRED = ("stage", "canonical", "decision", "failure", "idempotent",
            "tenancy", "tests", "live")


def by_name(name):
    for row in STAGES:
        if row["stage"] == name:
            return row
    return None


def missing_tests():
    """Test modules a stage names that do not exist.

    The whole reason this is a module. A stage naming a deleted test file
    is a stage that reads as covered.
    """
    out = []
    for row in STAGES:
        for name in row["tests"]:
            if importlib.util.find_spec("tests." + name) is None:
                out.append({"stage": row["stage"], "module": name})
    return out


def uncovered():
    """Stages naming no test at all."""
    return [row["stage"] for row in STAGES if not row["tests"]]


def live_required():
    return [{"stage": r["stage"], "class": r["live"], "note": r["note"]}
            for r in STAGES if r["live"]]


def blocking():
    return [r["stage"] for r in STAGES if r["live"] == BLOCKING]


def summarise():
    return {
        "stages": len(STAGES),
        "with_tests": len([r for r in STAGES if r["tests"]]),
        "missing_test_modules": missing_tests(),
        "uncovered": uncovered(),
        "live_required": live_required(),
        "blocking": blocking(),
        "note": "a stage with tests is a stage somebody covered. That is "
                "not the same as a stage that is correct, and this module "
                "does not claim otherwise",
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.pilotpath",
                               description=__doc__)
    p.add_argument("--json", action="store_true")
    p.add_argument("--stage")
    a = p.parse_args(argv)

    if a.stage:
        found = by_name(a.stage)
        if found is None:
            print(f"no such stage: {a.stage}")
            return 1
        print(json.dumps(found, indent=2, default=str))
        return 0

    if a.json:
        print(json.dumps({"stages": list(STAGES), "summary": summarise()},
                         indent=2, default=str))
        return 0

    found = summarise()
    for row in STAGES:
        flag = f"  [{row['live']}]" if row["live"] else ""
        print(f"{row['stage']:<28} {len(row['tests'])} test module(s){flag}")
    print()
    print(f"{found['stages']} stages, {found['with_tests']} with tests")
    if found["missing_test_modules"]:
        print("MISSING TEST MODULES:")
        for row in found["missing_test_modules"]:
            print(f"  {row['stage']}: {row['module']}")
    if found["blocking"]:
        print("BLOCKING: " + ", ".join(found["blocking"]))
    print("\n" + found["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
