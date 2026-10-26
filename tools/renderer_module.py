"""Compile selected current renderer sources or verify a pinned release; no installer."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"shared"))
from frlg.rendering import PROFILES,compile_components,verify
from frlg.rom import GateError,Image,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("compile","verify"))
    parser.add_argument("--profile",choices=tuple(PROFILES),required=True)
    parser.add_argument("--rom",type=Path)
    parser.add_argument("--output-dir",type=Path,help="compile artifacts in a NEW directory only")
    parser.add_argument("--arm-prefix",default="arm-none-eabi-")
    args=parser.parse_args()
    if args.mode=="verify" and (not args.rom or args.output_dir):parser.error("verify needs --rom, never writes output")
    if args.mode=="compile" and args.rom:parser.error("compile does not read a game ROM")
    try:
        if args.mode=="verify":
            image=Image.load(args.rom,PROFILES[args.profile]["sha256"],0x1000000)
            report=verify(image.data,args.profile,arm_prefix=args.arm_prefix);image.unchanged()
        else:
            payloads,report=compile_components(args.profile,arm_prefix=args.arm_prefix)
            report["written"]=False
            if args.output_dir:
                args.output_dir.mkdir(exist_ok=False)
                for row in report["components"]:
                    target=args.output_dir/(row["name"]+".bin")
                    with target.open("xb") as handle:handle.write(payloads[row["name"]])
                    if sha(target.read_bytes())!=row["sha256"]:raise GateError("artifact readback mismatch")
                report["written"]=True
                with (args.output_dir/"manifest.json").open("x",encoding="utf8") as handle:json.dump(report,handle,indent=2)
        print(json.dumps(report,indent=2))
    except (GateError,OSError,ValueError,subprocess.SubprocessError) as exc:
        detail=getattr(exc,"stderr",None)
        print(f"FAIL: {exc}\n{detail.decode() if isinstance(detail,bytes) else detail or ''}",file=sys.stderr);return 1
    return 0


if __name__=="__main__":sys.exit(main())
