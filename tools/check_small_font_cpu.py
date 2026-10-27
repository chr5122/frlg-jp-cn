"""Optional generated-font CPU integration: no game, font or save input."""
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
from frlg.small_font_pack import build_small_font


def independent_tile(pixels,x,y):
    result=bytearray()
    for row in pixels[y:y+8]:
        left=sum(row[x+i] << (6-2*i) for i in range(4))
        right=sum(row[x+4+i] << (6-2*i) for i in range(4))
        result.extend((right,left))
    return bytes(result)


def run(prefix: Path, arm_prefix='arm-none-eabi-', cc='cc'):
    gids=(0,7,8,255,256,0xAFF)
    glyphs=[]
    for i,gid in enumerate(gids):
        pixels=[[0]*16 for _ in range(16)]
        for x,y,value in ((0,0,1),(9,1,2),(2,8,2),(9,12,1)):
            pixels[y][x]=value if i%2==0 else 3-value
        glyphs.append(dict(unicode=chr(0x4E00+i),glyph_id=gid,pixels=pixels,width=10+i))
    artifacts,_=build_small_font(dict(schema=1,source='Independent synthetic marks, MIT',glyphs=glyphs))
    expected=b''.join(independent_tile(g['pixels'],x,y) for g in glyphs
                      for x,y in ((0,0),(8,0),(0,8),(8,8)))
    with tempfile.TemporaryDirectory() as directory:
        tmp=Path(directory);pages=tmp/'pages';pages.mkdir()
        for name,data in artifacts.items():(pages/name).write_bytes(data)
        decoder=tmp/'decoder.bin';decoder.write_bytes(compile_components('leafgreen-2.3-r89',arm_prefix=arm_prefix)[0]['small'])
        expected_path=tmp/'expected.bin';expected_path.write_bytes(expected)
        obj,stub,exe=(tmp/name for name in ('tile.o','tile.bin','cpu'))
        commands=[
            [arm_prefix+'as','-mcpu=arm7tdmi','-mthumb',str(ROOT/'tests/fixtures/small_tile_copy.s'),'-o',str(obj)],
            [arm_prefix+'objcopy','-O','binary','--only-section=.text',str(obj),str(stub)],
            [cc,'-std=c11','-Wall','-Wextra','-I'+str(prefix/'include'),str(ROOT/'tests/small_font_cpu.c'),
             '-L'+str(prefix/'lib'),'-lmgba','-Wl,-rpath,'+str(prefix/'lib'),'-o',str(exe)]]
        for command in commands:subprocess.run(command,check=True,capture_output=True,timeout=60)
        cmd=[str(exe),str(decoder),str(stub),str(pages),str(expected_path)]
        result=subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=60)
        report=json.loads(result.stdout)
        page=pages/'page_00.bin';broken=bytearray(page.read_bytes());broken[0]^=1;page.write_bytes(broken)
        negative=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
        if negative.returncode==0 or 'tile bytes' not in negative.stderr:
            raise ValueError('CPU did not reject a corrupted font tile')
        report['corrupt_tile_negative_rejected']=True
        return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mgba-prefix',type=Path,required=True)
    args=parser.parse_args()
    try:print(json.dumps(run(args.mgba_prefix),indent=2))
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        detail=getattr(exc,'stderr',None)
        print(f'FAIL: {exc}\n{detail.decode() if isinstance(detail,bytes) else detail or ""}',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':sys.exit(main())
