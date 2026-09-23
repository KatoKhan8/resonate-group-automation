#!/usr/bin/env bash
# Provision a Hetzner Cloud host for Resonate. Ubuntu 26.04 LTS.
#
# NOTHING HAS BEEN RUN AGAINST THE HOST. This script is written, reviewed and
# unexecuted, per the operator's instruction. `--check` changes nothing and is
# the only mode that should be run first.
#
#   bash provision.sh --check     # report what it WOULD do, change nothing
#   bash provision.sh             # do it, idempotently
#
# Host facts it was written against, given by the operator 2026-09-23:
#   Hetzner Cloud, hel1 (Helsinki), 4 GB plan, ~75 GB disk, IPv4 + IPv6
#   Ubuntu 26.04.1 LTS, kernel 7.0
#
# THE FIREWALL IS THE FIRST THING THAT HAPPENS, before any package is
# installed and before any service can bind. A host that is reachable while it
# is being configured is a host being configured in public.
#
# ORDER MATTERS INSIDE THE FIREWALL STEP TOO: allow 22 BEFORE enabling ufw.
# `ufw enable` with a default-deny policy and no ssh rule locks you out of a
# remote host, and the recovery is Hetzner's web console.
set -euo pipefail

CHECK=0
[[ "${1:-}" == "--check" ]] && CHECK=1

APP_USER="${APP_USER:-resonate}"
APP_HOME="/home/${APP_USER}"
APP_DIR="${APP_DIR:-${APP_HOME}/resonate-group-automation}"
SECRETS_FILE="/etc/resonate/secrets.env"

# The Python floor the code actually needs, not a version copied from a brief.
# Checked at runtime against whatever 26.04 ships rather than assumed: this
# script has never been run, and asserting a version nobody has verified is
# how a cutover discovers it at 23:00.
PY_MIN_MAJOR=3
PY_MIN_MINOR=12

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
note() { printf '   %s\n' "$*"; }
run()  {
  if [[ $CHECK -eq 1 ]]; then printf '   WOULD: %s\n' "$*"; else eval "$@"; fi
}

[[ $CHECK -eq 1 ]] && note "--check: nothing below will be executed."

# --------------------------------------------------------------------------
say "1. FIREWALL FIRST — 22 and 443 only"

run "apt-get update -qq"
run "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ufw"

# Allow BEFORE enable. See the header.
run "ufw allow 22/tcp  comment 'ssh'"
run "ufw allow 443/tcp comment 'https'"
run "ufw default deny incoming"
run "ufw default allow outgoing"
run "yes | ufw enable"
run "ufw status verbose"

note "PORT 80 IS CLOSED, AND THAT IS A DECISION WITH A CONSEQUENCE."
note "Let's Encrypt HTTP-01 validation needs port 80. With 80 closed, the"
note "reverse proxy MUST use TLS-ALPN-01, which completes on 443 alone."
note "Caddy will try HTTP-01 first unless told otherwise, so its config has"
note "to disable that challenge explicitly - see 05-caddy in this directory."
note "Opening 80 just for ACME is the other option; it is not taken here."

# --------------------------------------------------------------------------
say "2. USER"

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  run "adduser --disabled-password --gecos '' ${APP_USER}"
else
  note "user ${APP_USER} already exists"
fi
run "usermod -aG sudo ${APP_USER}"

# The operator's key, copied from root's authorized_keys rather than pasted
# into this file. A key in a repository is a key in a repository.
run "install -d -m 700 -o ${APP_USER} -g ${APP_USER} ${APP_HOME}/.ssh"
run "cp /root/.ssh/authorized_keys ${APP_HOME}/.ssh/authorized_keys"
run "chown ${APP_USER}:${APP_USER} ${APP_HOME}/.ssh/authorized_keys"
run "chmod 600 ${APP_HOME}/.ssh/authorized_keys"

say "2b. SSH HARDENING"
run "sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config"
run "sed -i 's/^#\\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config"
note "Root login and passwords off. VERIFY A SECOND SSH SESSION AS"
note "${APP_USER} BEFORE CLOSING THE ONE YOU ARE IN. Reloading sshd with a"
note "broken config and no open session is the same lockout as the ufw one."
run "sshd -t"
run "systemctl reload ssh"

# --------------------------------------------------------------------------
say "3. TIME SYNC — before anything that timestamps"

run "timedatectl set-timezone UTC"
run "systemctl enable --now systemd-timesyncd"
run "timedatectl show -p NTPSynchronized --value"

note "UTC, not Europe/Zagreb, deliberately. Every send window in this"
note "repository is written in Z (487 is 07:00-15:00Z, 489 is 13:00-21:00Z)"
note "and systemd timers on a DST-shifting zone move twice a year against"
note "windows that do not. The operator reads Zagreb; the host thinks in UTC;"
note "the conversion is written down once, in step 5."

# --------------------------------------------------------------------------
say "4. PACKAGES"

run "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \\
     git curl ca-certificates sqlite3 fail2ban \\
     python3 python3-venv python3-pip"

say "4b. PYTHON VERSION — checked, not assumed"

# One `run` line, so --check prints it and writes nothing. The first version
# of this wrote a helper to /tmp unconditionally, which made --check a mode
# that still touched the filesystem - a dry run that is not dry is worse than
# no dry run, because it is believed.
PYGUARD='V=$(python3 -c "import sys; print(\"%d.%d\" % sys.version_info[:2])"); '
PYGUARD+='MAJ=${V%%.*}; MIN=${V##*.}; echo "   python3 is $V"; '
PYGUARD+='if [ "$MAJ" -lt '"${PY_MIN_MAJOR}"' ] || { [ "$MAJ" -eq '"${PY_MIN_MAJOR}"' ] && [ "$MIN" -lt '"${PY_MIN_MINOR}"' ]; }; then '
PYGUARD+='echo "   REFUSING: this codebase needs >= '"${PY_MIN_MAJOR}.${PY_MIN_MINOR}"' and the host has $V." >&2; exit 1; fi'
run "$PYGUARD"

