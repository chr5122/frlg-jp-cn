"""Synthetic integration of current summary-controls wrapper and measurer."""
from __future__ import annotations
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared'))
from frlg.rendering import compile_components

def run(prefix:Path,arm_prefix='arm-none-eabi-',cc='cc'):
    with tempfile.TemporaryDirectory() as directory:
        tmp=Path(directory);obj,cb,exe=(tmp/n for n in ['callbacks.o','callbacks.bin','cpu'])
        commands=[
            [arm_prefix+'as','-mcpu=arm7tdmi','-mthumb',str(ROOT/'tests/fixtures/small_measure_callbacks.s'),'-o',str(obj)],
            [arm_prefix+'objcopy','-O','binary','--only-section=.text',str(obj),str(cb)],
            [cc,'-std=c11','-Wall','-Wextra','-I'+str(prefix/'include'),str(ROOT/'tests/summary_controls_cpu.c'),'-L'+str(prefix/'lib'),'-lmgba','-Wl,-rpath,'+str(prefix/'lib'),'-o',str(exe)]]
        for command in commands:subprocess.run(command,check=True,capture_output=True,timeout=60)
        reports=[]
        for role,profile in [('fr','firered-2.4-0112'),('lg','leafgreen-2.4-r90')]:
            parts,_=compile_components(profile,arm_prefix=arm_prefix)
            wrapper,measure=tmp/(role+'_wrapper.bin'),tmp/(role+'_measure.bin')
            wrapper.write_bytes(parts['summary_controls']);measure.write_bytes(parts['small_measure'])
            args=[str(exe),role,str(wrapper),str(measure),str(cb)]
            result=subprocess.run(args+['good'],capture_output=True,text=True,check=True,timeout=60);row=json.loads(result.stdout);row['profile']=profile
            for variant,expected in [('bad-width','alignment result'),('bad-tail','bounded native continuation')]:
                negative=subprocess.run(args+[variant],capture_output=True,text=True,timeout=60)
                if negative.returncode==0 or expected not in negative.stderr:raise ValueError('CPU did not reject '+variant)
                row[variant+'_rejected']=True
            reports.append(row)
        return dict(status='SYNTHETIC_CPU_PASS',profiles=reports,game_font_or_save_input=False,hardware_certified=False)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mgba-prefix',type=Path,required=True);args=parser.parse_args()
    try:print(json.dumps(run(args.mgba_prefix),indent=2))
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        detail=getattr(exc,'stderr',None);print(f'FAIL: {exc}\n{detail.decode() if isinstance(detail,bytes) else detail or ""}',file=sys.stderr);return 1
    return 0
if __name__=='__main__':sys.exit(main())
