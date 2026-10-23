import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publication", ROOT / "tools/check_publication.py")
publication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication)


class PublicationTests(unittest.TestCase):
    def test_current_tree(self):
        found, errors = publication.inspect(ROOT)
        self.assertEqual(errors, [])
        self.assertEqual(set(found), publication.ALLOWED)

    def test_rogue_rom_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "game.gba").write_bytes(bytes([0, 1, 2]))
            _, errors = publication.inspect(root)
            self.assertTrue(any("not allowlisted" in e for e in errors))
            self.assertTrue(any("binary" in e for e in errors))

    def test_private_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_path = "/" + "Users" + "/" + "fixture" + "/" + "private-file"
            (root / "README.md").write_text(private_path, encoding="utf8")
            _, errors = publication.inspect(root)
            self.assertTrue(any("private home path" in e for e in errors))

    def test_fake_token_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_token = "gh" + "p_" + "X" * 32
            (root / "README.md").write_text(fake_token, encoding="utf8")
            _, errors = publication.inspect(root)
            self.assertTrue(any("GitHub token" in e for e in errors))

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "link").symlink_to("README.md")
            _, errors = publication.inspect(root)
            self.assertTrue(any("symlink forbidden" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
