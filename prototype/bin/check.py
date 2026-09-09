#!/usr/bin/env python3
"""Ping every provider with the cheapest call it offers. Run before a batch."""
import os, sys, json, urllib.request, urllib.error

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV = os.path.join(ROOT, "config", ".env")
if os.path.exists(ENV):
    for line in open(ENV):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def get(url, headers=None, method="GET", body=None, timeout=25):
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers=headers or {})
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()[:300].decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode("utf-8", "replace")
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


CHECKS = [
    ("ContactOut", "https://api.contactout.com/v1/stats?period=month",
     {"authorization": "basic", "token": os.environ.get("CONTACTOUT_TOKEN", "")}),
    ("HeyReach", "https://api.heyreach.io/api/public/auth/CheckApiKey",
     {"X-API-KEY": os.environ.get("HEYREACH_KEY", "")}),
    ("EmailBison", os.environ.get("BISON_BASE", "") + "/campaigns",
     {"Authorization": "Bearer " + os.environ.get("BISON_KEY", "")}),
    ("Reoon", "https://emailverifier.reoon.com/api/v1/verify?email=test@example.com&key="
     + os.environ.get("REOON_KEY", "") + "&mode=quick", {}),
    ("AI Ark", "https://api.ai-ark.com/v1/mcp?token=" + os.environ.get("AIARK_KEY", ""), {}),
]

for name, url, hdrs in CHECKS:
    code, body = get(url, hdrs)
    mark = "ok  " if code and 200 <= code < 300 else "FAIL"
    print(f"{mark} {name:<12} {code}  {body[:120].replace(chr(10),' ')}")
