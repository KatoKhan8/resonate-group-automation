#!/usr/bin/env python3
"""What must be configured, for which mode, and what is merely optional.

Two failure modes this exists to prevent, and they pull in opposite
directions:

**Demo mode must not require live credentials.** Somebody should be able to
clone this repository and run `py -m src.web --demo` with an empty
environment. A startup check that insists on a ContactOut token to show a
fictional dashboard is a check that gets deleted.

**Production must fail closed.** Starting a production process without a
session secret, or with demo authentication still accepted, is worse than not
starting. The whole point of a mode is that it changes what is allowed to be
missing.

So every variable is classified by the *mode that needs it* rather than by
whether it happens to be set:

  REQUIRED          production will not start without it
  PRODUCTION        needed before production, checked but not fatal in demo
  LIVE              needed only once live provider work is authorised
  OPTIONAL          a default exists and is fine

Nothing here reads a value. `report()` returns names, classifications and a
boolean for presence - the same discipline as
`src/web/security.py::credential_status`.

  python -m src.config
  python -m src.config --mode production
  python -m src.config --json
"""
import argparse
import json
import os

DEMO = "demo"
PRODUCTION = "production"
MODES = (DEMO, PRODUCTION)

REQUIRED = "required"
PRODUCTION_ONLY = "production"
LIVE = "live"
OPTIONAL = "optional"

