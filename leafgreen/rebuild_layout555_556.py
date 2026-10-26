"""Resource-free reproduction of two fixed LeafGreen layout revisions.

Reads the parent's live text tokens, not child bytes or a translation manifest.
No ROM, charmap, translated body, font or binary diff payload is bundled.
Historical offsets are NOT permission to reuse pools in a current ROM.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from frlg.rom import GateError, Image, sha, span, uint, BASE, verify_changes
from frlg.text import exact, read

SIZE = 0x1000000
STAGES = {
    '555': dict(parent='638f482e248c5e276670a8b0cad812f2179c2a6b92a2277c36419133608ac2af',
        output='f9a3b7c5b772b9d50e2b36b6970df47fbf125135cc6160425f08acea120d1f41'),
    '556': dict(parent='f9a3b7c5b772b9d50e2b36b6970df47fbf125135cc6160425f08acea120d1f41',
        output='094ce52b43ce394db6be2176865261f55153e7af02026c7a2ba305e35d4ca281'),
}
# Historical private punctuation IDs -> native single-byte punctuation.
# These are encoding identities, not bitmap or text assets.
NATIVE_PUNCT = {0x21: b'\xb0', 0x24: b'\xab', 0x6A: b'\xac', 0x37: b'\xad'}


def require(ok, label):
    if not ok:
        raise GateError(label)


def without_redundant_nl(raw: bytes):
    stream = exact(raw, 'cn')
    require(stream.status == 'OK', 'malformed parent text stream')
    removed = 0
    parts = []
    for index, (_, kind, token) in enumerate(stream.tokens):
        previous = stream.tokens[index - 1] if index else None
        if kind == 'layout' and token == b'\xfe' and previous and previous[1:] == ('layout', b'\xfa'):
            removed += 1
        else:
            parts.append(token)
    return b''.join(parts), removed


def native_punctuation(raw: bytes):
    stream = exact(raw, 'cn')
    require(stream.status == 'OK', 'malformed parent text stream')
    parts, converted = [], 0
    for _, kind, token in stream.tokens:
        gid = int.from_bytes(token[1:], 'big') if kind == 'cn' else None
        if gid in NATIVE_PUNCT:
            parts.append(NATIVE_PUNCT[gid])
            converted += 1
        else:
            parts.append(token)
    return b''.join(parts), converted


def build(parent: bytes, stage: str):
    require(stage in STAGES, 'unsupported stage')
    spec = STAGES[stage]
    require(type(parent) is bytes and len(parent) == SIZE and sha(parent) == spec['parent'], 'unexpected parent identity or size')
    out, writes, transformations = bytearray(parent), [], []

    def apply(at, payload, purpose):
        before = span(parent, at, len(payload))
        writes.append(dict(offset=at, before_hex=before.hex(), after_hex=payload.hex(), purpose=purpose))
        out[at:at + len(payload)] = payload

    def relocate(slots, source, target, old_size, new_size, operation, count):
        require(all(uint(parent, slot) == BASE + source for slot in slots), 'live text pointer differs')
        old = read(parent, source, 'cn', old_size)
        require(old.status == 'OK' and len(old.raw) == old_size, 'live stream capacity differs')
        new, n = operation(old.raw)
        require(n == count and len(new) == new_size and exact(new, 'cn').status == 'OK', 'transformation count/size differs')
        apply(target, new, 'new_pool')
        for slot in slots:
            apply(slot, struct.pack('<I', BASE + target), 'display_pointer')
        transformations.append(dict(source=hex(source), target=hex(target), old_bytes=old_size,
            new_bytes=new_size, tokens_changed=n, references=len(slots)))

    if stage == '555':
        relocate([0x18FA6D], 0xDC9930, 0xE38180, 176, 175, without_redundant_nl, 1)
        reference = read(parent, 0xB486C4, 'cn')
        require(reference.status == 'OK', 'native reference copy malformed')
        # Reference is corroboration only, never a source of payload bytes.
        result = exact(bytes(out[0xE38180:0xE38180 + 175]), 'cn')
        layout = lambda s: [token for _, kind, token in s.tokens if kind == 'layout']
        require(layout(reference) == layout(result), 'layout skeleton differs from retained reference copy')
    else:
        relocate([0x1697D9, 0x169818], 0xE3805C, 0xE38280, 75, 69, native_punctuation, 3)
        relocate([0x16A2C7, 0x16A2D2, 0x16A2DD, 0x16A2E8, 0x16A2F3, 0x16A2FE],
                 0xE380A8, 0xE382C8, 209, 183, native_punctuation, 13)
    product = bytes(out)
    report = verify_changes(parent, product, writes, [])
    require(sha(product) == spec['output'], 'historical output identity differs')
    return product, dict(**report, stage=stage, parent_sha256=spec['parent'], output_sha256=spec['output'],
        transformations=transformations, method='LIVE_PARENT_TOKEN_TRANSFORMATION',
        requires_external_charmap=False, requires_translation_manifest=False,
        original_discovery_algorithm_replayed=False, runtime_tested=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage', required=True, choices=sorted(STAGES))
    ap.add_argument('--parent', required=True, type=Path)
    ap.add_argument('--compare', type=Path, help='optional independent retained child, read-only')
    args = ap.parse_args()
    spec = STAGES[args.stage]
    parent = Image.load(args.parent, spec['parent'], SIZE)
    product, report = build(parent.data, args.stage)
    inputs = [parent]
    if args.compare:
        child = Image.load(args.compare, spec['output'], SIZE)
        require(product == child.data, 'independent retained child bytes differ')
        inputs.append(child)
    for image in inputs:
        image.unchanged()
    print(json.dumps(dict(replay=report, compared_existing=args.compare is not None,
        inputs_unchanged=True, output_written=False, complete_clean_rom_rebuild=False), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (GateError, OSError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
