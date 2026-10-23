"""The global-signal classifier (L2 spec 8.1 and 8.2): net classes and per-node role flags.

The rules are implemented once, in :mod:`loki.features.roles` (L1 spec 6.7); this module adapts
an L2 :class:`~loki.analysis.graphio.Graph` to L1's feature graph, delegates the classification
and exposes the numpy arrays the graphlet tasks consume. numpy is imported inside functions after
:func:`loki.analysis.require`, so importing this module needs the standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loki.analysis import require
from loki.analysis.graphio import Graph, to_feature_graph
from loki.features.roles import CLASS_NAMES as CLASS_NAMES
from loki.features.roles import SignalConfig as SignalConfig
from loki.features.roles import classify_nets
from loki.features.roles import is_forcing as _is_forcing
from loki.features.roles import is_hold as _is_hold

if TYPE_CHECKING:
    import numpy.typing as npt

#: The classifier's effective default; a module-level value, so the signature needs no call.
_DEFAULT_CONFIG = SignalConfig()


@dataclass(frozen=True)
class SignalInfo:
    """Per-edge classes and per-node role flags of one netlist (L2 spec 8.1 and 8.2).

    ``edge_class`` is int8 ``(E,)`` with indices into :data:`CLASS_NAMES`; ``roles`` is int64
    ``(N, 4)`` with columns ``clock_domain, has_reset, const_inputs, enable``; ``classified``
    counts the nets per class name and ``clock_domains`` is the number of clock nets.
    """

    edge_class: npt.NDArray[Any]
    roles: npt.NDArray[Any]
    classified: dict[str, int]
    clock_domains: int


def _check_bits(bits: npt.NDArray[Any], width: int) -> None:
    if width < 0:
        raise ValueError("width must be >= 0")
    expected = (1 << width,)
    if bits.shape != expected:
        raise ValueError(f"table has shape {bits.shape}, expected {expected}")


def lut_bits(table_hex: str, width: int) -> npt.NDArray[Any]:
    """A LUT truth table as uint8 of length ``2**width`` (L2 spec 8.1).

    Index is the address and address bit ``k`` is input ``I<k>``; ``table_hex`` is L0 spec
    6.4's MSB-first hex string, read like a binary number whose bit ``k`` is the output for the
    input pattern ``k`` (:data:`loki.blifout.LUT_ROW_ORDER`). An empty string is the table 0.
    """
    require("analysis")
    import numpy as np

    if width < 0:
        raise ValueError("width must be >= 0")
    table = int(table_hex, 16) if table_hex else 0
    if table >> (1 << width):
        raise ValueError(f"table {table_hex!r} does not fit {1 << width} rows")
    return np.asarray([(table >> address) & 1 for address in range(1 << width)], dtype=np.uint8)


def lut_restrict(bits: npt.NDArray[Any], width: int, k: int, value: int) -> npt.NDArray[Any]:
    """The table over the remaining inputs with input ``k`` fixed to ``value``, order kept."""
    require("analysis")
    import numpy as np

    _check_bits(bits, width)
    if not 0 <= k < width or value not in (0, 1):
        raise ValueError(f"input {k} cannot take value {value} of width {width}")
    addresses = np.arange(1 << (width - 1), dtype=np.int64)
    low = (1 << k) - 1
    full = ((addresses & ~low) << 1) | (value << k) | (addresses & low)
    return np.asarray(bits[full])


def _bits_int(bits: npt.NDArray[Any], width: int) -> int:
    """The integer truth table of a ``lut_bits`` array."""
    _check_bits(bits, width)
    return sum(int(bit) << address for address, bit in enumerate(bits.tolist()))


def is_forcing(bits: npt.NDArray[Any], width: int, k: int) -> bool:
    """True when some value of input ``k`` makes the output constant (L1's integer rule)."""
    require("analysis")
    return _is_forcing(_bits_int(bits, width), width, k)


def is_hold(bits: npt.NDArray[Any], width: int, k: int, q: int) -> bool:
    """True when, for some value of input ``k``, the output equals input ``q`` for every other
    input (the hold path of a clock-enable mux whose flip-flop output is ``q``)."""
    require("analysis")
    return _is_hold(_bits_int(bits, width), width, k, q)


def classify_signals(g: Graph, cfg: SignalConfig = _DEFAULT_CONFIG) -> SignalInfo:
    """Classify every net of ``g`` (spec 8.1) and derive the per-node role flags (8.2).

    Delegates to :func:`loki.features.roles.classify_nets` on
    :func:`loki.analysis.graphio.to_feature_graph` of the same netlist, so L1 and L2 always see
    one classification. ``cfg`` defaults to ``SignalConfig(min_fanout=16, dominance=0.8)``.
    """
    require("analysis")
    import numpy as np

    net_roles = classify_nets(to_feature_graph(g), cfg)
    # The feature graph sorts its edges by (dst, pin, src, net), so the class of every edge of
    # ``g`` comes from its net's class, keeping ``edge_class`` aligned with ``g``'s own edges.
    edge_class = np.fromiter(
        (CLASS_NAMES.index(net_roles.net_class[int(net[1:])]) for net in g.net),
        dtype=np.int8, count=g.n_edges,
    )
    roles = np.asarray(
        [
            (node.clock_domain, node.has_reset, node.const_inputs, node.enable)
            for node in net_roles.nodes
        ],
        dtype=np.int64,
    ).reshape(g.n_nodes, 4)
    return SignalInfo(edge_class, roles, dict(net_roles.classified), net_roles.clock_domains)
