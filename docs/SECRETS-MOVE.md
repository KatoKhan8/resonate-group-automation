# Secrets move checklist — /etc/resonate/secrets.env

**GENERATED from `config.VARIABLES` by `scripts/server/secrets_checklist.py`. Do not hand-edit.**

Regenerate it rather than adding a line: a hand-written list is one
somebody has to remember to edit the day a variable is added, and a
cutover that completes with a credential missing leaves an estate
that looks configured. `CONTACTOUT_KEY` does not exist, and a
session once concluded four providers were unauthenticated by
guessing names — CLAUDE.md records it.

## How the file is written

    sudo -e /etc/resonate/secrets.env        # root writes it; the app only reads it

`0640 root:resonate`, created empty by `provision.sh` step 8. systemd's
`EnvironmentFile=` loads it as root before dropping to `resonate`, so no
value ever reaches a command line, a unit file, or a shell history.

One `NAME=value` per line, no `export`, no quotes unless the value
contains a space. **Never** commit it, never echo it, never paste a
value into Slack or a transcript.

## A set variable is not an authenticated one

    py -3 scripts/server/secrets_checklist.py --verify-names   # SET / ABSENT
    py -3 scripts/credential_health.py --verify                # does it work

The first answers whether a name is present. The second actually asks
the provider and keeps five states apart, including the one that
matters most: a transport failure is NOT a bad key.

## PRODUCTION — needed BEFORE anything is deployed - it decides where state lives

- [ ] `QUEUE`  *(state)*
      where canonical state lives. Every other state file defaults to this one's directory, so it is the single lever that moves the whole set. Required in production because a container filesystem is ephemeral: unset, the queue lands somewhere that is deleted on the next deploy, and an empty store is a *valid* store - nothing downstream can tell the difference between a fresh workspace and one whose records were thrown away. Point it at a mounted volume

## REQUIRED — needed BEFORE the web application starts at all

- [ ] `AUTH_CLIENT_ID`  *(auth)*
      the OAuth client registered for this deployment. Checked against every id_token's audience
- [ ] `AUTH_CLIENT_SECRET`  *(auth)*
      authenticates this server to the provider's token endpoint. Never leaves this process and never reaches a page
- [ ] `AUTH_ISSUER`  *(auth)*
      the identity provider's base URL. Its endpoints are read from {issuer}/.well-known/openid-configuration rather than configured, so a provider that moves one does not need a redeploy
- [ ] `AUTH_PROVIDER`  *(auth)*
      'oidc', or unset for demo sign-in. Any other value is refused rather than ignored: falling back to demo here would be unauthenticated access reached by way of a variable somebody set to turn authentication on
- [ ] `AUTH_REDIRECT_URL`  *(auth)*
      where the provider sends the browser back. Must match the value registered with the provider exactly, and must be https

## LIVE — needed BEFORE the estate is started (not needed for a shadow deploy)

- [ ] `AIARK_KEY`  *(providers)*
      enrichment. A fallback, and one that needs a stated reason
- [ ] `APIFY_TOKEN`  *(providers)*
      research actors. Bounded, SSRF-guarded, and not run in this build
- [ ] `BISON_KEY`  *(providers)*
      EmailBison, the email sending platform. Reads only in this build
- [ ] `BLITZ_API_KEY`  *(providers)*
      the second structured provider, and never the first one asked. The only source for a company's mail domain, and the only index that addresses a company by its LinkedIn URL. Bills in records, not credits
- [ ] `CONTACTOUT_TOKEN`  *(providers)*
      company-first enrichment. People-count is free; everything else burns credits
- [ ] `DELIVERABLE_KEY`  *(providers)*
      verification. Its wire contract has never been validated - see LIVE-VALIDATION-PLAN.md
- [ ] `HEYREACH_KEY`  *(providers)*
      HeyReach, the LinkedIn platform. Reads only in this build
- [ ] `LLM_API_KEY`  *(providers)*
      draft generation, through any OpenAI-compatible endpoint
- [ ] `LLM_BASE_URL`  *(providers)*
      the OpenAI-compatible endpoint to call. Set it to point at OpenRouter, a local server, or anything else speaking that shape; unset means no model is configured and generation refuses
- [ ] `LLM_MODEL`  *(providers)*
      the model id to ask for, in whatever form the endpoint expects
- [ ] `REOON_KEY`  *(providers)*
      the escalation verifier, reached only when two providers disagree
- [ ] `SLACK_BOT_TOKEN`  *(slack)*
      a token alone never enables posting; SLACK_LIVE must also be set
- [ ] `SLACK_OPS_CHANNEL`  *(slack)*
      the one global operations channel. Per-workspace channels are workspace policies, never environment variables
- [ ] `SLACK_SIGNING_SECRET`  *(slack)*
      without it every inbound Slack interaction is refused rather than trusted

## OPTIONAL — needed only if that behaviour is wanted

