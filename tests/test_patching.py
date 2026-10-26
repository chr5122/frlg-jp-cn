import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frlg.patching import PROFILES, apply_recipe
from frlg.rom import GateError, sha

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("patch_rom", ROOT / "tools/patch_rom.py")
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.parent = b"synthetic\xff\xff"
        self.product = b"Synthetic\xff\xff"
        self.recipe = dict(schema=1, game="firered-jp-rev0", output_sha256=sha(self.product),
                           writes=[dict(offset=0, before_hex="73", after_hex="53", purpose="patch")],
                           protected=[dict(start=9, end=11, name="synthetic guard")])

    def apply(self, recipe=None, parent=None, expected=None):
        return apply_recipe(self.parent if parent is None else parent,
                            self.recipe if recipe is None else recipe,
                            expected_sha256=sha(self.parent) if expected is None else expected,
                            size=len(self.parent))

    def test_success(self):
        product, report = self.apply()
        self.assertEqual(product, self.product)
        self.assertEqual(report["changed_bytes"], 1)
        self.assertEqual(report["runtime"], "UNOBSERVED")
        self.assertFalse(report["complete_translation"])

    def test_wrong_identity(self):
        for data in (b"wrong size", b"SYNTHETIC\xff\xff"):
            with self.subTest(data=data), self.assertRaises(GateError):
                self.apply(parent=data)
        with self.assertRaises(GateError):
            self.apply(expected="0" * 64)

    def test_schema(self):
        for key, value in (("schema", True), ("schema", 2), ("game", "unknown"),
                           ("output_sha256", "x" * 64), ("writes", []), ("protected", {})):
            recipe = copy.deepcopy(self.recipe)
            recipe[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(GateError):
                self.apply(recipe)
        recipe = dict(self.recipe, unexpected=True)
        with self.assertRaises(GateError):
            self.apply(recipe)

    def test_write_rejections(self):
        for change in (dict(offset=True), dict(offset=-1), dict(offset=0x08000000),
                       dict(before_hex="00"), dict(after_hex=""), dict(after_hex="5354"),
                       dict(after_hex="zz"), dict(purpose="unknown"), dict(purpose="new_pool")):
            recipe = copy.deepcopy(self.recipe)
            recipe["writes"][0].update(change)
            with self.subTest(change=change), self.assertRaises((GateError, ValueError)):
                self.apply(recipe)

    def test_overlap_and_guards(self):
        recipe = copy.deepcopy(self.recipe)
        recipe["writes"] *= 2
        with self.assertRaises(GateError):
            self.apply(recipe)
        for lo, hi in ((0, 1), (-1, 1), (9, 12), (10, 9), (0x08000000, 0x08000001)):
            recipe = copy.deepcopy(self.recipe)
            recipe["protected"] = [dict(start=lo, end=hi, name="guard")]
            with self.subTest(lo=lo, hi=hi), self.assertRaises(GateError):
                self.apply(recipe)

    def test_output_identity_and_noop(self):
        recipe = copy.deepcopy(self.recipe)
        recipe["output_sha256"] = "0" * 64
        with self.assertRaises(GateError):
            self.apply(recipe)
        recipe["output_sha256"] = sha(self.parent)
        recipe["writes"][0]["after_hex"] = "73"
        with self.assertRaises(GateError):
            self.apply(recipe)

    def test_new_pool(self):
        recipe = copy.deepcopy(self.recipe)
        recipe["protected"] = []
        recipe["writes"] = [dict(offset=9, before_hex="ffff", after_hex="0102", purpose="new_pool")]
        recipe["output_sha256"] = sha(b"synthetic\x01\x02")
        self.assertEqual(self.apply(recipe)[0], b"synthetic\x01\x02")

    def test_io_dry_run_new_only_and_readback(self):
        # Test-only profile replacement; production profiles stay pinned to real originals.
        profile = dict(sha256=sha(self.parent), size=len(self.parent))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(PROFILES, {self.recipe["game"]: profile}):
            original, recipe, output = (Path(tmp) / name for name in ("input.gba", "recipe.json", "output.gba"))
            original.write_bytes(self.parent)
            recipe.write_text(json.dumps(self.recipe), encoding="utf8")
            self.assertFalse(CLI.run(original, recipe)["written"])
            self.assertFalse(output.exists())
            self.assertTrue(CLI.run(original, recipe, output)["written"])
            self.assertEqual(output.read_bytes(), self.product)
            for target in (original, recipe, output):
                with self.subTest(target=target), self.assertRaises(GateError):
                    CLI.run(original, recipe, target)
            self.assertEqual(original.read_bytes(), self.parent)
            self.assertEqual(output.read_bytes(), self.product)

    def test_duplicate_json_and_real_cli_wrong_rom(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, recipe, output = (Path(tmp) / name for name in ("input.gba", "recipe.json", "output.gba"))
            recipe.write_text('{"schema":1,"schema":1}', encoding="utf8")
            with self.assertRaises(GateError):
                CLI.load_recipe(recipe)
            original.write_bytes(self.parent)
            recipe.write_text(json.dumps(self.recipe), encoding="utf8")
            result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/patch_rom.py"),
                                     "--original", str(original), "--recipe", str(recipe),
                                     "--output", str(output)], capture_output=True, text=True, cwd=tmp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("identity mismatch", result.stderr)
            self.assertFalse(output.exists())
            self.assertEqual(original.read_bytes(), self.parent)
