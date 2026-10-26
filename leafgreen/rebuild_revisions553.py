"""Pinned FIX552->553 replay with an external private manifest and charmap.

No translations, charmap, ROM bytes or binary patch payloads are distributed.
The precise historical codec quirks are local to this wrapper; public RAW
bypass stays disabled. This is not the old edit-discovery/width algorithm.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from frlg.encode import encode, load_charmap, EncodeError
from frlg.rom import GateError, Image, sha, span, number, uint, BASE, verify_changes
from frlg.text import exact, read

SIZE=0x1000000
PARENT_SHA='e2988fb6007b8c752502d7bbc851b0cb329175af5c01326306031671e5696344'
OUTPUT_SHA='7c68b4391868e8bf83d0bc15154bea804a6a98d6b1cf9445bd27b53d40fcbaae'
MANIFEST_SHA='57855f080700288e31734c60c591b67c66ac44f78c716a129107eb660077886e'
CHARMAP_SHAS=frozenset({'3a50c6f6d93a3caefb382102cfe4a1217694617d6e7b04a0e435801f61234c8a',
    '464c5ab50700544e349c07217ef949d2ac7cf2566bbdf89737854bc4863fabd4'})
ENTRY_COUNT=13
CHANGED_BYTES=3498


def require(ok,label):
    if not ok:raise GateError(label)


def historical_encode(source: str, charmap):
    # The553 codec rounds each ellipsis run up to an even number of B0s.
    source=re.sub('…+',lambda m:'…' * ((len(m.group())+1)//2*2),source)
    source=source.replace('{FD01}','{PLAYER}').replace('{FD06}','{RIVAL}')
    # Only the one known extended control is allowed. Other RAW requests
    # continue to be rejected by the shared encoder, not interpreted.
    pieces=source.split('{RAW:FC0B5601}')
    payload=b'\xfc\x0b\x56\x01'.join(encode(p,charmap,require_end=False) for p in pieces)+b'\xff'
    require(exact(payload,'cn').status=='OK','historical encoded stream malformed')
    return payload


def build(parent: bytes, manifest_raw: bytes, charmap):
    require(type(parent) is bytes and len(parent)==SIZE and sha(parent)==PARENT_SHA,'unexpected parent identity or size')
    require(type(manifest_raw) is bytes and sha(manifest_raw)==MANIFEST_SHA,'manifest identity mismatch')
    body=json.loads(manifest_raw)
    require(body['fix']==553 and body['sha256']==OUTPUT_SHA and len(body['entries'])==ENTRY_COUNT,'manifest stage/output/count differs')
    out,writes=bytearray(parent),[]
    def apply(at,payload,purpose):
        before=span(parent,at,len(payload))
        writes.append(dict(offset=at,before_hex=before.hex(),after_hex=payload.hex(),purpose=purpose))
        out[at:at+len(payload)]=payload
    for entry in body['entries']:
        source,target=number(entry['old_stream']),number(entry['new_stream'])
        old=historical_encode(entry['old'],charmap)
        actual=read(parent,source,'cn',len(old))
        require(actual.status=='OK' and actual.raw==old,'full old text differs from live parent')
        new=historical_encode(entry['new'],charmap)
        require(len(new)==entry['bytes'] and target%4==0,'new length/alignment differs')
        require(0xE372B8<=target and target+len(new)<=0xE3805C,'target outside historical553 window')
        # The old builder required the text plus four look-ahead bytes FF.
        require(span(parent,target,len(new)+4)==b'\xff'*(len(new)+4),'historical text/guard window not FF')
        require(bool(entry['slots']),'entry has no live references')
        apply(target,new,'new_pool')
        for slot in entry['slots']:
            at=number(slot)
            require(uint(parent,at)==BASE+source,'live pointer preimage differs')
            apply(at,struct.pack('<I',BASE+target),'display_pointer')
    product=bytes(out)
    report=verify_changes(parent,product,writes,[])
    require(report['changed_bytes']==CHANGED_BYTES,'historical delta count differs')
    require(sha(product)==OUTPUT_SHA,'output identity differs')
    return product,dict(**report,parent_sha256=PARENT_SHA,output_sha256=OUTPUT_SHA,entries=ENTRY_COUNT,
        method='EXTERNAL_MANIFEST_REENCODING_WITH_FULL_OLD_TEXT_AND_POINTER_CHECKS',
        manifest_discovery_or_width_checks_replayed=False,runtime_tested=False)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--parent',required=True,type=Path)
    ap.add_argument('--manifest',required=True,type=Path)
    ap.add_argument('--charmap',required=True,type=Path)
    ap.add_argument('--compare',type=Path)
    args=ap.parse_args()
    parent=Image.load(args.parent,PARENT_SHA,SIZE)
    manifest=Image.load(args.manifest,MANIFEST_SHA)
    raw=args.charmap.read_bytes();require(sha(raw) in CHARMAP_SHAS,'unrecognized charmap identity')
    mapping=Image.load(args.charmap,sha(raw));cmap=load_charmap(args.charmap)
    product,report=build(parent.data,manifest.data,cmap)
    inputs=[parent,manifest,mapping]
    if args.compare:
        child=Image.load(args.compare,OUTPUT_SHA,SIZE)
        require(child.data==product,'independent retained child differs');inputs.append(child)
    for image in inputs:image.unchanged()
    print(json.dumps(dict(replay=report,compared_existing=args.compare is not None,inputs_unchanged=True,
        output_written=False,complete_clean_rom_rebuild=False),indent=2))


if __name__=='__main__':
    try:main()
    except (GateError,EncodeError,OSError,KeyError,ValueError,TypeError) as exc:
        print(f'FAIL: {exc}',file=sys.stderr);sys.exit(1)
