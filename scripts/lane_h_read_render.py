"""Throwaway: read the re-rendered step 1 and the language calls."""
import sys, os, json, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = r'C:/Users/Zvonimir/Desktop/resonate-group-automation/work'
detail = json.load(open(os.path.join(W, "lane-h-render-2026-09-25.json"),
                        encoding="utf-8"))
ren = [r for r in detail if r["state"] == "rendered" and r["in_128"]]
print("rendered in the 128:", len(ren))
for r in ren[:int(sys.argv[1]) if len(sys.argv) > 1 else 8]:
    v = r["variables"]
    f = v["pack_fact"]
    print("=" * 78)
    print("%s  [%s]  %s" % (r["email"], r["country"], f["source_url"]))
    print("  anchor %d words: %r" % (r["after"]["anchor_words"],
                                     r["after"]["anchor"][:120]))
    print("  matched tokens (%d): %s"
          % (r["after"]["n_matched"], ", ".join(r["after"]["matched"][:14])))
    print()
    print(v["body_1"])
    print()
print("=" * 78)
print("HELD for language, in the 128:")
for r in detail:
    if r["in_128"] and r["state"] == "held" and "not in English" in (r["reason"] or ""):
        print("   %-34s %-16s %s" % (r["domain"], r["country"], r["reason"]))
