#!/usr/bin/env python3
"""2e - back up the estate's state, and PROVE the backup restores.

    py -3 scripts/server/backup.py --backup --into /var/backups/resonate
    py -3 scripts/server/backup.py --restore ARCHIVE --into /tmp/restored
    py -3 scripts/server/backup.py --drill   --into /var/backups/resonate
    py -3 scripts/server/backup.py --ship    ARCHIVE      # REFUSES today

A BACKUP THAT HAS NEVER BEEN RESTORED IS NOT A BACKUP. It is a file with a
date in its name. `--drill` is therefore the command this file exists for:
it takes a backup, restores it into a throwaway directory, and compares the
restored tree against the source BY NAME AND BY HASH. A drill that passes is
the only evidence that any of this works.

WHAT IS BACKED UP. `work/` - the queue, the campaign registry, the
heartbeats, the watch events. CLAUDE.md: "work/queue.jsonl holds record
state and work/campaigns.jsonl holds campaign state. Those two files are the
only state." Everything else in the deployment is reconstructible from git.

WHAT IS NOT, AND WHY IT IS A REFUSAL RATHER THAN AN OMISSION:

  /etc/resonate/secrets.env    NEVER. A backup is a copy that travels, and
                               the whole design of that file is that it does
                               not. It is re-created by hand from
                               docs/SECRETS-MOVE.md, which is what a
                               checklist is for.

TWO OPERATOR VALUES ARE UNFILLED, AND THIS SCRIPT REFUSES RATHER THAN
GUESSING. Per the operator's instruction for 2e and 2f: named, unfilled
inputs that refuse, rather than a guessed destination or an unencrypted
archive leaving the host.

  BACKUP_TARGET      where the archive goes off-host. UNSET. There is no
                     sensible default: a guess is either a host that does
                     not exist, or - worse - one that does and should not
                     receive this.

  BACKUP_ENCRYPTION  how the archive is encrypted before it leaves. UNSET,
                     and the 6b decision is still open. `work/` is 300 real
                     companies and 92 real contacts and "it is not ours to
                     publish" is CLAUDE.md's phrasing. An unencrypted
                     archive on someone else's disk is publishing it slowly.

`--backup`, `--restore` and `--drill` all work TODAY and are exercised by
the tests, because they are local. `--ship` is the only thing blocked, and
it refuses loudly with the names of the two values it needs.
"""
import argparse
import datetime
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

#: Named here so the refusal can print them. Read from the environment so an
#: operator filling them changes nothing in git.
BACKUP_TARGET = "BACKUP_TARGET"
BACKUP_ENCRYPTION = "BACKUP_ENCRYPTION"
#: The age PUBLIC key the archive is encrypted TO. A recipient is not a
#: secret and belongs in secrets.env. The matching PRIVATE key is generated
#: on the operator's laptop and never reaches this host - which is the whole
#: design, and carries one consequence that is easy to miss and expensive:
#: THE HOST CANNOT DECRYPT ITS OWN BACKUP. See `verify_encrypted`.
BACKUP_AGE_RECIPIENT = "BACKUP_AGE_RECIPIENT"
#: Hetzner Storage Boxes speak SSH on 23, not 22.
BACKUP_SSH_PORT = "BACKUP_SSH_PORT"

#: The first bytes of an age file. Checked before anything is uploaded: if
#: encryption silently did not happen, this is what stops plaintext leaving.
AGE_MAGIC = b"age-encryption.org/v1"

#: Never in an archive, at any size, under any flag.
NEVER_BACKED_UP = ("secrets.env", ".env")


def state_dir():
    """Where `work/` actually is, asked of the store rather than assumed."""
    from src import store
    return os.path.dirname(store.queue_path())


