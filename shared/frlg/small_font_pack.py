"""Pack caller-owned small glyphs; never read or allocate game resources."""
from __future__ import annotations

from .font_pack import _charmap, _validated_glyphs
from .font_pages import MAX_GID, PAGE_SPAN
from .glyph_codec import encode_tile
from .rom import GateError, sha


def build_small_font(document: dict, normal_charmap: dict | None = None):
    """Produce contiguous 64-byte glyph slots and a 0xB00-byte width table.

    A supplied normal charmap must have identical characters and glyph IDs.
    Unallocated widths are zero; only the accompanying charmap allocates IDs.
    """
    records = _validated_glyphs(document, extra_keys=('width',), width=16, height=13)
    pages = {}
    widths = bytearray(MAX_GID + 1)
    for gid, character, pixels, glyph in records:
        width = glyph['width']
        if type(width) is not int or not 0 <= width <= 16:
            raise GateError('small glyph width must be an integer in 0..16')
        if any(pixel for row in pixels for pixel in row[width:]):
            raise GateError('small glyph ink extends beyond its advance width')
        page = pages.setdefault(gid >> 8, bytearray(b'\xff' * PAGE_SPAN))
        slot = (gid & 255) * 64
        for off, x, y in ((0, 0, 0), (16, 8, 0), (32, 0, 8), (48, 8, 8)):
            page[slot + off:slot + off + 16] = encode_tile(pixels, x, y)
        widths[gid] = width
    allocations = {character: gid for gid, character, *_ in records}
    if normal_charmap is not None:
        if not isinstance(normal_charmap, dict):
            raise GateError('normal charmap must be an allocated mapping')
        try:
            normal = {character: item['_gid'] for character, item in normal_charmap.items()}
        except (KeyError, TypeError) as exc:
            raise GateError('malformed normal charmap') from exc
        if normal != allocations or any(type(gid) is not int for gid in normal.values()):
            raise GateError('normal and small charmap allocations must match exactly')
    artifacts = {f'page_{page:02X}.bin': bytes(data) for page, data in sorted(pages.items())}
    artifacts['blank_page.bin'] = b'\xff' * PAGE_SPAN
    artifacts['widths.bin'] = bytes(widths)
    artifacts['charmap.csv'] = _charmap(records)
    report = dict(schema=1, glyph_count=len(records), pages=sorted(pages), max_gid=MAX_GID,
                  page_span=PAGE_SPAN, slot_layout='contiguous-64-byte', height=13,
                  normal_charmap='MATCHED' if normal_charmap is not None else 'UNVERIFIED',
                  artifacts={name: dict(size=len(data), sha256=sha(data)) for name, data in artifacts.items()},
                  permission='CALLER_MUST_VERIFY', runtime='UNOBSERVED', rom_installed=False)
    return artifacts, report
