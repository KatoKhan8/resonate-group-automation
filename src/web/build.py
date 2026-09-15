"""Export the exact production assets without adding a frontend runtime.

    python -m src.web.build

The server serves these same files via an explicit allowlist. This release
artifact is useful for packaging and integrity checks, not a standalone SPA.
It contains no application state, environment variables or client data.
"""
import argparse
import hashlib
import json
from pathlib import Path

from . import assets


def build(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, content in (("app.css", assets.CSS.encode("utf-8")),
                          ("app.js", assets.JS.encode("utf-8")),
                          ("resonate-logo.png", assets.LOGO)):
        (destination / name).write_bytes(content)
        manifest[name] = {"sha256": hashlib.sha256(content).hexdigest(),
                          "bytes": len(content), "version": assets.digest(content)}
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="out/web", help="asset artifact directory")
    args = parser.parse_args()
    manifest = build(args.output)
    print(f"Built {len(manifest)} production assets in {args.output}")
    for name, entry in manifest.items():
        print(f"  {name}: {entry['bytes']} bytes; sha256 {entry['sha256']}")


if __name__ == "__main__":
    main()