# (name, classification, group, why it matters)
#
# The `why` is not documentation for its own sake: it is what an operator sees
# when the check fails, and "SESSION_SECRET is not set" without it is a line
# somebody works around rather than fixes.
VARIABLES = (
    ("APP_MODE", OPTIONAL, "app",
     "demo or production. Unset defaults to demo, which is the safe "
     "default. Set *explicitly* to demo it also installs the fictional "
     "estate, which is how one start command serves both the published "
     "demonstration and the real deployment"),
    ("WEB_HOST", OPTIONAL, "app",
     "loopback by default; a deployment binds behind a TLS proxy"),
    ("WEB_PORT", OPTIONAL, "app",
     "8765 by default. A platform usually supplies this as $PORT"),

    ("AUTH_PROVIDER", REQUIRED, "auth",
     "'oidc', or unset for demo sign-in. Any other value is refused rather "
     "than ignored: falling back to demo here would be unauthenticated "
     "access reached by way of a variable somebody set to turn "
     "authentication on"),
    ("AUTH_ISSUER", REQUIRED, "auth",
     "the identity provider's base URL. Its endpoints are read from "
     "{issuer}/.well-known/openid-configuration rather than configured, so a "
     "provider that moves one does not need a redeploy"),
    ("AUTH_CLIENT_ID", REQUIRED, "auth",
     "the OAuth client registered for this deployment. Checked against every "
     "id_token's audience"),
    ("AUTH_CLIENT_SECRET", REQUIRED, "auth",
     "authenticates this server to the provider's token endpoint. Never "
     "leaves this process and never reaches a page"),
    ("AUTH_REDIRECT_URL", REQUIRED, "auth",
     "where the provider sends the browser back. Must match the value "
     "registered with the provider exactly, and must be https"),
    ("AUTH_ALLOWED_DOMAINS", OPTIONAL, "auth",
     "comma-separated email domains that may sign in at all. A second fence "
     "in front of the membership table, not a replacement for it: an allowed "
     "domain with no user row still gets nowhere"),

    ("SESSION_SECRET", OPTIONAL, "auth",
     "reserved, and read by nothing. Sessions are opaque tokens held in this "
     "process, so there is no cookie to sign - it was classified REQUIRED "
     "while production authentication did not exist, which made it a "
     "required variable nothing consumed. The four AUTH_ variables above are "
     "what production actually needs. It stays named for the session store a "
     "second process would need"),

    ("QUEUE", PRODUCTION_ONLY, "state",
     "where canonical state lives. Every other state file defaults to this "
     "one's directory, so it is the single lever that moves the whole set. "
     "Required in production because a container filesystem is ephemeral: "
     "unset, the queue lands somewhere that is deleted on the next deploy, "
     "and an empty store is a *valid* store - nothing downstream can tell "
     "the difference between a fresh workspace and one whose records were "
     "thrown away. Point it at a mounted volume"),

    ("DATABASE_URL", OPTIONAL, "database",
     "reserved, and read by nothing. There is no SQL backend in this build - "
     "no driver, no schema, no query - so a Postgres instance provisioned "
     "for it would sit empty while the real state sat on disk. It blocked "
     "production startup until the release audit noticed that it required a "
     "database nothing used while QUEUE, which decides whether client data "
     "survives a deploy, was optional. DATABASE-MIGRATION.md is the plan "
     "that would make this real"),

    ("CONTACTOUT_TOKEN", LIVE, "providers",
     "company-first enrichment. People-count is free; everything else burns "
     "credits"),
    ("BLITZ_API_KEY", LIVE, "providers",
     "the second structured provider, and never the first one asked. The only "
     "source for a company's mail domain, and the only index that addresses a "
     "company by its LinkedIn URL. Bills in records, not credits"),
    ("AIARK_KEY", LIVE, "providers",
     "enrichment. A fallback, and one that needs a stated reason"),
    ("REOON_KEY", LIVE, "providers",
     "the escalation verifier, reached only when two providers disagree"),
    ("DELIVERABLE_KEY", LIVE, "providers",
     "verification. Its wire contract has never been validated - see "
     "LIVE-VALIDATION-PLAN.md"),
    ("REPLY_POLL_ENABLED", OPTIONAL, "app",
     "reconcile replies on a timer. Off unless set: a background thread "
     "that reaches a provider is not a default. It reads, and what it "
     "protects is how quickly a confirmed reply stops that lead"),
    ("REPLY_POLL_SECONDS", OPTIONAL, "app",
     "seconds between sweeps. 300 by default; under 60 is raised to 60"),
    ("REPLY_POLL_PROVIDERS", OPTIONAL, "app",
     "a subset of emailbison,heyreach. Both by default. An unknown name is "
     "refused rather than ignored, because polling nothing would otherwise "
     "report healthy"),

    ("DIGEST_SCHEDULE", OPTIONAL, "app",
     "off, daily or weekdays. Off unless set. The digest rides the reply "
     "watcher's thread, so it needs no second timer - but it is switched "
     "separately, because a workspace with no provider credentials still "
     "wants a summary"),
    ("DIGEST_HOUR", OPTIONAL, "app",
     "the hour the digest covers up to, 0-23, UTC. 8 by default. An hour "
     "that cannot be read is refused rather than defaulted: a digest "
     "arriving at the wrong time every day looks like a working schedule"),

    ("BISON_KEY", LIVE, "providers",
     "EmailBison, the email sending platform. Reads only in this build"),
    ("HEYREACH_KEY", LIVE, "providers",
     "HeyReach, the LinkedIn platform. Reads only in this build"),
    ("APIFY_TOKEN", LIVE, "providers",
     "research actors. Bounded, SSRF-guarded, and not run in this build"),
    ("LLM_API_KEY", LIVE, "providers",
     "draft generation, through any OpenAI-compatible endpoint"),
    ("LLM_BASE_URL", LIVE, "providers",
     "the OpenAI-compatible endpoint to call. Set it to point at OpenRouter, "
     "a local server, or anything else speaking that shape; unset means no "
     "model is configured and generation refuses"),
    ("LLM_MODEL", LIVE, "providers",
     "the model id to ask for, in whatever form the endpoint expects"),
    ("GROQ_API_KEY", LIVE, "providers",
     "the primary reasoning provider - fast, cheap, structured thinking"),
    ("OPENROUTER_API_KEY", LIVE, "providers",
     "the fallback reasoning provider; its absence is an explicit refusal"),

    ("SLACK_BOT_TOKEN", LIVE, "slack",
     "a token alone never enables posting; SLACK_LIVE must also be set"),
    ("SLACK_SIGNING_SECRET", LIVE, "slack",
     "without it every inbound Slack interaction is refused rather than "
     "trusted"),
    ("SLACK_OPS_CHANNEL", LIVE, "slack",
     "the one global operations channel. Per-workspace channels are "
     "workspace policies, never environment variables"),
)

