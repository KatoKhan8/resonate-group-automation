"""Prove the `pack_for` agreement assertion is LIVE, by making it fail.

An assertion that has never been seen to fail is indistinguishable from an
assertion that cannot. This feeds `admitted_pack` a real row twice: once with
lane D's real `pack_for`, which must agree, and once with a stand-in that
returns a different pack, which must raise.
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import lane_h_pack_grounded_render as H

_cad, _s7, packfacts, actors = H.load_lanes()

ROW = {"snippet": "We design, build and deliver creative events",
       "source_url": "https://example.com/about", "kind": "site_page"}


class Disagrees:
    """Lane D's module with one function replaced."""
    ADMITTED = packfacts.ADMITTED
    identity_of = staticmethod(packfacts.identity_of)

    @staticmethod
    def pack_for(rec):
        return {"facts": []}, {}


pack, admitted, verdicts = H.admitted_pack([ROW], "example.com", packfacts,
                                           actors)
assert len(pack["facts"]) == 1 and verdicts["admitted"] == 1, verdicts
print("ok    real packfacts agrees: 1 admitted fact, verdicts %s"
      % dict(verdicts))

try:
    H.admitted_pack([ROW], "example.com", Disagrees, actors)
except AssertionError as exc:
    print("ok    a disagreeing pack_for RAISES: %s" % str(exc)[:90])
else:
    print("FAIL  the assertion did not fire - it cannot fail and proves "
          "nothing")
    raise SystemExit(1)

# and the identity guard itself, fail-closed on a foreign host
foreign = dict(ROW, source_url="https://www.linkedin.com/posts/someone")
pack, admitted, verdicts = H.admitted_pack([foreign], "example.com",
                                           packfacts, actors)
assert not pack["facts"], pack
print("ok    a LinkedIn host is %s and admits nothing"
      % [k for k in verdicts])
print("\n0 failure(s)")
