"""Synthetic fixtures only: no translations, native glyphs or ROM payloads."""
import copy
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frlg.rom import GateError, sha

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('manifest_replay', ROOT / 'leafgreen/rebuild_557_559.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


class ManifestReplayTests(unittest.TestCase):
    def fixture(self):
        parent = bytearray(b'\xff' * 128)
        parent[0:4] = struct.pack('<I', 0x08000021)
        parent[0x20:0x24] = b'\x00\x01\x02\xff'
        body = dict(name='FIX558', sha256='', entries=[dict(addr='0x20', new_stream='0x40', bytes=5,
            head='00', zh='甲', refs=[dict(literal_at='0x0', old='0x21', new='0x41')])])
        cmap = {'甲': {'_gid': 1}}
        expected = bytearray(parent)
        expected[0:4] = struct.pack('<I',0x08000041)
        expected[0x40:0x45] = b'\x00\xf7\x00\x01\xff'
        body['sha256'] = sha(expected)
        return bytes(parent), body, cmap, bytes(expected)

    def invoke(self, parent, body, cmap, expected, changed=5, writes=2):
        raw = json.dumps(body).encode()
        pin = dict(parent=sha(parent), output=sha(expected), changed=changed, writes=writes,
                   manifest=sha(raw), entries=len(body['entries']), local=len(body.get('local_entries', [])))
        with patch.object(replay, 'SIZE', len(parent)), patch.dict(replay.STAGES, {'558':pin}):
            return replay.build(parent,'558',raw,cmap)

    def test_exact_prefix_relative_pointer_and_inputs_unchanged(self):
        p,b,c,e = self.fixture()
        self.assertEqual(self.invoke(p,b,c,e)[0],e)
        self.assertEqual(p[0x40:0x45],b'\xff'*5)
        self.assertEqual(b['entries'][0]['refs'][0]['new'],'0x41')

    def test_local_capacity_and_padding(self):
        p,b,c,e = self.fixture()
        b['local_entries'] = [dict(addr='0x20',capacity=4,new_bytes=2,zh='！')]
        out = bytearray(e);out[0x20:0x24] = b'\xab\xff\xff\xff'
        b['sha256']=sha(out)
        self.assertEqual(self.invoke(p,b,c,bytes(out),changed=8,writes=3)[0],bytes(out))
        b['local_entries'][0]['capacity']=3
        with self.assertRaises(GateError): self.invoke(p,b,c,bytes(out),7,3)

    def test_legacy_placeholder_alias(self):
        p,b,c,e=self.fixture()
        b['entries'][0].update(zh='{FD02}',bytes=4)
        out=bytearray(e);out[0x40:0x45]=b'\x00\xfd\x02\xff\xff'
        b['sha256']=sha(out)
        self.assertEqual(self.invoke(p,b,c,bytes(out),changed=4)[0],bytes(out))

    def test_control_order_positive_and_no_resource_dependencies(self):
        p=bytearray(b'\xff'*replay.SIZE)
        p[0xE37E05:0xE37E08]=bytes.fromhex('fa ab fb')
        e=bytearray(p);e[0xE37E05:0xE37E08]=bytes.fromhex('ab fa fb')
        pin=dict(parent=sha(p),output=sha(e),changed=2,writes=1)
        with patch.dict(replay.STAGES,{'557':pin}):
            self.assertEqual(replay.build(bytes(p),'557')[0],bytes(e))
            with self.assertRaises(GateError):replay.build(bytes(p),'557',b'{}',{})

    def test_pointer_offset_and_preimage_rejected(self):
        for key,value in [('old','0x22'),('new','0x42')]:
            p,b,c,e=self.fixture();b['entries'][0]['refs'][0][key]=value
            with self.subTest(key=key),self.assertRaises(GateError):self.invoke(p,b,c,e)
        p,b,c,e=self.fixture();p=bytes(4)+p[4:]
        with self.assertRaises(GateError):self.invoke(p,b,c,e)

    def test_pool_overlap_nonff_and_bounds_rejected(self):
        p,b,c,e=self.fixture();changed=bytearray(p);changed[0x40]=0
        with self.assertRaises(GateError):self.invoke(bytes(changed),b,c,e)
        p,b,c,e=self.fixture();b['entries']*=2
        with self.assertRaises(GateError):self.invoke(p,b,c,e,writes=4)
        p,b,c,e=self.fixture();b['entries'][0]['new_stream']='0x1000'
        with self.assertRaises(GateError):self.invoke(p,b,c,e)

    def test_size_counts_final_identity_and_token_errors_rejected(self):
        p,b,c,e=self.fixture()
        for mutate in [lambda d:d['entries'][0].update(bytes=4),lambda d:d.update(sha256='0'*64),
                       lambda d:d['entries'][0].update(zh='{RAW:FF}')]:
            bad=copy.deepcopy(b);mutate(bad)
            with self.subTest(body=bad),self.assertRaises(ValueError):self.invoke(p,bad,c,e)
        with self.assertRaises(GateError):self.invoke(p,b,c,e,changed=6)
        with self.assertRaises(GateError):self.invoke(p,b,c,e,writes=3)

    def test_parent_and_manifest_gate_before_parsing(self):
        p,b,c,e=self.fixture();raw=json.dumps(b).encode()
        pin=dict(parent=sha(p),manifest=sha(raw))
        with patch.object(replay,'SIZE',len(p)),patch.dict(replay.STAGES,{'558':pin}):
            with self.assertRaises(GateError):replay.build(p[:-1],'558',raw,c)
            with self.assertRaises(GateError):replay.build(p,'558',b'{broken',c)
            with self.assertRaises(GateError):replay.build(bytearray(p),'558',raw,c)
        for stage in replay.STAGES:
            with self.assertRaises(GateError):replay.build(b'wrong parent',stage)

    def test_public_cli_rejects_wrong_input_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fixture.gba';p.write_bytes(b'not a game')
            q=subprocess.run([sys.executable,'-B',str(ROOT/'leafgreen/rebuild_557_559.py'),
                '--stage','557','--parent',str(p)],capture_output=True,text=True)
            self.assertNotEqual(q.returncode,0)
            self.assertIn('identity mismatch',q.stderr)
            self.assertEqual(list(Path(tmp).iterdir()),[p])
            self.assertEqual(p.read_bytes(),b'not a game')


if __name__=='__main__':unittest.main()
