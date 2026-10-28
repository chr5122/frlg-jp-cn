import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from frlg.font_pages import MAX_GID
from frlg.rom import GateError
from frlg.small_measure import measure_small

ROOT=Path(__file__).resolve().parents[1]


class SmallMeasurementTests(unittest.TestCase):
    def setUp(self):
        b=bytearray(MAX_GID+1)
        for gid,width in ((0x100,10),(0x1FF,11),(0x92F,0),(0xAFF,12)):b[gid]=width
        self.widths=bytes(b)
        self.allocated={0x100,0x1FF,0x92F,0xAFF}
        self.native={0:4,1:5,2:6}
        self.icons={0:8,2:10}

    def run_width(self,encoded):
        return measure_small(bytes.fromhex(encoded),self.widths,self.allocated,self.native,self.icons)

    def test_meaningful_extent_and_pen_shift(self):
        cases=[('ff',0,0),('010000ff',5,13),('00010002ff',19,19),
               ('f70100ff',10,10),('f701ffff',11,11),('f7092fff',0,0),
               ('f80200ff',10,14),('01fc0d0202ff',8,8),('01fc0d1e00ff',5,34),
               ('f70afff800ff',20,20),('fc0d10f7010000ff',26,30),('02ff',6,6)]
        for encoded,extent,pen in cases:
            with self.subTest(encoded=encoded):
                actual=self.run_width(encoded)
                self.assertEqual((actual['extent'],actual['pen']),(extent,pen))
                self.assertEqual(actual['runtime'],'NOT_EXECUTED')

    def test_reject_unsupported_or_malformed_controls(self):
        for raw in ('','01','01ff00','f7ff','f800','fd02ff','f900ff','faff','fbff','feff',
                    'fc0602ff','fc99ff','f70b00ff','f70101ff'):
            with self.subTest(raw=raw),self.assertRaises(GateError):self.run_width(raw)
        with self.assertRaises(GateError):measure_small(b'\xff'*4097,self.widths,self.allocated,self.native,self.icons)

    def test_missing_widths_and_allocations_fail_closed(self):
        for raw in ('03ff','f803ff'):
            with self.subTest(raw=raw),self.assertRaises(GateError):self.run_width(raw)
        for widths in (b'',bytes([17])*(MAX_GID+1),bytearray(MAX_GID+1)):
            with self.subTest(widths=type(widths)),self.assertRaises(GateError):
                measure_small(b'\xff',widths,self.allocated,self.native,self.icons)
        for ids in ([],{True},{MAX_GID+1},{'256'}):
            with self.subTest(ids=ids),self.assertRaises(GateError):
                measure_small(b'\xff',self.widths,ids,self.native,self.icons)
        for mapping in ({1:True},{1:-1},{1:256}):
            with self.subTest(mapping=mapping),self.assertRaises(GateError):
                measure_small(b'\x01\xff',self.widths,self.allocated,mapping,self.icons)

    def test_cli_reuses_packer_output_and_rejects_missing_input(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp=Path(directory);widths=tmp/'widths.bin';cmap=tmp/'charmap.csv'
            widths.write_bytes(self.widths);cmap.write_text('unicode,glyph_id,status\n中,0x0100,allocated\n',encoding='utf8')
            inputs=(widths.read_bytes(),cmap.read_bytes())
            cmd=[sys.executable,'-B',str(ROOT/'tools/measure_small.py'),'--text-hex','f70100ff',
                 '--widths',str(widths),'--charmap',str(cmap)]
            result=subprocess.run(cmd,cwd=directory,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['extent'],10)
            self.assertEqual((widths.read_bytes(),cmap.read_bytes()),inputs)
            bad=subprocess.run(cmd[:3]+['--text-hex','01ff','--widths',str(widths),'--charmap',str(cmap)],
                               capture_output=True,text=True)
            self.assertNotEqual(bad.returncode,0)
            self.assertIn('missing native glyph width',bad.stderr)

    def test_synthetic_cpu_execution_with_both_profiles(self):
        prefix=Path(os.environ.get('FRLG_MGBA_PREFIX','/opt/homebrew'))
        if (not (prefix/'include/mgba/core/core.h').is_file() or not shutil.which('cc') or
                not any((prefix/'lib').glob('libmgba*')) or
                not all(shutil.which('arm-none-eabi-'+n) for n in ('as','ld','objcopy'))):
            self.skipTest('optional GNU Arm/cc/mGBA development files unavailable')
        spec=importlib.util.spec_from_file_location('check_small_measure_cpu',ROOT/'tools/check_small_measure_cpu.py')
        tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
        report=tool.run(prefix)
        self.assertEqual([x['cases'] for x in report['profiles']],[24,24])
        self.assertTrue(all(x['bad_width_rejected'] for x in report['profiles']))
        self.assertTrue(all(x['ram_relocation_tested'] for x in report['profiles']))
        self.assertFalse(report['game_or_save_input'])
        self.assertFalse(report['hardware_certified'])


if __name__=='__main__':unittest.main()
