"""Public distribution boundaries and integrity, without private course inputs."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.public_release import check_tree, export_public


class PublicReleaseTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).resolve().parents[1] / ".work" / "public-release-tests"
        work.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "source"
        self.assertTrue(self.root.is_relative_to(work.resolve()))
        self.root.mkdir()
        license_text = "MIT License\n\nCopyright (c) fixture contributors\n"
        files = {
            "README.md": "# Fixture\r\n\r\n[中文](README.zh-CN.md)\r\n",
            "README.zh-CN.md": "# 合成发行测试\n[English](README.md)\n",
            "LICENSE": license_text,
            "THIRD_PARTY_NOTICES.md": "Original synthetic test fixture.\n",
            "skills/fish-proteus817/LICENSE.txt": license_text,
            "skills/fish-proteus817/SKILL.md": (
                "---\nname: fish-proteus817\ndescription: Synthetic publication fixture\n"
                "license: MIT\ncompatibility: Synthetic Windows fixture\n"
                "metadata:\n  version: '0.1.1'\n---\n\nUse the synthetic fixture.\n"
            ),
            "module.py": "VALUE = 3\n",
        }
        for name, data in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data.encode("utf-8"))
        self.config = {"schema": "fish-proteus.public-source.v1", "version": "0.1.1", "files": sorted([*files, "public-release.json"])}
        self.save_config()

    def save_config(self):
        (self.root / "public-release.json").write_text(json.dumps(self.config), encoding="utf-8")

    def export(self, name="release"):
        return export_public(self.root, self.root / ".work" / name)

    def test_only_reviewed_files_are_exported_and_archive_is_reproducible(self):
        private = self.root / ".local" / "credentials.json"
        private.parent.mkdir()
        private.write_text('{"token":"synthetic-private-value"}', encoding="utf-8")
        first, second = self.export("first"), self.export("second")
        self.assertEqual(first["archive_sha256"], second["archive_sha256"])
        tree = Path(first["tree"])
        self.assertFalse((tree / ".local").exists())
        self.assertNotIn(b"\r", (tree / "README.md").read_bytes())
        self.assertEqual(check_tree(tree)["status"], "passed")
        with zipfile.ZipFile(first["archive"]) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(self.config["files"]) + 1)
            self.assertFalse(any("credentials" in name for name in names))

    def test_changed_file_is_not_accepted_as_the_recorded_release(self):
        tree = Path(self.export()["tree"])
        (tree / "module.py").write_text("VALUE = 4\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "identity changed"):
            check_tree(tree)

    def test_unlisted_file_is_rejected(self):
        tree = Path(self.export()["tree"])
        (tree / "unreviewed.txt").write_text("Not reviewed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unlisted"):
            check_tree(tree)

    def test_private_binary_and_escaping_paths_fail_before_output_creation(self):
        original = list(self.config["files"])
        for name in ("../outside.py", "C:/private.py", "folder\\private.py", "evidence/report.json", ".local/token.txt", "firmware.exe", "diagram.png"):
            with self.subTest(name=name):
                self.config["files"] = original + [name]
                self.save_config()
                with self.assertRaises(ValueError):
                    self.export()
                self.assertFalse((self.root / ".work" / "release").exists())

    def test_case_collisions_and_existing_output_are_rejected(self):
        self.config["files"].append("readme.md")
        self.save_config()
        with self.assertRaisesRegex(ValueError, "case-colliding"):
            self.export()
        self.config["files"].pop()
        self.save_config()
        self.export()
        with self.assertRaisesRegex(ValueError, "unused"):
            self.export()

    def test_publication_does_not_follow_an_external_symlink(self):
        outside = self.root.parent / "outside.py"
        outside.write_text("PRIVATE = 1\n", encoding="utf-8")
        target = self.root / "module.py"
        target.unlink()
        try:
            target.symlink_to(outside)
        except OSError:
            self.skipTest("This Windows account cannot create symlinks")
        with self.assertRaisesRegex(ValueError, "escapes|symlink"):
            self.export()

    def test_mismatched_license_or_frontmatter_version_is_rejected(self):
        (self.root / "skills/fish-proteus817/LICENSE.txt").write_text("Different notice\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "same MIT license"):
            self.export("license")
        (self.root / "skills/fish-proteus817/LICENSE.txt").write_bytes((self.root / "LICENSE").read_bytes())
        path = self.root / "skills/fish-proteus817/SKILL.md"
        path.write_text(path.read_text(encoding="utf-8").replace("'0.1.1'", "'0.1.0'"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "version"):
            self.export("version")

    def test_broken_reference_and_binary_text_are_rejected(self):
        readme = self.root / "README.md"
        readme.write_text("[Missing](missing.md)\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Broken"):
            self.export("links")
        readme.write_bytes(b"Not text\0payload")
        with self.assertRaisesRegex(ValueError, "NUL"):
            self.export("binary")


if __name__ == "__main__":
    unittest.main()
