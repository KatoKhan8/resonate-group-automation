#!/usr/bin/env python3
"""Restore drill: prove the backup can be restored.

A backup nobody has restored is a belief, not a backup.  This script:

1. Extracts the newest (or specified) archive to a ``mkdtemp``.
2. Points ``store.use_directory`` at the temp dir and reads it.
3. Diffs record counts against the live store via ``store.stats()``.
4. Compares against ``docs/state/QUEUE-MANIFEST.json``.
5. Reports timing, archive size, record count, verdict.
6. Deletes the temp directory.  Two directories holding the same live
   estate is the single-writer gate broken by operator error.

Usage:
    py -3 scripts/restore_drill.py [--archive-dir DIR] [--archive PATH]
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import store


def find_newest_archive(archive_dir):
    """The most recent .zip in *archive_dir* by mtime, or None."""
    if not os.path.isdir(archive_dir):
        return None
    zips = [os.path.join(archive_dir, f) for f in os.listdir(archive_dir)
            if f.endswith(".zip")]
    if not zips:
        return None
    return max(zips, key=os.path.getmtime)


def extract_archive(archive_path, target_dir):
    """Extract a zip archive.  Raises on a corrupted or truncated file."""
    with zipfile.ZipFile(archive_path, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise zipfile.BadZipFile(
                f"corrupted entry in archive: {bad}")
        zf.extractall(target_dir)


def compare_stats(live_stats, restored_stats):
    """Return a human-readable diff of two stats dicts."""
    lines = []
    lr = live_stats.get("records", 0)
    rr = restored_stats.get("records", 0)
    if lr != rr:
        lines.append(f"  records: live={lr} restored={rr}")
    ls = live_stats.get("states", {})
    rs = restored_stats.get("states", {})
    for k in sorted(set(ls) | set(rs)):
        if ls.get(k, 0) != rs.get(k, 0):
            lines.append(f"  state {k}: live={ls.get(k, 0)} "
                         f"restored={rs.get(k, 0)}")
    ll = live_stats.get("lanes", {})
    rl = restored_stats.get("lanes", {})
    for k in sorted(set(ll) | set(rl)):
        if ll.get(k, 0) != rl.get(k, 0):
            lines.append(f"  lane {k}: live={ll.get(k, 0)} "
                         f"restored={rl.get(k, 0)}")
    return lines


def run_drill(archive_path, manifest_data=None, live_stats=None,
              live_dir=None):
    """Run the full restore drill.

    Parameters
    ----------
    archive_path : str
        Path to the zip archive to restore.
    manifest_data : dict, optional
        Parsed QUEUE-MANIFEST.json.  When None, read from the default
        location in docs/state/.
    live_stats : dict, optional
        Pre-captured live stats.  Captured from the store when None.
    live_dir : str, optional
        The live work directory.  Defaults to the store's queue directory.

    Returns
    -------
    dict  with keys ok, archive_size, restore_seconds, live_records,
    restored_records, restored_stats, stats_match, manifest_matches,
    temp_dir_exists, error.
    """
    t0 = time.monotonic()
    result = {
        "ok": False,
        "archive_size": 0,
        "restore_seconds": 0,
        "live_records": 0,
        "restored_records": 0,
        "restored_stats": {},
        "stats_match": False,
        "manifest_matches": False,
        "temp_dir_exists": False,
        "error": None,
    }

    if not os.path.isfile(archive_path):
        result["error"] = f"archive not found: {archive_path}"
        return result

    result["archive_size"] = os.path.getsize(archive_path)

    if live_dir is None:
        live_dir = os.path.dirname(store.queue_path())

    if live_stats is None:
        live_stats = store.stats()
    result["live_records"] = live_stats.get("records", 0)

    if manifest_data is None:
        manifest_path = os.path.join(ROOT, "docs", "state",
                                     "QUEUE-MANIFEST.json")
        if os.path.isfile(manifest_path):
            with open(manifest_path, encoding="utf-8") as f:
                manifest_data = json.load(f)
        else:
            manifest_data = {}

    # `store.use_directory` sets QUEUE and clears every STATE_OVERRIDES
    # entry, process-wide. This function is imported by tests, so leaving the
    # process pointed at a temp directory that `finally` then deletes is the
    # exact environment-leak class TASK-264 exists to remove - shipped by the
    # task that runs right before it. Saved here and restored unconditionally.
    _saved_env = {"QUEUE": os.environ.get("QUEUE")}
    for _var in store.STATE_OVERRIDES:
        _saved_env[_var] = os.environ.get(_var)

    tmp = tempfile.mkdtemp(prefix="rga-restore-drill-")
    try:
        try:
            extract_archive(archive_path, tmp)
        except Exception as exc:
            result["error"] = f"extraction failed: {exc}"
            shutil.rmtree(tmp, ignore_errors=True)
            return result

        store.use_directory(tmp)
        restored_recs = store.load()
        restored_stats = store.stats(restored_recs)
        result["restored_stats"] = restored_stats
        result["restored_records"] = restored_stats.get("records", 0)

        diffs = compare_stats(live_stats, restored_stats)
        result["stats_match"] = len(diffs) == 0
        result["stats_diff"] = diffs

        if manifest_data and "records" in manifest_data:
            result["manifest_matches"] = (
                restored_stats.get("records", 0)
                == manifest_data["records"])
            result["manifest_records"] = manifest_data["records"]
            if manifest_data.get("stages"):
                restored_states = restored_stats.get("states", {})
                result["manifest_stages_match"] = (
                    restored_states == manifest_data["stages"])
        else:
            result["manifest_matches"] = None

        # An empty restore is not a clean restore. Zero records compared
        # against a live store that also holds zero records satisfies
        # `stats_match` perfectly and says nothing at all - the same vacuous
        # pass this repository has now shipped three times (F-003's
        # `coverage()` against nothing, `leadstop.sweep` never incrementing,
        # and the shadow ledger trap §11 is written to avoid). The drill
        # asserts it RESTORED something before it is allowed to say ok.
        if result["restored_records"] <= 0:
            result["error"] = (
                "restored 0 records: an empty restore proves nothing. "
                "Run the drill where the live estate is, or against an "
                "archive that carries records.")
            result["ok"] = False
        elif result["manifest_matches"] is None:
            # No manifest is not a pass either. The manifest is in git
            # precisely so a restore can be checked against something that is
            # NOT in the backup; without it the drill is checking the archive
            # against itself.
            result["error"] = (
                "no QUEUE-MANIFEST.json with a record count: the drill has "
                "nothing independent of the archive to check against.")
            result["ok"] = False
        else:
            result["ok"] = (result["stats_match"]
                            and result["manifest_matches"] is True)

    except Exception as exc:
        result["error"] = str(exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        result["temp_dir_exists"] = os.path.isdir(tmp)
        for _var, _val in _saved_env.items():
            if _val is None:
                os.environ.pop(_var, None)
            else:
                os.environ[_var] = _val

    result["restore_seconds"] = round(time.monotonic() - t0, 3)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Restore drill: prove the backup restores correctly.")
    p.add_argument("--archive-dir",
                   default=os.path.join(ROOT, "backups"),
                   help="Directory containing backup archives")
    p.add_argument("--archive", default=None,
                   help="Specific archive (default: newest in dir)")
    p.add_argument("--manifest",
                   default=os.path.join(ROOT, "docs", "state",
                                        "QUEUE-MANIFEST.json"),
                   help="QUEUE-MANIFEST.json path")
    args = p.parse_args(argv)

    archive = args.archive or find_newest_archive(args.archive_dir)
    if not archive:
        print("no archive found in " + args.archive_dir)
        return 1

    manifest_data = {}
    if os.path.isfile(args.manifest):
        with open(args.manifest, encoding="utf-8") as f:
            manifest_data = json.load(f)

    live_stats = store.stats()

    result = run_drill(archive, manifest_data=manifest_data,
                       live_stats=live_stats)

    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
