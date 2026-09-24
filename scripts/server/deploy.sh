#!/usr/bin/env bash
# 2c - deploy the repository to the host AT A TAG, with a rollback.
#
# NOTHING HAS BEEN RUN AGAINST THE HOST. Written, reviewed and unexecuted,
# like provision.sh before it. `--check` changes nothing and is the only mode
# that should be run first.
#
#   bash deploy.sh --check --tag v2026.09.24
#   bash deploy.sh --tag v2026.09.24 --no-start     # shadow: install, do not run
#   bash deploy.sh --tag v2026.09.24
#   bash deploy.sh --rollback
#
# A TAG, NEVER A BRANCH. A branch moves under you: `git pull` on `master`
# deploys whatever master happens to be at that second, two deploys an hour
# apart are different code with the same name, and a rollback has nothing to
# return to. The tag is the deployed artifact's identity, and this script
# refuses anything that is not one.
#
# WHY A SINGLE CHECKOUT AND NOT releases/ + a `current` symlink. The usual
# atomic-symlink layout is the better pattern in general and the wrong one
# here: `work/` lives INSIDE the tree and is gitignored - it is the queue,
# the campaign registry and every heartbeat. A releases layout would orphan
# it on each deploy, or need it symlinked out, and a deploy that silently
# leaves the estate pointing at an empty `work/` is the worst failure this
# whole package exists to prevent. One checkout, `git checkout <tag>`,
# `work/` untouched because git does not track it.
#
# ZERO THIRD-PARTY DEPENDENCIES, so there is no venv step and no pip. See
# requirements.txt: every import in src/ is stdlib. If that ever stops being
# true this script needs a dependency step and the claim in requirements.txt
# needs deleting in the same commit.
set -euo pipefail

CHECK=0
ROLLBACK=0
NO_START=0
FORCE=0
SKIP_UNITS=0
TAG=""

APP_USER="${APP_USER:-resonate}"
APP_HOME="/home/${APP_USER}"
APP_DIR="${APP_DIR:-${APP_HOME}/resonate-group-automation}"
REPO_URL="${REPO_URL:-}"
SECRETS_FILE="${SECRETS_FILE:-/etc/resonate/secrets.env}"
UNIT_NAME="resonate-supervisor.service"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"
# The previously deployed ref, so a rollback has somewhere to go. Outside the
# checkout ON PURPOSE: a state file inside the tree is a state file a
# `git checkout` can change underneath the script that is reading it.
STATE_FILE="${STATE_FILE:-${APP_HOME}/.resonate-deployed}"
# Left behind by the 2026-09-23 suite run. Not a deployment: no .git, no
# work/, no hosts/. It is deleted here so nobody ever deploys onto it or
# reads it as the app.
STAGING_COPY="${STAGING_COPY:-${APP_HOME}/suite-check}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)      CHECK=1 ;;
    --rollback)   ROLLBACK=1 ;;
    --no-start)   NO_START=1 ;;
    --force)      FORCE=1 ;;
    # Used by the tests, which run on a machine with no systemd. It ANNOUNCES
    # itself rather than being inferred from `command -v systemctl`: a deploy
    # path that silently decides not to install the unit is a deploy that
    # reports success and leaves the estate unmanaged.
    --skip-units) SKIP_UNITS=1 ;;
    --tag)        TAG="${2:-}"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
  shift
done

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
note() { printf '   %s\n' "$*"; }
run()  {
  if [[ $CHECK -eq 1 ]]; then printf '   WOULD: %s\n' "$*"; else eval "$@"; fi
}
die()  { printf '\n   REFUSING: %s\n' "$*" >&2; exit 1; }

[[ $CHECK -eq 1 ]] && note "--check: nothing below will be executed."
[[ $SKIP_UNITS -eq 1 ]] && note "--skip-units: the systemd unit will NOT be installed or started."

# --------------------------------------------------------------------------
say "1. PREFLIGHT"

command -v git >/dev/null 2>&1 || die "git is not installed."

if [[ $ROLLBACK -eq 0 && -z "${TAG}" ]]; then
  die "no --tag given. This script deploys a TAG, never a branch."
fi

