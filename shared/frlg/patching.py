"""Exact-input, fixed-size patch recipes; no discovery or resource allocation."""
from __future__ import annotations

import re

from .rom import GateError, number, sha, span, verify_changes


PROFILES = {
    "firered-jp-rev0": {
        "sha256": "1e4af44b0c75cc8649bfb8649dc4ae5850bf5358bd6b9cd0bf779c99f9db1486",
        "size": 16777216,
    },
    "leafgreen-jp-rev0": {
        "sha256": "2957b392dc09fc8df45a660af5493368d7bd378d299862f4cc115998e9da0bf2",
        "size": 16777216,
    },
}


def apply_recipe(parent: bytes, recipe: dict, *, expected_sha256: str, size: int):
    """Return verified bytes and a report. Caller supplies a trusted input identity."""
    if len(parent) != size or sha(parent) != expected_sha256:
        raise GateError("original ROM identity mismatch")
    fields = {"schema", "game", "output_sha256", "writes", "protected"}
    if not isinstance(recipe, dict) or set(recipe) != fields:
        raise GateError("recipe fields must be schema/game/output_sha256/writes/protected")
    if type(recipe["schema"]) is not int or recipe["schema"] != 1:
        raise GateError("unsupported recipe schema")
    if not isinstance(recipe["game"], str) or recipe["game"] not in PROFILES:
        raise GateError("unknown game profile")
    target = recipe["output_sha256"]
    if not isinstance(target, str) or not re.fullmatch(r"[0-9a-f]{64}", target):
        raise GateError("output_sha256 must be a lowercase SHA-256")
    writes, protected = recipe["writes"], recipe["protected"]
    if not isinstance(writes, list) or not writes:
        raise GateError("writes must be a nonempty list")
    if not isinstance(protected, list):
        raise GateError("protected must be a list, even when empty")
    for guard in protected:
        if not isinstance(guard, dict) or set(guard) != {"start", "end", "name"}:
            raise GateError("invalid protected range fields")
        lo, hi = number(guard["start"]), number(guard["end"])
        if not isinstance(guard["name"], str) or not guard["name"] or not 0 <= lo < hi <= size:
            raise GateError("protected ranges require a name and bounded file offsets")
    product = bytearray(parent)
    for write in writes:
        if not isinstance(write, dict) or set(write) != {"offset", "before_hex", "after_hex", "purpose"}:
            raise GateError("invalid write fields")
        if write["purpose"] not in ("patch", "new_pool"):
            raise GateError("purpose must be patch or new_pool")
        if not all(isinstance(write[key], str) for key in ("before_hex", "after_hex")):
            raise GateError("write bytes must be hexadecimal strings")
        before, after = bytes.fromhex(write["before_hex"]), bytes.fromhex(write["after_hex"])
        at = number(write["offset"])
        if not before or len(before) != len(after):
            raise GateError("writes must have equal nonempty byte lengths")
        if span(parent, at, len(before)) != before:
            raise GateError(f"preimage mismatch at {at:#x}")
        product[at:at + len(after)] = after
    product = bytes(product)
    report = verify_changes(parent, product, writes, protected)
    if not report["changed_bytes"]:
        raise GateError("recipe does not change any bytes")
    if sha(product) != target:
        raise GateError("output SHA-256 mismatch")
    report.update(game=recipe["game"], input_sha256=expected_sha256,
                  output_sha256=target, size=size, runtime="UNOBSERVED",
                  complete_translation=False)
    return product, report
