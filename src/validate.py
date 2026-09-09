#!/usr/bin/env python3
"""Check our trim assumptions against ContactOut's real responses.

Four of the ContactOut trims were written against the documented shapes rather
than an observed response. Before phase 4 runs at scale, each one should be
checked once, deliberately, against a domain you are happy to spend a few
credits on. This is the command that does that, and it is built so it cannot
run away with your credits or leave a customer's data in the repo.

Safety, in order of how much it matters:

  - dry run is the default. `--live-validation` is required for any paid call
  - `--max-credits N` is required with it, and the run refuses to start if the
    estimate exceeds N. Nothing is called before the estimate is shown
  - the domain and the address are yours to supply. There is no default, and a
    domain from config/suppress.txt is refused outright
  - raw responses are written to work/validation/, which is gitignored, never
    to the queue
  - the console output redacts addresses and every key

  python -m src.validate                                  what it would do
  python -m src.validate --domain your.test               same, priced
  python -m src.validate --domain your.test --email you@your.test \
      --live-validation --max-credits 12
"""
import argparse
import json
import os
import re

from . import ingest, providers, store
from .providers import ProviderError, apify, contactout, deliverable

# What each check costs, from BUILD-SPEC section 5.1 and the live tool schemas.
CHECKS = {
    "people-count": {
        "credits": 0,
        "why": "free, and it confirms the domain is real before anything is spent",
        "trim": ("query", "profiles", "mobiles"),
    },
    "decision-makers": {
        "credits": 10,
        "why": "1 search credit per profile returned, 1 email credit per profile "
               "with contact info. The estimate assumes 5 profiles",
        "trim": ("name", "title", "company", "linkedin", "email", "location",
                 "seniority", "current"),
    },
    "people-search": {
        "credits": 5,
        "why": "1 search credit per profile returned. The estimate assumes 5",
        "trim": ("name", "title", "company", "linkedin", "email", "location",
                 "seniority", "current"),
    },
    "email-verifier": {
        "credits": 1,
        "why": "1 verifier credit on a definitive result",
        "trim": ("email", "verdict"),
    },
    "company-information-from-domain": {
        "credits": 1,
        "why": "1 search credit per company found",
        "trim": ("name", "domain", "email_domain", "employees", "revenue",
                 "founded", "industry", "offices", "specialties", "stack"),
    },
}

ORDER = ("people-count", "company-information-from-domain", "decision-makers",
         "people-search", "email-verifier")

# Deliverable: one operation, and the contract has to be confirmed first.
DELIVERABLE_CHECKS = {
    "deliverable-verify": {
        "credits": deliverable.COST_PER_VERIFY,
        "why": "one verification credit, on an address you own",
        "trim": ("provider", "status", "email", "deliverable", "safe_to_send",
                 "catch_all", "disposable", "role_account", "score", "reason"),
    },
}

# Apify: billed in compute units, so there is no credit figure to quote
# honestly. The real bound is the scope, and the cap is a run count.
APIFY_CHECKS = {
    "apify-research": {
        "credits": 0,
        "why": "billed in Apify compute units, not credits: capped by runs, "
               "pages, items and time",
        "trim": ("source_type", "provider", "source_url", "actor",
                 "retrieved_at", "field", "fact"),
    },
}

PROVIDERS = {"contactout": CHECKS, "deliverable": DELIVERABLE_CHECKS,
             "apify": APIFY_CHECKS}


def specs_for(provider="contactout"):
    return PROVIDERS.get(provider, CHECKS)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class Refused(RuntimeError):
    """The run was stopped before anything was spent."""


def redact(text):
    """Addresses and keys never reach the console or a log line."""
    text = EMAIL_RE.sub(lambda m: m.group(0)[:2] + "***@" + m.group(0).split("@")[-1],
                        str(text))
    for param in ("token", "key", "api_key"):
        text = re.sub(rf"({param}=)[^&\s\"']+", r"\1***", text, flags=re.I)
    return text


def output_dir():
    """Gitignored: work/ is excluded wholesale."""
    return os.path.join(os.path.dirname(store.queue_path()), "validation")


