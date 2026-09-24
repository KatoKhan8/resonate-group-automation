#!/usr/bin/env python3
"""2d - the secrets move checklist, DERIVED from config.VARIABLES.

    py -3 scripts/server/secrets_checklist.py                # the checklist
    py -3 scripts/server/secrets_checklist.py --out docs/SECRETS-MOVE.md
    py -3 scripts/server/secrets_checklist.py --verify-names # what is set

WHY THIS IS GENERATED AND NOT WRITTEN. CLAUDE.md opens a section with
"CREDENTIAL NAMES COME FROM `config.VARIABLES`. NEVER GUESS ONE", and it is
there because a session once invented four plausible variable names, reported
ContactOut, Blitz, Apify and Slack as unauthenticated, and concluded that
decision-maker discovery was impossible. All four were set. `CONTACTOUT_KEY`
does not exist.

A hand-written checklist is that same failure with a longer half-life: it is
a list somebody has to remember to edit the day a variable is added, and the
cost of forgetting is a cutover that completes with a credential missing and
an estate that looks configured. The monitor table taught this branch the
lesson once already. This file reads the registry.

IT NEVER PRINTS A VALUE. Not in the checklist, not in --verify-names, not in
an error. `--verify-names` reports each name as SET or ABSENT and nothing
else - that distinction is the whole point, and it is deliberately weaker
than it looks: a SET variable is NOT an authenticated one.
`scripts/credential_health.py --verify` is what answers that, and it keeps
five states apart where this keeps two.
"""
import argparse
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src import config  # noqa: E402

SECRETS_FILE = "/etc/resonate/secrets.env"

#: INFRA VARIABLES. These are NOT in `config.VARIABLES` and should not be:
#: that registry is the application's, and nothing in `src/` reads any of
#: these. They are declared here, next to the tooling that does read them,
#: and they are on the checklist because the checklist is what somebody works
#: through at 23:00 - a variable nobody lists is a variable nobody sets.
#:
#: (name, when, why)
INFRA_VARIABLES = (
    ("BACKUP_TARGET", "before the first off-host backup",
     "user@host:/path of the Storage Box. SSH, not SMB."),
    ("BACKUP_ENCRYPTION", "with BACKUP_TARGET",
     "`age`. Any other value is refused rather than treated as none."),
    ("BACKUP_AGE_RECIPIENT", "with BACKUP_TARGET",
     "the age PUBLIC key (age1...). NEVER the private key: the private half "
     "is generated on the operator's laptop and must never reach this host. "
     "The consequence is deliberate - the host can encrypt and cannot "
     "decrypt, so it cannot verify its own backups."),
    ("BACKUP_SSH_PORT", "optional",
     "23 by default, which is what a Hetzner Storage Box speaks."),
    ("PUBLIC_HOSTNAME", "before Caddy starts",
     "the name on the certificate. DNS must already resolve to this host: "
     "TLS-ALPN issuance happens at startup, and a failure is rate-limited "
     "per ACCOUNT for a week."),
    ("WEBHOOK_SIGNING_SECRET", "before the receiver accepts anything",
     "HMAC-SHA256 shared secret. Without it every POST is refused rather "
     "than recorded unverified. Generate it on the host - it is not a value "
     "that needs to come from anywhere else."),
)

#: NOT a secret and NOT in this file: the Storage Box PASSWORD. It is typed
#: once, into an interactive prompt, to install the host's ssh public key on
#: the Storage Box - and never again. Authentication afterwards is by key. A
#: password in `secrets.env` would be a reusable credential sitting on the
#: machine that only ever needed it once.
NEVER_IN_SECRETS = (
    ("the Storage Box password", "docs/SECRETS-MOVE.md, 'the password'"),
    ("the age PRIVATE key", "the operator's laptop only"),
    ("Claude Code's credential", "a user login, authenticated once per host"),
)

#: What each classification means for the CUTOVER, which is a different
#: question from what it means to the application. `live` variables are the
#: ones that let the estate touch a provider: absent, the app runs and reads
#: nothing. That is exactly the shadow deploy, so they are NOT needed to
#: install - they are needed to start.
WHEN = {
    "required": "BEFORE the web application starts at all",
    "production": "BEFORE anything is deployed - it decides where state lives",
    "live": "BEFORE the estate is started (not needed for a shadow deploy)",
    "optional": "only if that behaviour is wanted",
}

ORDER = ("production", "required", "live", "optional")


def variables():
    """(name, classification, category, why) from the registry, sorted."""
    rows = []
    for entry in config.VARIABLES:
        name, classification, category, why = (list(entry) + [""] * 4)[:4]
        rows.append((name, classification, category, why))
    return sorted(rows, key=lambda r: (ORDER.index(r[1])
                                       if r[1] in ORDER else 99, r[0]))


