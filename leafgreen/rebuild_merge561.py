"""Merge exact external FIX558/FIX559/islands FIX560, in memory only.

No ROM bytes, translation text, fonts or binary diff payloads are bundled.
This does not build either branch from source or certify their contents.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from frlg.merge import disjoint_merge
from frlg.rom import GateError, Image, sha

SIZE = 0x1000000
BASE_SHA = 'e8bdb1132cda745d04ec7f252e8ffb3781ea649ea24ac41be1143704d77894ca'
SAVE_SHA = '7ebf81ba53c49bcb6fb94d2ea4a39ec97ac8e9467bc25ed4bb0bd219e6f828ba'
ISLANDS_SHA = '88585ccc1155b702a398bd75ce5e2501a4afc270a63c71d5999d1c2ebca9970c'
OUTPUT_SHA = '80a306a3a7c873eeae97b95d831d4dd9f29a1299e408b5c6fe38b178d25ab01c'


def build(base: bytes, save: bytes, islands: bytes):
    for data, expected in ((base, BASE_SHA), (save, SAVE_SHA), (islands, ISLANDS_SHA)):
        if len(data) != SIZE or sha(data) != expected:
            raise GateError('unexpected merge input identity or size')
    product, report = disjoint_merge(base, save, islands)
    if (report['left_changed_bytes'], report['right_changed_bytes'], report['changed_bytes']) != (344, 30880, 31224):
        raise GateError('historical branch delta counts differ')
    if sha(product) != OUTPUT_SHA:
        raise GateError('merged output identity differs')
    return product, dict(**report, output_sha256=OUTPUT_SHA, status='PINNED_MERGE_PASS')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, required=True, help='exact FIX558')
    ap.add_argument('--save', type=Path, required=True, help='exact FIX559 save-prompt branch')
    ap.add_argument('--islands', type=Path, required=True, help='exact four-to-seven-islands FIX560, NOT island-menu FIX560')
    ap.add_argument('--compare', type=Path, help='optional existing FIX561 to compare, read-only')
    args = ap.parse_args()
    images = [Image.load(path, expected, SIZE) for path, expected in (
        (args.base, BASE_SHA), (args.save, SAVE_SHA), (args.islands, ISLANDS_SHA))]
    product, report = build(*(image.data for image in images))
    if args.compare:
        reference = Image.load(args.compare, OUTPUT_SHA, SIZE)
        images.append(reference)
        if reference.data != product:
            raise GateError('existing FIX561 bytes differ')
    for image in images:
        image.unchanged()
    print(json.dumps(dict(merge=report, compared_existing=args.compare is not None,
                          inputs_unchanged=True, output_written=False,
                          complete_clean_rom_rebuild=False, runtime_tested=False), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (GateError, OSError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
