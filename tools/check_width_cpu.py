"""Optional generated-memory CPU test; stops before every native continuation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"shared"))
from frlg.rendering import compile_components


def run(prefix: Path, arm_prefix="arm-none-eabi-", cc="cc"):
    with tempfile.TemporaryDirectory() as directory:
        temp=Path(directory)
        executable=temp/"width_cpu"
        subprocess.run([cc,"-std=c11","-Wall","-Wextra","-I"+str(prefix/"include"),
            str(ROOT/"tests/width_cpu.c"),"-L"+str(prefix/"lib"),"-lmgba",
            "-Wl,-rpath,"+str(prefix/"lib"),"-o",str(executable)],
            check=True,capture_output=True,timeout=60)
        reports=[]
        for game,profile in (("fr","firered-2.3-0111"),("lg","leafgreen-2.3-r89")):
            parts,_=compile_components(profile,arm_prefix=arm_prefix)
            scanner,alias=temp/"scanners.bin",temp/"alias.bin"
            scanner.write_bytes(parts["scanners"])
            alias.write_bytes(parts.get("width_alias",b""))
            command=[str(executable),game,str(scanner),str(alias)]
            result=subprocess.run(command,check=True,capture_output=True,text=True,timeout=60)
            report=json.loads(result.stdout)
            # Break only the real alias width, bypassing compilation-hash gates.
            raw=bytearray(parts["width_alias"] if game=="fr" else parts["scanners"])
            at=0x1A if game=="fr" else 0x16A
            if raw[at:at+2]!=bytes.fromhex("0c20"):raise ValueError("negative mutation preimage")
            raw[at]=11
            (alias if game=="fr" else scanner).write_bytes(raw)
            negative=subprocess.run(command,capture_output=True,text=True,timeout=60)
            if negative.returncode==0 or "width accumulator" not in negative.stderr:
                raise ValueError("CPU did not reject incorrect alias width")
            report["incorrect_width_negative_rejected"]=True
            reports.append(report)
        return dict(reports=reports,scope="CPU_ONLY_NO_NATIVE_CONTINUATIONS",hardware_certified=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mgba-prefix",type=Path,required=True)
    args=parser.parse_args()
    try:print(json.dumps(run(args.mgba_prefix),indent=2))
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        stderr=getattr(exc,"stderr",b"")
        print(f"FAIL: {exc}\n{stderr.decode() if isinstance(stderr,bytes) else stderr}",file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":sys.exit(main())
