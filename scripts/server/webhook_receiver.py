#!/usr/bin/env python3
"""2f - a RECORD-ONLY webhook receiver that answers before it closes.

    py -3 scripts/server/webhook_receiver.py --record-dir DIR [--port 8787]

WHAT IT DOES: verifies a signature, writes the request to a JSONL file, and
answers 200. WHAT IT NEVER DOES: act on it. No queue write, no provider call,
no send, no state change. A webhook is a claim by a third party, and this
build has no path that treats one as an instruction.

---------------------------------------------------------------------------
THE THING THIS FILE EXISTS TO GET RIGHT: IT ANSWERS BEFORE IT CLOSES.

`tests/test_upload_is_never_truncated.AnOversizedUploadIsRefused` - all four
of it - fails on Linux and passes on Windows with:

    BrokenPipeError: [Errno 32] Broken pipe
    urllib.error.URLError: <urlopen error [Errno 32] Broken pipe>

The server refuses the oversized body and closes the connection before the
client has finished sending it. On Windows the client still reads the
refusal; on Linux it gets EPIPE and NEVER SEES THE MESSAGE AT ALL. The test
asserts the refusal says what the limit is, and on the host there is no
response to read. A sender in that position has a transport error instead of
an answer, and will retry - forever, identically.

TWO CORRECT RULES WERE IN CONFLICT, and noticing that is the whole fix:

  1. `src/web/app.py` refuses an oversized upload BEFORE READING A BYTE, on
     the announced Content-Length, and its comment explains why at length: a
     short read looks exactly like a smaller file, and 267,107 rows once
     disappeared with no trace but a single ragged row.

  2. A peer cannot read your answer if you close while it is still writing.

Both hold. They are reconciled by a distinction the upload path never needed
to make:

     ***  DRAINING IS NOT ACCEPTING.  ***

This receiver reads the oversized body and THROWS IT AWAY WITHOUT PARSING A
BYTE OF IT, purely so the socket is clear enough for the refusal to be
readable. Nothing is recorded, nothing is interpreted, and the refusal says
so. Rule 1 is about not USING a short read. Rule 2 is about the peer being
able to hear you. Draining serves the second without touching the first.

THE DRAIN IS BOUNDED, because an unbounded one is a denial of service with a
polite excuse. `DRAIN_LIMIT` bytes are read and discarded; past that the
receiver answers anyway and closes, and a peer sending more than that may
still see EPIPE. That bound is a decision, not an oversight, and it is
printed at startup.
"""
import argparse
import datetime
import hashlib
import hmac
import io
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

#: A webhook is a notification, not a file transfer. Anything past this is
#: refused - readably.
MAX_BODY = 64 * 1024

#: How much of an oversized body is read and discarded so the refusal can be
#: read. 1 MiB covers any plausible webhook, including a badly wrong one,
#: without letting a sender hold a thread open for as long as it likes.
DRAIN_LIMIT = 1024 * 1024

#: Read in chunks, so a slow sender does not hold one enormous allocation.
CHUNK = 16 * 1024

SIGNATURE_HEADER = "X-Resonate-Signature"
SIGNING_SECRET = "WEBHOOK_SIGNING_SECRET"

PATH = "/webhook"


def sign(secret, body):
    """The signature a sender must send: sha256=<hex>, over the raw body."""
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


