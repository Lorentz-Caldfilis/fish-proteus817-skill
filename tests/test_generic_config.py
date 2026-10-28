"""Discovery, immutable resource isolation and actual catalogue boundaries."""
from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from fish_proteus.automation import Library
from fish_proteus.config import ProteusConfig
from fish_proteus._vendor.proteus_auto.proteus_project import UnsupportedFormat


class GenericConfigurationTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).resolve().parents[1] / ".work" / "generic-config-tests"
        work.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def config(self, name):
        install = self.root / name
        executable = install / "BIN" / "PDS.EXE"
        library = install / "DATA" / "LIBRARY"
        library.mkdir(parents=True)
        return ProteusConfig(executable, library, install / "DATA" / "SAMPLES",
                             install / "DATA" / "SAMPLES" / "template.pdsprj")

    @staticmethod
    def catalogue(directory, name):
        header = bytearray(32)
        header[:16] = b"DEVICE LIBRARY\x1a\0"
        struct.pack_into("<IIH", header, 16, 400, 1, 1)
        entry = bytearray(80)
        entry[:len(name)] = name.encode("ascii")
        struct.pack_into("<I", entry, 64, 112)
        (directory / "FIXTURE.LIB").write_bytes(header + entry + struct.pack("<I", 20) + bytes(16))

    def test_explicit_resources_are_isolated_between_two_installations(self):
        one, two = self.config("one"), self.config("two")
        self.catalogue(one.library_root, "PART_A")
        self.catalogue(two.library_root, "PART_B")
        self.assertEqual(Library(config=one).search()[0]["name"], "PART_A")
        self.assertEqual(Library(config=two).search()[0]["name"], "PART_B")
        self.assertEqual(Library(config=one).search("PART_B"), [])
        with self.assertRaises(FrozenInstanceError):
            one.library_root = two.library_root

    def test_explicit_paths_take_precedence_over_environment(self):
        one, two = self.config("explicit"), self.config("environment")
        with patch.dict(os.environ, {"FISH_PROTEUS_EXE": str(two.executable),
                                     "FISH_PROTEUS_LIBRARY": str(two.library_root)}):
            resolved = ProteusConfig.discover(executable=one.executable, library_root=one.library_root)
        self.assertEqual(resolved.library_root, one.library_root)
        self.assertEqual(resolved.samples_root, one.samples_root)

    def test_protected_installation_targets_are_rejected_after_path_resolution(self):
        config = self.config("install")
        for target in (config.library_root / "new.pdsprj",
                       config.executable.parent / ".." / "DATA" / "new.pdsprj",
                       config.samples_root / "new.pdsprj"):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "outside installed"):
                config.check_destination(target)
        self.assertEqual(config.check_destination(self.root / "out.pdsprj"), self.root / "out.pdsprj")

    def test_corrupt_catalogue_pointer_does_not_become_an_available_part(self):
        config = self.config("bad")
        self.catalogue(config.library_root, "PART_A")
        path = config.library_root / "FIXTURE.LIB"
        corrupt = bytearray(path.read_bytes())
        struct.pack_into("<I", corrupt, 96, 0xFFFFFFFF)
        path.write_bytes(corrupt)
        with self.assertRaisesRegex(UnsupportedFormat, "outside LIB"):
            Library(config=config)


if __name__ == "__main__":
    unittest.main()
