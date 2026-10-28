"""Optional small-measurer CPU integration using synthetic metric callbacks."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared'))
from frlg.rendering import compile_components


def run(prefix: Path,arm_prefix='arm-none-eabi-',cc='cc'):
    with tempfile.TemporaryDirectory() as directory:
        tmp=Path(directory);obj,cb,exe=(tmp/name for name in ('callbacks.o','callbacks.bin','cpu'))
        commands=[
            [arm_prefix+'as','-mcpu=arm7tdmi','-mthumb',str(ROOT/'tests/fixtures/small_measure_callbacks.s'),'-o',str(obj)],
            [arm_prefix+'objcopy','-O','binary','--only-section=.text',str(obj),str(cb)],
            [cc,'-std=c11','-Wall','-Wextra','-I'+str(prefix/'include'),str(ROOT/'tests/small_measure_cpu.c'),
             '-L'+str(prefix/'lib'),'-lmgba','-Wl,-rpath,'+str(prefix/'lib'),'-o',str(exe)]]
        for command in commands:subprocess.run(command,check=True,capture_output=True,timeout=60)
        profiles=[]
        for role,profile in [('fr','firered-2.3-0111'),('lg','leafgreen-2.3-r89')]:
            raw=compile_components(profile,arm_prefix=arm_prefix)[0]['small_measure'];code=tmp/(role+'.bin');code.write_bytes(raw)
            args=[str(exe),role,str(code),str(cb)]
            result=subprocess.run(args+['good'],check=True,capture_output=True,text=True,timeout=60)
            report=json.loads(result.stdout);report['profile']=profile
            negative=subprocess.run(args+['bad'],capture_output=True,text=True,timeout=60)
            if negative.returncode==0 or 'width result' not in negative.stderr:
                raise ValueError('CPU did not reject the wrong glyph width')
            report['bad_width_rejected']=True;profiles.append(report)
        return dict(status='SYNTHETIC_CPU_PASS',profiles=profiles,game_or_save_input=False,hardware_certified=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mgba-prefix',required=True,type=Path);args=parser.parse_args()
    try:print(json.dumps(run(args.mgba_prefix),indent=2))
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        detail=getattr(exc,'stderr',None)
        print(f'FAIL: {exc}\n{detail.decode() if isinstance(detail,bytes) else detail or ""}',file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
