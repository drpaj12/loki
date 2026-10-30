"""Claims v2: intent-level claims derived from a ``loki re`` run (hints v2, Part A of the brief).

The L1 loop (``loki.re``) is not changed in its scoring. This package reads its graph and overlay
and writes claims that say what a piece does (counter, state machine, shift register, bus with a
purpose), with a probability that is a calibrated posterior (``loki.intent.calib``).
"""