# These two bill per profile RETURNED, so their cost is a function of how many
# come back, not a constant. The published figures assume five. people-count is
# free and reports the real number, so pass it in and the estimate stops being
# a guess. Neither endpoint takes a page-size parameter, so this bounds the
# plan, not the billing: if more profiles come back than were counted, more is
# spent, and no cap this side of the wire can prevent that.
PER_PROFILE = {
    "decision-makers": lambda profiles, reveal: profiles * (2 if reveal else 1),
    "people-search": lambda profiles, reveal: profiles,
}
ASSUMED_PROFILES = 5


def estimate(checks, email=None, provider="contactout",
             profiles=ASSUMED_PROFILES, reveal=True):
    """What this run would cost, before a single call is made."""
    specs = specs_for(provider)
    total = 0
    rows = []
    for name in checks:
        spec = specs[name]
        cost = spec["credits"]
        why = spec["why"]
        if name in PER_PROFILE and provider == "contactout":
            cost = PER_PROFILE[name](profiles, reveal)
            why = (f"1 search credit per profile returned"
                   + (", 1 email credit per profile with contact info"
                      if reveal and name == "decision-makers" else "")
                   + f". {profiles} profile(s) expected")
        if name in ("email-verifier", "deliverable-verify") and not email:
            continue
        rows.append({"check": name, "credits": cost, "why": why})
        total += cost
    return {"rows": rows, "total": total}


def guard(domain, live, max_credits, planned, provider="contactout",
          max_apify_runs=None, runs=0):
    """Everything that must be true before a paid call is allowed.

    The estimate is checked against the cap here, before the first request, so
    a run can never spend part way and then discover it was over.
    """
    if not live:
        return
    if provider == "deliverable" and deliverable.transport_gaps():
        # The response half is allowed to be unread here: reading it is what
        # this harness is for. The request half is not - without it there is
        # no call to make, only a guess to send.
        raise Refused(
            "the Deliverable request contract is incomplete, so there is "
            "nothing safe to call. Missing: "
            + "; ".join(g.split(":")[0] for g in deliverable.transport_gaps()))
    if provider == "apify":
        if max_apify_runs is None:
            raise Refused("--max-apify-runs is required for a live Apify "
                          "validation. State the ceiling before anything runs.")
        if runs > max_apify_runs:
            raise Refused(f"this would start {runs} actor run(s), over your "
                          f"--max-apify-runs {max_apify_runs}. Nothing started.")
    if not domain:
        raise Refused("--domain is required for a live validation. There is no "
                      "default, on purpose.")
    if domain in ingest.load_suppress():
        raise Refused(f"{domain} is on the suppression list. Pick a domain you "
                      "own or one that is not a live account.")
    if max_credits is None:
        raise Refused("--max-credits is required with --live-validation. State "
                      "the ceiling you accept before anything is spent.")
    if planned > max_credits:
        raise Refused(f"this run is estimated at {planned} credits, over your "
                      f"--max-credits {max_credits}. Nothing was called.")


def compare(name, trimmed, raw, provider="contactout"):
    """Where our assumptions and the real response disagree."""
    expected = set(specs_for(provider)[name]["trim"])
    if isinstance(trimmed, list):
        got = set(trimmed[0]) if trimmed else set()
        sample = trimmed[0] if trimmed else {}
    else:
        got = set(trimmed or {})
        sample = trimmed or {}

    empty = sorted(k for k, v in (sample or {}).items() if v in (None, "", [], {}))
    raw_keys = set()
    payload = raw
    if isinstance(payload, dict):
        payload = payload.get("data", payload)
        if isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    raw_keys |= set(value[0])
                elif isinstance(value, dict):
                    raw_keys |= set(value)
            raw_keys |= set(payload)
    return {
        "check": name,
        "expected_fields": sorted(expected),
        "missing_from_trim": sorted(expected - got),
        "unexpected_in_trim": sorted(got - expected),
        "trimmed_but_empty": empty,
        "raw_keys_we_ignore": sorted(raw_keys - {"data", "status", "status_code"}),
        "verdict": "matches" if not (expected - got) and not empty else "differs",
    }