def _digest(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(root):
    """{relative path: sha256} for every file under `root`.

    BY NAME AND BY HASH. A restore drill that compared counts would pass
    while a file came back truncated, and the whole point of the drill is to
    be the thing that cannot pass vacuously.
    """
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            out[rel] = _digest(full)
    return out


def compare(before, after):
    """(ok, missing, extra, changed) between two inventories.

    ITS OWN FUNCTION SO IT CAN BE TESTED DIRECTLY, and it is here because a
    mutation found the gap: replacing the whole comparison with
    `len(before) == len(after)` left the drill's test GREEN, since a healthy
    restore has equal counts either way. The test that was supposed to guard
    this asserted on `inventory()` and never reached the comparison the drill
    actually uses. A guard aimed next to the thing it guards is not a guard.
    """
    missing = sorted(set(before) - set(after))
    extra = sorted(set(after) - set(before))
    changed = sorted(k for k in set(before) & set(after)
                     if before[k] != after[k])
    return (not (missing or extra or changed)), missing, extra, changed


def _excluded(rel):
    base = os.path.basename(rel)
    return base in NEVER_BACKED_UP


def backup(source, into, now=None):
    """Write a .tar.gz of `source` into `into`. Returns the archive path."""
    if not os.path.isdir(source):
        raise SystemExit("REFUSING: %s does not exist. There is no state to "
                         "back up, and an empty archive is worse than none - "
                         "it restores cleanly over a live estate." % source)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    os.makedirs(into, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(into, "resonate-state-%s.tar.gz" % stamp)

    kept = 0
    with tarfile.open(path, "w:gz") as tar:
        for rel in sorted(inventory(source)):
            if _excluded(rel):
                sys.stderr.write("excluded (never backed up): %s\n" % rel)
                continue
            tar.add(os.path.join(source, rel), arcname=rel)
            kept += 1
    if not kept:
        os.unlink(path)
        raise SystemExit("REFUSING: nothing was added to the archive. An "
                         "empty backup is a restore that silently empties "
                         "the estate.")
    sys.stderr.write("wrote %s (%d files)\n" % (path, kept))
    return path


def restore(archive, into, force=False):
    """Extract `archive` into `into`, which must be empty unless --force.

    IT WILL NOT RESTORE OVER A LIVE ESTATE BY DEFAULT. A restore is the one
    operation that can destroy the thing it is meant to protect, and the
    command to do it is short and typed in a hurry at exactly the wrong
    moment.
    """
    if os.path.exists(into) and os.listdir(into) and not force:
        raise SystemExit(
            "REFUSING: %s is not empty. A restore over live state is how a "
            "backup destroys the estate it was taken to protect. Restore "
            "into a fresh directory and compare, or pass --force if you have "
            "decided." % into)
    os.makedirs(into, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            # A tar member naming `../` escapes the destination. The archives
            # this script writes never contain one; the archives it READS are
            # whatever was handed to it.
            name = member.name.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                raise SystemExit(
                    "REFUSING: archive member %r escapes the destination."
                    % member.name)
            if _excluded(name):
                raise SystemExit(
                    "REFUSING: archive contains %r, which is never backed up "
                    "and must never be restored from one." % member.name)
        tar.extractall(into)
    sys.stderr.write("restored into %s\n" % into)
    return into


def drill(source, into):
    """Back up, restore into a throwaway directory, compare by name and hash.

    Returns (ok, report). This is the only thing in this file that is
    evidence rather than intention.
    """
    archive = backup(source, into)
    scratch = tempfile.mkdtemp(prefix="resonate-restore-drill-")
    try:
        restore(archive, scratch)
        before = {k: v for k, v in inventory(source).items()
                  if not _excluded(k)}
        after = inventory(scratch)
        ok, missing, extra, changed = compare(before, after)
        report = [
            "DRILL %s" % ("PASSED" if ok else "FAILED"),
            "  archive     %s" % archive,
            "  files       %d" % len(before),
            "  missing     %d %s" % (len(missing), missing[:5] or ""),
            "  unexpected  %d %s" % (len(extra), extra[:5] or ""),
            "  CHANGED     %d %s" % (len(changed), changed[:5] or ""),
        ]
        if ok:
            report.append("  every file came back, byte for byte.")
        return ok, "\n".join(report)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def encrypt(archive, recipient):
    """Encrypt `archive` to `recipient` with age. Returns the .age path.

    REFUSES RATHER THAN DEGRADING. If `age` is missing, or the output does
    not begin with age's own magic bytes, this raises. The failure it exists
    to prevent is the quiet one: an encryptor that is not installed, a step
    that is skipped, and 300 real companies landing on somebody else's disk
    in the clear while the log says "shipped".
    """
    if not shutil.which("age"):
        raise SystemExit(
            "REFUSING: %s=age but the `age` binary is not installed.\n"
            "  Nothing is ever shipped unencrypted. Install age, or unset\n"
            "  the target so the backup stays local." % BACKUP_ENCRYPTION)
    out = archive + ".age"
    proc = subprocess.run(["age", "-r", recipient, "-o", out, archive],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("REFUSING: age failed (%s)"
                         % (proc.stderr.strip().splitlines() or ["no detail"])[0])
    if not os.path.exists(out):
        raise SystemExit("REFUSING: age reported success and wrote no file.")
    with io.open(out, "rb") as fh:
        head = fh.read(len(AGE_MAGIC))
    if head != AGE_MAGIC:
        os.unlink(out)
        raise SystemExit(
            "REFUSING: the output does not start with age's magic bytes, so "
            "it is not an age file. Nothing is uploaded.")
    return out


def ship(archive):
    """Encrypt, then upload. Every missing input is a refusal that names it."""
    target = os.environ.get(BACKUP_TARGET, "").strip()
    encryption = os.environ.get(BACKUP_ENCRYPTION, "").strip()
    recipient = os.environ.get(BACKUP_AGE_RECIPIENT, "").strip()
    port = os.environ.get(BACKUP_SSH_PORT, "").strip() or "23"

    problems = []
    if not target:
        problems.append(
            "  %s is unset. There is no sensible default: a guessed\n"
            "  destination is either a host that does not exist or, worse,\n"
            "  one that does and should not receive this." % BACKUP_TARGET)
    if not encryption:
        problems.append(
            "  %s is unset. work/ is 300 real companies and 92 real\n"
            "  contacts and it is not ours to publish." % BACKUP_ENCRYPTION)
    elif encryption != "age":
        problems.append(
            "  %s=%r is not a scheme this understands. Only `age` is\n"
            "  implemented, and an unknown scheme is refused rather than\n"
            "  quietly treated as none." % (BACKUP_ENCRYPTION, encryption))
    if encryption == "age" and not recipient:
        problems.append(
            "  %s is unset. age encrypts TO a public recipient. Generate\n"
            "  the key pair on the operator's laptop - the private half must\n"
            "  never reach this host - and put only the age1... public half\n"
            "  here." % BACKUP_AGE_RECIPIENT)
    elif recipient and not recipient.startswith("age1"):
        problems.append(
            "  %s does not look like an age recipient (age1...). A PRIVATE\n"
            "  key in this field would be a private key in secrets.env, on\n"
            "  the host, which is the one thing this design forbids."
            % BACKUP_AGE_RECIPIENT)
    if problems:
        sys.stderr.write(
            "REFUSING to ship %s off-host.\n\n%s\n\nNothing was sent.\n"
            % (os.path.basename(archive), "\n\n".join(problems)))
        return 2

    sealed = encrypt(archive, recipient)
    sys.stderr.write("encrypted -> %s\n" % os.path.basename(sealed))

    # ONLY the .age file is named here. The plaintext archive is not an
    # argument to this command and cannot be uploaded by it.
    cmd = ["scp", "-P", port, "-o", "BatchMode=yes",
           "-o", "StrictHostKeyChecking=accept-new", sealed, target]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr.strip().splitlines() or ["no detail"])[0]
        sys.stderr.write(
            "UPLOAD FAILED (%s).\n"
            "  The encrypted archive is still here: %s\n"
            "  'Permission denied' means the host's ssh key is not installed\n"
            "  on the Storage Box yet - see docs/SECRETS-MOVE.md.\n"
            % (detail, sealed))
        return 1
    sys.stderr.write("uploaded the ENCRYPTED archive.\n")
    return 0


def verify_encrypted(sealed, identity, source):
    """Decrypt `sealed` and compare against `source`.

    NOT RUNNABLE ON THE HOST, and that is the design working rather than
    failing. The private key is generated on the operator's laptop and never
    reaches the host, so the host can encrypt and cannot decrypt. The
    consequence is easy to miss and expensive: THE HOST CANNOT VERIFY ITS OWN
    BACKUPS. The plaintext drill there proves tar round-trips; only this
    proves that what was actually shipped can be opened again, and it has to
    run where the identity is.
    """
    if not shutil.which("age"):
        raise SystemExit("REFUSING: `age` is not installed here.")
    if not os.path.exists(identity):
        raise SystemExit(
            "REFUSING: no identity at %s. This runs where the PRIVATE key is "
            "- the laptop - and nowhere else." % identity)
    scratch = tempfile.mkdtemp(prefix="resonate-verify-")
    try:
        plain = os.path.join(scratch, "decrypted.tar.gz")
        proc = subprocess.run(["age", "-d", "-i", identity, "-o", plain, sealed],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            sys.stderr.write("DECRYPT FAILED - the archive cannot be opened "
                             "with this identity.\n")
            return 1
        into = os.path.join(scratch, "tree")
        restore(plain, into)
        before = {k: v for k, v in inventory(source).items() if not _excluded(k)}
        ok, missing, extra, changed = compare(before, inventory(into))
        print("ENCRYPTED VERIFY %s" % ("PASSED" if ok else "FAILED"))
        print("  files %d  missing %d  unexpected %d  CHANGED %d"
              % (len(before), len(missing), len(extra), len(changed)))
        return 0 if ok else 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Back up the estate, and prove it restores")
    ap.add_argument("--backup", action="store_true")
    ap.add_argument("--restore", metavar="ARCHIVE")
    ap.add_argument("--drill", action="store_true")
    ap.add_argument("--ship", metavar="ARCHIVE")
    ap.add_argument("--verify-encrypted", metavar="SEALED",
                    help="decrypt and compare. Runs where the PRIVATE key "
                         "is - the laptop - never on the host.")
    ap.add_argument("--identity", help="age identity file, for "
                                       "--verify-encrypted")
    ap.add_argument("--into", help="destination directory")
    ap.add_argument("--state-dir", help="what to back up (default: work/)")
    ap.add_argument("--force", action="store_true",
                    help="restore into a non-empty directory")
    args = ap.parse_args()

    source = args.state_dir or state_dir()

    if args.verify_encrypted:
        if not args.identity:
            ap.error("--verify-encrypted needs --identity")
        return verify_encrypted(args.verify_encrypted, args.identity, source)
    if args.ship:
        return ship(args.ship)
    if args.drill:
        if not args.into:
            ap.error("--drill needs --into")
        ok, report = drill(source, args.into)
        print(report)
        return 0 if ok else 1
    if args.restore:
        if not args.into:
            ap.error("--restore needs --into")
        restore(args.restore, args.into, force=args.force)
        return 0
    if args.backup:
        if not args.into:
            ap.error("--backup needs --into")
        backup(source, args.into)
        return 0
    ap.error("one of --backup, --restore, --drill or --ship")


if __name__ == "__main__":
    sys.exit(main())
