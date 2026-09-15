"""TASK-111: Follow-up probes for edge cases."""
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


# 1. Does lead 146592 still exist?
print("=== Does lead 146592 exist? ===")
status, data = get("/leads/146592")
print(f"GET /leads/146592: {status}")
if isinstance(data, dict):
    d = data.get("data", {})
    if isinstance(d, dict):
        print(f"  id: {d.get('id')}, email: {str(d.get('email',''))[:5]}..., "
              f"first_name: {d.get('first_name')}, company: {d.get('company')}")
    else:
        print(f"  data: {str(d)[:200]}")

# 2. Try a lead we know exists from campaign 352's first page
print("\n=== Find a lead from campaign 352 ===")
status, data = get("/campaigns/352/leads", {"page": "1"})
if status == 200 and isinstance(data, dict):
    leads = data.get("data", [])
    if leads:
        lid = leads[0].get("id")
        print(f"First lead on campaign 352 page 1: id={lid}")

        # Try per-lead replies
        print(f"\n=== GET /leads/{lid}/replies ===")
        s2, d2 = get(f"/leads/{lid}/replies", {"page": "1"})
        print(f"Status: {s2}")
        if isinstance(d2, dict):
            print(f"Keys: {list(d2.keys())}")
            if "data" in d2:
                dd = d2["data"]
                if isinstance(dd, list):
                    print(f"data: list[{len(dd)}]")
                elif isinstance(dd, dict):
                    print(f"data keys: {list(dd.keys())}")
                    print(f"data: {str(dd)[:200]}")
            if "message" in d2:
                print(f"message: {d2['message']}")

        # Try per-lead sent-emails
        print(f"\n=== GET /leads/{lid}/sent-emails ===")
        s3, d3 = get(f"/leads/{lid}/sent-emails", {"page": "1"})
        print(f"Status: {s3}")
        if isinstance(d3, dict):
            print(f"Keys: {list(d3.keys())}")
            if "data" in d3:
                dd = d3["data"]
                if isinstance(dd, list):
                    print(f"data: list[{len(dd)}]")
                    if dd:
                        print(f"  first item keys: {list(dd[0].keys()) if isinstance(dd[0], dict) else type(dd[0])}")
                elif isinstance(dd, dict):
                    print(f"data: {str(dd)[:200]}")
            if "message" in d3:
                print(f"message: {d3['message']}")

# 3. Individual scheduled email - does it have a lead field?
print("\n=== GET /scheduled-emails/22290485 (full field list) ===")
status, data = get("/scheduled-emails/22290485")
if status == 200 and isinstance(data, dict):
    d = data.get("data", {})
    if isinstance(d, dict):
        print(f"All fields: {sorted(d.keys())}")
        print(f"Has 'lead' key: {'lead' in d}")
        if "lead" in d:
            print(f"lead type: {type(d['lead'])}")

# 4. Events payload detail
print("\n=== GET /events payload detail ===")
status, data = get("/events", {"pagination_type": "cursor", "per_page": "5"})
if status == 200 and isinstance(data, dict):
    events = data.get("data", [])
    if events:
        e = events[0]
        payload = e.get("payload", {})
        print(f"payload keys: {sorted(payload.keys())}")
        if "event" in payload:
            print(f"payload.event keys: {sorted(payload['event'].keys())}")
        if "data" in payload:
            pd = payload["data"]
            print(f"payload.data keys: {sorted(pd.keys()) if isinstance(pd, dict) else type(pd)}")
            if isinstance(pd, dict) and "scheduled_email" in pd:
                se = pd["scheduled_email"]
                print(f"payload.data.scheduled_email keys: {sorted(se.keys()) if isinstance(se, dict) else type(se)}")

# 5. Workspaces - how many now?
print("\n=== GET /workspaces count ===")
status, data = get("/workspaces")
if status == 200 and isinstance(data, dict):
    ws = data.get("data", [])
    print(f"Workspaces: {len(ws)}")
    for w in ws:
        if isinstance(w, dict):
            print(f"  id={w.get('id')}, name={w.get('name')}, "
                  f"personal_team={w.get('personal_team')}, main={w.get('main')}")

# 6. Check /campaigns/{id}/leads/attach-lead-list (docs only)
# This is a POST route, so we just note it as "docs only, not probed"
print("\n=== Routes NOT probed (write-only, docs only) ===")
print("POST /campaigns/{id}/leads/attach-lead-list - docs only, not probed")
print("POST /leads/bulk/csv - docs only, not probed")
print("DELETE /campaigns/{id}/remove-sender-emails - docs only, not probed")
print("DELETE /campaigns/{id} - docs only, not probed")
print("DELETE /leads/{id} - docs only, not probed")
print("POST /tags - docs only, not probed")
print("POST /tags/attach-to-leads - docs only, not probed")
print("POST /tags/attach-to-campaigns - docs only, not probed")
print("POST /tags/attach-to-sender-emails - docs only, not probed")
print("DELETE /tags/attach-to-leads - docs only, not probed")
print("DELETE /tags/attach-to-campaigns - docs only, not probed")
print("DELETE /tags/attach-to-sender-emails - docs only, not probed")
print("POST /replies/{id}/reply - docs only, not probed")
print("POST /replies/{id}/attach-email-to-reply - docs only, not probed")
print("POST /webhook-events/test-event - docs only, not probed")
print("POST /campaigns/{id}/create-schedule-from-template - docs only, not probed")
