"""Replay specific external LeafGreen FIX557/558/559 inputs, in memory only.

No ROM, translation manifest, charmap or binary diff payload is bundled.
Manifest replay does not repeat the historical consumer-discovery algorithm.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from frlg.encode import load_charmap, encode, EncodeError
from frlg.rom import GateError, Image, sha, span, number, BASE, verify_changes
from frlg.text import read

SIZE = 0x1000000
STAGES = {
    '557': dict(parent='094ce52b43ce394db6be2176865261f55153e7af02026c7a2ba305e35d4ca281',
        output='540fa6afde1449b95fc20580f7f6004a9d484f6059c16fc2041ee8f9b1af6363', changed=2, writes=1),
    '558': dict(parent='540fa6afde1449b95fc20580f7f6004a9d484f6059c16fc2041ee8f9b1af6363',
        output='e8bdb1132cda745d04ec7f252e8ffb3781ea649ea24ac41be1143704d77894ca', changed=380, writes=33,
        manifest='931d59a73b2ebdefe661e63cc01323024c2df5a49b89d53c1d97206d9b26c16a', entries=16, local=0),
    '559': dict(parent='e8bdb1132cda745d04ec7f252e8ffb3781ea649ea24ac41be1143704d77894ca',
        output='7ebf81ba53c49bcb6fb94d2ea4a39ec97ac8e9467bc25ed4bb0bd219e6f828ba', changed=344, writes=16,
        manifest='9b516dafb178e19ac89407b8cd3ee2dd95883b6ccae99c028a6efa9f830acfb3', entries=5, local=1),
}
CHARMAP_SHAS = frozenset({
    '3a50c6f6d93a3caefb382102cfe4a1217694617d6e7b04a0e435801f61234c8a',
    '464c5ab50700544e349c07217ef949d2ac7cf2566bbdf89737854bc4863fabd4',
})


def require(ok, reason):
    if not ok:
        raise GateError(reason)


def build(parent: bytes, stage: str, manifest_raw: bytes | None = None, charmap=None):
    require(stage in STAGES, 'unsupported stage')
    spec = STAGES[stage]
    require(type(parent) is bytes and len(parent) == SIZE and sha(parent) == spec['parent'],
            'unexpected parent identity or size')
    out, writes = bytearray(parent), []

    def apply(at, payload, purpose):
        before = span(parent, at, len(payload))
        require(bool(payload), 'empty write')
        writes.append(dict(offset=at, before_hex=before.hex(), after_hex=payload.hex(), purpose=purpose))
        out[at:at + len(payload)] = payload

    if stage == '557':
        require(manifest_raw is None and charmap is None, 'FIX557 has no external text dependencies')
        at = 0xE37E05
        require(span(parent, at, 3) == bytes.fromhex('fa ab fb'), 'WAIT/punctuation preimage mismatch')
        apply(at, bytes.fromhex('ab fa fb'), 'control_order')
    else:
        require(type(manifest_raw) is bytes and sha(manifest_raw) == spec['manifest'], 'manifest identity mismatch')
        require(isinstance(charmap, dict), 'external charmap required')
        body = json.loads(manifest_raw)
        require(body['name'] == 'FIX' + stage and body['sha256'] == spec['output'], 'manifest stage/output mismatch')
        entries, local = body['entries'], body.get('local_entries', [])
        require(len(entries) == spec['entries'] and len(local) == spec['local'], 'manifest entry count differs')
        for entry in entries:
            at = number(entry['new_stream'])
            head = bytes.fromhex(entry['head'])
            # Only this explicitly named legacy token alias occurs here.
            payload = head + encode(entry['zh'].replace('{FD02}', '{STR_VAR_1}'), charmap)
            require(len(payload) == entry['bytes'], 'encoded payload size differs')
            apply(at, payload, 'new_pool')
            require(bool(entry['refs']), 'unreferenced relocation')
            for ref in entry['refs']:
                off, old, new = (number(ref[k]) for k in ('literal_at', 'old', 'new'))
                delta = old - number(entry['addr'])
                require(0 <= delta <= len(head), 'pointer does not target retained prefix/body start')
                require(new == at + delta, 'relative pointer displacement differs')
                require(span(parent, off, 4) == struct.pack('<I', BASE + old), 'literal pointer preimage mismatch')
                apply(off, struct.pack('<I', BASE + new), 'display_pointer')
        for entry in local:
            at, capacity = number(entry['addr']), number(entry['capacity'])
            original = read(parent, at, 'jp', capacity)
            require(original.status == 'OK' and len(original.raw) == capacity, 'local native stream capacity mismatch')
            payload = encode(entry['zh'], charmap)
            require(len(payload) == entry['new_bytes'] and len(payload) <= capacity, 'local text overflow')
            apply(at, payload + b'\xff' * (capacity - len(payload)), 'local_text')
    product = bytes(out)
    report = verify_changes(parent, product, writes, [])
    require(report['changed_bytes'] == spec['changed'] and report['write_ranges'] == spec['writes'], 'historical delta counts differ')
    require(sha(product) == spec['output'], 'output identity differs')
    return product, dict(**report, stage=stage, parent_sha256=spec['parent'], output_sha256=spec['output'],
        method='CONTROL_ORDER_PATCH' if stage == '557' else 'EXTERNAL_MANIFEST_ENCODING_AND_PREIMAGE_REPLAY',
        old_discovery_algorithm_replayed=False, new_resource_allocation=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage', choices=sorted(STAGES), required=True)
    ap.add_argument('--parent', type=Path, required=True)
    ap.add_argument('--manifest', type=Path, help='exact external historical manifest for558/559; never executed')
    ap.add_argument('--charmap', type=Path, help='one of the two pinned compatible local maps; not supplied')
    ap.add_argument('--compare', type=Path, help='optional retained child; read-only')
    args = ap.parse_args()
    spec = STAGES[args.stage]
    parent = Image.load(args.parent, spec['parent'], SIZE)
    inputs = [parent]
    raw = cmap = None
    if args.stage != '557':
        require(args.manifest is not None and args.charmap is not None, 'manifest and charmap required')
        manifest = Image.load(args.manifest, spec['manifest'])
        map_raw = args.charmap.read_bytes()
        require(sha(map_raw) in CHARMAP_SHAS, 'unrecognized charmap identity')
        map_image = Image.load(args.charmap, sha(map_raw))
        inputs += [manifest, map_image]
        raw, cmap = manifest.data, load_charmap(args.charmap)
    else:
        require(args.manifest is None and args.charmap is None, 'FIX557 needs neither manifest nor charmap')
    product, report = build(parent.data, args.stage, raw, cmap)
    if args.compare:
        child = Image.load(args.compare, spec['output'], SIZE)
        require(product == child.data, 'retained child bytes differ')
        inputs.append(child)
    for image in inputs:
        image.unchanged()
    print(json.dumps(dict(replay=report, compared_existing=args.compare is not None,
        inputs_unchanged=True, output_written=False, runtime_tested=False, complete_clean_rom_rebuild=False), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (GateError, EncodeError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
