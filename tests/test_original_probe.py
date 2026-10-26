import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frlg import original_probe as probe
from frlg.patching import PROFILES
from frlg.rom import GateError, sha, uint

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_original_probe", ROOT / "tools/build_original_probe.py")
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


def glyphs(gid=0x100):
    p = [[0]*16 for _ in range(16)]
    p[0][0] = p[11][11] = 1
    return dict(schema=1, source="Project-owned synthetic probe, MIT",
                glyphs=[dict(unicode="中", glyph_id=gid, pixels=p)])


class OriginalProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = "leafgreen-jp-rev0"
        cls.adapter = copy.deepcopy(probe.ADAPTERS[cls.game])
        parent = bytearray(b"\xff" * 0x1000000)
        parent[probe.HOOK:probe.HOOK+8] = probe.HOOK_BEFORE
        at = cls.adapter["slot"]
        parent[at:at+4] = cls.adapter["original_text"].to_bytes(4,"little")
        cls.parent = bytes(parent)
        cls.adapter["consumer_sha256"] = sha(cls.parent[cls.adapter["consumer_start"]:cls.adapter["consumer_end"]])
        cls.adapter["tile_sha256"] = sha(cls.parent[0x2F5C:0x2FE4])

    def setUp(self):
        contexts = [patch.dict(PROFILES, {self.game: dict(size=len(self.parent), sha256=sha(self.parent))}),
                    patch.dict(probe.ADAPTERS, {self.game: self.adapter}),
                    patch.object(probe, "compile_code", return_value=(b"\x70\x47", {}))]
        for context in contexts:
            result = context.start()
            self.addCleanup(context.stop)
        self.compiler = result

    def test_exact_writes_protected_data_and_full_reservation(self):
        result, report = probe.build(self.parent, self.game, glyphs(), "中中")
        self.assertEqual(result[probe.TEXT:probe.TEXT+11], bytes.fromhex("fc0604f70100f70100faff"))
        self.assertEqual(uint(result,self.adapter["slot"]), 0x08000000+probe.TEXT)
        self.assertEqual(uint(result,probe.HOOK+4), 0x08000000+probe.CODE+1)
        for lo,hi in ((0,0xC0),(0x6E000,0x92000),(0x1CEDD0,0x1F1118),(0x1F1344,0x1F1348)):
            self.assertEqual(result[lo:hi], self.parent[lo:hi])
        self.assertEqual(result[probe.POOL:probe.CODE], b"\xff"*16)
        self.assertEqual(result[probe.POOL_END-0x100:probe.POOL_END], b"\xff"*0x100)
        self.assertEqual(report["new_reservation"]["end"], probe.POOL_END)
        self.assertEqual(report["runtime"], "UNOBSERVED")
        self.assertFalse(report["complete_translation"])
        self.assertFalse(report["native_width_and_placeholder_hooks_installed"])

    def test_wrong_original_rejected_before_compiler(self):
        for parent, game in ((b"wrong",self.game),(self.parent,"unknown")):
            with self.subTest(game=game), self.assertRaises(GateError):
                probe.build(parent,game,glyphs(),"中")
        self.compiler.assert_not_called()

    def test_hook_slot_consumer_callback_pool_gates(self):
        cases = [(probe.HOOK,"dispatch"),(self.adapter["slot"],"literal"),
                 (self.adapter["consumer_start"],"consumer"),(0x2F5C,"tile decoder"),
                 (probe.POOL_END-1,"pool")]
        for at,message in cases:
            parent=bytearray(self.parent);parent[at]^=1;parent=bytes(parent)
            with patch.dict(PROFILES,{self.game:dict(size=len(parent),sha256=sha(parent))}):
                with self.subTest(at=at), self.assertRaisesRegex(GateError,message):
                    probe.build(parent,self.game,glyphs(),"中")
        self.compiler.assert_not_called()

    def test_text_limits_and_native_copy_ff_rejection(self):
        for line in ("", "中"*15, "文", "中。", "{PLAYER}", "中\n"):
            with self.subTest(line=line), self.assertRaises(GateError):
                probe.build(self.parent,self.game,glyphs(),line)
        for gid in (0xFF,0x1FF,0xAFF):
            with self.subTest(gid=gid), self.assertRaisesRegex(GateError,"StringCopy"):
                probe.build(self.parent,self.game,glyphs(gid),"中")
        self.compiler.assert_not_called()

    def test_layout_pages_and_missing_pages(self):
        result,report=probe.build(self.parent,self.game,glyphs(0xA00),"中"*14)
        self.assertEqual(report["maximum_ink_width"],168)
        self.assertEqual(uint(result,probe.CONFIG+4),11)
        blank=uint(result,probe.CONFIG+8)
        self.assertEqual(uint(result,probe.TABLE),blank)
        self.assertEqual(uint(result,probe.TABLE+10*4),0x08000000+probe.FONT)
        self.assertEqual(result[probe.TEXT+45:probe.TEXT+47],bytes.fromhex("faff"))

    def test_cli_dry_run_new_only_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent,source,out=(Path(tmp)/name for name in ("original.gba","glyphs.json","new.gba"))
            parent.write_bytes(self.parent);source.write_text(json.dumps(glyphs()),encoding="utf8")
            self.assertFalse(CLI.run(parent,self.game,source,"中")["written"])
            self.assertFalse(out.exists())
            report=CLI.run(parent,self.game,source,"中",out)
            self.assertTrue(report["written"])
            self.assertEqual(sha(out.read_bytes()),report["output_sha256"])
            self.assertEqual(parent.read_bytes(),self.parent)
            for target in (parent,source,out):
                with self.subTest(target=target), self.assertRaises(GateError):
                    CLI.run(parent,self.game,source,"中",target)

    def test_production_cli_wrong_input_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent,source,out=(Path(tmp)/name for name in ("original.gba","glyphs.json","new.gba"))
            parent.write_bytes(b"wrong");source.write_text(json.dumps(glyphs()),encoding="utf8")
            result=subprocess.run([sys.executable,"-B",str(ROOT/"tools/build_original_probe.py"),
                                   "--original",str(parent),"--game",self.game,"--glyphs",str(source),
                                   "--text","中","--output",str(out)],cwd=tmp,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("identity mismatch",result.stderr)
            self.assertFalse(out.exists())


class OriginalProbeAssemblyTests(unittest.TestCase):
    def test_real_compiler_and_adapter_bindings(self):
        if not all(shutil.which("arm-none-eabi-"+name) for name in ("as","ld","objcopy")):
            self.skipTest("optional GNU Arm binutils not installed")
        code,sources=probe.compile_code(13)
        self.assertEqual(len(code),244)
        # Actual template +4 is windowId; +5 is fontId. Old probe guard missed F7.
        self.assertEqual(code[4:6],bytes.fromhex("7079"))
        self.assertIn("shared/patches/cn_original_probe.s",sources)
        self.assertNotEqual(probe.ADAPTERS["firered-jp-rev0"]["consumer_sha256"],
                            probe.ADAPTERS["leafgreen-jp-rev0"]["consumer_sha256"])
