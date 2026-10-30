import random
import unittest
from typing import Any

from loki.intent.verify import N, verify_claim

W = 4


def sigs(names: list[str], seed: int = 1) -> dict[str, int]:
    rng = random.Random(seed)
    return {n: rng.getrandbits(N) for n in names}


def d_wires(sig: dict[str, int], nxt: list[int | None], q: list[str]) -> dict[str, str]:
    """Add one D wire per state bit holding the given next-state value on each vector."""
    out: dict[str, str] = {}
    for i, name in enumerate(q):
        sig[f"d_{name}"] = sum(((n or 0) >> i & 1) << v for v, n in enumerate(nxt))
        out[name] = f"d_{name}"
    return out


def state(sig: dict[str, int], q: list[str], v: int) -> int:
    return sum(((sig[n] >> v) & 1) << i for i, n in enumerate(q))


def bit(sig: dict[str, int], n: str, v: int) -> int:
    return (sig[n] >> v) & 1


def counter_claim(**over: Any) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "q": [f"q[{i}]" for i in range(W)], "width": W, "dir": "up", "modulus": 10, "wrap": 0,
        "en": {"net": "en", "active": 1},
        "rst": {"net": "rst", "active": 1, "value": 0}, "async": False,
    }
    facts.update(over)
    return {"id": "h1", "kind": "counter", "source": "seq", "facts": facts, "nets": {}}


def decade(sig: dict[str, int], q: list[str]) -> list[int | None]:
    out: list[int | None] = []
    for v in range(N):
        s = state(sig, q, v)
        if bit(sig, "rst", v):
            out.append(0)
        elif not bit(sig, "en", v):
            out.append(s)
        else:
            out.append(0 if s == 9 else (s + 1) & 15)
    return out


class VerifyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.q = [f"q[{i}]" for i in range(W)]
        self.sig = sigs([*self.q, "en", "rst"])

    def test_true_decade_counter_verifies(self) -> None:
        dmap = d_wires(self.sig, decade(self.sig, self.q), self.q)
        v = verify_claim(counter_claim(), self.sig, dmap)
        self.assertTrue(v.ok)
        self.assertEqual(v.bad, 0)
        self.assertGreater(v.checked, 100)

    def test_wrong_modulus_fails(self) -> None:
        dmap = d_wires(self.sig, decade(self.sig, self.q), self.q)
        v = verify_claim(counter_claim(modulus=12), self.sig, dmap)
        self.assertFalse(v.ok)
        self.assertGreater(v.bad, 0)

    def test_wrong_bit_order_fails(self) -> None:
        dmap = d_wires(self.sig, decade(self.sig, self.q), self.q)
        v = verify_claim(counter_claim(q=self.q[::-1]), self.sig, dmap)
        self.assertFalse(v.ok)

    def test_async_reset_vectors_are_skipped(self) -> None:
        nxt = decade(self.sig, self.q)
        for v in range(N):
            if bit(self.sig, "rst", v):
                nxt[v] = 7  # the D wire says nothing about an asynchronous reset
        dmap = d_wires(self.sig, nxt, self.q)
        self.assertFalse(verify_claim(counter_claim(), self.sig, dmap).ok)
        got = verify_claim(counter_claim(**{"async": True}), self.sig, dmap)
        self.assertTrue(got.ok)
        self.assertLess(got.checked, N)

    def test_unknown_net_is_unverified(self) -> None:
        dmap = d_wires(self.sig, decade(self.sig, self.q), self.q)
        v = verify_claim(counter_claim(en={"net": "nope", "active": 1}), self.sig, dmap)
        self.assertIsNone(v.ok)

    def test_fsm_transitions(self) -> None:
        q = ["s0", "s1"]
        sig = sigs([*q, "go", "rst"], 3)
        nxt: list[int | None] = []
        for v in range(N):
            s = state(sig, q, v)
            go = bit(sig, "go", v)
            nxt.append(0 if bit(sig, "rst", v) else ({0: 1 if go else 0, 1: 2 if go else 0,
                                                      2: 0 if go else 2}.get(s, 0)))
        dmap = d_wires(sig, nxt, q)
        moves = [(0, 1, [[["go", 1]]]), (0, 0, [[["go", 0]]]), (1, 2, [[["go", 1]]]),
                 (1, 0, [[["go", 0]]]), (2, 0, [[["go", 1]]]), (2, 2, [[["go", 0]]])]
        claim: dict[str, Any] = {"id": "h2", "kind": "fsm", "source": "seq", "nets": {},
                                 "facts": {
            "q": q, "width": 2, "states": [0, 1, 2], "controls": ["go"], "async": False,
            "rst": {"net": "rst", "active": 1, "value": 0},
            "transitions": [{"src": s, "dst": d, "cond": c} for s, d, c in moves]}}
        self.assertTrue(verify_claim(claim, sig, dmap).ok)
        claim["facts"]["transitions"][0]["dst"] = 2
        self.assertFalse(verify_claim(claim, sig, dmap).ok)

    def test_mode_table_shift_with_load(self) -> None:
        q = ["q[0]", "q[1]", "q[2]"]
        sig = sigs([*q, "load", "ena", "d[0]", "d[1]", "d[2]"], 5)
        nxt: list[int | None] = []
        for v in range(N):
            s = state(sig, q, v)
            if bit(sig, "load", v):
                nxt.append(state(sig, ["d[0]", "d[1]", "d[2]"], v))
            elif bit(sig, "ena", v):
                nxt.append(s >> 1)
            else:
                nxt.append(s)
        dmap = d_wires(sig, nxt, q)
        claim: dict[str, Any] = {"id": "h3", "kind": "shift_reg", "source": "seq", "nets": {},
                                 "facts": {
            "q": q, "width": 3, "async": False, "modes": [
                {"label": "hold", "cond": [[["load", 0], ["ena", 0]]], "data": []},
                {"label": "load-const", "cond": [[["load", 1]]],
                 "data": ["d[0]", "d[1]", "d[2]"]},
                {"label": "shift-r", "cond": [[["load", 0], ["ena", 1]]], "data": ["#0"]}]}}
        self.assertTrue(verify_claim(claim, sig, dmap).ok)

    def test_overlay_claim_is_not_verified(self) -> None:
        v = verify_claim({"id": "h4", "kind": "bus", "source": "overlay", "facts": {}, "nets": {}},
                         {}, {})
        self.assertIsNone(v.ok)


if __name__ == "__main__":
    unittest.main()
