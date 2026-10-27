"""Synthetic audit gates and optional real assembly; no game/font input."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frlg import font_pages, rendering as r
from frlg.rom import GateError, sha

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools/renderer_module.py"
ARM = all(shutil.which("arm-none-eabi-" + x) for x in ("as", "ld", "objcopy"))
EXPECTED = {
    "firered-2.3-0111": [
        (244, "eec29b313840930b6d892f4b77dbb1a886c55b7fc591ca2e884b4f5bb7ea2074"),
        (108, "0d90f350aeaeb7c3b20e1bc9d2b93d3e984bb2cc31b151b057bfa664eeaa74f8"),
        (32, "f407e075eab28cad8a9007f3e7905abb499013b52aa1a218ca89c7ff11087c85"),
        (76, "e5b3613e5b8f10428bb24fae94fcbb57a378bb5339c62a3f2c632ae01a9104e5"),
        (144, "4c6344130dcc5b7803dfc8d125dffc43ced1e3a3ffc85c35e77c2716db2a60bf"),
        (36, "a75eb9f1bbf202ea4d693bb97e7f21795028972ccdb32c2bccb73862063d2343"),
        (172, "1c9489fd4b85021224085f1ea705b10254439a3d5a4c0fd4e0f083f2a89c2d45")],
    "leafgreen-2.3-r89": [
        (244, "9f0402b0bd1c6360f62fab8417cab29d02edea37bad7db1911689dd688d89028"),
        (108, "46faae476f43f24af8835f843713e29f40e451a2f89594fe46177c0acdcf7a86"),
        (44, "e4e6c3b83f21d16d62b9e89c10a9fa71b047fee4d055959cdc1875d7b79dc438"),
        (160, "4936ed94f982c0bae1c94b5973e1cbef4c86f06ce3c1c56159e1f8befe6d76f0"),
        (384, "0398f88c51cbfec709814ac895d19ad2c2cb5085f368c6bf37eb28cca7313c7d"),
        (204, "a13f8f2b05db22b23d724cf013fcda724683ad2dd3219ec865448d636db60957")],
}


class RendererAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = dict(r.PROFILES["firered-2.3-0111"])
        data = bytearray(b"\xff" * 0x1000000)
        cls.parts = {name: b"\x70\x47" * 4 for name in (
            "main", "small", "metrics", "gate", "scanners", "width_alias", "secondary_gate")}
        rows = []
        for name, raw in cls.parts.items():
            at = cls.profile[name]
            data[at:at + len(raw)] = raw
            rows.append(dict(name=name, offset=at, bytes=len(raw)))
        data[0x5814:0x5818] = bytes.fromhex(cls.profile["hook"])
        for at, key in ((0x5CA0, "fixed_entry"), (0x5E28, "variable_entry")):
            data[at:at + 4] = cls.profile[key].to_bytes(4, "little")
        at = cls.profile["gate_tail"] - 0x08000001
        data[at:at + 8] = bytes.fromhex("004b1847") + (0x08000001 + cls.profile["secondary_gate"]).to_bytes(4, "little")
        table = font_pages.page_table_bytes()
        at = font_pages.PAGE_TABLE_ROM
        data[at:at + len(table)] = table
        at = cls.profile["small_pages"]
        data[at:at + 44] = (0x08800000).to_bytes(4, "little") * 11
        at = cls.profile["small_widths"]
        data[at:at + 0xB00] = b"\x0a" * 0xB00
        cls.data = bytes(data)
        cls.report = dict(components=rows, runtime="UNOBSERVED", complete_renderer_export=False)

    def fixture(self, data=None):
        data = self.data if data is None else data
        profile = dict(self.profile, sha256=sha(data))
        for context in (patch.dict(r.PROFILES, {"fixture": profile}),
                        patch.object(r, "compile_components", return_value=(self.parts, dict(self.report)))):
            context.start()
            self.addCleanup(context.stop)
        return data

    def test_selected_components_and_resource_boundaries(self):
        result = r.verify(self.fixture(), "fixture")
        self.assertEqual(result["status"], "SELECTED_PRODUCTION_SOURCE_MATCH")
        self.assertEqual(result["small_width_range"], [10, 10])
        self.assertEqual(len(result["small_page_offsets"]), 11)
        self.assertFalse(result["hardware_certified"])
        self.assertFalse(result["complete_renderer_export"])

    def test_independent_component_negatives(self):
        for at in (0x5814, 0x5CA0, 0x5E28, 0x7B82A4, *(self.profile[x] for x in self.parts)):
            data = bytearray(self.data)
            data[at] ^= 1
            self.fixture(bytes(data))  # actual changed SHA, independent expected bytes
            with self.subTest(at=hex(at)), self.assertRaises(GateError):
                r.verify(bytes(data), "fixture")
            self.doCleanups()

    def test_resource_structure_negatives(self):
        cases = [(font_pages.PAGE_TABLE_ROM, b"\x01"),
                 (font_pages.BLANK_PAGE_ROM, b"\0"),
                 (self.profile["small_pages"], b"\0" * 4),
                 (self.profile["small_pages"], (0x08FFFFFC).to_bytes(4, "little")),
                 (self.profile["small_widths"], b"\x11")]
        for at, raw in cases:
            data = bytearray(self.data)
            data[at:at + len(raw)] = raw
            self.fixture(bytes(data))
            with self.subTest(at=hex(at), raw=raw), self.assertRaises(GateError):
                r.verify(bytes(data), "fixture")
            self.doCleanups()

    def test_wrong_identity_or_profile(self):
        for profile in r.PROFILES:
            with self.assertRaisesRegex(GateError, "identity"):
                r.verify(b"wrong", profile)
        with self.assertRaises(GateError):
            r.verify(b"wrong", "unknown")
        with self.assertRaises(GateError):
            r.compile_components("unknown")

    def test_compile_layout_drift(self):
        with patch.object(r, "_assemble", return_value=b"\x70\x47"):
            with self.assertRaisesRegex(GateError, "layout drift"):
                r.compile_components("firered-2.3-0111")

    def test_profiles_are_independently_bound(self):
        fr, lg = r.PROFILES.values()
        for field in ("sha256", "main", "small", "metrics", "gate", "gate_tail", "hook"):
            self.assertNotEqual(fr[field], lg[field])
        self.assertFalse(fr["prefix_bx"])
        self.assertTrue(lg["prefix_bx"])

    def test_cli_rejects_wrong_rom_and_write_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.gba"
            path.write_bytes(b"wrong")
            output = Path(directory) / "output"
            base = [sys.executable, "-B", str(CLI)]
            tail = ["--profile", "firered-2.3-0111", "--rom", str(path)]
            for args in (["verify", *tail], ["verify", *tail, "--output-dir", str(output)],
                         ["compile", *tail]):
                result = subprocess.run(base + args, cwd=directory, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())
                self.assertEqual(path.read_bytes(), b"wrong")

    @unittest.skipUnless(ARM, "optional GNU Arm binutils unavailable")
    def test_compiled_production_hashes(self):
        for profile, expected in EXPECTED.items():
            parts, report = r.compile_components(profile)
            self.assertFalse(report["rom_installed"])
            self.assertFalse(report["complete_renderer_export"])
            self.assertEqual(report["runtime"], "UNOBSERVED")
            self.assertEqual(len(report["components"]), len(expected))
            if profile.startswith("leafgreen"):
                self.assertIn("dispatch-table", report["known_issues"][0])
            else:
                self.assertEqual(report["known_issues"], [])
            for row, (size, digest) in zip(report["components"], expected):
                self.assertEqual(row["bytes"], size)
                self.assertEqual(sha(parts[row["name"]]), digest)

    @unittest.skipUnless(ARM, "optional GNU Arm binutils unavailable")
    def test_compile_cli_new_directory_and_readback(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "artifacts"
            cmd = [sys.executable, "-B", str(CLI), "compile", "--profile", "leafgreen-2.3-r89",
                   "--output-dir", str(out)]
            result = subprocess.run(cmd, cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((out / "manifest.json").read_text())
            self.assertEqual(sorted(x.name for x in out.iterdir()),
                             ["gate.bin", "main.bin", "manifest.json", "metrics.bin", "scanners.bin", "secondary_gate.bin", "small.bin"])
            for row in report["components"]:
                self.assertEqual(sha((out / (row["name"] + ".bin")).read_bytes()), row["sha256"])
            second = subprocess.run(cmd, capture_output=True)
            self.assertNotEqual(second.returncode, 0)

    def test_synthetic_width_cpu_and_wrong_width_negative(self):
        prefix = Path(os.environ.get("FRLG_MGBA_PREFIX", "/opt/homebrew"))
        if (not ARM or not shutil.which("cc") or
                not (prefix / "include/mgba/core/core.h").is_file() or
                not any((prefix / "lib").glob("libmgba*"))):
            self.skipTest("optional GNU Arm/cc/mGBA development files unavailable")
        spec = importlib.util.spec_from_file_location("check_width_cpu", ROOT / "tools/check_width_cpu.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        report = tool.run(prefix)
        self.assertEqual([x["cases"] for x in report["reports"]], [396, 1008])
        self.assertEqual(report["scope"], "CPU_ONLY_NO_NATIVE_CONTINUATIONS")
        for row in report["reports"]:
            self.assertTrue(row["incorrect_width_negative_rejected"])
            self.assertFalse(row["native_continuations_executed"])
            self.assertFalse(row["game_font_or_save_input"])
            self.assertFalse(row["hardware_certified"])
