"""Measure a caller-supplied one-line encoded stream using explicit widths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared'))
sys.path.insert(0,str(ROOT/'tools'))
from frlg.encode import load_charmap
from frlg.rom import GateError,sha
from frlg.small_measure import measure_small
from patch_rom import load_recipe


def table(path):
    if path is None:
        return {}
    data=load_recipe(path)
    if not isinstance(data,dict):raise GateError('width input must be a JSON object')
    result={}
    for key,value in data.items():
        try:index=int(key,0)
        except (ValueError,TypeError) as exc:raise GateError('invalid width index') from exc
        if not 0<=index<=255 or index in result:raise GateError('duplicate or out-of-range width index')
        if type(value) is not int or not 0<=value<=255:raise GateError('width must be an integer in 0..255')
        result[index]=value
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text-hex',required=True,help='complete CN token stream including FF')
    parser.add_argument('--widths',required=True,type=Path)
    parser.add_argument('--charmap',required=True,type=Path)
    parser.add_argument('--native-widths',type=Path)
    parser.add_argument('--icon-widths',type=Path)
    args=parser.parse_args()
    try:
        inputs=[x for x in (args.widths,args.charmap,args.native_widths,args.icon_widths) if x is not None]
        before=[sha(path.read_bytes()) for path in inputs]
        cmap=load_charmap(args.charmap)
        result=measure_small(bytes.fromhex(args.text_hex),args.widths.read_bytes(),
            {row['_gid'] for row in cmap.values()},table(args.native_widths),table(args.icon_widths))
        if any(sha(path.read_bytes())!=digest for path,digest in zip(inputs,before)):
            raise GateError('input changed during measurement')
        print(json.dumps(result,indent=2))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f'FAIL: {exc}',file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
