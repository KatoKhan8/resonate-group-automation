"""Throwaway: the tables the merge request needs, with denominators named."""
import sys, os, json, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = r'C:/Users/Zvonimir/Desktop/resonate-group-automation/work'
D = json.load(open(os.path.join(W, "lane-h-render-2026-09-25.json"),
                   encoding="utf-8"))
N = json.load(open(os.path.join(W, "lane-h-nonen-render-2026-09-25.json"),
                   encoding="utf-8"))

s128 = [r for r in D if r["in_128"]]
s105 = [r for r in D if r["in_105"]]
print("SET OVERLAP")
print("  179 total, 128 no-record, 105 under caps")
print("  in BOTH 128 and 105 :", sum(1 for r in D if r["in_128"] and r["in_105"]))
print("  in 128 only         :", sum(1 for r in D if r["in_128"] and not r["in_105"]))
print("  in 105 only         :", sum(1 for r in D if r["in_105"] and not r["in_128"]))
print("  in neither          :", sum(1 for r in D if not r["in_105"] and not r["in_128"]))
print("  cohorts of the 128  :", collections.Counter(r["cohort"] for r in s128))

print("\nANCHOR DISTRIBUTION, the 128")
for key in ("before", "after"):
    dist = collections.Counter(r[key]["anchor_words"] for r in s128 if r[key])
    tot = sum(dist.values())
    print("  %-7s n=%d  %s" % (key, tot, dict(sorted(dist.items()))))

print("\nBEFORE, the 128: what the 69 rule-1 passes actually rested on")
passes = [r["before"] for r in s128 if r["before"]["rule1"]]
print("  passes                      ", len(passes))
print("  resting on ONE distinct word", sum(1 for m in passes if m["single_word"]))
print("  that one word is `marketing`", sum(1 for m in passes if m["single_word_is_marketing"]))
words = collections.Counter()
for m in passes:
    if m["single_word"]:
        words[m["matched"][0]] += 1
print("  the single words, by count  ", words.most_common(10))
print("  category-words-only passes  ", sum(1 for m in passes if m["category_only"]))
print("  `marketing` matched at all  ",
      sum(1 for m in passes if "marketing" in m["matched"]))

print("\nAFTER, the 26: what each opener references")
for r in s128:
    if r["state"] != "rendered":
        continue
    f = r["variables"]["pack_fact"]
    print("  %-34s %-14s %-11s anchor %2d  %s"
          % (r["domain"], r["country"], f["page"], r["after"]["anchor_words"],
             f["source_url"]))

print("\nHOLDS, the 128, full reasons")
for reason, n in collections.Counter(
        r["reason"] for r in s128 if r["state"] == "held").most_common():
    print("  %4d  %s" % (n, reason))

print("\nTHE NON-ENGLISH LEVER")
n128 = [r for r in N if r["in_128"]]
print("  english-only  rendered %d of 128" % sum(1 for r in s128 if r["state"] == "rendered"))
print("  allow non-en  rendered %d of 128" % sum(1 for r in n128 if r["state"] == "rendered"))
langs = collections.Counter()
for r in n128:
    if r["state"] == "rendered":
        langs[r["variables"]["pack_fact"].get("language", "?")] += 1
print("  by language:", dict(langs))

print("\nPAGE KIND OF THE QUOTE, the 128")
print(" ", dict(collections.Counter(
    r["variables"]["pack_fact"]["page"] for r in s128
    if r["state"] == "rendered")))

print("\nEVERY QUOTE, the 128, for the by-hand quality read")
n = 0
for r in s128:
    if r["state"] != "rendered":
        continue
    n += 1
    f = r["variables"]["pack_fact"]
    print("  %2d %-26s %-14s %r" % (n, r["domain"], f["page"], f["quote"]))

print("\nIDENTITY")
tot = collections.Counter()
for r in D:
    tot.update(r["identity"])
print(" ", dict(tot))
print("  leads with >=1 admitted fact, of 179:",
      sum(1 for r in D if r["pack_facts_admitted"]))
print("  leads with >=1 admitted fact, of 128:",
      sum(1 for r in s128 if r["pack_facts_admitted"]))
print("  leads with >=1 admitted fact, of 105:",
      sum(1 for r in s105 if r["pack_facts_admitted"]))
