"""Optional synthetic mGBA CPU matrix; requires local mGBA dev files and GNU Arm."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from firered.tm_names import compile_routes


def run(prefix: Path, arm_prefix="arm-none-eabi-", cc="cc"):
    with tempfile.TemporaryDirectory() as directory:
        temp=Path(directory)
        routes=temp/"routes.bin"
        payload=compile_routes(arm_prefix)
        routes.write_bytes(payload)
        obj,copy,tool=(temp/name for name in ("copy.o","copy.bin","tm_cpu"))
        commands=[
            [arm_prefix+"as","-mcpu=arm7tdmi","-mthumb",str(ROOT/"tests/fixtures/tm_copy.s"),"-o",str(obj)],
            [arm_prefix+"objcopy","-O","binary","--only-section=.text",str(obj),str(copy)],
            [cc,"-std=c11","-Wall","-Wextra","-I"+str(prefix/"include"),
             str(ROOT/"tests/tm_cpu.c"),"-L"+str(prefix/"lib"),"-lmgba",
             "-Wl,-rpath,"+str(prefix/"lib"),"-o",str(tool)]]
        for command in commands:subprocess.run(command,check=True,capture_output=True,timeout=60)
        result=subprocess.run([str(tool),str(routes),str(copy)],check=True,capture_output=True,text=True,timeout=60)
        report=json.loads(result.stdout)
        # Independent CPU rejection, not just the compiler's expected SHA gate.
        broken=bytearray(payload);broken[0]^=1
        bad=temp/"wrong_getter.bin";bad.write_bytes(broken)
        negative=subprocess.run([str(tool),str(bad),str(copy)],capture_output=True,text=True,timeout=60)
        if negative.returncode==0 or "getter returns own buffer" not in negative.stderr:
            raise ValueError("CPU did not reject the wrong getter offset")
        report["wrong_getter_negative_rejected"]=True
        return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mgba-prefix",type=Path,required=True)
    parser.add_argument("--arm-prefix",default="arm-none-eabi-")
    parser.add_argument("--cc",default="cc")
    args=parser.parse_args()
    try:print(json.dumps(run(args.mgba_prefix,args.arm_prefix,args.cc),indent=2))
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        detail=getattr(exc,"stderr",None)
        print(f"FAIL: {exc}\n{detail.decode() if isinstance(detail,bytes) else detail or ''}",file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":sys.exit(main())