class Wire:
    """Records what actually came back, so a trim can be judged against it.

    Provider modules return trimmed dicts and never raw payloads (that rule is
    what keeps a provider's idea of a useful response out of an LLM context).
    This harness still has to see the whole thing to report what we discard, so
    it listens at the transport seam instead of asking a module to hand it over.
    """

    def __init__(self, inner):
        self.inner = inner
        self.seen = []

    def __call__(self, method, url, headers, body, timeout):
        status, text = self.inner(method, url, headers, body, timeout)
        try:
            payload = json.loads(text) if text else None
        except (ValueError, TypeError):
            payload = None
        # The url is redacted here, at the point of capture, so no later path
        # can write a key into work/validation or onto the console.
        self.seen.append({"url": providers.redact(url), "status": status,
                          "payload": payload})
        return status, text

    def since(self, mark):
        return self.seen[mark:]


def profiles_returned(raw):
    """How many profiles a paid search actually billed for.

    Confirmed live: the answer carries metadata.total_results and a profiles
    map keyed by LinkedIn URL. This is the only honest per-call spend figure
    available - ContactOut exposes no per-call charge - so it is computed from
    the response rather than assumed from the plan.
    """
    if not isinstance(raw, dict):
        return None
    body = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    profiles = body.get("profiles")
    if isinstance(profiles, (dict, list)):
        return len(profiles)
    meta = body.get("metadata")
    if isinstance(meta, dict) and isinstance(meta.get("total_results"), int):
        return meta["total_results"]
    return None


def observed_cost(name, raw, reveal=True):
    """What a per-profile check really cost, or None when it cannot be known."""
    if name not in PER_PROFILE:
        return None
    count = profiles_returned(raw)
    if count is None:
        return None
    return PER_PROFILE[name](count, reveal)


def call(name, domain=None, email=None, reveal=True):
    """One provider call, trimmed. Only reached when live validation is on."""
    if name == "deliverable-verify":
        # The one caller permitted to spend on an unread response shape.
        return deliverable.verify(email, unread_contract=True)
    if name == "apify-research":
        raise Refused("this harness never starts an actor run. Enable Apify for "
                      "a client and use python -m src.research instead.")
    if name == "people-count":
        return contactout.people_count(domain=domain)
    if name == "decision-makers":
        return contactout.decision_makers(domain, reveal_info=reveal)
    if name == "people-search":
        return contactout.people_search(domain=domain)
    if name == "email-verifier":
        return contactout.email_verifier(email)
    if name == "company-information-from-domain":
        return contactout.company_info(domain)
    raise Refused(f"unknown check: {name}")


def run(domain=None, email=None, checks=None, live=False, max_credits=None,
        raw_sink=None, provider="contactout", max_apify_runs=None,
        profiles=ASSUMED_PROFILES, reveal=True):
    """Dry by default. Returns the plan, the cost, and any differences found."""
    specs = specs_for(provider)
    default_order = ORDER if provider == "contactout" else tuple(specs)
    checks = [c for c in (checks or default_order) if c in specs]
    if not email:
        checks = [c for c in checks
                  if c not in ("email-verifier", "deliverable-verify")]
    priced = estimate(checks, email, provider, profiles, reveal)
    costs = {row["check"]: row["credits"] for row in priced["rows"]}
    guard(domain, live, max_credits, priced["total"], provider,
          max_apify_runs=max_apify_runs, runs=len(checks))

    result = {"live": live, "provider": provider, "domain": domain,
              "checks": checks, "estimate": priced, "spent": 0,
              "reveal": reveal, "observed": 0, "counted": [],
              "findings": [], "errors": []}
    if not live:
        return result

    os.makedirs(raw_sink or output_dir(), exist_ok=True)
    # set_transport hands back whatever was installed, which is what the
    # recorder delegates to and what is put back in the finally below.
    wire = Wire(None)
    wire.inner = providers.set_transport(wire)
    try:
        for name in checks:
            cost = costs.get(name, specs[name]["credits"])
            if result["spent"] + cost > max_credits:
                result["errors"].append({"check": name,
                                         "why": "would exceed --max-credits"})
                break
            mark = len(wire.seen)
            try:
                trimmed = call(name, domain=domain, email=email,
                               reveal=reveal)
            except ProviderError as e:
                result["errors"].append({"check": name, "why": redact(str(e))})
                continue
            result["spent"] += cost
            exchanges = wire.since(mark)
            raw = exchanges[-1]["payload"] if exchanges else {}
            path = os.path.join(raw_sink or output_dir(), f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"check": name, "trimmed": trimmed,
                           "exchanges": exchanges}, f, indent=2,
                          ensure_ascii=False)
            actual = observed_cost(name, raw, reveal)
            if actual is not None:
                result["observed"] += actual
                result["counted"].append({"check": name,
                                          "profiles": profiles_returned(raw),
                                          "credits": actual})
            result["findings"].append(compare(name, trimmed, raw, provider))
    finally:
        providers.set_transport(wire.inner)
    return result


