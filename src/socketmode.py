#!/usr/bin/env python3
"""Slack Socket Mode over the standard library. No third-party dependencies.

OPERATOR, 2026-09-21: "connects via Socket Mode (stdlib websocket client, no
third-party deps)".

## What Socket Mode is, in the three facts that matter here

1. `apps.connections.open` is called with the APP-LEVEL token (`xapp-`), not
   the bot token, and returns a single-use `wss://` URL.
2. Every envelope the server sends must be ACKNOWLEDGED by sending back
   `{"envelope_id": "..."}` within three seconds, or Slack redelivers it.
   A redelivered mention answered twice is the failure this ack prevents.
3. The server sends `{"type": "disconnect"}` before it rotates a connection,
   usually every few minutes. **That is ordinary housekeeping, not an
   error** - a loop that treats it as a failure alarms all day, and one that
   ignores it stops receiving events without noticing.

## Why the frames are hand-written

A websocket client is a handshake, a masked frame writer and a frame reader
with continuation and control frames. That is small enough to own, and owning
it means the monitor has no dependency that can vanish on a machine rebuild.

CLIENT FRAMES MUST BE MASKED. The RFC requires it and Slack closes the
connection on an unmasked frame, which reads exactly like an auth failure
from the outside.

## What this module is NOT

It does not know what an event means, it cannot post, and it holds no bot
token. It hands envelopes to a callback and acknowledges them. Everything
that decides or answers lives above it.
"""
import base64
import json
import os
import secrets
import socket
import ssl
import struct
import urllib.parse
import urllib.request

CONNECTIONS_OPEN = "https://slack.com/api/apps.connections.open"

#: Slack's own name for "you used a bot token where an app token belongs".
WRONG_TOKEN_TYPE = "not_allowed_token_type"

OPCODE_TEXT = 0x1
OPCODE_BINARY = 0x2
OPCODE_CLOSE = 0x8
OPCODE_PING = 0x9
OPCODE_PONG = 0xA


class SocketModeError(RuntimeError):
    """The connection could not be established or was lost. Never carries a
    token: the message is built from Slack's error code and nothing else."""


def open_connection_url(app_token, timeout=30):
    """Ask Slack for a websocket URL. Returns the `wss://` string.

    Raises `SocketModeError` naming Slack's own error code. The
    `not_allowed_token_type` case is called out by name because it is the one
    a human can fix in thirty seconds and cannot diagnose from a stack trace:
    it means an `xoxb-` bot token was supplied where an `xapp-` app-level
    token with `connections:write` is required.
    """
    if not app_token:
        raise SocketModeError(
            "SLACK_APP_TOKEN is not set. Socket Mode needs an APP-LEVEL "
            "token (xapp-...) with connections:write, from Basic Information "
            "-> App-Level Tokens.")
    request = urllib.request.Request(
        CONNECTIONS_OPEN, data=b"",
        headers={"Authorization": f"Bearer {app_token}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        error = body.get("error", "unknown")
        if error == WRONG_TOKEN_TYPE:
            raise SocketModeError(
                "Slack refused the connection with `not_allowed_token_type`: "
                "SLACK_APP_TOKEN holds a BOT token (xoxb-...) where an "
                "APP-LEVEL token (xapp-...) with connections:write is "
                "required. Create one under Basic Information -> App-Level "
                "Tokens and set it as SLACK_APP_TOKEN.")
        raise SocketModeError(f"apps.connections.open refused: {error}")
    url = body.get("url")
    if not url:
        raise SocketModeError("apps.connections.open returned no url")
    return url


class WebSocket:
    """One connection. Text frames in, text frames out, control frames handled."""

    def __init__(self, url, timeout=60):
        parts = urllib.parse.urlparse(url)
        host = parts.hostname
        port = parts.port or 443
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        raw = socket.create_connection((host, port), timeout=timeout)
        context = ssl.create_default_context()
        self.sock = context.wrap_socket(raw, server_hostname=host)
        self.sock.settimeout(timeout)
        self._buffer = b""
        self._handshake(host, path)

    def _handshake(self, host, path):
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n")
        self.sock.sendall(request.encode("ascii"))
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise SocketModeError("the server closed during the handshake")
            head += chunk
        header, _, rest = head.partition(b"\r\n\r\n")
        status = header.split(b"\r\n", 1)[0].decode("latin-1")
        if "101" not in status:
            raise SocketModeError(f"websocket upgrade refused: {status}")
        self._buffer = rest

    # ------------------------------------------------------------ reading

    def _recv_exactly(self, count):
        while len(self._buffer) < count:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise SocketModeError("the connection closed")
            self._buffer += chunk
        out, self._buffer = self._buffer[:count], self._buffer[count:]
        return out

    def recv(self):
        """The next application message as text, or None for a control frame.

        Returns None rather than blocking through control frames so the caller
        keeps its own timing: a ping answered inside a long read is invisible
        to the loop that needs to heartbeat.
        """
        payload, opcode = self._recv_frame()
        if opcode == OPCODE_PING:
            self._send_frame(payload, OPCODE_PONG)
            return None
        if opcode == OPCODE_PONG:
            return None
        if opcode == OPCODE_CLOSE:
            raise SocketModeError("the server sent a close frame")
        if opcode in (OPCODE_TEXT, OPCODE_BINARY, 0x0):
            return payload.decode("utf-8", "replace")
        return None

    def _recv_frame(self):
        first, second = self._recv_exactly(2)
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._recv_exactly(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._recv_exactly(8))[0]
        mask = self._recv_exactly(4) if masked else None
        payload = self._recv_exactly(length) if length else b""
        if mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        while not fin and opcode != OPCODE_CLOSE:
            more, next_opcode = self._recv_frame()
            payload += more
            fin = True
            if next_opcode not in (0x0,):
                break
        return payload, opcode

    # ------------------------------------------------------------ writing

    def send(self, text):
        self._send_frame(text.encode("utf-8"), OPCODE_TEXT)

    def _send_frame(self, payload, opcode):
        """Masked, always. An unmasked client frame is closed by the server
        and the symptom looks exactly like a bad token."""
        header = bytearray()
        header.append(0x80 | opcode)
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < (1 << 16):
            header.append(0x80 | 126)
            header.extend(struct.pack(">H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack(">Q", length))
        mask = secrets.token_bytes(4)
        header.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def close(self):
        try:
            self._send_frame(b"", OPCODE_CLOSE)
        except Exception:                                       # noqa: BLE001
            pass
        try:
            self.sock.close()
        except Exception:                                       # noqa: BLE001
            pass


def envelopes(websocket):
    """Yield `(type, envelope)` for every message, acknowledging each one.

    The ack goes out BEFORE the caller sees the envelope, because Slack's
    three-second window is shorter than an LLM call and a redelivered mention
    answered twice is worse than a mention acknowledged before it is
    understood. Idempotency by message ts is the caller's job and is the
    right place for it.
    """
    while True:
        raw = websocket.recv()
        if raw is None:
            continue
        try:
            message = json.loads(raw)
        except ValueError:
            continue
        kind = message.get("type")
        envelope_id = message.get("envelope_id")
        if envelope_id:
            websocket.send(json.dumps({"envelope_id": envelope_id}))
        yield kind, message
