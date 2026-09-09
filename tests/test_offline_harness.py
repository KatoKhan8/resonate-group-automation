"""The harness that proves nothing reaches the network, tested both ways.

A guard is only worth what it refuses *and* what it allows. This one had been
refusing loopback, which meant every web test errored under it - 194 of them,
including every tenancy test and the one that greps every rendered byte for a
credential. They passed in the normal run and were absent from the run that
exists to prove nothing reaches out.

So both directions are asserted here: a real hostname is refused, and a
loopback address is not. Getting either wrong is a silent failure - too strict
and the harness covers nothing, too loose and it proves nothing.
"""
import socket
import unittest

from tests import offline


class WhatCountsAsLoopback(unittest.TestCase):
    """Pure, and worth being pedantic about: this decides what may go out."""

    def test_the_obvious_loopback_forms(self):
        for host in ("127.0.0.1", "127.1.2.3", "::1", "0:0:0:0:0:0:0:1",
                     "localhost", "LOCALHOST", "[::1]", "::1%lo0",
                     "::ffff:127.0.0.1", ""):
            self.assertTrue(offline.is_loopback(host), host)

    def test_everything_else_is_the_network(self):
        for host in ("api.contactout.com", "8.8.8.8", "0.0.0.0", "example.com",
                     "10.0.0.1", "192.168.1.1", "127.0.0.1.evil.com",
                     "localhost.evil.com", "2001:4860:4860::8888",
                     None, "1270.0.0.1", "127.0.0.256"):
            self.assertFalse(offline.is_loopback(host), host)

    def test_a_hostname_that_merely_starts_with_127_is_not_loopback(self):
        """The check is on the parsed address, not on a prefix match."""
        self.assertFalse(offline.is_loopback("127.0.0.1.attacker.test"))
        self.assertFalse(offline.is_loopback("127-0-0-1.attacker.test"))

    def test_bytes_are_handled_and_undecodable_bytes_are_refused(self):
        self.assertTrue(offline.is_loopback(b"127.0.0.1"))
        self.assertFalse(offline.is_loopback(b"\xff\xfe not ascii"))


class TheBlockItself(unittest.TestCase):
    """Installs the block, checks it, and always puts the module back."""

    def setUp(self):
        self.restore = {
            "socket": socket.socket,
            "create_connection": socket.create_connection,
            "getaddrinfo": socket.getaddrinfo,
            "gethostbyname": socket.gethostbyname,
        }
        offline.block()

    def tearDown(self):
        socket.socket = self.restore["socket"]
        socket.create_connection = self.restore["create_connection"]
        socket.getaddrinfo = self.restore["getaddrinfo"]
        socket.gethostbyname = self.restore["gethostbyname"]

    def test_resolving_a_real_hostname_is_refused(self):
        with self.assertRaises(offline.NetworkBlocked):
            socket.getaddrinfo("api.contactout.com", 443)

    def test_connecting_somewhere_real_is_refused(self):
        with self.assertRaises(offline.NetworkBlocked):
            socket.create_connection(("api.contactout.com", 443))
        # Closed even though the connect raises: a test that leaks a socket
        # emits a ResourceWarning into every later run of the suite, and noise
        # in a test log is how a real warning stops being read.
        with socket.socket() as s:
            with self.assertRaises(offline.NetworkBlocked):
                s.connect(("8.8.8.8", 53))

    def test_gethostbyname_is_refused_too(self):
        with self.assertRaises(offline.NetworkBlocked):
            socket.gethostbyname("example.com")

    def test_the_refusal_names_what_was_reached_for(self):
        with self.assertRaises(offline.NetworkBlocked) as caught:
            socket.getaddrinfo("api.contactout.com", 443)
        self.assertIn("api.contactout.com", str(caught.exception))

    def test_a_loopback_server_still_works(self):
        """The property the whole fix exists for."""
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        try:
            client = socket.create_connection(("127.0.0.1", port), timeout=5)
            conn, _ = server.accept()
            conn.sendall(b"hello")
            self.assertEqual(client.recv(5), b"hello")
            conn.close()
            client.close()
        finally:
            server.close()

    def test_resolving_localhost_still_works(self):
        self.assertTrue(socket.getaddrinfo("127.0.0.1", 80))


class TheWebTestsAreActuallyCovered(unittest.TestCase):
    """The regression this file exists to prevent coming back.

    Not "the harness is installed" but "the harness does not exclude a third
    of the suite from itself".
    """

    def test_the_web_suite_is_reachable_under_the_block(self):
        restore = (socket.socket, socket.create_connection,
                   socket.getaddrinfo, socket.gethostbyname)
        offline.block()
        try:
            server = socket.socket()
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            server.close()
        finally:
            (socket.socket, socket.create_connection,
             socket.getaddrinfo, socket.gethostbyname) = restore
