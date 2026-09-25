# Buggie — evaluation before use

**Asked for by the operator, 2026-09-26: "evaluate it first (what it needs,
what it reads, whether it can see secrets or work/); if it is safe, install it
and run it."**

Source inspected at `https://github.com/athm793/buggie-skill`, cloned and read
rather than judged from the marketing page. Apache 2.0, author `athm793`.

## VERDICT: safe to run, with one containment that is not optional

Run it against a **fresh clone from GitHub**, never against the working tree.
Reason below.

## It is already installed

No installation was needed. This machine already has it:

    ~/.claude/agents/        13 agent definitions
    ~/.claude/commands/buggie.md
    ~/.claude/buggie/        scripts, workflows

The 13 agents match the published repository exactly by name.

## What it needs

Node 18 or newer. This machine has v24.20.0. No API key of its own. No
account, no licence key, no registration.

## What it reads

**The entire codebase.** That is the whole point of it, and it is also the
finding that matters here.

## The site's central safety claim is weaker than stated

The site says: *"The hunters cannot write. Every hunting specialist is defined
with no Edit and no Write tool at all."*

**Read literally that is true. Read as a security property it is not.**

    13 of 13 agents are granted Bash.

`Bash` subsumes both denied tools. An agent with Bash can read
`config/.env`, read `work/queue.jsonl`, write a file with `>`, and reach the
network with `curl`. Denying `Edit` and `Write` while granting `Bash`
constrains style, not capability.

One agent, `surgical-fixer.md`, is additionally granted `Edit` and `Write`
outright. That is by design - it is the fixer, used only on pre-confirmed
findings - but it means the installed set does contain a write-capable agent,
which the page's wording does not lead a reader to expect.

**This is not an accusation.** Nothing in the scripts reaches the network:

    grep -nE "fetch\(|https?://|axios|request\(|curl" scripts/*.mjs scripts/*.js
    -> no matches

The code does what it says. The point is narrower and it still matters: **the
read-only guarantee is not enforced by the tool, so it cannot be relied on in
a repository holding credentials and other people's personal data.**

## Why that matters HERE specifically

This repository has two things most do not:

    config/.env    live provider credentials
    work/          300 real companies, 92 real contacts, prospect research

Both are gitignored, deliberately. Neither is tracked:

    git ls-files | grep -cE "^config/\.env$|^work/"   ->  0

So they exist on disk but not in git, and an agent reading "the entire
codebase" from the working tree would read both. Even with no exfiltration by
the tool, **whatever an agent reads becomes model context**, and prospect PII
and API keys should not enter a review transcript.

## The containment

**Run it against a fresh clone.** A clone from GitHub contains the code and
none of the data, because both exclusions are already in `.gitignore` and
verified above at zero tracked files.

    git clone <repo> /tmp/buggie-target
    # /tmp/buggie-target has no config/.env and no work/

This costs nothing, needs no change to Buggie, and turns a "should be fine"
into a property that can be checked in one command.

## The second cost, which is not a safety question

Buggie runs **13 Claude agents**. Claude usage was reported by the operator at
70 to 75 percent of the weekly limit, and the standing order moved bounded
work to Qwen for exactly that reason. A full sweep is a meaningful spend
against the constrained budget, so it is run **scoped** - master and merged
branches, findings handed to Qwen as tasks - rather than as an open-ended
audit.

## What it produces

Findings, not changes. `--fix` is explicit and is not used here. Findings
become Qwen tasks with acceptance checks, per the standing order.
