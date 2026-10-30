"""Repository metadata stays aligned without Proteus or a desktop."""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _version(text: str) -> str:
    match = re.search(r'(?m)^version = "(\d+\.\d+\.\d+)"$', text)
    if match is None:
        raise AssertionError("pyproject.toml is missing a project version")
    return match.group(1)


class ProjectMetadataTests(unittest.TestCase):
    def test_version_is_consistent(self):
        version = _version((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        package = (ROOT / "fish_proteus" / "__init__.py").read_text(encoding="utf-8")
        release = json.loads((ROOT / "public-release.json").read_text(encoding="utf-8"))
        skill = (ROOT / "skills" / "fish-proteus817" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f'__version__ = "{version}"', package)
        self.assertEqual(release["version"], version)
        self.assertIn(f'version: "{version}"', skill)
        self.assertRegex(skill, r"(?m)^name: fish-proteus817$")
        self.assertRegex(skill, r"(?m)^license: MIT$")

    def test_console_script_points_at_the_json_cli(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('fish-proteus = "fish_proteus.cli:main"', text)

    def test_public_allowlist_matches_existing_sources(self):
        release = json.loads((ROOT / "public-release.json").read_text(encoding="utf-8"))
        files = release["files"]
        self.assertIsInstance(files, list)
        self.assertEqual(files, sorted(files))
        self.assertNotIn("PUBLIC_MANIFEST.json", files)
        missing = [name for name in files if not (ROOT / name).is_file()]
        self.assertEqual(missing, [])

    def test_skill_entrypoint_stays_where_the_installer_expects_it(self):
        skill = ROOT / "skills" / "fish-proteus817" / "SKILL.md"
        license_copy = skill.parent / "LICENSE.txt"
        self.assertTrue(skill.is_file())
        self.assertTrue(license_copy.is_file())
        self.assertEqual((ROOT / "LICENSE").read_bytes(), license_copy.read_bytes())