KEY_PLACEHOLDER = "<from the environment, never printed>"


def _key_present(name):
    """Is this credential readable, without reading it?

    `providers.key` loads `config/.env` on demand - the repository reads a
    credential at call time and never at import - and raises rather than
    returning a value it does not have. Here the question is only whether
    it would succeed, and the answer must never be the value itself.
    """
    try:
        providers.key(name)
        return True
    except providers.MissingKey:
        return False


def request_preview(provider, email):
    """Exactly what would be sent, with the key replaced by a placeholder.

    A dry run that only prints a price is not much of a rehearsal. What somebody
    approving a paid call actually needs to see is the request: which host,
    which path, which method, where the key travels and what the body says. The
    key itself is the one thing that must not be on the screen, so it is built
    with a placeholder rather than redacted afterwards - a value that was never
    fetched cannot be printed by accident.

    Returns None for a provider with no single canonical request to show.
    """
    if provider != "deliverable":
        return None
    current = deliverable.settings()
    submit_url = deliverable.endpoint(current["path"])
    status_url = (deliverable.endpoint(current["status_path"])
                  if current["status_path"] else None)
    style = current["auth"]
    if style == "header":
        auth = f"{deliverable.HEADER_NAME}: {KEY_PLACEHOLDER}"
    elif style == "bearer":
        auth = f"Authorization: Bearer {KEY_PLACEHOLDER}"
    else:
        auth = f"?api_key={KEY_PLACEHOLDER}"
    return {
        "provider": "deliverable",
        "method": current["method"],
        "submit": submit_url,
        "status": status_url,
        "auth_style": style,
        "auth": auth,
        "key_variable": deliverable.KEY_VAR,
        # Asked through the same door the call itself uses. This read
        # `os.environ` directly, and credentials live in `config/.env`
        # which `providers.key` loads on demand - so a key that was
        # present was printed as "NOT set".
        #
        # That is worse than a cosmetic slip, because this preview sits on
        # the exact command `LIVE-VALIDATION-PLAN.md` sends somebody to for
        # the Deliverable contract, which is the blocker holding the whole
        # email lane. Being told a key is missing is being told to go and
        # find one you already have.
        "key_present": _key_present(deliverable.KEY_VAR),
        "body": {"email": redact(email) if email else "<the address you supply>"},
        "status_body": {"task_id": "<returned by the submit call>"},
        "max_calls": 1 + deliverable.POLL_ATTEMPTS,
        "max_credits": deliverable.COST_PER_VERIFY,
        "fields_read": sorted(deliverable.KNOWN_FIELDS),
        "contract_gaps": deliverable.contract_gaps(),
    }


