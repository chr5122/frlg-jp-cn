import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frlg.name_slots import audit_names, pack_names
from frlg.rom import GateError, sha

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("tm_names",ROOT/"firered/tm_names.py")
TM=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(TM)


class NameSlotTests(unittest.TestCase):
    def setUp(self):
        self.cmap={"中":{"_gid":0x100},"文":{"_gid":0x101}}

    def test_lengths_and_roundtrip(self):
        table,report=pack_names(["中"*n for n in range(1,6)],self.cmap,count=5)
        self.assertEqual(len(table),80)
        self.assertEqual(report["max_bytes_including_end"],16)
        self.assertEqual(report["symbol_count_histogram"],{n:1 for n in range(1,6)})
        self.assertEqual(report,audit_names(table,0,5))
        self.assertEqual(report["translation_quality"],"NOT_REVIEWED")

    def test_padding_is_not_an_extra_name(self):
        data=bytes.fromhex("f70100ff")+b"\x55"*12
        self.assertEqual(audit_names(data,0,1)["max_bytes_including_end"],4)

    def test_reject_empty_controls_capacity_and_internal_ff(self):
        for names in ([""],["中"*6],["中{NL}"],["中{PLAYER}"],["{FONT_MALE}中"]):
            with self.subTest(names=names),self.assertRaises(GateError):
                pack_names(names,self.cmap,count=1)
        with self.assertRaisesRegex(GateError,"truncate"):
            pack_names(["中"],{"中":{"_gid":0x1FF}},count=1)
        for raw in (b"\xff"*16,b"\x01"*16,bytes.fromhex("fc99ff")+b"\0"*13,
                    bytes.fromhex("f70b00ff")+b"\0"*12):
            with self.subTest(raw=raw),self.assertRaises(GateError):audit_names(raw,0,1)

    def test_argument_and_extent_gates(self):
        for count,stride,offset in ((True,16,0),(1,True,0),(0,16,0),(2,16,0),(1,16,-1)):
            with self.subTest(count=count,stride=stride,offset=offset),self.assertRaises(GateError):
                audit_names(b"\x01\xff"+b"\0"*14,offset,count,stride)
        with self.assertRaises(GateError):pack_names(["中"],self.cmap,count=2)
        with self.assertRaises(GateError):pack_names([123],self.cmap,count=1)


class ProductionTMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data=bytearray(b"\xff"*0x1000000)
        table,_=pack_names(["中"]*355,{"中":{"_gid":0x100}},count=355)
        data[TM.TABLE:TM.TABLE+len(table)]=table
        for at,raw in TM.AFTER.items():data[at:at+len(bytes.fromhex(raw))]=bytes.fromhex(raw)
        data[0x11D8F4:0x11D900]=bytes.fromhex("004b18470194ed08c046c046")
        data[0x11CE60:0x11CE64]=(0x28D4).to_bytes(4,"little")
        for at,raw in ((0x11CDCC,"2901"),(0x11CEF8,"0904"),(0x11CEFE,"090b")):
            data[at:at+2]=bytes.fromhex(raw)
        cls.payload=b"\x70\x47"*48
        data[TM.CODE:TM.CODE+96]=cls.payload
        cls.data=bytes(data)
        cls.deps=[(at,n,sha(cls.data[at:at+n]),label) for at,n,_,label in TM.DEPENDENCIES]
        cls.table_sha=sha(table)

    def fixture(self,data=None):
        data=self.data if data is None else data
        contexts=[patch.dict(TM.RELEASES,{"fixture":sha(data)}),
                  patch.object(TM,"DEPENDENCIES",self.deps),
                  patch.object(TM,"TABLE_SHA",self.table_sha),
                  patch.object(TM,"compile_routes",return_value=self.payload)]
        for context in contexts:
            result=context.start();self.addCleanup(context.stop)
        return data

    def test_release_source_and_prerequisites(self):
        report=TM.verify_feature(self.fixture(),"fixture")
        self.assertEqual(report["names"]["entries"],355)
        self.assertEqual(report["code_bytes"],96)
        self.assertFalse(report["hardware_certified"])
        self.assertEqual(report["runtime"],"UNOBSERVED")

    def test_independent_structural_negatives_not_only_rom_hash(self):
        cases=[(0x8900,"dependency"),(0x11D8B0,"dependency"),(0x11CE60,"allocation"),
               (0x11CDCC,"stride"),(0x11CEF8,"stride"),(0x11CEFE,"stride"),
               (0x11D8F4,"getter"),(0xED9464,"tail"),(TM.TABLE,"table"),
               (0x11CDD4,"binding"),(TM.CODE,"source")]
        for at,reason in cases:
            data=bytearray(self.data);data[at]^=1;data=bytes(data)
            # Supply the ACTUAL changed fixture SHA, retaining independent expected dependencies.
            self.fixture(data)
            with self.subTest(at=hex(at)),self.assertRaisesRegex(GateError,reason):
                TM.verify_feature(data,"fixture")
            self.doCleanups()

    def test_unprepared_or_wrong_rom_rejected(self):
        with self.assertRaises(GateError):TM.patch(b"original without prerequisites")
        with self.assertRaises(GateError):TM.verify_feature(b"wrong")

    def test_public_cli_wrong_input_and_verify_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"input.gba";path.write_bytes(b"wrong")
            command=[sys.executable,"-B",str(ROOT/"firered/tm_names.py"),"verify","--rom",str(path)]
            result=subprocess.run(command,cwd=directory,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("identity mismatch",result.stderr)
            result=subprocess.run(command+["--output",str(Path(directory)/"new.gba")],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((Path(directory)/"new.gba").exists())

    def test_real_assembly_production_identity(self):
        if not all(shutil.which("arm-none-eabi-"+name) for name in ("as","ld","objcopy")):
            self.skipTest("optional GNU Arm binutils not installed")
        payload=TM.compile_routes()
        self.assertEqual(len(payload),96)
        self.assertEqual(sha(payload),TM.CODE_SHA)

    def test_synthetic_cpu_and_real_ram_relocation(self):
        prefix=Path(os.environ.get("FRLG_MGBA_PREFIX","/opt/homebrew"))
        if (not (prefix/"include/mgba/core/core.h").is_file() or not shutil.which("cc") or
                not any((prefix/"lib").glob("libmgba*")) or
                not all(shutil.which("arm-none-eabi-"+name) for name in ("as","ld","objcopy"))):
            self.skipTest("optional local mGBA development files/GNU Arm/cc unavailable")
        spec=importlib.util.spec_from_file_location("check_tm_cpu",ROOT/"tools/check_tm_cpu.py")
        tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
        report=tool.run(prefix)
        self.assertEqual(report["writer_cases"],1420)
        self.assertEqual(report["getter_cases"],16)
        self.assertTrue(report["wrong_getter_negative_rejected"])
        self.assertFalse(report["game_or_save_input"])
