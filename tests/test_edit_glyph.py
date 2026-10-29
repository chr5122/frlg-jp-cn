import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from frlg.font_pack import build_font
from frlg.rom import GateError

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"tools/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


editor = load("edit_glyph")
template = load("create_glyph_template")


class EditGlyphTests(unittest.TestCase):
    def test_edit_preview_and_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, grid, output = (Path(tmp) / name for name in ("source.json", "grid.txt", "output.json"))
            doc = template.template("中文中", "Self-drawn")
            source.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf8")
            original = source.read_bytes()
            drawing = "1..........2\n" + "............\n" * 11
            grid.write_text(drawing, encoding="utf8")
            self.assertEqual(editor.run(source, "中", grid, output), drawing)
            self.assertEqual(editor.run(output, "中"), drawing)
            edited = json.loads(output.read_text(encoding="utf8"))
            self.assertEqual(edited["glyphs"][1], doc["glyphs"][1])
            self.assertEqual(edited["glyphs"][0]["pixels"][0], [1] + [0] * 10 + [2] + [0] * 4)
            self.assertEqual(edited["glyphs"][0]["pixels"][12:], [[0] * 16] * 4)
            self.assertEqual(build_font(edited)[1]["glyph_count"], 2)
            self.assertEqual(source.read_bytes(), original)

    def test_reject_bad_grids_and_unknown_character(self):
        for grid in ("", "............\n" * 11, "............\n" * 13,
                     "...........x\n" + "............\n" * 11,
                     "........... \n" + "............\n" * 11):
            with self.subTest(grid=grid), self.assertRaises(GateError):
                editor.parse_grid(grid)
        with self.assertRaises(GateError):
            editor.find_glyph(template.template("中", "Self-drawn"), "文")

    def test_refuse_overwrite_and_invalid_grid_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, grid, output = (Path(tmp) / name for name in ("source.json", "grid.txt", "output.json"))
            source.write_text(json.dumps(template.template("中", "Self-drawn")), encoding="utf8")
            grid.write_text("bad", encoding="utf8")
            for target in (source, grid):
                with self.subTest(target=target), self.assertRaises(GateError):
                    editor.run(source, "中", grid, target)
            with self.assertRaises(GateError):
                editor.run(source, "中", grid, output)
            self.assertFalse(output.exists())
            grid.write_text("............\n" * 12, encoding="utf8")
            output.write_text("preserve", encoding="utf8")
            with self.assertRaises(GateError):
                editor.run(source, "中", grid, output)
            self.assertEqual(output.read_text(encoding="utf8"), "preserve")
