**READING AN OLD MUTATION CLAIM — the reader's test (`glm/0080`):** a kill
that names the test that died and states its failure signature certifies
itself — stale bytecode can only counterfeit a *green* verdict, so a red run
proves the mutant's own bytes executed. Everything else — a survivor, a
no-op, a kill whose reason is described but never named — is only as good as
one recorded fact: look for a byte-length change, a revert in a later whole
second, a `__pycache__` deletion before the run, or a load-proof CLEAN. Any
one of those clears it; missing all of them the verdict is UNKNOWN to the
reader; and a size-identical write inside the same whole second as the
previous run means treat the verdict as void and re-measure before building
on it. This is `0075`'s clearing rule stated as a cheap test rather than a
warning, and `0080` validated it over this lane's whole recorded corpus:
55 kept records, 30 SAFE / 19 UNKNOWN / 6 AFFECTED — every UNKNOWN in the
pre-0072 era, when kills were recorded without names.
