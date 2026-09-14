"""READ-ONLY provider readback for a HeyReach campaign. Writes nothing."""
import json, re, sys
sys.path.insert(0, r"C:\Users\Zvonimir\Desktop\resonate-group-automation")
from src.providers import heyreach

SINGLE = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")
DOUBLE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")

def paths(node, acc=None):
    if not isinstance(node, dict): return [[]]
    kind = node.get("nodeType")
    msgs = ((node.get("payload") or {}).get("messages") or [])
    label = kind
    if msgs and isinstance(msgs[0], str):
        label = f"{kind}:{msgs[0][:55]}"
    delay = f"{node.get('actionDelay')}{str(node.get('actionDelayUnit') or '')[:1]}"
    me = [f"{label} (+{delay})"]
    kids = [(k, node.get(k)) for k in ("conditionalNode", "unconditionalNode")
            if isinstance(node.get(k), dict)]
    if not kids: return [me]
    out = []
    for k, child in kids:
        tag = "YES" if k == "conditionalNode" else "NO"
        for sub in paths(child):
            out.append(me + [f"  [{tag}]"] + sub)
    return out

cid = int(sys.argv[1])
c = heyreach.campaign_read(cid)
print("=" * 74)
print("PROVIDER READBACK - HeyReach campaign", cid)
print("=" * 74)
for k in ("id", "name", "status", "listId", "creationTime"):
    print(f"  {k:16} {c.get(k)}")
accounts = c.get("campaignAccountIds") or c.get("accountIds") or c.get("linkedInAccountIds")
print(f"  {'senders':16} {accounts}")
print(f"  {'schedule':16} {json.dumps(c.get('campaignSchedule') or c.get('schedule'), default=str)[:200]}")

try:
    items, total = heyreach.campaign_leads(cid)
    print(f"  {'leads':16} total={total} returned={len(items)}")
    for it in items[:5]:
        print("      ", json.dumps(it, default=str)[:160])
except Exception as e:
    print("  leads            ERROR:", repr(e)[:150])

if c.get("listId"):
    try:
        lst = heyreach.list_by_id(c["listId"])
        print(f"  {'list':16} {lst.get('name')} count={lst.get('totalItemsCount') or lst.get('count')}")
    except Exception as e:
        print("  list             ERROR:", repr(e)[:120])

seq = heyreach.campaign_sequence(cid)
raw = json.dumps(seq)
nodes = heyreach.walk_sequence(seq)[0]
print(f"\n  SEQUENCE: {len(nodes)} nodes")
kinds = {}
for n in nodes:
    kinds[n.get("nodeType")] = kinds.get(n.get("nodeType"), 0) + 1
print("  node types:", kinds)
print("  merge variables :", sorted(set(SINGLE.findall(raw))))
print("  DOUBLE brace    :", sorted(set(DOUBLE.findall(raw))) or "none (correct)")
print("  'jacob' present :", "jacob" in raw.lower())
print("  '&partner'      :", "&partner" in raw.lower())
print("  InMail node     :", "INMAIL" in raw.upper())
print("  open-profile    :", "OPEN_PROFILE" in raw.upper())
print("\n  BRANCH PATHS:")
for i, p in enumerate(paths(seq), 1):
    print(f"   path {i}:")
    for s in p:
        print("     ", s)
