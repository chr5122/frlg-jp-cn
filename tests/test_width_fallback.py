import importlib.util
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from frlg.rom import GateError,sha

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('width_fallback',ROOT/'leafgreen/width_fallback.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)


class WidthFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=bytearray(b'\xff'*0x1000000);j=bytearray(p)
        p[M.AT:M.AT+4]=bytes.fromhex('295e0008')
        j[0x5E28:0x5E2C]=bytes.fromhex('825e0008')
        p[0x1F1344:0x1F1348]=bytes.fromhex('9d8c0008')
        c=bytearray(p);c[M.AT]=0x83
        cls.parent,cls.original,cls.child=bytes(p),bytes(j),bytes(c)
        cls.code=bytes(c[0xBC0000:0xBC0180])

    def fixture(self,parent=None,original=None):
        p=self.parent if parent is None else parent;j=self.original if original is None else original
        for ctx in (patch.object(M,'PARENT_SHA',sha(p)),patch.object(M,'ORIGINAL_SHA',sha(j)),
                    patch.object(M,'OUTPUT_SHA',sha(self.child)),patch.object(M,'_assemble',return_value=self.code)):
            ctx.start();self.addCleanup(ctx.stop)
        return p,j

    def test_one_byte_candidate_with_synthetic_identities(self):
        b,r=M.patch(*self.fixture())
        self.assertEqual(b,self.child);self.assertEqual(r['changed_bytes'],1)
        self.assertFalse(r['baseline_promoted']);self.assertFalse(r['uploaded'])

    def test_native_proof_preimages_and_save_slot(self):
        for source,at in [('p',M.AT),('j',0x5E28),('p',0x5E82),('p',0x1F1344)]:
            p,j=bytearray(self.parent),bytearray(self.original)
            (p if source=='p' else j)[at]^=1
            self.fixture(bytes(p),bytes(j))
            with self.subTest(source=source,at=hex(at)),self.assertRaises(GateError):M.patch(bytes(p),bytes(j))
            self.doCleanups()

    def test_source_and_final_identity_gates(self):
        inputs=self.fixture()
        with patch.object(M,'_assemble',return_value=b'wrong'):
            with self.assertRaisesRegex(GateError,'source match'):M.patch(*inputs)
        with patch.object(M,'OUTPUT_SHA','0'*64):
            with self.assertRaisesRegex(GateError,'output mismatch'):M.patch(*inputs)

    def test_wrong_real_inputs_fail_before_compiler(self):
        with patch.object(M,'_assemble') as compile:
            with self.assertRaises(GateError):M.patch(b'wrong',b'wrong')
            compile.assert_not_called()

    def test_cli_rejects_wrong_rom_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'wrong.gba';p.write_bytes(b'wrong');o=Path(d)/'new.gba'
            r=subprocess.run([sys.executable,'-B',str(ROOT/'leafgreen/width_fallback.py'),
                '--parent',str(p),'--original',str(p),'--output',str(o)],cwd=d,capture_output=True)
            self.assertNotEqual(r.returncode,0);self.assertFalse(o.exists());self.assertEqual(p.read_bytes(),b'wrong')

    def test_cli_fixture_dry_run_new_output_and_no_overwrite(self):
        self.fixture()
        with tempfile.TemporaryDirectory() as d:
            p,j,o=(Path(d)/name for name in ('parent.gba','original.gba','new.gba'))
            p.write_bytes(self.parent);j.write_bytes(self.original)
            args=['width_fallback.py','--parent',str(p),'--original',str(j)]
            with patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(M.main(),0)
            self.assertFalse(o.exists())
            with patch.object(sys,'argv',args+['--output',str(o)]),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(M.main(),0)
            self.assertEqual(o.read_bytes(),self.child)
            with patch.object(sys,'argv',args+['--output',str(o)]),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(M.main(),1)
            self.assertEqual(p.read_bytes(),self.parent);self.assertEqual(j.read_bytes(),self.original)
            self.assertEqual(o.read_bytes(),self.child)
