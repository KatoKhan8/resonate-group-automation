#!/usr/bin/env python3
r"""TASK 0130 - what does a lane-day cost?

Reads the ONLY record on this machine that carries per-call token counts for
the lane sessions: Claude Code's own session transcripts under
  %USERPROFILE%\.claude\projects\<cwd-slug>\<session-uuid>.jsonl

Each `{"type":"assistant"}` record carries `message.usage` and `requestId`.
MULTIPLE RECORDS SHARE ONE requestId - one per content block of the same
assistant message - so a naive sum roughly DOUBLES the bill. We dedupe by
(sessionId, requestId) and verify that duplicates agree on usage.

`entrypoint` separates the two kinds of session in a lane tree:
  sdk-cli -> dispatched by lane_watcher.ps1 as `claude -p`  == A LANE TASK
  cli     -> the operator sitting in that tree by hand      == NOT a lane task

No network call. No model call. Read-only.
"""
import json, io, os, glob, sys, collections

HOME = os.environ.get("USERPROFILE") or os.path.expanduser("~")
PROJ = os.path.join(HOME, ".claude", "projects")

# lane -> project slug, from tools/START-ALL-LANES.ps1 (the authority on which
# worktree each lane runs in). A lane absent from this map is not a lane.
LANES = {
    "glm":         "C--Users-Zvonimir-Desktop-wt-glm-review-2026-10-14",
    "glm-b":       "C--Users-Zvonimir-Desktop-wt-glm-b-2026-10-14",
    "glm-c":       "C--Users-Zvonimir-Desktop-wt-glm-c-2026-10-14",
    "suppression": "C--Users-Zvonimir-Desktop-wt-suppression-2026-10-14",
    "pilotcaps":   "C--Users-Zvonimir-Desktop-wt-pilotcaps-2026-10-14",
    "qwen":        "C--Users-Zvonimir-qwc",
    "webapp":      "C--Users-Zvonimir-Desktop-resonate-trees-wt-webapp-2026-10-15",
}

FIELDS = ("input_tokens", "output_tokens",
          "cache_creation_input_tokens", "cache_read_input_tokens",
          "cache_1h", "cache_5m", "thinking_tokens",
          "web_search_requests", "web_fetch_requests")


def extract(u):
    """Flatten one `message.usage` into FIELDS. Cache creation is split by TTL
    because the two tiers are priced differently (5m and 1h write multipliers
    are not the same number), and a total that merges them cannot be priced."""
    cc = u.get("cache_creation") or {}
    otd = u.get("output_tokens_details") or {}
    stu = u.get("server_tool_use") or {}
    return (
        int(u.get("input_tokens") or 0),
        int(u.get("output_tokens") or 0),
        int(u.get("cache_creation_input_tokens") or 0),
        int(u.get("cache_read_input_tokens") or 0),
        int(cc.get("ephemeral_1h_input_tokens") or 0),
        int(cc.get("ephemeral_5m_input_tokens") or 0),
        int(otd.get("thinking_tokens") or 0),
        int(stu.get("web_search_requests") or 0),
        int(stu.get("web_fetch_requests") or 0),
    )


def sessions_for(slug):
    """One dict per session file: tokens deduped by requestId."""
    out = []
    for path in sorted(glob.glob(os.path.join(PROJ, slug, "*.jsonl"))):
        seen = {}
        conflicts = 0
        dup_records = 0
        entrypoints = collections.Counter()
        models = collections.Counter()
        first = last = None
        prompt = None
        sidechain_calls = 0
        for line in io.open(path, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            ts = r.get("timestamp")
            if ts:
                if first is None or ts < first:
                    first = ts
                if last is None or ts > last:
                    last = ts
            if prompt is None and r.get("type") in ("user", "queue-operation"):
                c = r.get("content") or (r.get("message") or {}).get("content")
                if isinstance(c, list):
                    c = " ".join(str(x.get("text", "")) for x in c
                                 if isinstance(x, dict))
                prompt = str(c or "")[:120].replace("\n", " ")
            if r.get("type") != "assistant":
                continue
            msg = r.get("message") or {}
            u = msg.get("usage")
            if not u:
                continue
            entrypoints[r.get("entrypoint")] += 1
            key = r.get("requestId") or msg.get("id")
            vals = extract(u)
            rec = (msg.get("model"), vals)
            if key in seen:
                dup_records += 1
                if seen[key] != rec:
                    conflicts += 1
                continue
            seen[key] = rec
            models[msg.get("model")] += 1
            if r.get("isSidechain"):
                sidechain_calls += 1
        tot = collections.defaultdict(lambda: collections.Counter())
        for model, vals in seen.values():
            for f, v in zip(FIELDS, vals):
                tot[model][f] += v
        out.append(dict(
            path=os.path.basename(path), calls=len(seen),
            dup_records=dup_records, conflicts=conflicts,
            entrypoints=dict(entrypoints), by_model={m: dict(c) for m, c in tot.items()},
            first=first, last=last, prompt=prompt,
            sidechain_calls=sidechain_calls,
            models=dict(models)))
    return out


def main():
    grand = {}
    for lane, slug in LANES.items():
        if not os.path.isdir(os.path.join(PROJ, slug)):
            print("MISSING project dir for lane %s: %s" % (lane, slug))
            continue
        grand[lane] = sessions_for(slug)
    json.dump(grand, io.open(sys.argv[1], "w", encoding="utf-8"), indent=1)
    print("wrote %s" % sys.argv[1])


if __name__ == "__main__":
    main()
