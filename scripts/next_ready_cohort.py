#!/usr/bin/env python3
"""The maximum ADDITIONAL genuinely READY cohort, per channel, today.

    py -3 scripts/next_ready_cohort.py [--json out.json]

STRICTLY READ-ONLY. Writes nothing to any provider and nothing to `work/`.
Every provider call below is a GET. Nothing here stages, activates, pauses or
re-approves anything, and it deliberately does not import `providerwrites`.

WHY A SEPARATE SCRIPT. `scripts/linkedin_ready_truth.py` answers this for
LinkedIn only, and it screens approval on `approval.by == "operator-control-arm"`
- which is an ATTRIBUTION, not a fingerprint. This asks the question
`executionguard` actually asks, on both channels, and in the guard's own order,
so that "the first gate that stops them" is the gate that would really stop
them.

THE LADDER, IN `executionguard.authorize` ORDER, restricted to the gates that
are a fact about a CONTACT rather than about a campaign that does not exist
yet:

  copy              every step the channel's sequence needs renders
  tenancy           the record belongs to the campaign's client
  approval          `approval.fingerprint(step) == step.approval.fingerprint`
  eligibility       `eligibility.decide(...)` says eligible
  suppression       none of `executionguard.SUPPRESSION_REASONS` is named
  copy_lint         `lint.check_step` refuses nothing
  claims            `claims.check` refuses nothing
  fatigue           `fatigue.check` says ok
  collision         per-contact, per-channel, EXACTLY as the guard calls it
  account_collision `check_account` + `account_policy` == allow

The campaign-level gates - campaign_approval, readback, sender, pilot_cap,
stoppability, ledger, killswitch - are NOT evaluated and cannot be: they are
properties of the campaign row, the provider read-back and the day's ledger,
and the next batch has no campaign row yet. A contact this script calls READY
is a contact whose own facts are clean; the batch that stages it still has to
pass those seven.

THE APPROVAL GATE IS THE FOUR-ARGUMENT CALL, AND THAT IS THE WHOLE POINT.
`approval.is_approved(rec, key, step_key)` with no fourth argument compares the
STORED step to itself, so it returns True for any step carrying an approval
object whatever the words now say. Measured here on 2026-09-17: on the email
channel the three-argument form passes 23 contacts and the four-argument form
passes 10. The thirteen it disagrees about are contacts whose copy was
regenerated after approval - approved words that no longer exist.

THE LINKEDIN COLLISION CALL'S ARGUMENTS ARE ALSO THE POINT, and the reason is
recorded in `scripts/linkedin_ready_truth.py`: the RAW `linkedin` value, the
contact NAME, and the client SLUG. Canonicalising the URL first, dropping the
name, or passing the numeric workspace each returns `clear` on a profile the
guard refuses.

TWO PASSES, BECAUSE "WHAT STOPS THEM" AND "WHAT WOULD UNBLOCK THEM" ARE
DIFFERENT QUESTIONS. Pass A walks the ladder in order and stops at the first
refusal, so the counts add up to the population. Pass B then asks the SAFETY
questions - suppression, fatigue, collision, account - of everyone, including
the people pass A stopped earlier, because a contact held for missing copy may
also be a contact we must never write to, and reporting the first one without
the second would send somebody off to generate copy for a person who is
answered.

Identifiers are hashed. `tests/test_fixture_hygiene.py` is the contract: no
tracked file may carry a real name, domain, address or profile vanity.
"""
import argparse
import collections
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (approval, cadence, claims, clients, collision,    # noqa: E402
                 eligibility, executionguard, fatigue, lint, store,
                 verification)
from src.providers import load_env                                 # noqa: E402

CLIENT = "productive"
BISON_WORKSPACE = 10