def checklist():
    rows = variables()
    out = [
        "# Secrets move checklist — /etc/resonate/secrets.env",
        "",
        "**GENERATED from `config.VARIABLES` by "
        "`scripts/server/secrets_checklist.py`. Do not hand-edit.**",
        "",
        "Regenerate it rather than adding a line: a hand-written list is one",
        "somebody has to remember to edit the day a variable is added, and a",
        "cutover that completes with a credential missing leaves an estate",
        "that looks configured. `CONTACTOUT_KEY` does not exist, and a",
        "session once concluded four providers were unauthenticated by",
        "guessing names — CLAUDE.md records it.",
        "",
        "## How the file is written",
        "",
        "    sudo -e %s        # root writes it; the app only reads it" % SECRETS_FILE,
        "",
        "`0640 root:resonate`, created empty by `provision.sh` step 8. systemd's",
        "`EnvironmentFile=` loads it as root before dropping to `resonate`, so no",
        "value ever reaches a command line, a unit file, or a shell history.",
        "",
        "One `NAME=value` per line, no `export`, no quotes unless the value",
        "contains a space. **Never** commit it, never echo it, never paste a",
        "value into Slack or a transcript.",
        "",
        "## A set variable is not an authenticated one",
        "",
        "    py -3 scripts/server/secrets_checklist.py --verify-names   # SET / ABSENT",
        "    py -3 scripts/credential_health.py --verify                # does it work",
        "",
        "The first answers whether a name is present. The second actually asks",
        "the provider and keeps five states apart, including the one that",
        "matters most: a transport failure is NOT a bad key.",
        "",
    ]
    for classification in ORDER:
        group = [r for r in rows if r[1] == classification]
        if not group:
            continue
        out.append("## %s — needed %s" % (classification.upper(),
                                          WHEN.get(classification, "")))
        out.append("")
        for name, _c, category, why in group:
            out.append("- [ ] `%s`  *(%s)*" % (name, category))
            if why:
                out.append("      %s" % why)
        out.append("")
    out.append("## INFRA — not in `config.VARIABLES`, and read by the tooling")
    out.append("")
    out.append("Nothing in `src/` reads any of these. They are listed because")
    out.append("a variable nobody lists is a variable nobody sets.")
    out.append("")
    for name, when, why in INFRA_VARIABLES:
        out.append("- [ ] `%s`  *(%s)*" % (name, when))
        out.append("      %s" % why)
    out.append("")
    out.append("### The Storage Box password — where and when")
    out.append("")
    out.append("**It does not go in this file, and it is not typed on the")
    out.append("host more than once.** Install the host's ssh public key on")
    out.append("the Storage Box, and authentication afterwards is by key:")
    out.append("")
    out.append("    # ON THE HOST, once. -s because a Storage Box has no shell.")
    out.append("    ssh-copy-id -s -p 23 <user>@<user>.your-storagebox.de")
    out.append("")
    out.append("Type it at the interactive prompt **only**. Never as a command")
    out.append("argument — that puts it in shell history and in `ps` — and")
    out.append("never into a file. Hetzner's web UI can install the key")
    out.append("instead, which avoids typing it on the host at all, and is")
    out.append("the better route if it is available to you.")
    out.append("")
    out += [
        "## What is deliberately NOT in this file",
        "",
        "- **Claude Code's credential.** It is a user credential for an",
        "  interactive tool, authenticated once per host by a person in a tmux",
        "  session (2h §4). `secrets.env` is for what the application needs to",
        "  run, and conflating the two puts a personal login in the deploy path.",
        "- **`BACKUP_TARGET` and `PUBLIC_HOSTNAME`.** Operator values, still",
        "  unfilled. 2e and 2f are built as named inputs that REFUSE rather",
        "  than guessing a hostname or shipping an unencrypted archive off-host.",
        "- **Host addresses and the ssh user.** `hosts/production.env`,",
        "  gitignored, never printed.",
        "",
        "%d application variables from `config.VARIABLES`, plus %d infra "
        "variables declared in the generator." % (len(rows), len(INFRA_VARIABLES)),
        "",
    ]
    return "\n".join(out)


#: `NAME=` at the start of a line. The VALUE is never captured - there is no
#: group for it - so it cannot be printed by accident later.
_ASSIGN = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=")


def names_in(path):
    """The variable NAMES set in a secrets file. Values are never read."""
    found = set()
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.lstrip().startswith("#"):
                continue
            m = _ASSIGN.match(line)
            if m:
                found.add(m.group(1))
    return found


def verify_names(path):
    if not os.path.exists(path):
        sys.stderr.write("%s does not exist.\n" % path)
        return 2
    try:
        present = names_in(path)
    except OSError as exc:
        # Do not print the exception's payload: on some systems a read error
        # carries a fragment of the file.
        sys.stderr.write("cannot read %s (%s)\n" % (path, type(exc).__name__))
        return 2

    rows = variables()
    known = {r[0] for r in rows} | {n for n, _w, _y in INFRA_VARIABLES}
    worst = 0
    print("INFRA (declared in this generator, not config.VARIABLES)")
    for name, _when, _why in INFRA_VARIABLES:
        print("  %-8s %-24s (infra)"
              % ("SET" if name in present else "ABSENT", name))
    print("")
    for classification in ORDER:
        group = [r for r in rows if r[1] == classification]
        if not group:
            continue
        print("%s" % classification.upper())
        for name, _c, category, _why in group:
            state = "SET" if name in present else "ABSENT"
            if state == "ABSENT" and classification in ("required", "production"):
                worst = max(worst, 1)
            print("  %-8s %-24s (%s)" % (state, name, category))
        print("")

    extra = sorted(present - known)
    if extra:
        # Not an error: `hosts/production.env`-style operator values and the
        # two unfilled 2e/2f inputs legitimately live here too. It is printed
        # because a typo'd name looks exactly like this.
        print("NOT IN config.VARIABLES (names only, check for typos):")
        for name in extra:
            print("  %s" % name)
        print("")
    print("A SET variable is not an authenticated one. "
          "Run scripts/credential_health.py --verify for that.")
    return worst


def main():
    ap = argparse.ArgumentParser(description="The secrets move checklist")
    ap.add_argument("--out", help="write the checklist here")
    ap.add_argument("--verify-names", action="store_true",
                    help="report which names are SET or ABSENT. Never values.")
    ap.add_argument("--file", default=SECRETS_FILE,
                    help="the secrets file to inspect (default %s)" % SECRETS_FILE)
    args = ap.parse_args()

    if args.verify_names:
        return verify_names(args.file)

    text = checklist()
    if args.out:
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        sys.stderr.write("wrote %s\n" % args.out)
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
