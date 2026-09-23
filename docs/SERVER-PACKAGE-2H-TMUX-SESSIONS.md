# 2h — three named tmux sessions on the host

Operator addition, 2026-09-23. Part of the server package, after 2g.

**Status: SPECIFIED, NOT BUILT.** The units below are written against a host
that does not yet have the repository on it — `deploy.sh` (2c) is what puts
it there. Verification is explicitly scheduled for **after the shadow
deploy** (item 3): reboot, all three sessions present, attach works.

---

## 1. WHAT THIS IS FOR

Three long-lived working sessions on the host, one per worktree, that
survive both a disconnect and a reboot. You ssh in, attach, and you are
where you were.

    session      worktree                          what it is
    production   ~/resonate-group-automation       the main checkout
    agent        ~/resonate-slack-agent            the Slack agent worktree
    infra        ~/resonate-infra                  this worktree

Each opens with Claude Code available, authenticated **once per host**.

---

## 2. THE RULE THAT OUTRANKS THE CONVENIENCE

**Code is never edited on the host outside git. Deploys go only through
`deploy.sh`.**

This is the whole reason the section needs a rule at all. A tmux session on
the production host with an editor in it is an invitation to fix something
at 23:00 and discover three weeks later that the host and the repository
disagree — and the host is the one that is running. The sessions exist to
*watch, run and diagnose*, not to author.

What that means concretely:

- read, run, query, tail logs, run the suite: **yes**
- `git pull` on a tag through `deploy.sh`: **yes**
- edit a file in place, hotfix a loop, `pip install` something: **no**
- commit from the host: **no** — the worktrees are deploy targets, not
  development checkouts

`deploy.sh` (2c) is the only writer, it deploys a **tag**, and it has the
rollback. A change that is not in git is a change that does not survive the
next deploy, and one that silently loses it is worse.

---

## 3. SYSTEMD USER SERVICES

User services, not system ones, so the sessions belong to `resonate` and
carry its environment and its Claude Code credentials.

**Lingering is the part that is easy to miss.** A user manager normally
starts at first login and stops at last logout, so a session started this
way would NOT come back after a reboot until somebody logged in — which is
the opposite of what this is for. `loginctl enable-linger resonate` is what
makes the user manager start at boot.

    sudo loginctl enable-linger resonate

`~/.config/systemd/user/tmux-session@.service`, one template for all three:

    [Unit]
    Description=tmux session %i for resonate
    After=default.target

    [Service]
    Type=forking
    # `new-session -d` returns immediately, so Type=forking is correct and
    # RemainAfterExit is not - the server keeps running after tmux exits.
    ExecStart=/usr/bin/tmux new-session -d -s %i -c %h/%i-worktree
    ExecStop=/usr/bin/tmux kill-session -t %i
    Restart=no
    # A session that is killed by hand should STAY killed. Restart=always
    # would resurrect it under the operator and make `tmux kill-session`
    # look broken.

    [Install]
    WantedBy=default.target

The working directory differs per session, so `%h/%i-worktree` is a
placeholder — the real units either pass the path explicitly or the
generator writes three concrete units. Three concrete units are simpler to
read and this package prefers that:

    tmux-production.service   -c /home/resonate/resonate-group-automation
    tmux-agent.service        -c /home/resonate/resonate-slack-agent
    tmux-infra.service        -c /home/resonate/resonate-infra

Enable:

    systemctl --user enable --now tmux-production tmux-agent tmux-infra

---

## 4. CLAUDE CODE, AUTHENTICATED ONCE PER HOST

Installed for the `resonate` user and authenticated **interactively, once**,
by a person. The credential then lives in that user's home and every session
picks it up.

**It is not in git, not in `/etc/resonate/secrets.env`, and not in a unit
file.** It is a user credential for an interactive tool, not a service
credential — `secrets.env` is for what the application needs to run, and
conflating the two puts a personal login into the deploy path.

Authentication is a **manual step in the cutover runbook**, done once, by
the operator, in one of these sessions.

---

## 5. RUNBOOK SECTION (the one page)

    ssh resonate@<host>              # key only; root login is disabled

    tmux attach -t production        # the main checkout
    tmux attach -t agent             # the Slack agent worktree
    tmux attach -t infra             # this worktree

    Ctrl-b d                         # detach, leaves everything running
    tmux ls                          # what is there
    Ctrl-b (  /  Ctrl-b )            # previous / next session

Sessions **survive disconnects** — close the laptop, the work keeps running —
and **survive reboots**, because the user manager lingers and the three
units are enabled.

They do not survive `tmux kill-server`, and they are not a backup: anything
that matters is in git or in `work/`, never only in a pane.

### Mobile

Any SSH client works. Nothing about this is special to a desktop terminal:
connect, `tmux attach -t production`, detach with `Ctrl-b d`. On a phone
keyboard the prefix is usually the awkward part — most iOS and Android SSH
clients have a configurable control key or a prefix macro; set one once.

This is the intended way to check on a run from away from the desk, which is
also why the no-editing rule matters more than it looks: a phone is the
worst possible place to hand-edit a production file.

---

## 6. VERIFICATION — AFTER THE SHADOW DEPLOY

Not before: two of the three worktrees do not exist on the host until
`deploy.sh` has run.

    1. sudo reboot
    2. wait for ssh, do NOT log in as a way of starting anything
    3. systemctl --user list-units 'tmux-*'       all three active
    4. tmux ls                                    production, agent, infra
    5. tmux attach -t production                  lands in the main checkout
    6. Ctrl-b d, attach to the other two

Step 2 is the real test. If the sessions only appear once you have logged
in, **lingering is not enabled** and the whole thing fails exactly when it
is needed — after an unattended 02:00 reboot, with nobody logged in.

A reboot at 02:00Z is the scheduled one (step 5 of `provision.sh`); this
verification should NOT wait for it. Reboot deliberately, during the shadow
phase, while nothing is running that sends.