# The sequence each channel's next batch would run. LinkedIn takes its steps
# from the cohort campaign's resolved cadence (li1..li5 plus the email legs);
# the staged graph needs li1..li5. Email takes them from campaign 487's own
# `cadence_steps`, which are em1..em3.
REQUIRED = {"linkedin": ("li1", "li2", "li3", "li4", "li5"),
            "email": ("em1", "em2", "em3")}
SHAPE_CAMPAIGN = {"linkedin": "productive-linkedin-cohort-v2",
                  "email": "productive-email-control-v3"}

# The contacts already on a LIVE campaign. Read from the action ledger rather
# than hard-coded, so this cannot drift from what actually went out.
#
# 489 ADDED 2026-09-18, AND LEAVING IT OUT MISREPORTED ITS FIVE PEOPLE.
# `classify` decides ALREADY_LIVE first, and deliberately, because a contact
# staged on a running campaign collides with ITSELF - `check_address` finds its
# own lead row. A live campaign missing from this tuple therefore does not
# merely go uncounted: its cohort reappears under SAFETY_BLOCK with
# `collision` as the gate, which reads as "we must not contact these people"
# about the exact five we just started contacting. Measured immediately after
# activation: EMAIL ALREADY_LIVE stayed 10, collision rose 10 -> 15.
LIVE_CAMPAIGNS = ("productive-linkedin-cohort-v2", "productive-email-control-v3",
                  "productive-email-us-cohort-v1")

ATTEMPTS = 3

# Gate names in the order `executionguard.authorize` evaluates them.
LADDER = ("copy", "tenancy", "approval", "eligibility", "suppression",
          "copy_lint", "claims", "fatigue", "collision", "account_collision")

# A refusal a human can lift by doing work, versus a refusal that is the
# system telling us not to contact somebody. The split NEAR_MISS reports.
FIXABLE_GATES = ("copy", "copy_lint", "claims", "approval")
SAFETY_GATES = ("suppression", "collision", "account_collision", "fatigue")


def h(*parts):
    """The repo's identifier hash. Never print the input."""
    return hashlib.sha256(":".join(str(p) for p in parts)
                          .encode("utf-8")).hexdigest()[:12]


def retry(fn, *args, **kw):
    """Provider READS only. A read that keeps failing is `unknown`, not clear."""
    last = None
    for attempt in range(ATTEMPTS):
        try:
            return fn(*args, **kw)
        except Exception as exc:
            last = exc
            time.sleep(1.0 * (attempt + 1))
    raise last


def live_keys(channel):
    """(rec_id, contact_key) already on a live campaign, from the ledger."""
    from src import actionledger
    out = set()
    for row in actionledger.load():
        if (row.get("channel") == channel
                and row.get("campaign_id") in LIVE_CAMPAIGNS):
            out.add((row.get("rec_id"), row.get("contact_key")))
    return out


def population(recs, channel):
    """Every contact in the estate carrying ANY cadence step for this channel."""
    prefix = "li" if channel == "linkedin" else "em"
    out = []
    for rec in recs:
        by_key = {c.get("key"): c for c in (rec.get("contacts") or [])}
        for key, steps in (rec.get("cadence") or {}).items():
            if not any(str(s).startswith(prefix) for s in steps):
                continue
            contact = by_key.get(key)
            if contact is not None:
                out.append((rec, contact))
    return out


def render(rec, contact, channel, campaign, config):
    """The expanded step for every key the channel's sequence needs."""
    steps, missing = {}, []
    for step_key in REQUIRED[channel]:
        try:
            spec = executionguard._spec_for(step_key, campaign=campaign,
                                            config=config, rec=rec,
                                            contact=contact)
        except Exception:
            missing.append(step_key)
            continue
        expanded = cadence.expand_step(rec, contact, spec, config)
        if expanded:
            steps[step_key] = expanded
        else:
            missing.append(step_key)
    return steps, missing


