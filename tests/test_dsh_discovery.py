"""DSH discovery is portable and never depends on a developer's drive path."""
import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
# Script imports intentionally resolve from the same tools directory as the CLI.
sys.path.insert(0, str(TOOLS))
import dsh_headless


class DshDiscoveryTests(unittest.TestCase):
    def setUp(self):
        work = TOOLS.parent / ".work" / "dsh-discovery-tests"
        work.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(work.resolve()))

    def desktop(self):
        executable = self.root / "DeepSeek Harness.exe"
        executable.touch()
        archive = self.root / "resources" / "app.asar"
        archive.parent.mkdir()
        archive.touch()
        return executable

    def test_missing_path_and_configuration_fail_with_actionable_error(self):
        with patch.object(dsh_headless.shutil, "which", return_value=None), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "Pass --dsh-executable or set DSH_DESKTOP_EXE"):
                dsh_headless.find_command()

    def test_explicitly_configured_desktop_uses_bundled_cli(self):
        executable = self.desktop()
        with patch.object(dsh_headless.shutil, "which", return_value=None), patch.dict(os.environ, {"DSH_DESKTOP_EXE": str(executable)}):
            command, environment, route = dsh_headless.find_command()
        self.assertEqual(command[0], str(executable))
        self.assertTrue(command[1].endswith(str(Path("lib") / "bin.js")))
        self.assertEqual(environment, {"ELECTRON_RUN_AS_NODE": "1"})
        self.assertEqual(route, "desktop-bundled-cli")

    def test_incomplete_desktop_layout_is_rejected(self):
        executable = self.root / "DeepSeek Harness.exe"
        executable.touch()
        with self.assertRaisesRegex(ValueError, "resources/app.asar"):
            dsh_headless.find_command(executable)

    def test_explicit_cli_route_is_preserved(self):
        executable = self.root / "dsh-launcher.exe"
        executable.touch()
        self.assertEqual(dsh_headless.find_command(executable), ([str(executable)], {}, "explicit-cli"))

    def test_direct_script_loads_design_registry_without_site_or_editable_install(self):
        # Execute the real script from an unrelated cwd. -I ignores cwd and
        # PYTHONPATH; -S disables site packages and editable-install .pth files.
        # Listing the registry starts no DSH process and writes no skill/output.
        process = subprocess.run(
            [sys.executable, "-I", "-S", "-B", str(TOOLS / "dsh_headless.py"),
             "--workflow", "design", "--list-actions"],
            cwd=self.root, capture_output=True, text=True, encoding="utf8", timeout=15,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["workflow"], "design")
        self.assertTrue({"capabilities", "help", "library_search", "edit", "run_sequence", "verify"} <= set(result["actions"]))
        self.assertIn("help", result["default_actions"])
        self.assertNotIn("run_sequence", result["default_actions"])


if __name__ == "__main__":
    unittest.main()