class Receiver(BaseHTTPRequestHandler):

    server_version = "resonate-webhook"
    #: Set by `serve()`.
    record_dir = None
    secret = None

    # ---------------------------------------------------------------- plumbing
    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _respond(self, code, message):
        """Answer, with the body, and ALWAYS after the request body is dealt
        with. Every caller below drains first."""
        payload = json.dumps({"status": code, "detail": message}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        # Answer and close. The connection is not reused: a receiver that
        # keeps a connection open after refusing has to be sure the peer is
        # done writing, and it cannot be.
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        try:
            self.wfile.flush()
        except OSError:
            # The peer hung up before reading. Nothing left to do, and it
            # must not take the server down.
            pass

    def _drain(self, remaining):
        """Read and DISCARD up to DRAIN_LIMIT bytes. Returns bytes drained.

        Nothing here is parsed, decoded, stored or counted as content. This
        exists so the refusal below is readable on Linux, and for no other
        reason.
        """
        drained = 0
        while remaining > 0 and drained < DRAIN_LIMIT:
            want = min(CHUNK, remaining, DRAIN_LIMIT - drained)
            try:
                chunk = self.rfile.read(want)
            except OSError:
                break
            if not chunk:
                break
            drained += len(chunk)
            remaining -= len(chunk)
        return drained

    # ---------------------------------------------------------------- handlers
    def do_GET(self):
        # A liveness probe, and deliberately not a webhook path.
        if self.path.rstrip("/") == "/healthz":
            self._respond(200, "receiver up; record-only")
        else:
            self._respond(404, "this receiver answers POST %s only" % PATH)

    def do_POST(self):
        if self.path.rstrip("/") != PATH:
            self._respond(404, "unknown path; POST %s" % PATH)
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._respond(400, "Content-Length is not a number")
            return

        if length > MAX_BODY:
            # THE CASE THIS FILE IS ABOUT. Drain first - discarding every
            # byte - then answer, then close. The message names the limit and
            # the announced size, because a refusal a sender cannot act on
            # produces a retry loop.
            drained = self._drain(length)
            self.log_message("drained %d of %d announced bytes, recorded none",
                             drained, length)
            self._respond(
                413,
                "body is %d bytes, over the %d byte limit. NOTHING WAS "
                "RECORDED and nothing was parsed: the body was read only so "
                "this answer would reach you. Do not retry unchanged."
                % (length, MAX_BODY))
            return

        body = self.rfile.read(length) if length > 0 else b""
        if len(body) < length:
            self._respond(400, "only %d of %d announced bytes arrived; "
                               "refused rather than recorded short"
                          % (len(body), length))
            return

        if not self.secret:
            self._respond(503, "no %s configured; refusing rather than "
                               "recording an unverified request" % SIGNING_SECRET)
            return

        offered = self.headers.get(SIGNATURE_HEADER) or ""
        expected = sign(self.secret, body)
        # compare_digest, not ==: a timing comparison on a signature is the
        # one place where the obvious operator is the wrong one.
        if not hmac.compare_digest(offered, expected):
            self.log_message("signature rejected (%d bytes)", len(body))
            self._respond(401, "signature missing or invalid; nothing recorded")
            return

        self._record(body)
        self._respond(200, "recorded; this receiver never acts on a webhook")

    def _record(self, body):
        """Append the request to a JSONL file. The body is stored as TEXT and
        never evaluated - it is evidence, not an instruction."""
        now = datetime.datetime.now(datetime.timezone.utc)
        os.makedirs(self.record_dir, exist_ok=True)
        path = os.path.join(self.record_dir,
                            "webhook-%s.jsonl" % now.strftime("%Y%m%d"))
        entry = {
            "at": now.replace(microsecond=0).isoformat(),
            "path": self.path,
            "from": self.address_string(),
            "bytes": len(body),
            "headers": {k.lower(): v for k, v in self.headers.items()
                        if k.lower() in ("content-type", "user-agent",
                                         SIGNATURE_HEADER.lower())},
            "body": body.decode("utf-8", "replace"),
        }
        with io.open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def serve(record_dir, port=8787, host="127.0.0.1", secret=None):
    Receiver.record_dir = record_dir
    Receiver.secret = secret or os.environ.get(SIGNING_SECRET) or ""
    httpd = ThreadingHTTPServer((host, port), Receiver)
    sys.stderr.write(
        "webhook receiver on %s:%d  POST %s\n"
        "  record-only: it never acts on a webhook\n"
        "  max body   : %d bytes; oversized bodies are DRAINED (max %d) so\n"
        "               the refusal is readable, then refused, then closed\n"
        "  signature  : %s\n"
        % (host, port, PATH, MAX_BODY, DRAIN_LIMIT,
           "required" if Receiver.secret else "NOT CONFIGURED - all POSTs refused"))
    return httpd


def main():
    ap = argparse.ArgumentParser(description="Record-only webhook receiver")
    ap.add_argument("--record-dir", required=True)
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1",
                    help="loopback by default; Caddy terminates TLS in front")
    args = ap.parse_args()
    httpd = serve(args.record_dir, args.port, args.host)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