class Screen:
    """One evaluation of the whole estate, with the provider reads cached."""

    def __init__(self, recs, config):
        self.recs = recs
        self.config = config
        self._account = {}
        self._profile = {}
        self._address = {}

    def account(self, domain):
        if domain not in self._account:
            try:
                raw = retry(collision.check_account, domain,
                            expect_workspace=BISON_WORKSPACE)
                decision, why = collision.account_policy(raw)
                self._account[domain] = {
                    "decision": decision, "why": why,
                    "leads": raw.get("leads"),
                    "emails_sent_total": raw.get("emails_sent_total"),
                    "anyone_in_sequence": raw.get("anyone_in_sequence"),
                    "any_bounce": raw.get("any_bounce"),
                    "unknown_statuses": raw.get("unknown_statuses")}
            except Exception as exc:
                self._account[domain] = {
                    "decision": "unknown",
                    "why": f"{type(exc).__name__}: the estate could not be read",
                    "leads": None}
        return self._account[domain]

    def profile(self, contact):
        """EXACTLY the guard's call: raw value, contact name, client slug."""
        cache_key = (contact.get("linkedin"), contact.get("name"))
        if cache_key not in self._profile:
            try:
                verdict, detail = retry(collision.check_linkedin_profile,
                                        contact.get("linkedin"),
                                        contact.get("name"),
                                        expect_workspace=CLIENT)
                self._profile[cache_key] = {
                    "verdict": verdict,
                    "messages": (detail or {}).get("total_messages"),
                    "replied": (detail or {}).get("they_replied"),
                    "seat": (detail or {}).get("our_seat")}
            except Exception as exc:
                self._profile[cache_key] = {
                    "verdict": "unknown", "messages": None, "replied": None,
                    "why": type(exc).__name__}
        return self._profile[cache_key]

    def address(self, email):
        if email not in self._address:
            try:
                verdict, detail = retry(collision.check_address, email,
                                        expect_workspace=BISON_WORKSPACE)
                self._address[email] = {"verdict": verdict,
                                        "status": (detail or {}).get("status")}
            except Exception as exc:
                self._address[email] = {"verdict": "unknown",
                                        "why": type(exc).__name__}
        return self._address[email]

    # -- the ladder ------------------------------------------------------
    def walk(self, rec, contact, channel, campaign):
        """Pass A: the first gate that stops this contact, in guard order."""
        config = self.config
        required = REQUIRED[channel]
        steps, missing = render(rec, contact, channel, campaign, config)
        row = {"gate": None, "why": None, "missing_steps": missing,
               "steps_rendered": sorted(steps)}

        if missing:
            return dict(row, gate="copy",
                        why=f"{len(missing)} of {len(required)} steps do not "
                            f"render: {','.join(missing)}")

        if str(rec.get("client") or "").strip() != str(
                campaign.get("client") or "").strip():
            return dict(row, gate="tenancy",
                        why="the record's client is not the campaign's client")

        unapproved = [k for k in required
                      if not approval.is_approved(rec, contact["key"], k,
                                                  steps[k])]
        if unapproved:
            held = [k for k in required
                    if approval.approval_of(rec, contact["key"], k)]
            if not held:
                why = "no step carries an approval at all"
            elif len(held) < len(required):
                why = (f"only {len(held)} of {len(required)} steps carry an "
                       f"approval")
            else:
                why = (f"every step carries an approval but the fingerprint "
                       f"has moved on {len(unapproved)}; the words were "
                       f"edited after they were approved")
            return dict(row, gate="approval", why=why,
                        unapproved=unapproved, approved_steps=len(held))

        first = required[0]
        decided = eligibility.decide(rec, contact, first, channel=channel,
                                     config=config, step=steps[first])
        reasons = decided.get("reasons")
        reasons = reasons if isinstance(reasons, (list, tuple)) else [
            decided.get("reason")]
        named = {str(r) for r in reasons if r}
        suppressive = named & set(executionguard.SUPPRESSION_REASONS)
        if suppressive:
            return dict(row, gate="suppression",
                        why=", ".join(sorted(suppressive)))
        if decided.get("verdict") != eligibility.ELIGIBLE:
            return dict(row, gate="eligibility",
                        why=f"{decided.get('verdict')}: "
                            f"{','.join(sorted(named)) or 'no reason given'}")

        problems = lint.check_step(rec, contact["key"], steps[first])
        if problems:
            return dict(row, gate="copy_lint", why=",".join(sorted(problems)))

        text = steps[first].get("note") or steps[first].get("body") or ""
        found = claims.check(text, rec, contact)
        bad = found.get("problems") if isinstance(found, dict) else found
        if bad:
            return dict(row, gate="claims", why="claims refuses the copy")

        state = fatigue.check(rec, contact["key"], at=store.now(), config=config)
        if state.get("state") != "ok":
            return dict(row, gate="fatigue", why=str(state.get("state")))

        if channel == "linkedin":
            seen = self.profile(contact)
        else:
            seen = self.address(contact.get("email"))
        if seen["verdict"] != collision.CLEAR:
            return dict(row, gate="collision",
                        why=f"{channel} collision is {seen['verdict']}",
                        collision=seen)

        acct = self.account(rec.get("domain"))
        if acct["decision"] != collision.ALLOW:
            return dict(row, gate="account_collision",
                        why=f"the account says {acct['decision']}",
                        account=acct)

        return dict(row, gate=None, why="every contact-level gate passes",
                    collision=seen, account=acct)

    def safety(self, rec, contact, channel):
        """Pass B: the safety verdicts, asked of EVERYBODY.

        Independent of copy and approval on purpose. A contact whose first
        refusal is "no copy yet" may also be a contact nobody may write to,
        and a NEAR_MISS list that did not ask would send somebody to generate
        words for an account that has already answered us.
        """
        out = {}
        try:
            decided = eligibility.decide(rec, contact, REQUIRED[channel][0],
                                         channel=channel, config=self.config)
            reasons = decided.get("reasons") or [decided.get("reason")]
            named = {str(r) for r in reasons if r}
            out["eligibility"] = decided.get("verdict")
            out["eligibility_reasons"] = sorted(named)
            out["suppressed"] = sorted(
                named & set(executionguard.SUPPRESSION_REASONS))
        except Exception as exc:
            out["eligibility"] = "unknown"
            out["eligibility_reasons"] = [type(exc).__name__]
            out["suppressed"] = []
        try:
            out["fatigue"] = fatigue.check(rec, contact["key"], at=store.now(),
                                           config=self.config).get("state")
        except Exception:
            out["fatigue"] = "unknown"
        if channel == "linkedin":
            out["collision"] = self.profile(contact)
        elif contact.get("email"):
            out["collision"] = self.address(contact.get("email"))
        else:
            out["collision"] = {"verdict": "no_address"}
        out["account"] = self.account(rec.get("domain"))
        return out


