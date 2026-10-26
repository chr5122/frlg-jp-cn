import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from frlg.encode import encode, load_charmap
from frlg.font_pack import build_font
from frlg.font_pages import MAX_GID, PAGE_SPAN, glyph_slot_in_page
from frlg.glyph_codec import decode_four_block_glyph
from frlg.rom import GateError, sha

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_font", ROOT / "tools/build_font.py")
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


def fixture():
    pixels = [[0] * 16 for _ in range(16)]
    # Independently drawn synthetic marks, including the last live column/row.
    pixels[0][0], pixels[3][8], pixels[11][11] = 1, 2, 1
    return dict(schema=1, source="Project-owned synthetic test marks, MIT",
                glyphs=[dict(unicode="中", glyph_id="0x01FF", pixels=pixels)])


class FontPackTests(unittest.TestCase):
    def test_geometry_roundtrip_and_unallocated_blank(self):
        document = fixture()
        artifacts, report = build_font(document)
        table = bytes(sum((((v >> (2 * (3 - i))) & 3) % 3) * 3 ** (3 - i)
                          for i in range(4)) for v in range(256))
        page = artifacts["page_01.bin"]
        # Independent synthetic lookup; no ROM bytes copied into tests.
        actual = decode_four_block_glyph(table + page, 256 + glyph_slot_in_page(255), 0)
        self.assertEqual(actual, document["glyphs"][0]["pixels"])
        self.assertEqual(len(page), PAGE_SPAN)
        self.assertEqual(page[:64], b"\xff" * 64)
        self.assertEqual(artifacts["blank_page.bin"], b"\xff" * PAGE_SPAN)
        self.assertEqual(report["artifacts"]["page_01.bin"]["sha256"], sha(page))
        self.assertEqual(report["runtime"], "UNOBSERVED")
        self.assertFalse(report["rom_installed"])
        self.assertNotIn("source", report)

    def test_deterministic_pages_and_encoder_connection(self):
        document = fixture()
        second = copy.deepcopy(document["glyphs"][0])
        second.update(unicode="文", glyph_id=MAX_GID)
        document["glyphs"].append(second)
        artifacts, report = build_font(document)
        document["glyphs"].reverse()
        self.assertEqual(build_font(document), (artifacts, report))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.csv"
            path.write_bytes(artifacts["charmap.csv"])
            cmap = load_charmap(path)
            self.assertEqual(encode("中文。", cmap), bytes.fromhex("f701fff70affadff"))
            self.assertTrue(all(record["status"] == "allocated" for record in cmap.values()))

    def test_slot_boundaries_and_dense_page_zero(self):
        document = fixture()
        document["glyphs"] = []
        for index, gid in enumerate((0, 7, 8, 255, 256, MAX_GID)):
            item = fixture()["glyphs"][0]
            item.update(unicode=chr(0x4E00 + index), glyph_id=gid)
            document["glyphs"].append(item)
        artifacts, report = build_font(document)
        self.assertEqual(report["pages"], [0, 1, 10])
        for item in document["glyphs"]:
            gid = item["glyph_id"]
            slot = glyph_slot_in_page(gid & 255)
            self.assertEqual(artifacts[f"page_{gid >> 8:02X}.bin"][slot:slot+2], b"\x00\x40")

    def test_invalid_document_and_records(self):
        for key, value in (("schema", True), ("schema", 2), ("source", ""),
                           ("glyphs", []), ("glyphs", {})):
            document = fixture()
            document[key] = value
            with self.subTest(key=key), self.assertRaises(GateError):
                build_font(document)
        for key, value in (("unicode", "中文"), ("unicode", "{"), ("unicode", "\n"),
                           ("unicode", "A"), ("unicode", "。"), ("unicode", "\ud800"),
                           ("glyph_id", True), ("glyph_id", -1), ("glyph_id", MAX_GID+1),
                           ("pixels", [[0]*16]*15)):
            document = fixture()
            document["glyphs"][0][key] = value
            with self.subTest(key=key, value=repr(value)), self.assertRaises(GateError):
                build_font(document)

    def test_clipping_and_pixels_rejected(self):
        for x, y, value in ((12, 0, 1), (0, 12, 1), (0, 0, True),
                            (0, 0, -1), (0, 0, 3), (0, 0, 0.0)):
            document = fixture()
            document["glyphs"][0]["pixels"][y][x] = value
            with self.subTest(x=x, y=y, value=value), self.assertRaises(GateError):
                build_font(document)

    def test_duplicate_character_and_gid(self):
        for change in (dict(unicode="文"), dict(glyph_id=256), {}):
            document = fixture()
            second = copy.deepcopy(document["glyphs"][0])
            second.update(change)
            document["glyphs"].append(second)
            with self.subTest(change=change), self.assertRaises(GateError):
                build_font(document)

    def test_cli_dry_run_new_directory_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "pixels.json", Path(tmp) / "artifacts"
            source.write_text(json.dumps(fixture()), encoding="utf8")
            before = source.read_bytes()
            report = CLI.run(source)
            self.assertFalse(report["written"])
            self.assertFalse(target.exists())
            self.assertTrue(CLI.run(source, target)["written"])
            self.assertEqual(source.read_bytes(), before)
            for name, info in report["artifacts"].items():
                self.assertEqual(sha((target / name).read_bytes()), info["sha256"])
            with self.assertRaises(FileExistsError):
                CLI.run(source, target)
            source.write_text('{"schema":1,"schema":1}', encoding="utf8")
            with self.assertRaises(GateError):
                CLI.run(source)
            command = [sys.executable, "-B", str(ROOT / "tools/build_font.py"),
                       "--glyphs", str(source), "--output-dir", str(Path(tmp) / "invalid")]
            result = subprocess.run(command, cwd=tmp, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate JSON field", result.stderr)
            self.assertFalse((Path(tmp) / "invalid").exists())

    def test_production_cli_success_outside_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "pixels.json", Path(tmp) / "artifacts"
            source.write_text(json.dumps(fixture()), encoding="utf8")
            result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/build_font.py"),
                                     "--glyphs", str(source), "--output-dir", str(target)],
                                    cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["written"])
            self.assertEqual(json.loads((target / "manifest.json").read_text()), report)


class DecoderAssemblyTests(unittest.TestCase):
    def test_arm7_build_and_two_link_addresses(self):
        prefix = "arm-none-eabi-"
        if not all(shutil.which(prefix + name) for name in ("as", "ld", "objcopy", "objdump")):
            self.skipTest("optional GNU Arm binutils not installed")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            obj = tmp / "decoder.o"
            subprocess.run([prefix + "as", "-mcpu=arm7tdmi", "-mthumb",
                            str(ROOT / "shared/patches/cn_glyph.s"), "-o", str(obj)], check=True)
            payloads = []
            for base in ("0x08010000", "0x08F00000"):
                elf, binary = tmp / f"{base}.elf", tmp / f"{base}.bin"
                subprocess.run([prefix + "ld", "-Ttext=" + base, "-e", "cn_decode_glyph",
                                str(obj), "-o", str(elf)], check=True)
                subprocess.run([prefix + "objcopy", "-O", "binary", str(elf), str(binary)], check=True)
                payloads.append(binary.read_bytes())
                assembly = subprocess.check_output([prefix + "objdump", "-d", str(elf)], text=True)
                self.assertNotIn("blx", assembly)
                self.assertNotIn("bf00", assembly)
            self.assertEqual(payloads[0], payloads[1])
            self.assertEqual(len(payloads[0]), 108)
