"""Pack caller-owned pixel matrices, not fonts extracted from a game or donor."""
from __future__ import annotations

import csv
import io

from .encode import NATIVE
from .font_pages import MAX_GID, PAGE_SPAN, glyph_slot_in_page
from .glyph_codec import encode_tile
from .rom import GateError, number, sha


def build_font(document: dict):
    """Build address-independent pages and a charmap for the full 12x12 decoder.

    Pixel canvas is 16x16, but ink outside the 12x12 drawing area is rejected.
    Addresses and ROM allocation are deliberately not inferred here.
    """
    if not isinstance(document, dict) or set(document) != {"schema", "source", "glyphs"}:
        raise GateError("font input requires schema/source/glyphs")
    if type(document["schema"]) is not int or document["schema"] != 1:
        raise GateError("unsupported font input schema")
    if not isinstance(document["source"], str) or not document["source"].strip():
        raise GateError("describe the source and permission for your own glyph input")
    glyphs = document["glyphs"]
    if not isinstance(glyphs, list) or not 1 <= len(glyphs) <= MAX_GID + 1:
        raise GateError("nonempty bounded glyph list required")
    pages, records, characters, ids = {}, [], set(), set()
    for glyph in glyphs:
        if not isinstance(glyph, dict) or set(glyph) != {"unicode", "glyph_id", "pixels"}:
            raise GateError("glyph requires unicode/glyph_id/pixels")
        character, pixels = glyph["unicode"], glyph["pixels"]
        if (not isinstance(character, str) or len(character) != 1 or
                ord(character) < 32 or ord(character) == 127 or
                0xD800 <= ord(character) <= 0xDFFF or character in "{}" or character in NATIVE):
            raise GateError("one private printable character required; native characters stay native")
        gid = number(glyph["glyph_id"])
        if not 0 <= gid <= MAX_GID or gid in ids or character in characters:
            raise GateError("duplicate character/id or out-of-range glyph id")
        if (not isinstance(pixels, list) or len(pixels) != 16 or
                any(not isinstance(row, list) or len(row) != 16 for row in pixels)):
            raise GateError("pixels must be a 16x16 matrix")
        for y, row in enumerate(pixels):
            for x, pixel in enumerate(row):
                if type(pixel) is not int or not 0 <= pixel <= 2:
                    raise GateError("pixels must be integer source values 0..2")
                if (x >= 12 or y >= 12) and pixel != 0:
                    raise GateError("ink outside 12x12 would be clipped by the decoder")
        page = pages.setdefault(gid >> 8, bytearray(b"\xff" * PAGE_SPAN))
        slot = glyph_slot_in_page(gid & 255)
        for off, x, y in ((0, 0, 0), (0x10, 8, 0), (0x100, 0, 8), (0x110, 8, 8)):
            page[slot + off:slot + off + 16] = encode_tile(pixels, x, y)
        records.append((gid, character))
        ids.add(gid)
        characters.add(character)
    table = io.StringIO(newline="")
    writer = csv.writer(table, lineterminator="\n")
    writer.writerow(("unicode", "glyph_id", "status"))
    for gid, character in sorted(records):
        writer.writerow((character, f"0x{gid:04X}", "allocated"))
    artifacts = {f"page_{page:02X}.bin": bytes(data) for page, data in sorted(pages.items())}
    artifacts["blank_page.bin"] = b"\xff" * PAGE_SPAN
    artifacts["charmap.csv"] = table.getvalue().encode("utf8")
    # Counts/identities only: the private source attribution stays in the caller's input.
    report = dict(schema=1, glyph_count=len(records), pages=sorted(pages),
                  max_gid=MAX_GID, page_span=PAGE_SPAN, width=12, height=12,
                  artifacts={name: dict(size=len(data), sha256=sha(data))
                             for name, data in artifacts.items()},
                  permission="CALLER_MUST_VERIFY", runtime="UNOBSERVED", rom_installed=False)
    return artifacts, report