def approvers(rec, contact_key, channel):
    """WHO recorded each approval, which the fingerprint gate does not ask.

    `approval.fingerprint` answers "are these the words that were approved".
    It cannot answer "did a human approve them", and on a `generated` step -
    every LinkedIn step but li1 - the stored words ARE what `expand_step`
    returns, so an approval this system recorded about its own draft stays
    current for ever. Reported separately for exactly that reason.
    """
    seen = collections.Counter()
    for step_key in REQUIRED[channel]:
        record = approval.approval_of(rec, contact_key, step_key) or {}
        by = str(record.get("by") or "")
        if by:
            seen["operator" if "@" in by or by == "operator-control-arm"
                 else "self"] += 1
    return dict(seen)


def facts(rec, contact, channel, campaign, config):
    """The per-contact facts the report carries beside the verdict."""
    steps, missing = render(rec, contact, channel, campaign, config)
    decision = {}
    try:
        decision = verification.resolve(contact) or {}
    except Exception:
        decision = {}
    first = REQUIRED[channel][0]
    return {
        "approvers": approvers(rec, contact["key"], channel),
        "first_step_approved": bool(
            first in steps
            and approval.is_approved(rec, contact["key"], first, steps[first])),
        "contact": h(rec.get("id"), contact.get("key")),
        "account_hash": h(rec.get("domain")),
        "record_state": rec.get("state"),
        "persona": contact.get("persona"),
        "has_profile": bool(contact.get("linkedin")),
        "has_address": bool(contact.get("email")),
        "verified_email": decision.get("state"),
        "sendable": bool(lint.sendable(contact)) if contact.get("email") else None,
        "steps_required": len(REQUIRED[channel]),
        "steps_rendered": len(steps),
        "steps_missing": missing,
        "tenancy": (str(rec.get("client") or "")
                    == str(campaign.get("client") or "")),
    }


