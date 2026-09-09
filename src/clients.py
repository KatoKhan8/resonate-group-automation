"""Client config: config/clients/<client>.yaml. BUILD-SPEC section 4.

The repo has no third-party dependencies, so this reads the subset of YAML the
client files actually use: nested maps by indentation, scalars, inline lists in
square brackets (which may wrap across lines), comments, ints and booleans.

Anything outside that subset raises rather than being silently misread: a
misparsed persona cap is a spend, and a misparsed geo is a live customer getting
cold sequenced.
"""
import os
import re

from . import store

CLIENTS = os.path.join(store.ROOT, "config", "clients")


def clients_dir():
    """Where client configs are read from.

    Resolved per call rather than captured at import, because demo mode points
    it at a disposable directory of fictional clients *after* this module is
    already loaded. Without the override, demo mode would have to write its
    fictional workspaces into `config/clients/`, next to the real ones.
    """
    return os.environ.get("CLIENTS_DIR") or CLIENTS


class ConfigError(RuntimeError):
    """The client config could not be read as written."""


def scalar(text):
    text = text.strip()
    if not text:
        return None
    if text[0] in "\"'" and text[-1:] == text[0] and len(text) > 1:
        return text[1:-1]
    low = text.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if text.isdigit() or (text[0] == "-" and text[1:].isdigit()):
        return int(text)
    return text


def inline_list(text):
    inner = text.strip()[1:-1]
    return [scalar(part) for part in inner.split(",") if part.strip()]


def strip_comment(line):
    """Remove a trailing comment, but not a # inside quotes or a url."""
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def parse(text):
    """The YAML subset. Returns nested dicts."""
    root, stack = {}, [(-1, {})]
    stack[0] = (-1, root)
    pending = None            # an inline list still collecting its closing bracket

    for raw in text.splitlines():
        if pending is not None:
            target, key, buf = pending
            buf += " " + strip_comment(raw).strip()
            if "]" in buf:
                target[key] = inline_list(buf)
                pending = None
            else:
                pending = (target, key, buf)
            continue

        line = strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()

        if body.startswith("- "):
            raise ConfigError(f"block lists are not supported, use [a, b]: {body!r}")
        if ":" not in body:
            raise ConfigError(f"cannot parse line: {body!r}")

        key, _, value = body.partition(":")
        key, value = key.strip(), value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ConfigError(f"indentation error at {body!r}")
        parent = stack[-1][1]

        if value == "":
            child = {}
            parent[key] = child
            stack.append((indent, child))
        elif value.startswith("["):
            if "]" in value:
                parent[key] = inline_list(value)
            else:
                pending = (parent, key, value)
        else:
            parent[key] = scalar(value)
    if pending is not None:
        raise ConfigError("unterminated list")
    return root


# A client slug becomes a filename, so it is validated rather than trusted.
# Nothing accepted a slug from outside this process until a workspace could
# be created from the web, and "../../etc/passwd" is a perfectly good dict
# key right up until it is joined onto a path.
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")


# Windows opens these as devices whatever the extension, so `con.yaml` is
# not a file. The grammar above already refuses dots, slashes, colons,
# control characters and a trailing dot or space; these are the names that
# look ordinary and are not.
RESERVED = frozenset(
    ["con", "prn", "aux", "nul"]
    + [f"com{n}" for n in range(1, 10)]
    + [f"lpt{n}" for n in range(1, 10)])


def valid_slug(slug):
    text = str(slug or "")
    return bool(SLUG.match(text)) and text not in RESERVED


def path_for(client):
    if not valid_slug(client):
        raise ConfigError(
            f"{client!r} is not a usable client name. Lower case letters, "
            "digits and hyphens, starting with a letter or digit.")
    return os.path.join(clients_dir(), f"{client}.yaml")


def exists(client):
    return os.path.exists(path_for(client))


def overrides_for(client, rows=None):
    """The workspace settings that apply on top of this client's file.

    A workspace admin changes a handful of settings from `/settings` and
    they are stored beside the workspace rather than written back into a
    YAML file with comments in it. Applying them here rather than only in
    `repo.config` is the difference between one answer and two: before
    this, `python -m src.icp --client productive` read the file and the
    web layer read the file plus the overrides, so a workspace that had
    raised `verification.required_confirmations` to three was verifying at
    two from every command line. Nothing said so.

    An estate where two workspaces claim the same client has no single
    answer, so it raises rather than picking one. It cannot arise from the
    product - `create_workspace` refuses a duplicate slug and a config
    file that already exists - only from a hand-edited table, and a loud
    refusal is the right way to find that out.
    """
    from . import workspaces

    matches = [w for w in workspaces.workspaces(rows)
               if (w.get("client") or w.get("slug")) == client]
    if len(matches) > 1:
        names = ", ".join(sorted(str(w.get("slug")) for w in matches))
        raise ConfigError(
            f"{len(matches)} workspaces claim client {client!r} ({names}), "
            "so there is no single set of settings for it. Point each "
            "workspace at its own client file.")
    if not matches:
        return {}
    return workspaces.policy(matches[0].get("slug"), rows)