note "26.04's default python3 is whatever 26.04 ships, and this script has"
note "never been run against it. It is CHECKED rather than pinned to a"
note "version from a brief: the local machine develops on 3.14, so anything"
note "from 3.12 up is expected to work and only the host can confirm it."
note "THE REAL CONFIRMATION IS THE SUITE, not this check: run"
note "'python3 -m tests.offline' on the host before cutover and diff the"
note "failing set by name against docs/state/SUITE-BASELINE-2026-09-23.json."
note "A version that imports fine and fails 40 tests is the thing to catch."

# --------------------------------------------------------------------------
say "5. UNATTENDED UPGRADES — reboot pinned inside the no-send window"

run "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq unattended-upgrades"

read -r -d '' UU <<'EOF' || true
// Managed by scripts/server/provision.sh. Do not hand-edit.
//
// THE REBOOT WINDOW IS THE POINT OF THIS FILE.
// On 2026-09-23 a Windows Update restart at 05:29 local took the monitors
// down for four hours. The reboot is not being prevented here - it is being
// moved to a time when nothing is sending, and cold_start brings the estate
// back afterwards.
//
// Send windows, from CLAUDE.md:   487  Mon-Fri 07:00-15:00Z
//                                 489  Mon-Fri 13:00-21:00Z
// Nightly sourcing:               02:00 Europe/Zagreb = 00:00Z
//
// So the quiet band is 21:00Z -> 07:00Z, and 02:00Z sits inside it with the
// sourcing run finished and five hours before the first send window opens.
// 02:00Z is 04:00 in Zagreb during CEST and 03:00 during CET.
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-WithUsers "true";
Unattended-Upgrade::Automatic-Reboot-Time "02:00";
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF

if [[ $CHECK -eq 1 ]]; then
  note "WOULD write /etc/apt/apt.conf.d/52resonate-unattended-upgrades"
else
  printf '%s\n' "$UU" > /etc/apt/apt.conf.d/52resonate-unattended-upgrades
fi
run "systemctl enable --now unattended-upgrades"

note "A REBOOT IN THE QUIET WINDOW IS STILL A REBOOT. It is survivable only"
note "because the supervisor comes back by itself - systemd units in step 7,"
note "and cold_start --verify to confirm on two witnesses."

# --------------------------------------------------------------------------
say "6. FAIL2BAN"

read -r -d '' F2B <<'EOF' || true
[sshd]
enabled = true
port    = 22
maxretry = 5
findtime = 600
bantime  = 3600
EOF
if [[ $CHECK -eq 1 ]]; then
  note "WOULD write /etc/fail2ban/jail.d/resonate.conf"
else
  install -d /etc/fail2ban/jail.d
  printf '%s\n' "$F2B" > /etc/fail2ban/jail.d/resonate.conf
fi
run "systemctl enable --now fail2ban"

# --------------------------------------------------------------------------
say "7. DOCKER — for the F6 sourcing service only, installed and NOT enabled"

run "install -m 0755 -d /etc/apt/keyrings"
run "curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc"
run "chmod a+r /etc/apt/keyrings/docker.asc"
run "echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \$(. /etc/os-release && echo \$VERSION_CODENAME) stable' > /etc/apt/sources.list.d/docker.list"
run "apt-get update -qq"
run "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin"
run "systemctl disable --now docker.socket docker.service || true"
run "usermod -aG docker ${APP_USER}"

note "INSTALLED AND DISABLED, on purpose. The sourcing service is F6 and is"
note "not approved: its legal prerequisites (F6a) are unanswered. Docker's"
note "own daemon idles around 100 MB, and on a 4 GB host that is worth not"
note "spending until something needs it."
note "IF 26.04 HAS NO DOCKER CE REPO YET, this step fails loudly rather than"
note "silently installing docker.io. Check the codename before cutover; the"
note "Docker repo has historically lagged a new LTS by weeks."

# --------------------------------------------------------------------------
say "8. SECRETS FILE — root-owned, never in git, never printed"

run "install -d -m 0750 -o root -g ${APP_USER} /etc/resonate"
if [[ $CHECK -eq 1 ]]; then
  note "WOULD create ${SECRETS_FILE} (0640 root:${APP_USER}) if absent"
else
  [[ -f "${SECRETS_FILE}" ]] || {
    printf '# Resonate secrets. Filled by hand. NEVER committed, never echoed.\n' \
      > "${SECRETS_FILE}"
    chown root:"${APP_USER}" "${SECRETS_FILE}"
    chmod 0640 "${SECRETS_FILE}"
  }
fi
note "0640 root:${APP_USER} - the app reads it, only root writes it, and"
note "systemd's EnvironmentFile= loads it without it ever being on a command"
note "line or in the unit file. The key checklist is docs/SECRETS-MOVE.md."

# --------------------------------------------------------------------------
say "9. WHAT THIS SCRIPT DELIBERATELY DOES NOT DO"
note "- does not clone the repository (deploy.sh does, on a tag)"
note "- does not install systemd units (05-units step, separately reviewable)"
note "- does not copy work/ (cutover runbook, once, with sends stopped)"
note "- does not start anything that sends"
note "- does not write a single secret value"

say "DONE"
[[ $CHECK -eq 1 ]] && note "--check: nothing was changed."
exit 0
