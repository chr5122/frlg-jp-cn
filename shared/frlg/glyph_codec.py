"""LeafGreen-origin source glyph codec. No font pixels or lookup table bundled.

Ported from the project's bpgj_font_codec.py; public boundaries fail closed.
The native lookup table is read from the user's own Japanese ROM.
"""
from .rom import GateError, span

LOOKUP_OFFSET = 0x1CDF1C


def encode_row(pixels):
    if len(pixels) != 4 or any(type(x) is not int or not 0 <= x <= 2 for x in pixels):
        raise GateError('four source pixels in range 0..2 required')
    return sum(pixel << (2 * (3 - i)) for i, pixel in enumerate(pixels))


def encode_tile(pixels, x0=0, y0=0):
    if type(x0) is not int or type(y0) is not int or x0 < 0 or y0 < 0:
        raise GateError('nonnegative tile origin required')
    if len(pixels) < y0 + 8 or any(len(row) < x0 + 8 for row in pixels[y0:y0 + 8]):
        raise GateError('tile outside canvas')
    out = bytearray()
    for row in pixels[y0:y0 + 8]:
        left = encode_row(row[x0:x0 + 4])
        right = encode_row(row[x0 + 4:x0 + 8])
        # Native u16 input consumes the high byte first.
        out.extend((right, left))
    return bytes(out)


def decode_source_byte(rom, value, lookup_offset=LOOKUP_OFFSET):
    if type(value) is not int or not 0 <= value <= 255:
        raise GateError('source byte outside 0..255')
    ternary = span(rom, lookup_offset + value, 1)[0]
    pixels = []
    for _ in range(4):
        pixels.append(ternary % 3)
        ternary //= 3
    return pixels[::-1]


def decode_tile(rom, source, lookup_offset=LOOKUP_OFFSET):
    if len(source) != 16:
        raise GateError('encoded tile must be 16 bytes')
    return [decode_source_byte(rom, source[y * 2 + 1], lookup_offset) +
            decode_source_byte(rom, source[y * 2], lookup_offset) for y in range(8)]


def decode_four_block_glyph(rom, base, lookup_offset=LOOKUP_OFFSET):
    a, b, c, d = [decode_tile(rom, span(rom, base + off, 16), lookup_offset)
                  for off in (0, 0x10, 0x100, 0x110)]
    return [x + y for x, y in zip(a, b)] + [x + y for x, y in zip(c, d)]
