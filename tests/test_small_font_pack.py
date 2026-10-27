import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from frlg.encode import encode, load_charmap
from frlg.font_pack import build_font
from frlg.font_pages import MAX_GID, PAGE_SPAN
from frlg.glyph_codec import decode_tile
from frlg.rom import GateError, sha
from frlg.small_font_pack import build_small_font

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build_small_font', ROOT/'tools/build_small_font.py')
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


def fixture():
    pixels = [[0] * 16 for _ in range(16)]
    for x, y, v in ((0, 0, 1), (9, 1, 2), (2, 8, 2), (9, 12, 1)):
        pixels[y][x] = v
    return dict(schema=1, source='Independently drawn test pixels, MIT',
                glyphs=[dict(unicode='中', glyph_id=0x100, pixels=pixels, width=10)])


def lookup():
    return bytes(sum((((v >> (2 * (3 - i))) & 3) % 3) * 3 ** (3 - i)
                     for i in range(4)) for v in range(256))


class SmallFontTests(unittest.TestCase):
    def test_four_contiguous_tiles_and_width_table(self):
        doc = fixture()
        artifacts, report = build_small_font(doc)
        page = artifacts['page_01.bin']
        tiles = [decode_tile(lookup(), page[i:i+16], 0) for i in (0, 16, 32, 48)]
        actual = [a+b for a,b in zip(tiles[0], tiles[1])] + [a+b for a,b in zip(tiles[2], tiles[3])]
        self.assertEqual(actual, doc['glyphs'][0]['pixels'])
        self.assertEqual(len(page), PAGE_SPAN)
        self.assertEqual(page[64:128], b'\xff' * 64)
        self.assertEqual(len(artifacts['widths.bin']), MAX_GID + 1)
        self.assertEqual(artifacts['widths.bin'][0x100], 10)
        self.assertEqual(artifacts['widths.bin'][0x101], 0)
        self.assertEqual(report['normal_charmap'], 'UNVERIFIED')
        self.assertFalse(report['rom_installed'])
        self.assertEqual(report['runtime'], 'UNOBSERVED')
        self.assertNotIn('source', report)

    def test_cross_page_ids_and_deterministic_order(self):
        doc = fixture()
        doc['glyphs'] = []
        for index, gid in enumerate((0, 7, 8, 255, 256, MAX_GID)):
            item = copy.deepcopy(fixture()['glyphs'][0])
            item.update(unicode=chr(0x4E00+index), glyph_id=gid, width=index+10)
            doc['glyphs'].append(item)
        artifacts, report = build_small_font(doc)
        doc['glyphs'].reverse()
        self.assertEqual(build_small_font(doc), (artifacts, report))
        self.assertEqual(report['pages'], [0, 1, 10])
        for item in doc['glyphs']:
            gid = item['glyph_id']
            page = artifacts[f'page_{gid >> 8:02X}.bin']
            self.assertEqual(page[(gid & 255)*64:(gid & 255)*64+2], b'\x00\x40')
            self.assertEqual(artifacts['widths.bin'][gid], item['width'])

    def test_pairing_accepts_only_same_characters_and_ids(self):
        normal = fixture()
        for item in normal['glyphs']:
            item.pop('width')
            item['pixels'][12][9] = 0  # normal input uses a 12x12 canvas
        artifacts, _ = build_font(normal)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'charmap.csv'
            path.write_bytes(artifacts['charmap.csv'])
            cmap = load_charmap(path)
            small, report = build_small_font(fixture(), cmap)
            self.assertEqual(report['normal_charmap'], 'MATCHED')
            self.assertEqual(small['charmap.csv'], artifacts['charmap.csv'])
            self.assertEqual(encode('中', cmap), bytes.fromhex('f70100ff'))
            for invalid in ({}, {'中': {'_gid': 0x101}}, {'文': {'_gid': 0x100}},
                            {'中': {'_gid': True}}, {'中': {}}, 'bad'):
                with self.subTest(invalid=invalid), self.assertRaises(GateError):
                    build_small_font(fixture(), invalid)

    def test_reject_clipping_width_and_bad_input(self):
        for x, y, value, width in ((10, 0, 1, 10), (0, 13, 1, 16), (0, 0, True, 10),
                                   (0, 0, 3, 10), (0, 0, 1, 0)):
            doc = fixture()
            doc['glyphs'][0]['pixels'][y][x] = value
            doc['glyphs'][0]['width'] = width
            with self.subTest(x=x,y=y,value=value,width=width), self.assertRaises(GateError):
                build_small_font(doc)
        for width in (True, -1, 17, 10.0, '10'):
            doc = fixture(); doc['glyphs'][0]['width'] = width
            with self.subTest(width=width), self.assertRaises(GateError):
                build_small_font(doc)
        doc = fixture(); doc['glyphs'][0]['pixels'] = [[0]*16 for _ in range(16)]
        doc['glyphs'][0]['width'] = 0
        self.assertEqual(build_small_font(doc)[0]['widths.bin'][0x100], 0)
        doc = fixture(); doc['glyphs'].append(copy.deepcopy(doc['glyphs'][0]))
        with self.assertRaises(GateError): build_small_font(doc)

    def test_cli_pairing_dry_run_readback_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory); source = tmp/'small.json'; normal = tmp/'normal.csv'; out = tmp/'font'
            source.write_text(json.dumps(fixture()), encoding='utf8')
            normal.write_text('unicode,glyph_id,status\n中,0x0100,allocated\n', encoding='utf8')
            before = (source.read_bytes(), normal.read_bytes())
            self.assertEqual(CLI.run(source, normal)['normal_charmap'], 'MATCHED')
            report = CLI.run(source, normal, out)
            self.assertTrue(report['written'])
            for name, info in report['artifacts'].items():
                self.assertEqual(sha((out/name).read_bytes()), info['sha256'])
            self.assertEqual(json.loads((out/'manifest.json').read_text()), report)
            with self.assertRaises(FileExistsError): CLI.run(source, normal, out)
            self.assertEqual((source.read_bytes(), normal.read_bytes()), before)
            normal.write_text('unicode,glyph_id,status\n中,0x0101,allocated\n', encoding='utf8')
            bad = tmp/'invalid'
            command = [sys.executable, '-B', str(ROOT/'tools/build_small_font.py'),
                       '--glyphs', str(source), '--normal-charmap', str(normal), '--output-dir', str(bad)]
            result = subprocess.run(command, cwd=directory, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('match exactly', result.stderr)
            self.assertFalse(bad.exists())

    def test_cli_duplicate_json_and_outside_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory); source = tmp/'small.json'; out = tmp/'new'
            source.write_text(json.dumps(fixture()), encoding='utf8')
            command = [sys.executable, '-B', str(ROOT/'tools/build_small_font.py'), '--glyphs', str(source)]
            result = subprocess.run(command + ['--output-dir', str(out)], cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['normal_charmap'], 'UNVERIFIED')
            source.write_text('{"schema":1,"schema":1}', encoding='utf8')
            result = subprocess.run(command, cwd=directory, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('duplicate JSON field', result.stderr)

    def test_generated_pages_execute_with_production_small_decoder(self):
        prefix = Path(os.environ.get('FRLG_MGBA_PREFIX', '/opt/homebrew'))
        if (not (prefix/'include/mgba/core/core.h').is_file() or not shutil.which('cc') or
                not any((prefix/'lib').glob('libmgba*')) or
                not all(shutil.which('arm-none-eabi-'+n) for n in ('as','ld','objcopy'))):
            self.skipTest('optional local mGBA development files/GNU Arm/cc unavailable')
        spec = importlib.util.spec_from_file_location('small_cpu', ROOT/'tools/check_small_font_cpu.py')
        tool = importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
        report = tool.run(prefix)
        self.assertEqual(report['glyph_cases'], 12)
        self.assertEqual(report['fallback_cases'], 4)
        self.assertTrue(report['ram_relocation_tested'])
        self.assertTrue(report['corrupt_tile_negative_rejected'])
        self.assertFalse(report['game_font_or_save_input'])
        self.assertFalse(report['hardware_certified'])


if __name__ == '__main__':
    unittest.main()
