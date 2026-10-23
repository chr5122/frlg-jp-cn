from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

BASE = 0x08000000


class GateError(ValueError):
    """Invalid identity, bounds, schema or evidence: fail closed."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def number(value) -> int:
    if isinstance(value, bool):
        raise GateError("boolean is not an address")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise GateError(f"not an integer/address: {value!r}")


def span(data: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise GateError(f"out of bounds: {offset:#x}+{size:#x}/{len(data):#x}")
    return data[offset:offset + size]


def uint(data: bytes, offset: int, size=4, signed=False) -> int:
    return int.from_bytes(span(data, offset, size), "little", signed=signed)


def pointer(data: bytes, value: int) -> int:
    if not BASE <= value < BASE + len(data):
        raise GateError(f"invalid ROM pointer {value:#x}; actual size {len(data):#x}")
    return value - BASE


@dataclass(frozen=True)
class Image:
    path: Path
    data: bytes
    digest: str

    @classmethod
    def load(cls, path: Path, expected: str, size: int | None = None):
        data = path.read_bytes()
        got = sha(data)
        if got != expected or (size is not None and len(data) != size):
            raise GateError(f"identity mismatch: {path}, sha={got}, size={len(data)}")
        return cls(path.resolve(), data, got)

    def unchanged(self):
        if sha(self.path.read_bytes()) != self.digest:
            raise GateError(f"input changed during run: {self.path}")


def overlap(a, b) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def preimage_matches(actual: bytes, parent: bytes, declared_hex: str) -> bool:
    """Compare bytes with a hex declaration; no truthy fallback or type mixing."""
    try:
        declared = bytes.fromhex(declared_hex)
    except (ValueError, TypeError):
        return False
    return bool(declared) and actual == parent == declared


def protected_offsets(changes, ranges, image_size: int) -> list[int]:
    """All inputs are FILE OFFSETS. Reject accidentally supplied ROM VMAs."""
    for lo, hi in ranges:
        if not 0 <= lo < hi <= image_size:
            raise GateError("protected range is not a bounded file-offset range")
    result = []
    for at in changes:
        if not 0 <= at < image_size:
            raise GateError("changed address is not a file offset")
        if any(lo <= at < hi for lo, hi in ranges):
            result.append(at)
    return result


def verify_changes(parent: bytes, product: bytes, writes: list[dict], protected: list[dict]) -> dict:
    """Check actual ROM differences, not declared totals. Does not apply writes."""
    if len(parent) != len(product):
        raise GateError("ROM size changed")
    ranges = []
    for w in writes:
        at = number(w["offset"])
        before, after = bytes.fromhex(w["before_hex"]), bytes.fromhex(w["after_hex"])
        if not after or len(before) != len(after):
            raise GateError("write must have equal, nonempty before/after lengths")
        rg = (at, at + len(after))
        if any(overlap(rg, x) for x in ranges):
            raise GateError("overlapping writes")
        for z in protected:
            if overlap(rg, (number(z["start"]), number(z["end"]))):
                raise GateError(f"protected range: {z['name']}")
        if span(parent, at, len(before)) != before:
            raise GateError(f"parent preimage mismatch at {at:#x}")
        if span(product, at, len(after)) != after:
            raise GateError(f"product bytes mismatch at {at:#x}")
        if w.get("purpose") == "new_pool" and any(x != 0xFF for x in before):
            raise GateError("new pool overlaps non-FF parent bytes")
        ranges.append(rg)
    ranges.sort()
    index = 0
    changed = 0
    for at, (a, b) in enumerate(zip(parent, product)):
        if a == b:
            continue
        changed += 1
        while index < len(ranges) and ranges[index][1] <= at:
            index += 1
        if index == len(ranges) or not ranges[index][0] <= at < ranges[index][1]:
            raise GateError(f"out-of-plan change at {at:#x}")
    return {"status": "PASS", "changed_bytes": changed, "write_ranges": len(ranges)}