if [[ ! -d "${APP_DIR}/.git" ]]; then
  [[ -n "${REPO_URL}" ]] || die \
    "${APP_DIR} is not a git checkout and REPO_URL is unset. The first
   deploy needs a remote it can authenticate to; see docs/SECRETS-MOVE.md
   for the deploy key. This script will not invent one."
  say "1a. FIRST DEPLOY — cloning"
  run "git clone --no-checkout '${REPO_URL}' '${APP_DIR}'"
fi

cd "${APP_DIR}" 2>/dev/null || die "${APP_DIR} does not exist."

if [[ ! -f "${SECRETS_FILE}" ]]; then
  note "WARNING: ${SECRETS_FILE} does not exist."
  note "The unit's EnvironmentFile= will fail at start. 2d fills it."
elif [[ ! -s "${SECRETS_FILE}" ]] || ! grep -qv '^#' "${SECRETS_FILE}" 2>/dev/null; then
  note "WARNING: ${SECRETS_FILE} has no values in it, only comments."
  note "A shadow deploy is fine. Starting the estate is not."
fi

# --------------------------------------------------------------------------
say "2. THE WORKING TREE MUST BE CLEAN"
#
# The host is a DEPLOY TARGET, not a development checkout - 2h §2 is the
# rule. A dirty tree here means somebody edited code on the host, and the
# honest response is to REFUSE AND SHOW IT, not to discard it. `git checkout`
# would silently destroy a change made at 23:00 by somebody who then goes to
# bed believing it is live.
DIRTY="$(git status --porcelain 2>/dev/null || true)"
if [[ -n "${DIRTY}" ]]; then
  if [[ $FORCE -eq 1 ]]; then
    note "--force: discarding uncommitted changes on the host:"
    printf '%s\n' "${DIRTY}" | sed 's/^/     /'
    run "git checkout -- . && git clean -fd"
  else
    printf '%s\n' "${DIRTY}" | sed 's/^/     /' >&2
    die "the host's working tree has uncommitted changes (above).
   Code is never edited on the host outside git. Save what matters, then
   re-run with --force to discard it."
  fi
fi

# --------------------------------------------------------------------------
say "3. WHAT IS DEPLOYED NOW"

CURRENT="$(git describe --tags --exact-match 2>/dev/null || git rev-parse --short HEAD 2>/dev/null || echo 'nothing')"
note "current: ${CURRENT}"
if [[ -f "${STATE_FILE}" ]]; then
  note "recorded: $(cat "${STATE_FILE}")"
else
  note "recorded: (none - this is the first deploy through this script)"
fi

# --------------------------------------------------------------------------
if [[ $ROLLBACK -eq 1 ]]; then
  say "4. ROLLBACK"
  [[ -f "${STATE_FILE}" ]] || die \
    "no ${STATE_FILE}, so there is no previous deploy to return to.
   A rollback that guesses is not a rollback."
  PREVIOUS="$(sed -n '2p' "${STATE_FILE}" || true)"
  [[ -n "${PREVIOUS}" ]] || die \
    "${STATE_FILE} records no PREVIOUS ref - only the current one. The
   first deploy has nothing behind it."
  note "rolling back to: ${PREVIOUS}"
  run "git checkout --quiet --detach '${PREVIOUS}'"
  TAG="${PREVIOUS}"
else
  # ------------------------------------------------------------------------
  say "4. FETCH AND VERIFY THE TAG"

  run "git fetch --tags --prune origin"

  if [[ $CHECK -eq 0 ]]; then
    # A TAG, and proven to be one. `git rev-parse <name>` happily resolves a
    # branch, so asking for refs/tags/<name> explicitly is the whole check.
    git rev-parse --verify --quiet "refs/tags/${TAG}" >/dev/null || die \
      "'${TAG}' is not a tag in this repository.
   A branch deploys whatever it points at this second and gives a rollback
   nothing to return to."
  else
    note "WOULD verify refs/tags/${TAG} exists"
  fi

  say "5. CHECK OUT THE TAG"
  # Detached on purpose: the host is not on a branch, so nothing here can be
  # fast-forwarded by a stray pull.
  run "git checkout --quiet --detach 'refs/tags/${TAG}'"
