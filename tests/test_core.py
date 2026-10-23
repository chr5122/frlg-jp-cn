import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

from frlg import events, script, text
from frlg.rom import BASE, GateError, Image, number, pointer, protected_offsets, sha, span, verify_changes


class RomTests(unittest.TestCase):
    def test_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "fixture"
            p.write_bytes(b"synthetic")
            image = Image.load(p, sha(b"synthetic"), 9)
            image.unchanged()
            with self.assertRaises(GateError):
                Image.load(p, "0" * 64)
            with self.assertRaises(GateError):
                Image.load(p, sha(b"synthetic"), 8)
            p.write_bytes(b"changed")
            with self.assertRaises(GateError):
                image.unchanged()

    def test_bounds(self):
        self.assertEqual(pointer(b"abc", BASE + 2), 2)
        for value in (BASE - 1, BASE + 3, 0):
            with self.subTest(value=value), self.assertRaises(GateError):
                pointer(b"abc", value)
        for at, size in ((-1, 1), (0, -1), (2, 2)):
            with self.subTest(at=at, size=size), self.assertRaises(GateError):
                span(b"abc", at, size)
        with self.assertRaises(GateError):
            number(True)

    def test_plan(self):
        writes = [dict(offset=1, before_hex="ff", after_hex="10", purpose="new_pool")]
        self.assertEqual(verify_changes(b"\xff" * 3, b"\xff\x10\xff", writes, [])["changed_bytes"], 1)
        cases = [
            (b"\xff" * 3, b"\xff\x10\x11", writes, []),
            (b"\xff" * 3, b"\xff\x10\xff", writes * 2, []),
            (b"\xff" * 3, b"\xff\x10\xff", writes, [dict(start=1, end=2, name="guard")]),
            (b"\x00" * 3, b"\x00\x10\x00", writes, []),
            (b"\xff" * 3, b"\xff\x10", writes, []),
            (b"\xff" * 3, b"\xff\x10\xff", [dict(offset=1, before_hex="ff", after_hex="1011")], []),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(GateError):
                verify_changes(*case)

    def test_vma_is_not_file_offset(self):
        with self.assertRaises(GateError):
            protected_offsets([1], [(BASE, BASE + 2)], 16)
        self.assertEqual(protected_offsets([1, 3], [(0, 2)], 16), [1])


class TextTests(unittest.TestCase):
    def test_ff_inside_parameter_not_terminator(self):
        s = text.exact(bytes.fromhex("f701ffff"), "cn")
        self.assertEqual(s.status, "OK")
        self.assertEqual([k for _, k, _ in s.tokens], ["cn", "end"])
        self.assertEqual(text.exact(bytes.fromhex("fdffff"), "jp").status, "OK")

    def test_explicit_mode(self):
        raw = bytes.fromhex("f701feff")
        self.assertEqual(len(text.exact(raw, "cn").tokens), 2)
        self.assertEqual(len(text.exact(raw, "jp").tokens), 3)
        with self.assertRaises(GateError):
            text.read(raw, 0, "auto")

    def test_rejections(self):
        for raw, mode, status in [
            ("f701", "cn", "TRUNCATED_TOKEN"),
            ("fc99ff", "cn", "UNKNOWN_FC"),
            ("fc04ff", "cn", "TRUNCATED_TOKEN"),
            ("01", "jp", "NO_TERMINATOR"),
            ("ff01", "jp", "TRAILING_BYTES"),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(text.exact(bytes.fromhex(raw), mode).status, status)
        self.assertEqual(text.read(b"\x01\xff", 0, "jp", 1).status, "BUDGET_EXHAUSTED")

    def test_classification(self):
        cn = text.exact(bytes.fromhex("f70001ff"), "cn")
        self.assertEqual(text.classify(cn, {1: "中"}, {})["state"], "QUALIFIED_CN")
        self.assertEqual(text.classify(cn, {}, {})["state"], "UNKNOWN_GLYPH")
        mixed = text.exact(bytes.fromhex("f7000101ff"), "cn")
        self.assertEqual(text.classify(mixed, {1: "中"}, {1: "あ"})["state"], "MIXED")
        jp = text.exact(bytes.fromhex("fd01ff"), "jp")
        changed = text.exact(bytes.fromhex("f70001fd02ff"), "cn")
        self.assertEqual(text.classify(changed, {1: "中"}, {}, jp)["state"], "PARAMETER_MISMATCH")


class EventTests(unittest.TestCase):
    def fixture(self):
        rom = bytearray(256)
        rom[0] = 1
        rom[3] = 1
        struct.pack_into("<I", rom, 4, BASE + 32)
        struct.pack_into("<I", rom, 16, BASE + 64)
        struct.pack_into("<hh", rom, 36, -2, 3)
        struct.pack_into("<I", rom, 48, BASE + 200)
        rom[69] = 5
        struct.pack_into("<I", rom, 72, 0x81230007)
        return rom

    def test_actual_fields_hidden_item(self):
        got = events.parse_events(self.fixture(), 0)
        self.assertEqual(got["tables"]["obj"][0]["x"], -2)
        self.assertEqual(got["tables"]["obj"][0]["script"], BASE + 200)
        hidden = got["tables"]["bg"][0]
        self.assertEqual(hidden["role"], "hidden_item")
        self.assertIsNone(hidden["script"])

    def test_clone_is_separate_carrier(self):
        rom = self.fixture()
        rom[34] = 255
        got = events.parse_events(rom, 0)["tables"]["obj"][0]
        self.assertEqual(got["carrier"], "clone_object")

    def test_map_condition_table(self):
        rom = bytearray(128)
        rom[8] = 2
        struct.pack_into("<I", rom, 9, BASE + 32)
        struct.pack_into("<HHI", rom, 32, 0x4001, 2, BASE + 80)
        got = events.parse_map_scripts(rom, BASE + 8)
        self.assertEqual(got["condition_entries"], 1)
        self.assertEqual(got["entries"][0]["script"], BASE + 80)
        with self.assertRaises(GateError):
            events.parse_map_scripts(rom, BASE + 8, 1)


class ScriptTests(unittest.TestCase):
    def test_operand_and_stop(self):
        rom = bytearray(64)
        rom[0] = 0x67
        struct.pack_into("<I", rom, 1, BASE + 50)
        rom[5] = 2
        got = script.walk(rom, 0, {"0x67": {"width": 5}, "0x02": {"width": 1}})
        self.assertEqual(set(got["slots"]), {1})
        self.assertFalse(got["unknown"])

    def test_unknown_not_skipped(self):
        self.assertTrue(script.walk(bytes([0xAA, 2]), 0, {})["unknown"])

    def test_gotostd_no_fallthrough(self):
        rom = bytearray(64)
        rom[0:3] = bytes([8, 1, 0xAA])
        rom[20] = 2
        got = script.walk(rom, 0, {"0x08": {"width": 2}, "0x02": {"width": 1}}, {1: BASE + 20})
        self.assertFalse(got["unknown"])
        self.assertEqual(got["visited"], 2)

    def test_trainer_script_not_text(self):
        rom = bytearray(100)
        rom[0:2] = bytes([0x5C, 1])
        for offset, target in ((6, 60), (10, 65), (14, 70)):
            struct.pack_into("<I", rom, offset, BASE + target)
        rom[18] = rom[70] = 2
        got = script.walk(rom, 0, {"0x02": {"width": 1}})
        self.assertEqual(set(got["slots"]), {6, 10})
        self.assertFalse(got["unknown"])


class PatchTests(unittest.TestCase):
    def test_wrong_parent_rejected(self):
        path = Path(__file__).resolve().parents[1] / "firered/recap_species_range.py"
        spec = importlib.util.spec_from_file_location("range_patch", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(GateError):
            module.patch(b"not a game")


if __name__ == "__main__":
    unittest.main()