def load(client, workspace=None, rows=None):
    """Load a client config, refusing anything that is still a template.

    `workspace` names the workspace whose settings to apply, for a caller
    that already knows. Left out, it is inferred from the workspace table -
    which is what every one of the sixty-odd call sites that pass only a
    client name relies on.
    """
    if str(client).endswith(".example") or str(client).endswith("-example"):
        raise ConfigError(
            f"{client} is a template name. Copy it to a real client file, fill "
            "in the values and remove the `example: true` line.")
    path = path_for(client)
    if not os.path.exists(path):
        raise ConfigError(f"no config/clients/{client}.yaml")
    with open(path, encoding="utf-8") as f:
        config = parse(f.read())
    if config.get("example") is True:
        raise ConfigError(
            f"config/clients/{client}.yaml is still the unedited template: it "
            "carries `example: true`. Fill in the real values and remove that "
            "line before running a batch for this client.")
    config.setdefault("name", client)
    config.setdefault("personas", {})

    from . import workspaces

    settings = (workspaces.policy(workspace, rows) if workspace
                else overrides_for(client, rows))
    return workspaces.apply_policy(config, settings)



# A new client, written conservatively. What is deliberately absent is as
# important as what is here: no market and no personas, so the readiness
# checklist says so rather than a starter's placeholder being mistaken for
# somebody's actual ICP and used to select real people.
#
# Nothing about verification, sending or approval appears at all. Those are
# policy with safe defaults in code, and a per-client file that could
# restate them is a per-client file that could weaken them.
STARTER = """# Created by Resonate. Fill in the market and personas before
# running a batch for this client - the workspace setup page lists what is
# still missing.
name: {name}
domain: {domain}
booking_link: {booking_link}
sender:
  mode: client_rep          # the sending inbox adds its own signature
cadence: default
tone:
  email: professional, plain, no buzzwords
  linkedin: casual, human
"""


def create(slug, name, domain, booking_link="", created_by="unknown"):
    """Write a starter config for a new client. Never overwrites.

    Returns the path written. Refusing an existing file rather than merging
    is the whole safety of this: a client's ICP is somebody's real
    targeting, and a create that quietly replaced one would be the most
    expensive convenience in the product.
    """
    if not valid_slug(slug):
        raise ConfigError(
            f"{slug!r} is not a usable client name. Lower case letters, "
            "digits and hyphens, starting with a letter or digit.")
    path = path_for(slug)
    if os.path.exists(path):
        raise ConfigError(f"config/clients/{slug}.yaml already exists")
    if not str(name or "").strip():
        raise ConfigError("a client needs a name")

    body = STARTER.format(
        name=scalar_out(name), domain=scalar_out(domain),
        booking_link=scalar_out(booking_link))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(body)
    return path


def scalar_out(value):
    """One line of YAML scalar, with nothing in it that could be structure.

    The parser here reads a subset of YAML and the writer stays inside it:
    a name carrying a colon, a newline or a leading dash would come back as
    something other than what was typed.
    """
    # Every character that could start a structure becomes a space, and
    # then one collapse handles the lot - including the newlines, which are
    # the load-bearing part: a value that cannot reach a second line cannot
    # become a second key.
    #
    # Collapsing twice, as this did briefly, is worse than collapsing once:
    # a mutation removing either pass left the other doing the work, so the
    # guard tested as if it were fine while half of it was gone.
    #
    # A colon is left alone deliberately. A booking link needs one, and
    # `productive.yaml` has carried `https://...` since it was written.
    text = str(value or "")
    for banned in ("#", "{", "}", "[", "]", chr(34), chr(39)):
        text = text.replace(banned, " ")
    return " ".join(text.split())[:120].lstrip("-&*!|>%@`? ")


def personas(config):
    return config.get("personas") or {}


def angles_for(config, persona):
    return (personas(config).get(persona) or {}).get("angles") or {}


ANGLE_LABELS_KEY = "angle_labels"


def angle_labels(config):
    """Short display labels per angle key, keyed client-wide.

    A label is what a subject line calls an angle when the client's own phrase
    will not fit in one. It is never a claim: `angles` is what a message
    argues, and nothing that scores evidence, qualifies a company or reaches a
    model reads this.

    Client-wide rather than nested inside a persona because
    `web/api.save_persona` rebuilds a persona as exactly titles, cap and
    angles - a label kept in there would be dropped the first time somebody
    edited that persona in the product, and the subject would quietly go back
    to falling back. Nesting it under `angles` instead is worse: `angles_for`
    returns {key: phrase} and three callers do `str(phrase)` on the value, so
    a dict there would be scored as evidence text rather than raising.
    """
    labels = (config or {}).get(ANGLE_LABELS_KEY)
    if not isinstance(labels, dict):
        return {}
    return {str(key).strip().lower(): " ".join(str(value).split())
            for key, value in labels.items() if str(value or "").strip()}


def cap_for(config, persona, default=1):
    value = (personas(config).get(persona) or {}).get("cap_per_domain", default)
    return int(value) if value is not None else default


def titles_for(config, persona):
    return (personas(config).get(persona) or {}).get("titles") or []


NOTE_MODES = ("template", "llm")


def verification_policy(config):
    """The client's verification waterfall, over conservative defaults."""
    from . import verification
    return verification.policy_for(config)


def research_settings(config):
    """The client's public-web research settings. Off unless asked for."""
    from .providers import apify
    return apify.settings(config)


def linkedin_note_mode(config):
    """template or llm. Template is the default: it costs nothing and it cannot
    wander. BUILD-SPEC section 7 marks the day 3 note as generated, but section 8
    defines no prompt for it, so the choice is the client's to make."""
    setting = (config or {}).get("linkedin_connection_note") or {}
    mode = str(setting.get("mode") or "template").strip().lower()
    if mode not in NOTE_MODES:
        raise ConfigError(
            f"linkedin_connection_note.mode must be one of {', '.join(NOTE_MODES)}, "
            f"not {mode!r}")
    return mode
