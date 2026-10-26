"""Only synthetic token strings and fixture byte arrays; no game assets."""
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frlg.rom import GateError, sha

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('layout_replay',ROOT/'leafgreen/rebuild_layout555_556.py')
replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)


class LayoutReplayTests(unittest.TestCase):
    def test_historical554_regression_is_explicit_and_token_bounded(self):
        raw=bytes.fromhex('f7fafe fdab ab fa fe b0 ff')
        got,count=replay.historical554_layout(raw)
        self.assertEqual(got,bytes.fromhex('f7fafe fdab f70024 fa f70021 ff'))
        self.assertEqual(count,3)
        with self.assertRaises(GateError):replay.historical554_layout(b'\xab\xff')
        parent=bytearray(b'\xff'*replay.SIZE)
        first=b'\xf7\x00\x01'*21+b'\xab'*3+b'\xfa\xfe\xfe\xff'
        second=b'\xf7\x00\x01'*55+b'\xb0'*13+b'\xfa\xfe'+b'\xfe'*3+b'\xff'
        self.assertEqual((len(first),len(second)),(70,184))
        left=[0x1697D9,0x169818];right=[0x16A2C7,0x16A2D2,0x16A2DD,0x16A2E8,0x16A2F3,0x16A2FE]
        for slots,source,body in [(left,0xE372B8,first),(right,0xE37C64,second)]:
            parent[source:source+len(body)]=body
            for slot in slots:parent[slot:slot+4]=struct.pack('<I',0x08000000+source)
        expected=bytearray(parent)
        for slots,target,body in [(left,0xE3805C,first),(right,0xE380A8,second)]:
            new,n=replay.historical554_layout(body);expected[target:target+len(new)]=new
            for slot in slots:expected[slot:slot+4]=struct.pack('<I',0x08000000+target)
        with patch.dict(replay.STAGES,{'554':dict(parent=sha(parent),output=sha(expected))}):
            self.assertEqual(replay.build(bytes(parent),'554')[0],bytes(expected))
    def test_remove_only_token_boundary_wait_nl(self):
        raw=bytes.fromhex('f700fa fe fdfa fe fa fe ff')
        result,count=replay.without_redundant_nl(raw)
        self.assertEqual(result,bytes.fromhex('f700fa fe fdfa fe fa ff'))
        self.assertEqual(count,1)
        self.assertEqual(replay.without_redundant_nl(b'\xff'),(b'\xff',0))

    def test_native_punct_only_private_tokens(self):
        raw=bytes.fromhex('f70021 f70024 f7006a f70037 f70049 fd21 fc0b2100 ffff')
        # Final parameter-like FF bytes are not a valid extra terminator.
        with self.assertRaises(GateError):replay.native_punctuation(raw)
        raw=raw[:-1]
        got,count=replay.native_punctuation(raw)
        self.assertEqual(got,bytes.fromhex('b0 ab ac ad f70049 fd21 fc0b2100 ff'))
        self.assertEqual(count,4)

    def test_no_substring_replacement_inside_glyph_parameter(self):
        raw=bytes.fromhex('f7fafe fdfa fe ff')
        self.assertEqual(replay.without_redundant_nl(raw),(raw,0))

    def test_malformed_streams_rejected(self):
        for raw in [b'',b'\xf7\x00',b'\xfc\xff\xff',b'\xff\x01']:
            for fn in [replay.without_redundant_nl,replay.native_punctuation]:
                with self.subTest(raw=raw,fn=fn),self.assertRaises(GateError):fn(raw)

    def fixture556(self):
        p=bytearray(b'\xff'*replay.SIZE)
        a=(b'\xf7\x00\x01'*21)+b'\xf7\x00\x24'*3+b'\xfe\xfe\xff'
        b=(b'\xf7\x00\x01'*55)+b'\xf7\x00\x21'*13+b'\xfe'*4+b'\xff'
        self.assertEqual((len(a),len(b)),(75,209))
        p[0xE3805C:0xE3805C+75]=a;p[0xE380A8:0xE380A8+209]=b
        left=[0x1697D9,0x169818];right=[0x16A2C7,0x16A2D2,0x16A2DD,0x16A2E8,0x16A2F3,0x16A2FE]
        for slots,target in [(left,0xE3805C),(right,0xE380A8)]:
            for slot in slots:p[slot:slot+4]=struct.pack('<I',0x08000000+target)
        e=bytearray(p)
        for slots,source,target,raw in [(left,0xE3805C,0xE38280,a),(right,0xE380A8,0xE382C8,b)]:
            new,n=replay.native_punctuation(raw);e[target:target+len(new)]=new
            for slot in slots:e[slot:slot+4]=struct.pack('<I',0x08000000+target)
        return bytes(p),bytes(e)

    def run_fixture(self,p,e):
        with patch.dict(replay.STAGES,{'556':dict(parent=sha(p),output=sha(e))}):
            return replay.build(p,'556')

    def test_full_fixture_and_pointer_preimages(self):
        p,e=self.fixture556();got,report=self.run_fixture(p,e)
        self.assertEqual(got,e);self.assertEqual(report['write_ranges'],10)
        bad=bytearray(p);bad[0x169818]^=1
        with self.assertRaises(GateError):self.run_fixture(bytes(bad),e)
        # The555 production branch also gets a complete synthetic fixture.
        parent=bytearray(b'\xff'*replay.SIZE)
        raw=b'\xf7\x00\x01'*56+b'\xfd\x01\xfe\xfa\xfe\xb0\xb0\xff'
        self.assertEqual(len(raw),176)
        payload,n=replay.without_redundant_nl(raw);self.assertEqual(n,1)
        parent[0xDC9930:0xDC9930+176]=raw
        parent[0xB486C4:0xB486C4+175]=payload
        parent[0x18FA6D:0x18FA6D+4]=struct.pack('<I',0x08DC9930)
        expected=bytearray(parent);expected[0xE38180:0xE38180+175]=payload
        expected[0x18FA6D:0x18FA6D+4]=struct.pack('<I',0x08E38180)
        with patch.dict(replay.STAGES,{'555':dict(parent=sha(parent),output=sha(expected))}):
            self.assertEqual(replay.build(bytes(parent),'555')[0],bytes(expected))

    def test_pool_nonff_token_count_and_final_sha_rejected(self):
        p,e=self.fixture556()
        for at in [0xE38280,0xE382C8,0xE3805C+21*3]:
            bad=bytearray(p);bad[at]=0
            with self.subTest(at=at),self.assertRaises(GateError):self.run_fixture(bytes(bad),e)
        wrong=bytearray(e);wrong[0x10]^=1
        with self.assertRaises(GateError):self.run_fixture(p,bytes(wrong))

    def test_real_input_identity_rejected_without_writes(self):
        for stage in replay.STAGES:
            with self.assertRaises(GateError):replay.build(b'not a game',stage)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fixture.gba';p.write_bytes(b'not a game')
            q=subprocess.run([sys.executable,'-B',str(ROOT/'leafgreen/rebuild_layout555_556.py'),
                '--stage','555','--parent',str(p)],capture_output=True,text=True)
            self.assertNotEqual(q.returncode,0);self.assertIn('identity mismatch',q.stderr)
            self.assertEqual(list(Path(tmp).iterdir()),[p])


if __name__=='__main__':unittest.main()
