"""L2 analysis plugins: kinds and the lazy optional-extra check (L2 spec sections 2 and 10).

Heavy libraries are extras, so every module of this package imports them inside functions after
calling :func:`require`; importing ``loki.analysis`` alone needs the standard library only.
"""

from __future__ import annotations

import importlib

KINDS = ("export", "cluster", "graphlets", "gnn")

_EXTRAS: dict[str, tuple[str, ...]] = {
    "analysis": ("numpy", "scipy", "sklearn", "networkx"),
    "gnn": ("numpy", "scipy", "sklearn", "networkx", "torch", "torch_geometric"),
}


class MissingExtra(RuntimeError):
    """An optional dependency group of Loki is not installed."""


def require(extra: str) -> None:
    """Raise :class:`MissingExtra` unless every library of ``extra`` imports."""
    if extra not in _EXTRAS:
        raise ValueError(f"unknown extra {extra!r}")
    try:
        for module in _EXTRAS[extra]:
            importlib.import_module(module)
    except ImportError as exc:
        raise MissingExtra(
            f"this needs the '{extra}' extra: pip install 'loki[{extra}]'"
        ) from exc
