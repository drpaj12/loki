import random
import unittest

from loki.features import npn
from loki.features.npn import (
    NAMED,
    NpnClass,
    apply_transform,
    class_name,
    npn_brute,
    npn_class,
    shrink_support,
    stats,
)
from tests.features_fixtures import table_of

XOR6 = table_of(6, lambda v: sum(v) & 1)


def random_transform(t: int, w: int, rng: random.Random) -> int:
    perm = list(range(w))
    rng.shuffle(perm)
    return apply_transform(t, w, perm, rng.getrandbits(w), bool(rng.getrandbits(1)))


class NpnTest(unittest.TestCase):
    def test_shrink_support(self) -> None:
        t = table_of(6, lambda v: v[1] & (1 - v[4]))
        small, w, pos = shrink_support(t, 6)
        self.assertEqual((w, pos), (2, (1, 4)))
        self.assertEqual(small, 0b0010)
        self.assertEqual(shrink_support(0, 3), (0, 0, ()))
        self.assertEqual(shrink_support(0xFF, 3), (1, 0, ()))

    def test_transforms_match_primitives(self) -> None:
        rng = random.Random(5)
        for k in (2, 3, 5, 6):
            t = rng.getrandbits(1 << k)
            for j in range(k):
                flipped = apply_transform(t, k, list(range(k)), 1 << j, False)
                self.assertEqual(npn._flip(t, k, j), flipped)
            for j in range(k - 1):
                perm = list(range(k))
                perm[j], perm[j + 1] = perm[j + 1], perm[j]
                self.assertEqual(npn._swap(t, k, j), apply_transform(t, k, perm, 0, False))

    def test_sjt_visits_all_permutations(self) -> None:
        for n in range(1, 7):
            arr = list(range(n))
            seen = {tuple(arr)}
            for j in npn._sjt(n):
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                seen.add(tuple(arr))
            self.assertEqual(len(seen), len(set(seen)))
            self.assertEqual(len(seen), [1, 1, 2, 6, 24, 120, 720][n])
            self.assertEqual(len(npn._sjt(n)), max(0, len(seen) - 1))

    def test_npn_3_input_14_classes(self) -> None:
        keys = set()
        for t in range(256):
            c = npn_class(t, 3)
            self.assertEqual(c, npn_brute(t, 3))
            keys.add(c.key)
        self.assertEqual(len(keys), 14)

    def test_npn_4_input_222_classes(self) -> None:
        self.assertEqual(len({npn_class(t, 4).key for t in range(65536)}), 222)

    def test_npn_4_matches_brute_sample(self) -> None:
        rng = random.Random(11)
        for _ in range(60):
            t = rng.getrandbits(16)
            self.assertEqual(npn_class(t, 4), npn_brute(t, 4))

    def test_npn_invariance_random(self) -> None:
        rng = random.Random(7)
        for n in range(2000):
            w = 5 + n % 2
            if n % 10 == 0:
                sym = [rng.getrandbits(1) for _ in range(w + 1)]
                t = sum(sym[x.bit_count()] << x for x in range(1 << w))
            else:
                t = rng.getrandbits(1 << w)
            key = npn_class(t, w).key
            for _ in range(3):
                self.assertEqual(npn_class(random_transform(t, w, rng), w).key, key)

    def test_npn_matches_brute_6(self) -> None:
        rng = random.Random(3)
        tables = [rng.getrandbits(64) for _ in range(5)]
        for t in tables:
            self.assertEqual(npn_class(t, 6), npn_brute(t, 6))
        for name, c in NAMED.items():
            self.assertEqual(npn_class(c.table, c.width), npn_brute(c.table, c.width), name)

    def test_named_classes(self) -> None:
        xor3 = NAMED["xor3"]
        self.assertEqual(npn_class(table_of(3, lambda v: v[0] ^ v[1] ^ v[2]), 3), xor3)
        self.assertEqual(npn_class(table_of(3, lambda v: (1 - v[0]) ^ v[1] ^ (1 - v[2])), 3), xor3)
        maj = table_of(3, lambda v: int(sum(v) >= 2))
        majn = table_of(3, lambda v: int(((1 - v[0]) + v[1] + v[2]) >= 2))
        self.assertEqual(class_name(npn_class(maj, 3)), "maj3")
        self.assertEqual(class_name(npn_class(majn, 3)), "maj3")
        mux = table_of(3, lambda v: v[1] if v[2] else v[0])
        muxn = table_of(3, lambda v: (1 - v[1]) if v[2] else v[0])
        self.assertEqual(class_name(npn_class(mux, 3)), "mux2")
        self.assertEqual(class_name(npn_class(muxn, 3)), "mux2")
        self.assertEqual(npn_class(0b1000, 2), npn_class(0b1110, 2))
        self.assertEqual(class_name(npn_class(0b1110, 2)), "and2")
        self.assertEqual(class_name(npn_class(table_of(6, lambda v: v[0] ^ v[3]), 6)), "xor2")
        self.assertEqual(class_name(NpnClass(3, 5, True)), "other")
        names = ["const", "buf", "and2", "xor2", "and3", "xor3", "maj3", "mux2", "and4", "xor4",
                 "mux4"]
        self.assertEqual(sorted(NAMED), sorted(names))

    def test_key_format(self) -> None:
        self.assertEqual(NpnClass(2, 0x8, True).key, "2:8")
        self.assertEqual(NAMED["const"].key, "0:0")
        self.assertEqual(npn_class(1, 0), NAMED["const"])

    def test_wide_support_rejected(self) -> None:
        with self.assertRaises(ValueError):
            npn_class(table_of(7, lambda v: sum(v) & 1), 7)
        with self.assertRaises(ValueError):
            npn_brute(table_of(7, lambda v: sum(v) & 1), 7)
        self.assertEqual(npn_class(table_of(8, lambda v: v[2] & v[7]), 8), NAMED["and2"])

    def test_npn_stats(self) -> None:
        npn_class(XOR6, 6)
        s = stats()
        self.assertEqual(s["worst_enum"], 92160)
        self.assertLessEqual(s["worst_enum"], npn.NPN_ENUM_MAX)
        self.assertEqual(s["inexact"], 0)
        self.assertGreater(s["distinct_tables"], 0)


if __name__ == "__main__":
    unittest.main()
