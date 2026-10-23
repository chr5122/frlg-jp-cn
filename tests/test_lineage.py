import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frlg.lineage import endpoint, summarize
from frlg.lz77 import decompress
from frlg.merge import disjoint_merge
from frlg.rom import GateError, sha

ROOT = Path(__file__).resolve().parents[1]
A, B, C, D, E = (ch * 64 for ch in 'abcde')


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

    def test_multi_parent_ancestry_and_number_collision(self):
        rows = [dict(record_id='merge', manifest_sha256=E, body={
            'base': 'base.gba', 'base_sha256': A,
            'parents': [{'rom': 'FIX559.gba', 'sha256': B},
                        {'rom': 'FIX560-islands.gba', 'sha256': C}],
            'output': 'FIX561.gba', 'sha256': D})]
        for name, output in [('save', B), ('islands', C), ('other-FIX560', E)]:
            rows.append(dict(record_id=name, manifest_sha256=E,
                body={'base': 'base.gba', 'base_sha256': A,
                      'output': name + '.gba', 'sha256': output}))
        out = summarize(rows, {'FIX560-islands.gba': [C]}, D)
        self.assertEqual(out['target_declared_ancestry'], ['islands', 'merge', 'save'])
        self.assertEqual(out['target_unresolved_frontier'], [A])
        self.assertEqual(out['merge_records'], 1)
        deps = out['records'][0]['dependencies']
        self.assertEqual([d['role'] for d in deps], ['merge_base', 'branch', 'branch'])
        self.assertEqual(deps[2]['artifact_state'], 'FILE_SHA_MATCH')
        self.assertFalse(out['complete_rebuild_proven'])

    def test_incomplete_merge_never_becomes_base_only_edge(self):
        for parents in (None, {}, [], [{'rom': 'p.gba', 'sha256': B}],
                        [None, {'rom': 'p.gba', 'sha256': C}],
                        [{'rom': 'p.gba', 'sha256': B}, {'rom': 'q.gba'}]):
            with self.subTest(parents=parents):
                body = {'base': 'base.gba', 'base_sha256': A, 'parents': parents,
                        'output': 'out.gba', 'sha256': D}
                out = summarize([dict(record_id='merge', manifest_sha256=E, body=body)], target=D)
                self.assertEqual(out['records'][0]['state'], 'NEEDS_SCHEMA_OR_IDENTITY')
                self.assertEqual(out['target_declared_ancestry'], [])
                self.assertEqual(out['target_unresolved_frontier'], [D])

    def test_merge_aliases_conflicts_duplicates_and_output_cycle(self):
        bad_pairs = [
            [{'rom': 'p.gba', 'sha256': B, 'sha': C}, {'rom': 'q.gba', 'sha256': C}],
            [{'rom': 'p.gba', 'sha256': B}, {'rom': 'q.gba', 'sha256': B}],
            [{'rom': 'p.gba', 'sha256': A}, {'rom': 'q.gba', 'sha256': C}],
            [{'rom': 'same.gba', 'sha256': B}, {'rom': 'same.gba', 'sha256': C}],
            [{'rom': 'p.gba', 'sha256': D}, {'rom': 'q.gba', 'sha256': C}],
            [{'rom': 'p.gba', 'file': 'unbound.gba'}, {'rom': 'q.gba', 'sha256': C}],
        ]
        for parents in bad_pairs:
            with self.subTest(parents=parents):
                body = {'base': 'base.gba', 'base_sha256': A, 'parents': parents,
                        'output': 'out.gba', 'sha256': D}
                out = summarize([dict(record_id='merge', manifest_sha256=E, body=body)], target=D)
                self.assertEqual(out['records'][0]['state'], 'NEEDS_SCHEMA_OR_IDENTITY')

    def test_merge_does_not_export_unrelated_parent_payload(self):
        body = {'base': 'base.gba', 'base_sha256': A,
                'parents': [{'rom': 'left.gba', 'sha256': B, 'name': 'PRIVATE-LABEL'},
                            {'rom': 'right.gba', 'sha256': C, 'text': 'PRIVATE-TEXT'}],
                'output': 'out.gba', 'sha256': D}
        out = summarize([dict(record_id='merge', manifest_sha256=E, body=body)])
        self.assertEqual(out['records'][0]['state'], 'DECLARED_HASH_EDGE')
        self.assertNotIn('PRIVATE-', json.dumps(out))

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


class MergeTests(unittest.TestCase):
    def test_wrapper_success_counts_and_final_identity_with_synthetic_pins(self):
        spec = importlib.util.spec_from_file_location('merge561_fixture', ROOT / 'leafgreen/rebuild_merge561.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        base = bytes(32768)
        left = b'\x01' * 344 + bytes(32768 - 344)
        right = bytes(344) + b'\x02' * 30880 + bytes(1544)
        expected = b'\x01' * 344 + b'\x02' * 30880 + bytes(1544)
        # Unit fixtures only: do not claim these substitute for historical ROMs.
        original_pin = module.BASE_SHA
        with patch.multiple(module, SIZE=len(base), BASE_SHA=sha(base), SAVE_SHA=sha(left),
                            ISLANDS_SHA=sha(right), OUTPUT_SHA=sha(expected)):
            actual, report = module.build(base, left, right)
            self.assertEqual(actual, expected)
            self.assertEqual(report['changed_bytes'], 31224)
            with patch.object(module, 'OUTPUT_SHA', '0' * 64), self.assertRaises(GateError):
                module.build(base, left, right)
            short_left = b'\x01' * 343 + bytes(32768 - 343)
            with patch.object(module, 'SAVE_SHA', sha(short_left)), self.assertRaises(GateError):
                module.build(base, short_left, right)
        self.assertEqual(module.BASE_SHA, original_pin)

    def test_disjoint_union_and_inputs_unchanged(self):
        base, left, right = b'00000', b'10020', b'03004'
        product, report = disjoint_merge(base, left, right)
        self.assertEqual(product, b'13024')
        self.assertEqual(report, dict(left_changed_bytes=2, right_changed_bytes=2,
                                     overlap_bytes=0, changed_bytes=4))
        self.assertEqual((base, left, right), (b'00000', b'10020', b'03004'))
        self.assertEqual(disjoint_merge(base, base, base)[0], base)

    def test_reject_overlap_even_if_equal(self):
        for right in (b'100', b'200'):
            with self.subTest(right=right), self.assertRaises(GateError):
                disjoint_merge(b'000', b'100', right)

    def test_reject_size_and_mutable_inputs(self):
        for values in ((b'', b'', b''), (b'00', b'0', b'00'),
                       (bytearray(b'0'), b'0', b'0'), (b'0', b'0', None)):
            with self.subTest(values=values), self.assertRaises(GateError):
                disjoint_merge(*values)

    def test_pinned_merge_wrapper_and_readonly_cli(self):
        spec = importlib.util.spec_from_file_location('merge561', ROOT / 'leafgreen/rebuild_merge561.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(GateError):
            module.build(b'wrong base', b'', b'')
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / 'wrong.gba'
            parent.write_bytes(b'not a game')
            p = subprocess.run([sys.executable, '-B', str(ROOT / 'leafgreen/rebuild_merge561.py'),
                '--base', str(parent), '--save', str(parent), '--islands', str(parent)],
                capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn('identity mismatch', p.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [parent])
            self.assertEqual(parent.read_bytes(), b'not a game')


if __name__ == '__main__':
    unittest.main()
