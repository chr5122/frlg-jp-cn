"""Reproduce FIX581->582->583 from user-supplied, SHA-pinned inputs.

No font, title graphic, translation CSV or ROM is distributed. This does NOT
build FIX581 from a clean Japanese ROM. Default is an in-memory dry run.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
from frlg.encode import encode, load_charmap
from frlg.lz77 import decompress
from frlg.rom import GateError, Image, sha, span, verify_changes

SHA581 = 'a04696f9bc586c766ed563d18b702879701d0c9cfde4844f708d22dd749bc344'
SHA582 = 'd6afc4c9be8c5ee9e5328302bb49d75ef9a5172c58f361ad3aa66b880845eb2b'
SHA583 = '900b5247f04a30402ae35e3336c398006305efa0b7f01bdc3de1cdc28023c11c'
JP_SHA = '2957b392dc09fc8df45a660af5493368d7bd378d299862f4cc115998e9da0bf2'
DONOR_SHA = '8a74df389bd5504bc09939fcb5c9e0c277f916024dfbd4db4bf46eb46936aafc'
SIZE = 0x1000000


def require_image(data, expected):
    if len(data) != SIZE or sha(data) != expected:
        raise GateError('unexpected input SHA or size')


def title582(parent: bytes, original: bytes, donor: bytes):
    require_image(parent, SHA581)
    require_image(original, JP_SHA)
    require_image(donor, DONOR_SHA)
    if span(parent, 0x78230, 8) != struct.pack('<II', 0x083835E4, 0x08384EE0):
        raise GateError('native title resource pointers drifted')
    if span(original, 0x78230, 8) != span(parent, 0x78230, 8):
        raise GateError('original title pointer mismatch')
    if span(parent, 0x383584, 96) != span(donor, 0xEAB744, 96):
        raise GateError('required palette prefix differs')
    if span(parent, 0xE4A000, 0x2000) != b'\xff' * 0x2000:
        raise GateError('fixed historical title window is occupied')
    tiles, tiles_len = decompress(donor, 0x719C00, 0x4000)
    tile_map, map_len = decompress(donor, 0x71B600, 0x1000)
    jp_tiles, _ = decompress(original, 0x3835E4, 0x4000)
    jp_map, _ = decompress(original, 0x384EE0, 0x1000)
    if (len(tiles), len(tile_map), len(jp_tiles), len(jp_map)) != (0x30B0, 1280, 0x2C80, 1280):
        raise GateError('unexpected title resource dimensions')
    max_tile = max(v[0] & 0x3FF for v in struct.iter_unpack('<H', tile_map))
    if max(tiles) >= 48 or (max_tile + 1) * 64 > len(tiles):
        raise GateError('title palette or tile-map bounds invalid')
    tile_at = 0xE4A000
    map_at = (tile_at + tiles_len + 3) & ~3
    end = (map_at + map_len + 3) & ~3
    if end > 0xE4C000:
        raise GateError('title window overflow')
    product, writes = bytearray(parent), []
    for at, payload, purpose in (
        (tile_at, span(donor, 0x719C00, tiles_len), 'new_pool'),
        (map_at, span(donor, 0x71B600, map_len), 'new_pool'),
        (0x78230, struct.pack('<I', 0x08000000 + tile_at), 'display_pointer'),
        (0x78234, struct.pack('<I', 0x08000000 + map_at), 'display_pointer'),
    ):
        product[at:at + len(payload)] = payload
        writes.append(dict(offset=at, before_hex=span(parent, at, len(payload)).hex(),
                           after_hex=payload.hex(), purpose=purpose))
    result = bytes(product)
    report = verify_changes(parent, result, writes, [])
    if sha(result) != SHA582 or report['changed_bytes'] != 6209:
        raise GateError('FIX582 output identity mismatch')
    if decompress(result, tile_at)[0] != tiles or decompress(result, map_at)[0] != tile_map:
        raise GateError('relocated resource readback mismatch')
    return result, dict(**report, output_sha256=SHA582, new_instructions=0)


def hint583(parent: bytes, charmap):
    require_image(parent, SHA582)
    if struct.unpack_from('<I', parent, 0x131ED0)[0] != 0x081A9E2C:
        raise GateError('name-choice hint pointer drifted')
    if span(parent, 0x131E9C, 2) != bytes.fromhex('0c4a'):
        raise GateError('literal consumer drifted')
    payload = encode('自己取名{END}', charmap)
    if len(payload) != 13 or span(parent, 0xE499D0, 13) != b'\xff' * 13:
        raise GateError('historical hint capacity or preimage mismatch')
    product, writes = bytearray(parent), []
    for at, raw, purpose in ((0xE499D0, payload, 'new_pool'),
                             (0x131ED0, struct.pack('<I', 0x08E499D0), 'display_pointer')):
        product[at:at + len(raw)] = raw
        writes.append(dict(offset=at, before_hex=span(parent, at, len(raw)).hex(),
                           after_hex=raw.hex(), purpose=purpose))
    result = bytes(product)
    report = verify_changes(parent, result, writes, [])
    if sha(result) != SHA583 or report['changed_bytes'] != 15:
        raise GateError('FIX583 output identity mismatch; wrong external charmap')
    return result, dict(**report, output_sha256=SHA583, new_instructions=0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--from', dest='stage', choices=('fix581', 'fix582'), required=True)
    ap.add_argument('--parent', type=Path, required=True)
    ap.add_argument('--charmap', type=Path, required=True)
    ap.add_argument('--original', type=Path)
    ap.add_argument('--donor', type=Path)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    images = [Image.load(args.parent, SHA581 if args.stage == 'fix581' else SHA582, SIZE)]
    cmap_before = args.charmap.read_bytes()
    charmap = load_charmap(args.charmap)
    product, reports = images[0].data, []
    if args.stage == 'fix581':
        if args.original is None or args.donor is None:
            ap.error('--from fix581 requires --original and --donor')
        images.extend((Image.load(args.original, JP_SHA, SIZE), Image.load(args.donor, DONOR_SHA, SIZE)))
        product, report = title582(product, images[1].data, images[2].data)
        reports.append(report)
    product, report = hint583(product, charmap)
    reports.append(report)
    for image in images:
        image.unchanged()
    if args.charmap.read_bytes() != cmap_before:
        raise GateError('external charmap changed during build')
    if args.output:
        if args.output.resolve() in {image.path for image in images} | {args.charmap.resolve()}:
            raise GateError('output aliases an input')
        with args.output.open('xb') as target:
            target.write(product)
        if sha(args.output.read_bytes()) != SHA583:
            raise GateError('output readback mismatch')
    print(json.dumps(dict(stages=reports, output_written=args.output is not None,
                          complete_clean_rom_rebuild=False, runtime_tested=False), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (GateError, OSError, ValueError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