BY_NAME = {name: (classification, group, why)
           for name, classification, group, why in VARIABLES}


def mode():
    """The mode this process is running in. Demo unless told otherwise."""
    value = (os.environ.get("APP_MODE") or DEMO).strip().lower()
    return value if value in MODES else DEMO


def demo_estate_requested():
    """Has somebody *asked* for the fictional estate, rather than defaulted?

    `mode()` cannot answer this. Demo is what an unset `APP_MODE` means, so
    it cannot tell "nobody said" from "somebody said demo" - and those want
    opposite things. An operator running `py -m src.web` against their own
    `work/` directory has said nothing and must not have fixtures installed
    over the top of real records.

    A deployment is the other case. There is one start command in this
    repository and two services that run it, and the difference between
    them is exactly whether the data is invented. `APP_MODE=demo`, set
    explicitly, is that difference.

    This exists because the one command the repository shipped hardcoded
    `--demo`, which made a production deployment from it serve fictional
    companies at a production URL - safe, and wrong in the way that is
    worst: convincingly.
    """
    return (os.environ.get("APP_MODE") or "").strip().lower() == DEMO


def configured(name):
    return bool((os.environ.get(name) or "").strip())


def report(current=None):
    """Every variable, its classification, and whether it is set.

    Never returns a value. A configuration screen that prints what a key is
    set *to* is a configuration screen that ends up in a screenshot.
    """
    current = current or mode()
    rows = []
    for name, classification, group, why in VARIABLES:
        present = configured(name)
        rows.append({
            "name": name,
            "group": group,
            "classification": classification,
            "configured": present,
            "why": why,
            "blocking": _blocking(classification, present, current),
        })
    return {
        "mode": current,
        "variables": rows,
        "blockers": [r["name"] for r in rows if r["blocking"]],
        "live_ready": not [r for r in rows
                           if r["classification"] == LIVE
                           and not r["configured"]],
    }


def _blocking(classification, present, current):
    """Is this the thing that should stop the process starting?

    Only in production, and only for the two classifications that mean
    "production needs this". A missing provider key is never blocking: this
    build does not call providers, and a deployment that refuses to start
    without a ContactOut token cannot run a demo for a prospective client.
    """
    if current != PRODUCTION or present:
        return False
    return classification in (REQUIRED, PRODUCTION_ONLY)


def verify(current=None):
    """Raise in production if something required is missing. Never in demo.

    Called at startup. Demo mode returns the report and starts regardless,
    which is the whole point: an empty environment must be able to run the
    demonstration.
    """
    result = report(current)
    if result["mode"] == PRODUCTION and result["blockers"]:
        raise RuntimeError(
            "refusing to start in production mode without: "
            + ", ".join(result["blockers"])
            + ". Set them, or run with APP_MODE=demo.")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.config",
                                description=__doc__)
    p.add_argument("--mode", choices=MODES, help="check as if in this mode")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    result = report(args.mode)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"mode: {result['mode']}\n")
    group = None
    for row in result["variables"]:
        if row["group"] != group:
            group = row["group"]
            print(f"  [{group}]")
        mark = "set" if row["configured"] else "-"
        flag = "  BLOCKING" if row["blocking"] else ""
        print(f"    {row['name']:<24} {row['classification']:<11} "
              f"{mark:<4}{flag}")
    print()
    if result["blockers"]:
        print("will not start in production: "
              + ", ".join(result["blockers"]))
        return 1
    print("no blockers for this mode")
    if not result["live_ready"]:
        print("live provider work is not configured, which is correct for "
              "this build: nothing here sends, posts or spends.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
