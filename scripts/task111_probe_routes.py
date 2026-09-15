"""TASK-111: Read-only probe of EmailBison routes not yet confirmed.

ONLY GET REQUESTS. No POST/PATCH/PUT/DELETE.

For each route: status code, response shape, field inventory.
"""
import json
import os
import sys
import urllib.request
import urllib.error

# Load env
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


def shape(data, depth=0, prefix=""):
    """Describe the shape of a response without printing values."""
    if depth > 3:
        return "..."
    if isinstance(data, dict):
        fields = []
        for k, v in list(data.items())[:30]:
            if isinstance(v, dict):
                fields.append(f"{k}: dict({len(v)} keys)")
            elif isinstance(v, list):
                fields.append(f"{k}: list[{len(v)}]")
            elif isinstance(v, str):
                fields.append(f"{k}: str")
            elif isinstance(v, bool):
                fields.append(f"{k}: bool")
            elif isinstance(v, int):
                fields.append(f"{k}: int")
            elif isinstance(v, float):
                fields.append(f"{k}: float")
            elif v is None:
                fields.append(f"{k}: null")
            else:
                fields.append(f"{k}: {type(v).__name__}")
        return "{ " + ", ".join(fields) + " }"
    elif isinstance(data, list):
        if not data:
            return "[] (empty)"
        return f"[{len(data)} items, first: {shape(data[0], depth+1)}]"
    return type(data).__name__


probes = [
    # Already confirmed routes (sanity check)
    ("GET /users", "/users", None),
    ("GET /campaigns (page 1)", "/campaigns", {"page": "1"}),

    # Routes to confirm
    ("GET /workspaces", "/workspaces", None),
    ("GET /workspaces/10", "/workspaces/10", None),
    ("GET /tags", "/tags", None),
    ("GET /lead-lists", "/lead-lists", None),
    ("GET /events (cursor)", "/events", {"pagination_type": "cursor", "per_page": "5"}),
    ("GET /leads/146592/replies", "/leads/146592/replies", {"page": "1"}),
    ("GET /leads/146592/sent-emails", "/leads/146592/sent-emails", {"page": "1"}),
    ("GET /campaigns/schedule/templates", "/campaigns/schedule/templates", None),
    ("GET /scheduled-emails/22290485", "/scheduled-emails/22290485", None),

    # Routes that were 404 before - reconfirm
    ("GET /conversations", "/conversations", None),
    ("GET /threads", "/threads", None),
    ("GET /messages", "/messages", None),
    ("GET /webhooks", "/webhooks", None),
    ("GET /webhook-urls", "/webhook-urls", None),
    ("GET /blocklist/emails", "/blocklist/emails", None),
    ("GET /blocklist/domains", "/blocklist/domains", None),
    ("GET /campaigns/352/statistics", "/campaigns/352/statistics", None),
    ("GET /campaigns/352/reports", "/campaigns/352/reports", None),
    ("GET /campaigns/352/analytics", "/campaigns/352/analytics", None),
    ("GET /campaigns/352/variants", "/campaigns/352/variants", None),
    ("GET /campaigns/352/ab-test", "/campaigns/352/ab-test", None),
    ("GET /activity", "/activity", None),
    ("GET /audit-log", "/audit-log", None),
    ("GET /workspaces/current", "/workspaces/current", None),
    ("GET /me", "/me", None),
    ("GET /user", "/user", None),
    ("GET /account", "/account", None),
    ("GET /whoami", "/whoami", None),

    # Additional routes not yet probed
    ("GET /sender-emails (page 1)", "/sender-emails", {"page": "1"}),
    ("GET /custom-variables", "/custom-variables", {"page": "1"}),
    ("GET /replies (cursor, 5)", "/replies", {"pagination_type": "cursor", "per_page": "5"}),
    ("GET /campaigns/352/sequence-steps", "/campaigns/352/sequence-steps", None),
    ("GET /campaigns/481/sequence-steps", "/campaigns/481/sequence-steps", None),
]

print("=" * 80)
print("TASK-111: READ-ONLY EmailBison ROUTE PROBE")
print(f"Base: {BASE}")
print("=" * 80)

for label, path, params in probes:
    status, data = get(path, params)
    print(f"\n--- {label} ---")
    print(f"Status: {status}")
    if isinstance(data, dict):
        # Show keys at top level
        keys = list(data.keys())
        print(f"Top-level keys: {keys}")
        if "data" in data:
            d = data["data"]
            if isinstance(d, list):
                print(f"data: list[{len(d)}]")
                if d:
                    print(f"  first item shape: {shape(d[0])}")
            elif isinstance(d, dict):
                print(f"data: {shape(d)}")
            else:
                print(f"data: {type(d).__name__} = {str(d)[:100]}")
        if "meta" in data:
            print(f"meta: {shape(data['meta'])}")
        if "message" in data:
            print(f"message: {str(data['message'])[:200]}")
        if "success" in data:
            print(f"success: {data['success']}")
    elif isinstance(data, str):
        print(f"Body: {data[:300]}")
    else:
        print(f"Body type: {type(data).__name__}")
