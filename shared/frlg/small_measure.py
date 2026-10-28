"""Bounded host-side model of the production small-text extent routine.

The production assembly trusts its callers; this adapter validates the stream
and external widths first. It does not run, install, or replace game code.
"""
from __future__ import annotations

from .font_pages import MAX_GID
from .rom import GateError
from .text import exact


def _width(mapping, index, label):
    if not isinstance(mapping, dict) or index not in mapping:
        raise GateError(f'missing {label} width for {index:#x}')
    value = mapping[index]
    if type(value) is not int or not 0 <= value <= 255:
        raise GateError(f'invalid {label} width for {index:#x}')
    return value


def measure_small(stream: bytes, widths: bytes, allocated_ids: set[int],
                  native_widths: dict[int, int], icon_widths: dict[int, int]):
    """Return last meaningful-token extent, not simply the final pen position.

    Accept only one-line native characters, private F7 IDs, F8 icons and FC0D
    absolute pen moves. F7 operand bytes may contain 00 or FF. All widths must
    be supplied by the caller; zero-width allocated glyphs remain valid.
    """
    if not isinstance(stream, bytes) or not 1 <= len(stream) <= 4096:
        raise GateError('bounded immutable byte stream required')
    if not isinstance(widths, bytes) or len(widths) != MAX_GID+1 or any(x>16 for x in widths):
        raise GateError('small width table must contain 0xB00 entries in 0..16')
    if (not isinstance(allocated_ids, set) or
            any(type(gid) is not int or not 0 <= gid <= MAX_GID for gid in allocated_ids)):
        raise GateError('explicit bounded allocated glyph IDs required')
    parsed = exact(stream, 'cn')
    if parsed.status != 'OK':
        raise GateError(f'invalid text stream: {parsed.status}')
    pen = extent = count = 0
    for _, kind, raw in parsed.tokens:
        if kind == 'end':
            break
        if kind == 'glyph':
            pen += _width(native_widths, raw[0], 'native glyph')
            if raw[0] != 0:
                extent = pen
        elif kind == 'cn':
            gid = int.from_bytes(raw[1:], 'big')
            if gid > MAX_GID or gid not in allocated_ids:
                raise GateError(f'unallocated small glyph {gid:#x}')
            pen += widths[gid]
            extent = pen
        elif kind == 'parameter' and raw[0] == 0xF8:
            pen += _width(icon_widths, raw[1], 'icon')
            extent = pen
        elif kind == 'extended' and raw[:2] == b'\xfc\x0d':
            pen = raw[2]
        else:
            raise GateError(f'unsupported control in bounded small measurement: {raw.hex()}')
        count += 1
    return dict(status='PASS', extent=extent, pen=pen, tokens=count,
                runtime='NOT_EXECUTED', game_or_save_input=False)
