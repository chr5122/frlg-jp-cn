import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from frlg.lineage import endpoint, summarize
from frlg.lz77 import decompress
from frlg.rom import GateError

ROOT = Path(__file__).resolve().parents[1]
A, B, C = 'a' * 64, 'b' * 64, 'c' * 64


class LineageTests(unittest.TestCase):
    def test_nested_and_flat_schemas(self):
        for d in ({'input_rom': {'path': 'parent.gba', 'sha256': A}},
                  {'baseline': 'parent.gba', 'baseline_sha256': A},
                  {'input_rom': 'parent.gba', 'base_sha256': A}):
            with self.subTest(d=d):
                self.assertEqual(endpoint(d, 'input')['sha256'], A)
                self.assertEqual(endpoint(d, 'input')['state'], 'DECLARED_IDENTITY')

    def test_no_filename_or_save_hash_inference(self):
        d = {'input': 'FIX100.gba', 'output': 'FIX101.gba', 'save_sha256': A, 'source_sha256': B}
        self.assertEqual(endpoint(d, 'input')['state'], 'MISSING_HASH')
        self.assertEqual(endpoint(d, 'output')['state'], 'MISSING_HASH')
        self.assertEqual(endpoint({'sha256': A}, 'output')['state'], 'MISSING_ENDPOINT')

    def test_conflicting_and_unbound_endpoints(self):
        with self.assertRaises(ValueError):
            endpoint({}, 'guess')
        self.assertEqual(endpoint({'input': 'x.gba', 'input_sha256': A, 'base_sha256': B}, 'input')['state'], 'AMBIGUOUS_HASH')
        d = {'input': {'path': 'x.gba', 'sha256': A}, 'base': 'y.gba'}
        self.assertEqual(endpoint(d, 'input')['state'], 'UNBOUND_ADDITIONAL_ENDPOINT')

    def test_artifact_path_drift_and_payload_exclusion(self):
        record = dict(record_id='fixture.json', manifest_sha256=C,
                      body={'input': 'same-name.gba', 'input_sha256': A,
                            'output': 'child.gba', 'sha256': B,
                            'cn_text': 'PRIVATE-FIXTURE-TEXT', 'sav': {'path': 'PRIVATE-FIXTURE-SAVE'}})
        d = summarize([record], {'same-name.gba': [C]}, B)
        self.assertEqual(d['records'][0]['input']['artifact_state'], 'PATH_NOW_DIFFERS_FROM_DECLARED_SHA')
        self.assertNotIn('PRIVATE-FIXTURE', json.dumps(d))
        self.assertFalse(d['complete_rebuild_proven'])

    def test_hash_ancestry_and_cycle_termination(self):
        rows = [dict(record_id=n, manifest_sha256=C, body={'input': 'p.gba', 'input_sha256': x,
                'output': 'c.gba', 'output_sha256': y}) for n, x, y in [('one', A, B), ('two', B, C), ('loop', C, C)]]
        self.assertEqual(summarize(rows, target=C)['target_declared_ancestry'], ['loop', 'one', 'two'])

    def test_cli_production_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'fixture_manifest.json').write_text(json.dumps({'input': 'x.gba', 'input_sha256': A,
                'output': 'y.gba', 'output_sha256': B, 'cn_text': 'DO-NOT-EXPORT'}), encoding='utf8')
            (root / 'bad_manifest.json').write_text('{broken', encoding='utf8')
            p = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/audit_build_lineage.py'),
                '--analysis', str(root), '--summary-only'], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            d = json.loads(p.stdout)
            self.assertEqual(d['scanned_files'], 2)
            self.assertEqual(len(d['json_errors']), 1)
            self.assertNotIn('DO-NOT-EXPORT', p.stdout)
            self.assertFalse(d['complete_rebuild_proven'])
            bad = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/audit_build_lineage.py'),
                '--analysis', str(root), '--target-sha256', 'not-a-sha'], capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)


class Lz77Tests(unittest.TestCase):
    def test_literals_and_overlapping_back_reference(self):
        self.assertEqual(decompress(bytes.fromhex('1003000000414243')), (b'ABC', 8))
        self.assertEqual(decompress(bytes.fromhex('1006000040412000')), (b'AAAAAA', 8))

    def test_reject_malformed_streams(self):
        for raw in ('11', '10000000', '10030000800000', '1004000040412000', '100300000041'):
            with self.subTest(raw=raw), self.assertRaises(GateError):
                decompress(bytes.fromhex(raw))
        with self.assertRaises(GateError):
            decompress(bytes.fromhex('1003000000414243'), 0, 2)


class TailBuilderTests(unittest.TestCase):
    def test_unpinned_parents_rejected(self):
        spec = importlib.util.spec_from_file_location('tail', ROOT / 'leafgreen/rebuild_1_0_tail.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(GateError):
            module.hint583(b'wrong parent', {})
        with self.assertRaises(GateError):
            module.title582(b'wrong parent', b'', b'')


if __name__ == '__main__':
    unittest.main()