fi

# --------------------------------------------------------------------------
say "6. RECORD WHAT IS DEPLOYED, AND WHAT IT REPLACED"
# Two lines: current, then previous. Written AFTER the checkout succeeded, so
# a failed deploy does not rewrite history it did not make.
if [[ $CHECK -eq 1 ]]; then
  note "WOULD write ${STATE_FILE}: ${TAG} (previous: ${CURRENT})"
else
  printf '%s\n%s\n' "${TAG}" "${CURRENT}" > "${STATE_FILE}"
  note "${STATE_FILE}: ${TAG} (previous: ${CURRENT})"
fi

# --------------------------------------------------------------------------
say "7. THE STAGING COPY FROM 2026-09-23"
if [[ -d "${STAGING_COPY}" ]]; then
  note "${STAGING_COPY} exists. It has no .git, no work/ and no hosts/ - it"
  note "was a suite run, not a deployment, and it is removed so nothing"
  note "deploys onto it or reads it as the app."
  run "rm -rf '${STAGING_COPY}'"
else
  note "absent already."
fi

# --------------------------------------------------------------------------
say "8. THE SYSTEMD UNIT"
if [[ $SKIP_UNITS -eq 1 ]]; then
  note "skipped by --skip-units."
else
  # Generated HERE, from the table as it is on the host at deploy time, not
  # shipped as a committed file - the interpreter path and APP_DIR are host
  # facts. The generator exits 2 if the registry is unreadable, and that exit
  # propagates: a unit for an estate with no campaign watchers must not be
  # installed.
  GEN="${APP_DIR}/scripts/server/generate_units.py"
  run "python3 '${GEN}' --out-dir '${APP_DIR}/build/systemd' --app-dir '${APP_DIR}' --user '${APP_USER}'"
  run "sudo install -m 0644 -o root -g root '${APP_DIR}/build/systemd/${UNIT_NAME}' '${UNIT_DIR}/${UNIT_NAME}'"
  run "sudo systemctl daemon-reload"
  note "the derived table it was generated against:"
  run "cat '${APP_DIR}/build/systemd/MONITOR-TABLE.txt' | sed 's/^/     /'"
fi

# --------------------------------------------------------------------------
say "9. START, OR DELIBERATELY NOT"
if [[ $SKIP_UNITS -eq 1 ]]; then
  note "skipped by --skip-units."
elif [[ $NO_START -eq 1 ]]; then
  note "--no-start: the unit is INSTALLED and NOT STARTED, and not enabled."
  note "This is the shadow deploy. Nothing watches and nothing sends."
  note "To start it later:  sudo systemctl enable --now ${UNIT_NAME}"
else
  run "sudo systemctl enable ${UNIT_NAME}"
  run "sudo systemctl restart ${UNIT_NAME}"
  # A unit that is 'active' is not an estate that is up. `is-active` answers
  # about the supervisor process; cold_start --verify answers about the
  # monitors' heartbeats, which is the question anybody actually has.
  run "sleep 5"
  if [[ $CHECK -eq 0 ]]; then
    if ! systemctl is-active --quiet "${UNIT_NAME}"; then
      printf '\n   DEPLOY FAILED: %s is not active after start.\n' "${UNIT_NAME}" >&2
      printf '   Rolling back to %s.\n' "${CURRENT}" >&2
      git checkout --quiet --detach "${CURRENT}" || true
      sudo systemctl restart "${UNIT_NAME}" || true
      printf '   Rolled back. journalctl -u %s -n 50\n' "${UNIT_NAME}" >&2
      exit 1
    fi
    note "${UNIT_NAME} is active."
  fi
fi

# --------------------------------------------------------------------------
say "10. WHAT THIS SCRIPT DELIBERATELY DOES NOT DO"
note "- does not write a single secret value (2d does, by hand)"
note "- does not copy work/ (cutover runbook, once, with sends stopped)"
note "- does not run the suite (73 baseline failures; green is not the gate)"
note "- does not start anything that sends"
note "- does not commit, push, or edit code on the host"

say "DONE"
[[ $CHECK -eq 1 ]] && note "--check: nothing was changed."
exit 0