def run(channel, recs, config, campaigns_by_id, screen):
    campaign = campaigns_by_id[SHAPE_CAMPAIGN[channel]]
    live = live_keys(channel)
    rows = []
    for rec, contact in population(recs, channel):
        key = (rec.get("id"), contact.get("key"))
        row = facts(rec, contact, channel, campaign, config)
        row["already_live"] = key in live
        row.update(screen.walk(rec, contact, channel, campaign))
        row["safety"] = screen.safety(rec, contact, channel)
        rows.append(row)
    return rows


def classify(row):
    """READY / ALREADY_LIVE / NEAR_MISS / SAFETY_BLOCKED.

    ALREADY_LIVE IS DECIDED FIRST, and it has to be. A contact staged on a
    running campaign collides with ITSELF: `check_address` finds its own lead
    row `in_sequence` and `check_linkedin_profile` will find its own
    conversation the moment the first message lands. Reading that as a safety
    refusal would report the live cohort as blocked by the very campaign it is
    on, and would hide it from the ALREADY_LIVE count it belongs in.
    """
    if row.get("already_live"):
        return "ALREADY_LIVE"
    safety = row.get("safety") or {}
    unsafe = (bool(safety.get("suppressed"))
              or (safety.get("collision") or {}).get("verdict")
              not in (collision.CLEAR, None)
              or (safety.get("account") or {}).get("decision")
              != collision.ALLOW
              or safety.get("fatigue") not in ("ok", None))
    if row["gate"] is None:
        return "READY_NOW"
    if unsafe:
        return "SAFETY_BLOCKED"
    if row["gate"] in FIXABLE_GATES:
        return "NEAR_MISS"
    return "SAFETY_BLOCKED" if row["gate"] in SAFETY_GATES else "NEAR_MISS"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="next_ready_cohort")
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))
    recs = store.load()
    config = clients.load(CLIENT)
    campaigns_by_id = {c["campaign_id"]: c
                       for c in store.read_jsonl(store.campaigns_path())}
    screen = Screen(recs, config)

    report = {}
    for channel in ("linkedin", "email"):
        rows = run(channel, recs, config, campaigns_by_id, screen)
        for row in rows:
            row["class"] = classify(row)
        report[channel] = rows

        buckets = collections.Counter(r["class"] for r in rows)
        gates = collections.Counter(r["gate"] or "PASS" for r in rows)
        print(f"=== {channel.upper()}  population={len(rows)}")
        print(f"  READY_NOW    = {buckets['READY_NOW']}")
        print(f"  ALREADY_LIVE = {buckets['ALREADY_LIVE']}")
        print(f"  NEAR_MISS    = {buckets['NEAR_MISS']}")
        print(f"  SAFETY_BLOCK = {buckets['SAFETY_BLOCKED']}")
        print("  first gate that stops them:")
        for gate, count in gates.most_common():
            print(f"    {gate:<20} {count}")
        for row in rows:
            if row["class"] == "READY_NOW":
                print(f"    READY {row['contact']} persona={row['persona']} "
                      f"verified={row['verified_email']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, default=str)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
