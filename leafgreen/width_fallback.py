"""Pinned one-byte R89 fallback repair. Candidate only, never promote or upload."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared'))
from frlg import font_pages
from frlg.patching import PROFILES
from frlg.rendering import PROFILES as RENDER_PROFILES, _assemble
from frlg.rom import GateError,Image,sha,uint,verify_changes

PARENT_SHA=RENDER_PROFILES['leafgreen-2.3-r89']['sha256']
ORIGINAL_SHA=PROFILES['leafgreen-jp-rev0']['sha256']
OUTPUT_SHA='b6648dd18161de6aae734f17923617eea24ccef2175f2446b942df49c6db5be6'
AT=0xBC010C


def patch(parent: bytes, original: bytes, *, arm_prefix='arm-none-eabi-'):
    if len(parent)!=0x1000000 or sha(parent)!=PARENT_SHA:raise GateError('requires exact R89')
    if len(original)!=0x1000000 or sha(original)!=ORIGINAL_SHA:raise GateError('requires exact Japanese BPGJ Rev0')
    native=uint(original,0x5E28)
    if native!=0x08005E82 or uint(parent,AT)!=0x08005E29:raise GateError('native table or fallback mismatch')
    start=native-0x08000000
    if parent[start:start+0x2C]!=original[start:start+0x2C]:raise GateError('native continuation mismatch')
    if uint(parent,0x1F1344)!=0x08008C9D:raise GateError('native slot1 mismatch')
    code=_assemble('leafgreen/patches/width_scanners.s',0xBC0000,
        dict(CN_FONT_MAX_GID=font_pages.MAX_GID,SMALL_FULL10=1,COPY1_FULL10=1,PRIVATE_FULL12=1,
             NATIVE_VARIABLE_FALLBACK=native|1),arm_prefix)
    b=bytearray(parent);b[AT:AT+4]=(native|1).to_bytes(4,'little');b=bytes(b)
    if len(code)!=384 or b[0xBC0000:0xBC0180]!=code:raise GateError('corrected source match failed')
    writes=[dict(offset=AT,before_hex='295e0008',after_hex='835e0008',purpose='existing_literal')]
    changes=verify_changes(parent,b,writes,[dict(start=0x1F1344,end=0x1F1348,name='native save slot1')])
    if changes['changed_bytes']!=1 or sha(b)!=OUTPUT_SHA:raise GateError('exact one-byte output mismatch')
    return b,dict(status='CANDIDATE_BYTE_SPECIFICATION_PASS',parent_sha256=PARENT_SHA,
        original_sha256=ORIGINAL_SHA,sha256=OUTPUT_SHA,changed_bytes=1,new_instructions=0,
        new_allocations=[],baseline_promoted=False,uploaded=False,hardware_certified=False,
        native_table_slot=0x5E28,native_handler=native,bx_target=native|1,
        source_compiled=True,local_runtime_claim='see VALIDATION.md; CLI itself performs no runtime test')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent',required=True,type=Path)
    parser.add_argument('--original',required=True,type=Path)
    parser.add_argument('--output',type=Path,help='optional NEW output file; default in-memory')
    args=parser.parse_args()
    try:
        parent=Image.load(args.parent,PARENT_SHA,0x1000000)
        original=Image.load(args.original,ORIGINAL_SHA,0x1000000)
        b,report=patch(parent.data,original.data)
        report['written']=False
        if args.output:
            with args.output.open('xb') as f:f.write(b)
            if sha(args.output.read_bytes())!=OUTPUT_SHA:raise GateError('readback mismatch')
            report['written']=True
        parent.unchanged();original.unchanged()
        print(json.dumps(report,indent=2))
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        print(f'FAIL: {exc}',file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
