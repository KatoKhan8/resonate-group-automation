#!/usr/bin/env python3
"""Run the whole suite with the network physically unavailable.

The suite already arms a `urlopen` tripwire, but that only catches code going
through urllib. This closes the door lower down: `socket` itself refuses, so
anything that tries to reach a provider by any route - a library, a stray
`http.client`, a DNS lookup - fails loudly and names itself.

That distinction matters. A test that quietly reaches a provider passes on a
developer's machine, costs money, and fails in CI for reasons nobody can
reproduce. Running this before a commit is how "no test touches the network"
stops being a claim and becomes a fact.

  python -m tests.offline
  python -m tests.offline -v

## Loopback is not the network

The web tests start a real `ThreadingHTTPServer` on an ephemeral port and talk
to it over `urllib`, deliberately: most of what is worth asserting about a web
layer lives in the parts a direct handler call skips - the cookie, the CSRF
check, the status code, the headers. That traffic never leaves the machine.

For a while this file refused it anyway, and the result was that **every web
test errored under the offline harness** - 194 of them, including every tenancy
test, every permission test and the one that greps every rendered byte for a
credential. They passed in the normal run and were simply absent from the run
that is supposed to prove nothing reaches out. An audit that reports clean
because it watched nothing is worse than no audit, so loopback is allowed and
everything else is refused, rather than the harness covering two thirds of the
suite and being quiet about the rest.

"Loopback" here means an address that cannot leave the host: 127.0.0.0/8, ::1,
and the two names for them. A hostname that would need a resolver is still
refused, and `tests/test_offline_harness.py` asserts both directions.
"""
import socket
import sys
import unittest

# Addresses that cannot leave this machine. A name is included only if
# resolving it does not require a resolver on any normal system.
LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain",
                            "ip6-localhost", "ip6-loopback"})


class NetworkBlocked(RuntimeError):
    """A test tried to reach off the machine. Nothing in this suite may."""


def is_loopback(host):
    """Would connecting here stay on this machine?

    Conservative by construction: anything this cannot positively identify as
    loopback is treated as the network. A false "yes" here would let a real
    provider call through the one harness whose whole job is to stop it.
    """
    if host is None:
        return False
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    host = str(host).strip().strip("[]").lower()
    if not host:
        # An empty host means "this machine" to `bind`, and a connect with no
        # host is not a connect to anywhere else.
        return True
    if host in LOOPBACK_NAMES:
        return True
    # Scoped IPv6, e.g. ::1%lo0
    host = host.split("%", 1)[0]
    if host == "::1" or host == "0:0:0:0:0:0:0:1":
        return True
    if host.startswith("::ffff:"):
        host = host[len("::ffff:"):]
    parts = host.split(".")
    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255
                               for p in parts):
        return parts[0] == "127"
    return False


def _host_of(address):
    """The host out of whatever shape an address arrived in."""
    if isinstance(address, (tuple, list)) and address:
        return address[0]
    return address


def block():
    """Close every way off the machine, without breaking the ways around it.

    Replacing `socket.socket` wholesale also breaks the local sockets Python
    itself uses, so what is blocked here is the act of *reaching somewhere
    else*: connecting to a non-loopback address, and resolving a name that
    would need a resolver to answer.

    Returns what was replaced, for the record.
    """
    real_getaddrinfo = socket.getaddrinfo
    real_gethostbyname = socket.gethostbyname
    real_create_connection = socket.create_connection
    real_socket = socket.socket

    def refuse(what):
        raise NetworkBlocked(
            f"a test attempted to reach {what!r}, which is not this machine. "
            "The suite must run entirely offline: use a cassette, a fake "
            "transport, or a fixture.")

    def guarded_getaddrinfo(host, *args, **kwargs):
        if not is_loopback(host):
            refuse(host)
        return real_getaddrinfo(host, *args, **kwargs)

    def guarded_gethostbyname(host, *args, **kwargs):
        if not is_loopback(host):
            refuse(host)
        return real_gethostbyname(host, *args, **kwargs)

    def guarded_create_connection(address, *args, **kwargs):
        host = _host_of(address)
        if not is_loopback(host):
            refuse(host)
        return real_create_connection(address, *args, **kwargs)

    class OfflineSocket(real_socket):
        def connect(self, address, *args, **kwargs):
            host = _host_of(address)
            if not is_loopback(host):
                refuse(host)
            return super().connect(address, *args, **kwargs)

        def connect_ex(self, address, *args, **kwargs):
            host = _host_of(address)
            if not is_loopback(host):
                refuse(host)
            return super().connect_ex(address, *args, **kwargs)

        def sendto(self, data, *args):
            address = args[-1] if args else None
            host = _host_of(address)
            if address is not None and not is_loopback(host):
                refuse(host)
            return super().sendto(data, *args)

    replaced = {
        "socket.socket.connect": "loopback only",
        "socket.socket.connect_ex": "loopback only",
        "socket.socket.sendto": "loopback only",
        "socket.create_connection": "loopback only",
        "socket.getaddrinfo": "loopback only",
        "socket.gethostbyname": "loopback only",
    }
    socket.socket = OfflineSocket
    socket.create_connection = guarded_create_connection
    socket.getaddrinfo = guarded_getaddrinfo
    socket.gethostbyname = guarded_gethostbyname
    return replaced


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    verbosity = 2 if "-v" in argv else 1

    blocked = block()
    print("network blocked:", ", ".join(sorted(blocked)))
    print("loopback is permitted: the web tests drive a real server on an")
    print("ephemeral port, and that traffic never leaves this machine")
    print("running the full suite offline\n")

    loader = unittest.TestLoader()
    suite = loader.discover("tests")
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    print()
    if result.wasSuccessful():
        print(f"OK - {result.testsRun} tests, nothing reached off this machine")
        return 0
    print(f"FAILED - {len(result.failures)} failure(s), "
          f"{len(result.errors)} error(s) of {result.testsRun}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
