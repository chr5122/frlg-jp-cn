import csv
import importlib.util
import itertools
import json
import tempfile
import unittest
from pathlib import Path

from frlg import encode, font_pages, glyph_codec
from frlg.rom import GateError

ROOT = Path(__file__).resolve().parents[1]


class EncodeTests(unittest.TestCase):
    def setUp(self):
        self.cmap = {'中': {'_gid': 1}, '文': {'_gid': 0x1FF}}

    def test_unicode_native_tokens_and_embedded_ff(self):
        value = encode.encode('中文{NL}{PLAYER}！{END}', self.cmap)
        self.assertEqual(value, bytes.fromhex('f70001f701fffefd01abff'))
        self.assertEqual(encode.glyph_characters('中文{PLAYER}'), ['中', '文'])

    def test_end_handling(self):
        self.assertEqual(encode.encode('', {}), b'\xff')
        self.assertEqual(encode.encode('{END}', {}, require_end=False), b'\xff')
        self.assertEqual(encode.encode('中', self.cmap, require_end=False), bytes.fromhex('f70001'))
        for value in ('{END}中', '{END}{END}', '{END}{RAW:01}', '{RAW:ff}', '{RAW:fd}', '\n', '{UNKNOWN}', '{NL', '}'):
            with self.subTest(value=value), self.assertRaises(encode.EncodeError):
                encode.encode(value, self.cmap)

    def test_bad_gid_and_raw_glyph_collection(self):
        for gid in (-1, 0xB00, True):
            with self.subTest(gid=gid), self.assertRaises(encode.EncodeError):
                encode.encode('中', {'中': {'_gid': gid}})
        with self.assertRaises(encode.EncodeError):
            encode.glyph_characters('{RAW:f7}')

    def test_csv_gates(self):
        for rows in [ [('中', '0x01'), ('文', '0x01')], [('中', '0x01'), ('中', '0x02')], [('中文', '0x01')], [('中', '0xB00')] ]:
            with self.subTest(rows=rows), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / 'fixture.csv'
                with p.open('w', newline='', encoding='utf8') as f:
                    w = csv.writer(f)
                    w.writerow(['unicode', 'glyph_id', 'status'])
                    w.writerows((ch, gid, 'verified') for ch, gid in rows)
                with self.assertRaises(encode.EncodeError):
                    encode.load_charmap(p)


class FontPageTests(unittest.TestCase):
    def test_current_pages(self):
        self.assertEqual(font_pages.page_base_rom(9), 0xB64000)
        self.assertEqual(font_pages.page_base_rom(10), 0xB68000)
        self.assertEqual(len(font_pages.page_table_bytes()), 44)
        self.assertEqual(font_pages.glyph_slot_rom(0xA00), 0xB68000)

    def test_variants_cannot_reuse_later_reservations(self):
        for gid, variant in ((0x900, 'normal'), (0xA00, 'female'), (0x300, 'normal'), (0x300, 'female'), (0x300, 'bold'), (0, 'male'), (0xB00, 'male')):
            with self.subTest(gid=gid, variant=variant), self.assertRaises(ValueError):
                font_pages.glyph_slot_rom(gid, variant)


class CodecTests(unittest.TestCase):
    def test_all_legal_four_pixel_rows(self):
        # Synthetic lookup, not a ROM byte dump. Reserved source state3 unused.
        table = bytes(sum((((v >> (2 * (3 - i))) & 3) % 3) * 3 ** (3 - i) for i in range(4)) for v in range(256))
        for row in itertools.product(range(3), repeat=4):
            encoded = glyph_codec.encode_row(row)
            self.assertEqual(glyph_codec.decode_source_byte(table, encoded, 0), list(row))

    def test_tile_order_and_rejections(self):
        canvas = [[0] * 8 for _ in range(8)]
        canvas[0][0] = 1
        self.assertEqual(glyph_codec.encode_tile(canvas)[:2], b'\x00\x40')
        for row in ([0] * 3, [0, 0, 0, 3]):
            with self.subTest(row=row), self.assertRaises(GateError):
                glyph_codec.encode_row(row)
        with self.assertRaises(GateError):
            glyph_codec.encode_tile(canvas, 1, 0)
        with self.assertRaises(GateError):
            glyph_codec.decode_tile(b'', b'\x00' * 15)


class OriginDemoTests(unittest.TestCase):
    def test_demo_never_accepts_an_unpinned_input(self):
        spec = importlib.util.spec_from_file_location('first_glyph', ROOT / 'leafgreen/experiments/first_glyph.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(GateError):
            module.patch(b'not a ROM')
        p = module.pixels()
        self.assertEqual((len(p), len(p[0])), (16, 16))
        self.assertTrue(all(not any(row) for row in p[12:]))

    def test_machine_plan_keeps_full_build_incomplete(self):
        d = json.loads((ROOT / 'docs/BUILD_CHAIN.json').read_text(encoding='utf8'))
        self.assertFalse(d['complete_original_to_release_rebuild'])
        self.assertTrue(any(s['status'] == 'BUILD_LINEAGE_GAP' for s in d['stages']))
        evidence = json.loads((ROOT / 'docs/LEAFGREEN_ORIGIN_EVIDENCE.json').read_text(encoding='utf8'))
        self.assertFalse(evidence['complete_clean_rom_to_release_chain_verified'])
        self.assertFalse(evidence['payloads_exported'])


if __name__ == '__main__':
    unittest.main()
