#!/usr/bin/env bash
# Stage the laptop's work/ onto the production host so the host's own 22:30
# nightly job can encrypt it and ship it to the Storage Box as a prodwork
# archive.
#
# WHY THIS EXISTS. Measured 2026-09-27: the host's nightly backup is healthy and
# ships every night, but `nightly-backup.sh` only builds a PRODWORK archive when a
# `~/backup/work-*` directory has been staged for it; otherwise it logs
# "prodwork: no ~/backup/work-* directory; nothing to do" and ships only the
# 13 KB sanitised state archive. Nobody had staged anything since 2026-09-25, and
# the live estate is not on the host at all: the host's work/ was 80 KB while the
# laptop's was 544 MB across 540 files. So the estate had no backup for ~40 hours
# and no automated path would ever have produced one.
#
# This script is the missing link, and it is deliberately a stopgap until the
# estate itself moves to the host. It runs at 22:00 Zagreb, thirty minutes before
# the host job at 22:30, via the Windows scheduled task ResonateStageWorkToHost.
#
# SECRETS ARE EXCLUDED, not filtered afterwards. The exclude list is applied by
# tar itself, so a secret is never read out of work/ in the first place. Ordering
# matters here: a filter that runs after the bytes have moved has already moved
# them.
#
# Read-only with respect to the provider. This ships files; it sends nothing, it
# activates nothing, it touches no campaign.
set -uo pipefail

MAIN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENVF="$MAIN/../resonate-infra/hosts/production.env"
LOG="${STAGE_LOG:-$MAIN/../pool-logs/stage-work-to-host.log}"

say () { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }

[ -f "$ENVF" ] || { say "FATAL: no $ENVF"; exit 1; }
[ -d "$MAIN/work" ] || { say "FATAL: no $MAIN/work"; exit 1; }

# Read the host values. LAST non-empty wins, deliberately: production.env carried
# HOST_IPV4 twice with the first one empty, and a naive `grep | head -1` resolved
# to nothing and failed with "connect to host  port 22". The duplicate has since
# been removed, but a parser that survives it is the right parser.
read_var () {
  local name="$1" val=""
  while IFS= read -r line; do
    line="${line#"${line%%[![:space:]]*}"}"
    case "$line" in \#*|"") continue ;; esac
    line="${line#export }"
    case "$line" in
      "$name"=*)
        local v="${line#*=}"
        v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
        v="$(printf '%s' "$v" | tr -d '\r')"
        [ -n "$v" ] && val="$v"
        ;;
    esac
  done < "$ENVF"
  printf '%s' "$val"
}

HOST="$(read_var HOST_IPV4)"
USER_="$(read_var SSH_USER)"; USER_="${USER_:-resonate}"
PORT="$(read_var SSH_PORT)"; PORT="${PORT:-22}"

[ -n "$HOST" ] || { say "FATAL: HOST_IPV4 empty in $ENVF"; exit 1; }

STAMP="$(date -u +%Y-%m-%d)"
DEST="backup/work-$STAMP"

say "staging $MAIN/work -> \$HOME/$DEST on the host (host value not logged)"

SRC_BYTES="$(du -sb "$MAIN/work" 2>/dev/null | cut -f1)"
SRC_FILES="$(find "$MAIN/work" -type f 2>/dev/null | wc -l)"
say "source: $SRC_BYTES bytes, $SRC_FILES files"

# The exclude list. Anything that could carry a credential, plus caches and locks
# that are pure noise in a backup.
tar -C "$MAIN/work" \
    --exclude='*.env' --exclude='.env*' \
    --exclude='*secret*' --exclude='*Secret*' --exclude='*SECRET*' \
    --exclude='*.key' --exclude='*.pem' --exclude='*.p12' --exclude='*.pfx' \
    --exclude='*credential*' --exclude='*token*' --exclude='*.age' \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='*.lock' \
    -czf - . \
  | ssh -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 \
        -p "$PORT" "$USER_@$HOST" \
        "set -e; rm -rf \"\$HOME/$DEST.partial\"; mkdir -p \"\$HOME/$DEST.partial\"; \
         tar -C \"\$HOME/$DEST.partial\" -xzf -; \
         rm -rf \"\$HOME/$DEST\"; mv \"\$HOME/$DEST.partial\" \"\$HOME/$DEST\"; \
         printf 'staged %s bytes in %s files\\n' \
           \"\$(du -sb \"\$HOME/$DEST\" | cut -f1)\" \
           \"\$(find \"\$HOME/$DEST\" -type f | wc -l)\""
rc=${PIPESTATUS[1]:-$?}

# Extract into `.partial` and rename only on success, so the host job can never
# find a half-written directory and ship an incomplete archive as if it were the
# estate. A truncated backup that looks valid is worse than a missing one,
# because it is believed.
if [ "$rc" -ne 0 ]; then
  say "FAILED: ssh/tar pipeline exit $rc - nothing was renamed into place"
  exit "$rc"
fi

say "staged OK; the host's 22:30 job will encrypt and ship it as prodwork"