- [ ] `APP_MODE`  *(app)*
      demo or production. Unset defaults to demo, which is the safe default. Set *explicitly* to demo it also installs the fictional estate, which is how one start command serves both the published demonstration and the real deployment
- [ ] `AUTH_ALLOWED_DOMAINS`  *(auth)*
      comma-separated email domains that may sign in at all. A second fence in front of the membership table, not a replacement for it: an allowed domain with no user row still gets nowhere
- [ ] `DATABASE_URL`  *(database)*
      reserved, and read by nothing. There is no SQL backend in this build - no driver, no schema, no query - so a Postgres instance provisioned for it would sit empty while the real state sat on disk. It blocked production startup until the release audit noticed that it required a database nothing used while QUEUE, which decides whether client data survives a deploy, was optional. DATABASE-MIGRATION.md is the plan that would make this real
- [ ] `DIGEST_HOUR`  *(app)*
      the hour the digest covers up to, 0-23, UTC. 8 by default. An hour that cannot be read is refused rather than defaulted: a digest arriving at the wrong time every day looks like a working schedule
- [ ] `DIGEST_SCHEDULE`  *(app)*
      off, daily or weekdays. Off unless set. The digest rides the reply watcher's thread, so it needs no second timer - but it is switched separately, because a workspace with no provider credentials still wants a summary
- [ ] `REPLY_POLL_ENABLED`  *(app)*
      reconcile replies on a timer. Off unless set: a background thread that reaches a provider is not a default. It reads, and what it protects is how quickly a confirmed reply stops that lead
- [ ] `REPLY_POLL_PROVIDERS`  *(app)*
      a subset of emailbison,heyreach. Both by default. An unknown name is refused rather than ignored, because polling nothing would otherwise report healthy
- [ ] `REPLY_POLL_SECONDS`  *(app)*
      seconds between sweeps. 300 by default; under 60 is raised to 60
- [ ] `SESSION_SECRET`  *(auth)*
      reserved, and read by nothing. Sessions are opaque tokens held in this process, so there is no cookie to sign - it was classified REQUIRED while production authentication did not exist, which made it a required variable nothing consumed. The four AUTH_ variables above are what production actually needs. It stays named for the session store a second process would need
- [ ] `WEB_HOST`  *(app)*
      loopback by default; a deployment binds behind a TLS proxy
- [ ] `WEB_PORT`  *(app)*
      8765 by default. A platform usually supplies this as $PORT

## INFRA — not in `config.VARIABLES`, and read by the tooling

Nothing in `src/` reads any of these. They are listed because
a variable nobody lists is a variable nobody sets.

- [ ] `BACKUP_TARGET`  *(before the first off-host backup)*
      user@host:/path of the Storage Box. SSH, not SMB.
- [ ] `BACKUP_ENCRYPTION`  *(with BACKUP_TARGET)*
      `age`. Any other value is refused rather than treated as none.
- [ ] `BACKUP_AGE_RECIPIENT`  *(with BACKUP_TARGET)*
      the age PUBLIC key (age1...). NEVER the private key: the private half is generated on the operator's laptop and must never reach this host. The consequence is deliberate - the host can encrypt and cannot decrypt, so it cannot verify its own backups.
- [ ] `BACKUP_SSH_PORT`  *(optional)*
      23 by default, which is what a Hetzner Storage Box speaks.
- [ ] `PUBLIC_HOSTNAME`  *(before Caddy starts)*
      the name on the certificate. DNS must already resolve to this host: TLS-ALPN issuance happens at startup, and a failure is rate-limited per ACCOUNT for a week.
- [ ] `WEBHOOK_SIGNING_SECRET`  *(before the receiver accepts anything)*
      HMAC-SHA256 shared secret. Without it every POST is refused rather than recorded unverified. Generate it on the host - it is not a value that needs to come from anywhere else.

### The Storage Box password — where and when

**It does not go in this file, and it is not typed on the
host more than once.** Install the host's ssh public key on
the Storage Box, and authentication afterwards is by key:

    # ON THE HOST, once. -s because a Storage Box has no shell.
    ssh-copy-id -s -p 23 <user>@<user>.your-storagebox.de

Type it at the interactive prompt **only**. Never as a command
argument — that puts it in shell history and in `ps` — and
never into a file. Hetzner's web UI can install the key
instead, which avoids typing it on the host at all, and is
the better route if it is available to you.

## What is deliberately NOT in this file

- **Claude Code's credential.** It is a user credential for an
  interactive tool, authenticated once per host by a person in a tmux
  session (2h §4). `secrets.env` is for what the application needs to
  run, and conflating the two puts a personal login in the deploy path.
- **`BACKUP_TARGET` and `PUBLIC_HOSTNAME`.** Operator values, still
  unfilled. 2e and 2f are built as named inputs that REFUSE rather
  than guessing a hostname or shipping an unencrypted archive off-host.
- **Host addresses and the ssh user.** `hosts/production.env`,
  gitignored, never printed.

31 application variables from `config.VARIABLES`, plus 6 infra variables declared in the generator.
