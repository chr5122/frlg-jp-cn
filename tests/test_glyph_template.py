import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from frlg.font_pack import build_font
from frlg.rom import GateError

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/create_glyph_template.py"
spec = importlib.util.spec_from_file_location("create_glyph_template", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GlyphTemplateTests(unittest.TestCase):
    def test_duplicate_characters_share_safe_id_and_independent_canvases(self):
        doc = module.template("中文中", "Self-drawn glyphs")
        self.assertEqual([g["unicode"] for g in doc["glyphs"]], ["中", "文"])
        self.assertEqual([g["glyph_id"] for g in doc["glyphs"]], ["0x0100", "0x0101"])
        doc["glyphs"][0]["pixels"][0][0] = 1
        self.assertEqual(doc["glyphs"][1]["pixels"][0][0], 0)
        _, report = build_font(doc)
        self.assertEqual(report["glyph_count"], 2)

    def test_invalid_text_and_source(self):
        for line, source in (("", "self"), ("中" * 15, "self"), ("中A", "self"),
                             ("中\n", "self"), ("{中}", "self"), ("中", " ")):
            with self.subTest(line=line), self.assertRaises(GateError):
                module.template(line, source)

    def test_punctuation_reuses_native_glyphs(self):
        doc = module.template("中！文？中。", "Self-drawn")
        self.assertEqual([g["unicode"] for g in doc["glyphs"]], ["中", "文"])
        with self.assertRaises(GateError):
            module.template("！？。", "Self-drawn")

    def test_two_lines_share_glyph_assignments(self):
        doc = module.template("中文\n中！", "Self-drawn")
        self.assertEqual([g["unicode"] for g in doc["glyphs"]], ["中", "文"])
        with self.assertRaises(GateError):
            module.template("中\n文\n中", "Self-drawn")

    def test_cli_new_only_and_invalid_input_leaves_no_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "glyphs.json"
            command = [sys.executable, "-B", str(SCRIPT), "--text", "中文中",
                       "--source", "Self-drawn", "--output", str(path)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            raw = path.read_bytes()
            self.assertEqual(len(json.loads(raw)["glyphs"]), 2)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(path.read_bytes(), raw)
            bad = Path(directory) / "bad.json"
            command[command.index("中文中")] = "中A"
            command[-1] = str(bad)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertFalse(bad.exists())