def print_request_preview(preview):
    if not preview:
        return
    print()
    print("  the request that would be sent:")
    print(f"    provider     {preview['provider']}")
    print(f"    submit       {preview['method']} {preview['submit']}")
    if preview["status"]:
        print(f"    poll         POST {preview['status']}")
    print(f"    auth         {preview['auth']}")
    print(f"    key          {preview['key_variable']} is "
          f"{'set' if preview['key_present'] else 'NOT set'} "
          "(its value is never printed)")
    print(f"    body         {json.dumps(preview['body'])}")
    if preview["status"]:
        print(f"    poll body    {json.dumps(preview['status_body'])}")
    print(f"    max calls    {preview['max_calls']} "
          f"(1 submit, up to {preview['max_calls'] - 1} polls)")
    print(f"    max credits  {preview['max_credits']}")
    print("    fields read  " + ", ".join(preview["fields_read"][:12]))
    for extra in range(12, len(preview["fields_read"]), 12):
        print("                 "
              + ", ".join(preview["fields_read"][extra:extra + 12]))
    print("    unread fields in a real answer are reported, not ignored")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.validate")
    p.add_argument("--domain", help="a domain you own or are happy to spend on")
    p.add_argument("--email", help="an address you own, for the verifier check")
    p.add_argument("--check", action="append", dest="checks")
    p.add_argument("--live-validation", action="store_true", dest="live",
                   help="make the paid calls. Requires --max-credits")
    p.add_argument("--max-credits", type=int,
                   help="the ceiling you accept. The run refuses to exceed it")
    p.add_argument("--provider", default="contactout", choices=sorted(PROVIDERS))
    p.add_argument("--max-apify-runs", type=int,
                   help="ceiling on actor runs for an Apify validation")
    p.add_argument("--expect-profiles", type=int, default=ASSUMED_PROFILES,
                   dest="profiles",
                   help="how many profiles the paid searches will return. "
                        "people-count is free and tells you: pass the real "
                        "number so the estimate is not a guess")
    p.add_argument("--no-reveal", action="store_false", dest="reveal",
                   help="do not buy contact info on decision-makers. Halves "
                        "its cost and returns no addresses")
    a = p.parse_args(argv)

    specs = specs_for(a.provider)
    default_order = ORDER if a.provider == "contactout" else tuple(specs)
    checks = [c for c in (a.checks or default_order) if c in specs]
    if not a.email:
        checks = [c for c in checks
                  if c not in ("email-verifier", "deliverable-verify")]
    priced = estimate(checks, a.email, a.provider, a.profiles, a.reveal)

    print(f"{a.provider} response validation")
    print(f"  domain      {a.domain or '(none supplied: dry run only)'}")
    print(f"  address     {redact(a.email) if a.email else '(none supplied)'}")
    print(f"  raw output  {output_dir()}  (gitignored, never the queue)")
    if a.provider == "contactout" and any(c in PER_PROFILE for c in checks):
        print(f"  profiles    {a.profiles} expected, contact info "
              f"{'bought' if a.reveal else 'NOT bought'}")
    print()
    print("  planned calls and cost:")
    for row in priced["rows"]:
        print(f"    {row['check']:<34} {row['credits']:>3} credits  {row['why']}")
    print(f"    {'TOTAL':<34} {priced['total']:>3} credits")

    print_request_preview(request_preview(a.provider, a.email))

    if a.provider == "deliverable" and not deliverable.contract_verified():
        print("\n  contract   NOT CONFIRMED. Set these before validating:")
        for gap in deliverable.contract_gaps():
            print(f"             {gap}")
    if a.provider == "apify":
        print("  note       this harness never starts an actor run")

    if not a.live:
        print("\nDRY RUN. Nothing was called and nothing was spent.")
        print("To validate for real:")
        extra = " --max-apify-runs 1" if a.provider == "apify" else ""
        print(f"  python -m src.validate --provider {a.provider} "
              f"--domain your.test --email you@your.test \\")
        print(f"      --live-validation --max-credits {max(priced['total'], 1)}{extra}")
        return 0

    try:
        result = run(domain=a.domain, email=a.email, checks=checks, live=True,
                     max_credits=a.max_credits, provider=a.provider,
                     max_apify_runs=a.max_apify_runs, profiles=a.profiles,
                     reveal=a.reveal)
    except Refused as e:
        print(f"\nREFUSED: {e}")
        return 2

    print(f"\nspent {result['spent']} credit(s) of a {a.max_credits} "
          "ceiling, by the estimate above")
    if a.provider == "contactout" and any(c in PER_PROFILE for c in checks):
        print("  note: these bill per profile RETURNED. If more came back than "
              "expected,\n        more was spent than this line says.")
    print()
    for finding in result["findings"]:
        print(f"  {finding['check']:<34} {finding['verdict']}")
        for field in ("missing_from_trim", "trimmed_but_empty", "raw_keys_we_ignore"):
            if finding[field]:
                print(f"    {field}: {', '.join(finding[field])[:100]}")
    for err in result["errors"]:
        print(f"  {err['check']:<34} ERROR {err['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
