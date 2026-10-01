"""Read-only: how many stored angles would now be REFUSED by check_angle."""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from src import clients, generate, llm

QUEUE = os.environ["QUEUE"]

configs = {}


def config_for(name):
    if name not in configs:
        try:
            configs[name] = clients.load(name)
        except Exception as e:
            configs[name] = {"__error__": str(e)}
    return configs[name]


records = 0
contacts = 0
with_angle = 0
accepted = 0
refused = 0
reasons = collections.Counter()
examples = collections.defaultdict(list)
by_angle = collections.Counter()
refused_angles = collections.Counter()
no_config = collections.Counter()

with open(QUEUE, encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        records += 1
        cfg = config_for(rec.get("client"))
        if "__error__" in cfg:
            no_config[rec.get("client")] += 1
            cfg = {}
        for c in rec.get("contacts") or []:
            contacts += 1
            angle = c.get("angle")
            if not angle:
                continue
            with_angle += 1
            by_angle[str(angle)] += 1
            angles = generate.angles_for_contact(c, cfg)
            try:
                llm.check_angle(angle, angles)
                accepted += 1
            except llm.SchemaError as e:
                refused += 1
                refused_angles[str(angle)] += 1
                why = str(e)
                kind = ("no angles configured for persona"
                        if "configures no angles" in why
                        else "not a configured key")
                reasons[kind] += 1
                if len(examples[kind]) < 6:
                    examples[kind].append(
                        (rec.get("client"), c.get("persona"),
                         str(angle)[:70]))

print("records                 ", records)
print("contacts                ", contacts)
print("contacts with an angle  ", with_angle)
print("would be ACCEPTED       ", accepted)
print("would be REFUSED        ", refused)
print()
print("refusal reasons:", dict(reasons))
print()
print("top 12 stored angle values (count, refused):")
for value, n in by_angle.most_common(12):
    print(f"  {n:5d}  refused={refused_angles.get(value, 0):5d}  {value[:72]!r}")
print()
for kind, rows in examples.items():
    print(f"examples - {kind}:")
    for client, persona, angle in rows:
        print(f"   client={client} persona={persona} angle={angle!r}")
print()
print("records whose client config could not be loaded:", dict(no_config))
