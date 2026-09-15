"""TASK-111: Final probes - find leads with replies, check listing shapes."""
import json
import os
import urllib.request
import urllib.error

with open("config/.env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

BASE = os.environ.get("BISON_BASE", "https://send.resonategroup.co/api").rstrip("/")
KEY = os.environ["BISON_KEY"]


def get(path, params=None):
    url = BASE + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {KEY}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = body[:500]
            return resp.status, data
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            data = body
        return e.code, data
    except Exception as e:
        return 0, str(e)


# 1. Find a lead with replies from campaign 352
print("=== Find a lead with replies ===")
# Check replies to find one with a known lead
status, data = get("/replies", {"pagination_type": "cursor", "per_page": "5"})
if status == 200 and isinstance(data, dict):
    replies = data.get("data", [])
    for r in replies:
        if isinstance(r, dict) and r.get("type") == "Tracked Reply" and r.get("lead_id"):
            lid = r["lead_id"]
            rid = r["id"]
            print(f"Found reply id={rid}, lead_id={lid}, type={r['type']}")

            # Probe per-lead replies
            print(f"\n=== GET /leads/{lid}/replies ===")
            s2, d2 = get(f"/leads/{lid}/replies", {"page": "1"})
            print(f"Status: {s2}")
            if isinstance(d2, dict):
                dd = d2.get("data", [])
                if isinstance(dd, list):
                    print(f"data: list[{len(dd)}]")
                    if dd and isinstance(dd[0], dict):
                        print(f"  first reply keys: {sorted(dd[0].keys())}")
                if "meta" in d2:
                    print(f"meta: {json.dumps(d2['meta'], indent=2)[:300]}")

            # Probe per-lead sent-emails
            print(f"\n=== GET /leads/{lid}/sent-emails ===")
            s3, d3 = get(f"/leads/{lid}/sent-emails", {"page": "1"})
            print(f"Status: {s3}")
            if isinstance(d3, dict):
                dd = d3.get("data", [])
                if isinstance(dd, list):
                    print(f"data: list[{len(dd)}]")
                    if dd and isinstance(dd[0], dict):
                        print(f"  first sent-email keys: {sorted(dd[0].keys())}")
                if "meta" in d3:
                    print(f"meta: {json.dumps(d3['meta'], indent=2)[:300]}")
            break

# 2. Does the scheduled-emails LISTING carry a lead field?
print("\n=== GET /campaigns/352/scheduled-emails (page 1, check lead field) ===")
status, data = get("/campaigns/352/scheduled-emails", {"page": "1"})
if status == 200 and isinstance(data, dict):
    emails = data.get("data", [])
    if emails and isinstance(emails[0], dict):
        print(f"First scheduled email keys: {sorted(emails[0].keys())}")
        print(f"Has 'lead' key: {'lead' in emails[0]}")
        if "lead" in emails[0]:
            lead = emails[0]["lead"]
            if isinstance(lead, dict):
                print(f"  lead keys: {sorted(lead.keys())}")

# 3. Check a single reply by id
print("\n=== GET /replies - get one reply id ===")
status, data = get("/replies", {"pagination_type": "cursor", "per_page": "5"})
if status == 200 and isinstance(data, dict):
    replies = data.get("data", [])
    if replies:
        rid = replies[0].get("id")
        # Try GET /replies/{id}
        print(f"\n=== GET /replies/{rid} ===")
        s4, d4 = get(f"/replies/{rid}")
        print(f"Status: {s4}")
        if isinstance(d4, dict):
            print(f"Keys: {sorted(d4.keys())}")
            if "data" in d4:
                dd = d4["data"]
                if isinstance(dd, dict):
                    print(f"data keys: {sorted(dd.keys())}")
                else:
                    print(f"data: {str(dd)[:200]}")
            if "message" in d4:
                print(f"message: {d4['message']}")

# 4. Lead-lists meta.total
print("\n=== GET /lead-lists meta.total ===")
status, data = get("/lead-lists", {"page": "1"})
if status == 200 and isinstance(data, dict):
    meta = data.get("meta", {})
    print(f"meta.total: {meta.get('total')}")
    lists = data.get("data", [])
    print(f"lists on page: {len(lists)}")
    for l in lists[:3]:
        if isinstance(l, dict):
            print(f"  id={l.get('id')}, name={l.get('name')}, "
                  f"status={l.get('status')}, "
                  f"processed={l.get('leads_processed')}, "
                  f"succeeded={l.get('leads_succeeded')}, "
                  f"failed={l.get('leads_failed')}")

# 5. Events - how many are there? What types?
print("\n=== GET /events - type distribution ===")
status, data = get("/events", {"pagination_type": "cursor", "per_page": "100"})
if status == 200 and isinstance(data, dict):
    events = data.get("data", [])
    types = {}
    for e in events:
        if isinstance(e, dict):
            t = e.get("payload", {}).get("event", {}).get("type", "unknown")
            types[t] = types.get(t, 0) + 1
    print(f"Events on first page: {len(events)}")
    print(f"Type distribution: {types}")
    meta = data.get("meta", {})
    print(f"meta.next_cursor present: {bool(meta.get('next_cursor'))}")

# 6. Does /campaigns/{id}/leads?search= work?
print("\n=== GET /campaigns/352/leads?search= (is search supported?) ===")
status, data = get("/campaigns/352/leads", {"search": "nonexistent_xyz_12345"})
if status == 200 and isinstance(data, dict):
    leads = data.get("data", [])
    meta = data.get("meta", {})
    print(f"Search for nonexistent: {len(leads)} results, meta.total={meta.get('total')}")

# 7. Does /campaigns/{id} DELETE exist? (Just check OPTIONS/HEAD)
# We can't do DELETE (read-only rule), but we can note it's in docs
print("\n=== Write routes (docs only, NOT probed) ===")
print("DELETE /campaigns/{id} - docs only")
print("DELETE /campaigns/{id}/remove-sender-emails - docs only")
print("DELETE /leads/{id} - docs only")
print("POST /leads/bulk/csv - docs only")
print("POST /campaigns/{id}/leads/attach-lead-list - docs only")
print("POST /campaigns/{id}/create-schedule-from-template - docs only")
