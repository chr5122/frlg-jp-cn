"""Resource-free disjoint three-way merge; not a translation or build validator."""
from __future__ import annotations

from .rom import GateError


def disjoint_merge(base: bytes, left: bytes, right: bytes):
    """Reject *any* changed-byte overlap, including equal-value overlaps.

    All three inputs are immutable. This reproduces the historical FIX561
    policy, not Git's conflict resolution and not a generic binary patch.
    """
    if not all(isinstance(value, bytes) for value in (base, left, right)):
        raise GateError('merge inputs must be immutable bytes')
    if not base or len(base) != len(left) or len(base) != len(right):
        raise GateError('merge inputs must have the same nonzero size')
    result = bytearray(base)
    left_count = right_count = 0
    for at, (old, a, b) in enumerate(zip(base, left, right)):
        if a != old and b != old:
            raise GateError(f'branch deltas overlap at file offset {at:#x}')
        if a != old:
            result[at] = a
            left_count += 1
        elif b != old:
            result[at] = b
            right_count += 1
    return bytes(result), dict(left_changed_bytes=left_count, right_changed_bytes=right_count,
                               overlap_bytes=0, changed_bytes=left_count + right_count)
