"""Clean BPGJ -> one hand-drawn glyph experiment, not a translation release.

Revisits MVP01's independently drawn pixels with the subsequently corrected
native codec. This is NOT a byte-identical recreation of historical MVP01.
No donor Chinese ROM, font file, translation CSV or save is required.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'shared'))
from frlg.rom import GateError, Image, sha, span, verify_changes
from frlg.glyph_codec import encode_tile, decode_four_block_glyph

JP_SHA = '2957b392dc09fc8df45a660af5493368d7bd378d299862f4cc115998e9da0bf2'
FONT_BASE, WIDTH_BASE, SLOT = 0x1D6DD0, 0x1DEDD0, 0x1A


def pixels():
    # Original project hand-drawn test, not pixels extracted from a font.
    p = [[0] * 16 for _ in range(16)]
    for x in range(1, 9):
        p[1][x] = p[5][x] = p[10][x] = 1
    for y in range(1, 11):
        for x in (1, 8, 4, 5):
            p[y][x] = 1
    return p


def patch(parent: bytes):
    if len(parent) != 0x1000000 or sha(parent) != JP_SHA:
        raise GateError('requires exact original BPGJ Rev0')
    if span(parent, WIDTH_BASE + SLOT, 1) != b'\x0a':
        raise GateError('native test-slot width mismatch')
    canvas, product, writes = pixels(), bytearray(parent), []
    base = FONT_BASE + (SLOT >> 3) * 0x200 + (SLOT & 7) * 0x20
    for off, x, y in ((0, 0, 0), (0x10, 8, 0), (0x100, 0, 8), (0x110, 8, 8)):
        tile = encode_tile(canvas, x, y)
        at = base + off
        product[at:at + 16] = tile
        writes.append(dict(offset=at, before_hex=span(parent, at, 16).hex(),
                           after_hex=tile.hex(), purpose='experimental_glyph_only'))
    result = bytes(product)
    report = verify_changes(parent, result, writes, [])
    if decode_four_block_glyph(result, base) != canvas:
        raise GateError('native lookup round-trip mismatch')
    return result, dict(**report, input_sha256=JP_SHA, output_sha256=sha(result),
                        native_width_unchanged=True, instructions_changed=0,
                        source='independently hand-drawn project test',
                        runtime_display='UNOBSERVED', complete_translation=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--original', required=True, type=Path)
    ap.add_argument('--output', type=Path, help='optional new file; default: in-memory dry run')
    args = ap.parse_args()
    image = Image.load(args.original, JP_SHA, 0x1000000)
    result, report = patch(image.data)
    image.unchanged()
    if args.output:
        if args.output.resolve() == image.path:
            raise GateError('refusing to overwrite original')
        with args.output.open('xb') as target:
            target.write(result)
        if sha(args.output.read_bytes()) != report['output_sha256']:
            raise GateError('output readback mismatch')
    image.unchanged()
    report['output_written'] = args.output is not None
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (GateError, OSError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
