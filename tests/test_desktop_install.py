"""Installer transactions use isolated homes, never the account's DSH files."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "dsh_install_desktop.py"
SPEC = importlib.util.spec_from_file_location("dsh_install_desktop_tested", SCRIPT)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
HAS_YAML = importlib.util.find_spec("yaml") is not None


class DesktopInstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fish-desktop-install-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo with spaces"
        self.home = self.root / "dsh-home"
        self.profile = self.home / "profiles/desktop/cordis.patch.yml"
        self.profile.parent.mkdir(parents=True)
        (self.profile.parent / "package.json").write_text('{"name":"desktop"}', encoding="utf-8")
        self.original = (b"# arbitrary user configuration\r\n"
                         b"- id: user-model\r\n  config: !!js ({ model: 'original' })\r\n")
        self.profile.write_bytes(self.original)
        self.skill_source = self.repo / "skills/fish-proteus817"
        self.skill_source.mkdir(parents=True)
        (self.skill_source / "SKILL.md").write_text("---\nname: fish-proteus817\n---\noriginal skill", encoding="utf-8")
        (self.skill_source / "references").mkdir()
        (self.skill_source / "references/api.md").write_text("tool contract", encoding="utf-8")
        (self.repo / "tools").mkdir()
        (self.repo / "tools/dsh_desktop_tool.mjs").write_text("export const name='test';", encoding="utf-8")
        (self.repo / "tools/dsh_design_tool.mjs").write_text("export const parameters=()=>({});", encoding="utf-8")
        (self.repo / "tools/dsh_desktop_bootstrap.mjs").write_text("export const apply=async()=>{};", encoding="utf-8")
        (self.repo / "tools/desktop_gate.py").write_text("# trusted gate", encoding="utf-8")
        self.exe = self.root / "DSH/DeepSeek Harness.exe"
        self.exe.parent.mkdir()
        self.exe.write_bytes(b"fixture, never executed")
        (self.exe.parent / "resources").mkdir()
        (self.exe.parent / "resources/app.asar").write_bytes(b"fixture, never opened")
        self.runtime_patch = patch.object(installer, "_runtime_diagnostics", return_value={
            "python": "fixture-python", "pyyaml": True, "proteus": {}, "errors": []})
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)

    @property
    def installed_skill(self):
        return self.home / "skills/fish-proteus817"

    def run_install(self, **kwargs):
        return installer.install_desktop(repository=self.repo, dsh_home=self.home,
                                         dsh_executable=self.exe, **kwargs)

    def test_install_preserves_profile_bytes_and_is_idempotent(self):
        first = self.run_install()
        self.assertEqual(first["status"], "installed")
        content = self.profile.read_bytes()
        self.assertTrue(content.startswith(self.original))
        self.assertEqual(content.count(installer.BEGIN), 1)
        self.assertEqual(first["plugin_id"], installer.BOOTSTRAP_ID)
        self.assertIn(("id: " + first["plugin_id"]).encode(), content)
        self.assertEqual(installer._inventory(self.installed_skill), installer._inventory(self.skill_source))
        self.assertEqual((Path(first["backup"]) / "cordis.patch.yml").read_bytes(), self.original)
        manifest = Path(first["manifest"]).read_bytes()
        self.assertEqual(json.loads(manifest)["plugin_id"], first["plugin_id"])
        second = self.run_install()
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(self.profile.read_bytes(), content)
        self.assertEqual(Path(first["manifest"]).read_bytes(), manifest)
        self.assertNotIn(b"disabled:", content)
        self.assertNotIn(b"mode:", content)
        cache = Path(first["plugin_cache"]["directory"])
        self.assertTrue(first["plugin_cache"]["ready"])
        self.assertEqual(first["plugin"]["plugin"], (self.repo / "tools/dsh_desktop_bootstrap.mjs").as_uri())
        self.assertEqual(first["plugin"]["implementationModule"], (cache / "dsh_desktop_tool.mjs").as_uri())
        self.assertIn((cache / "dsh_desktop_tool.mjs").as_uri().encode(), content)
        for name in ("dsh_desktop_tool.mjs", "dsh_design_tool.mjs"):
            self.assertEqual((cache / name).read_bytes(), (self.repo / "tools" / name).read_bytes())

    def test_dry_run_has_no_writes_and_reports_missing_repo_files(self):
        (self.repo / "tools/desktop_gate.py").unlink()
        before = {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        result = self.run_install(dry_run=True)
        self.assertEqual(result["status"], "not_ready")
        self.assertTrue(any("desktop_gate.py" in error for error in result["errors"]))
        after = {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.repo / ".work").exists())
        with self.assertRaisesRegex(ValueError, "desktop_gate.py"):
            self.run_install()
        self.assertEqual(self.profile.read_bytes(), self.original)

    def test_upgrade_and_uninstall_restore_original_skill_keep_later_profile_edits(self):
        self.installed_skill.mkdir(parents=True)
        original_skill = b"user's older skill"
        (self.installed_skill / "SKILL.md").write_bytes(original_skill)
        self.run_install()
        (self.skill_source / "SKILL.md").write_text("new skill revision", encoding="utf-8")
        update = self.run_install()
        self.assertEqual(update["status"], "updated")
        later = b"- id: unrelated-later-plugin\r\n  config: {}\r\n"
        self.profile.write_bytes(self.profile.read_bytes() + later)
        removed = self.run_install(uninstall=True)
        self.assertEqual(removed["status"], "uninstalled")
        self.assertEqual(self.profile.read_bytes(), self.original + later)
        self.assertEqual((self.installed_skill / "SKILL.md").read_bytes(), original_skill)
        self.assertEqual(self.run_install(uninstall=True)["status"], "not_installed")

    def test_uninstall_keeps_identical_preexisting_skill(self):
        import shutil
        shutil.copytree(self.skill_source, self.installed_skill)
        before = installer._inventory(self.installed_skill)
        self.run_install()
        self.run_install(uninstall=True)
        self.assertEqual(installer._inventory(self.installed_skill), before)

    def test_new_global_skill_is_preserved_in_uninstall_backup(self):
        self.run_install()
        before = installer._inventory(self.installed_skill)
        result = self.run_install(uninstall=True)
        self.assertFalse(self.installed_skill.exists())
        self.assertEqual(installer._inventory(Path(result["backup"]) / "removed-skill"), before)

    def test_no_trailing_newline_roundtrip(self):
        no_newline = b"- id: first\n  config: {}"
        self.profile.write_bytes(no_newline)
        self.run_install()
        self.run_install(uninstall=True)
        self.assertEqual(self.profile.read_bytes(), no_newline)

    def test_foreign_registration_and_extra_skill_files_refuse_without_writes(self):
        conflict = self.original + b"- id: fish-proteus-desktop-tool\n"
        self.profile.write_bytes(conflict)
        with self.assertRaisesRegex(ValueError, "separate desktop registration"):
            self.run_install()
        self.assertEqual(self.profile.read_bytes(), conflict)
        self.profile.write_bytes(self.original)
        self.installed_skill.mkdir(parents=True)
        extra = self.installed_skill / "user-custom.md"
        extra.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "extra files"):
            self.run_install()
        self.assertEqual(extra.read_text(), "preserve")
        self.assertEqual(self.profile.read_bytes(), self.original)

    def test_user_changes_to_managed_block_or_skill_refuse_update_and_uninstall(self):
        self.run_install()
        current = self.profile.read_bytes()
        self.profile.write_bytes(current.replace(b"stateRoot:", b"userStateRoot:"))
        with self.assertRaisesRegex(ValueError, "block was edited"):
            self.run_install()
        with self.assertRaisesRegex(ValueError, "block was edited"):
            self.run_install(uninstall=True)
        self.profile.write_bytes(current)
        (self.installed_skill / "SKILL.md").write_text("user edits", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "skill was edited"):
            self.run_install(uninstall=True)

    def test_malformed_markers_refuse_without_mutation(self):
        for suffix in (installer.BEGIN, installer.END + b"\n" + installer.BEGIN,
                       installer.BEGIN + b"\n" + installer.BEGIN + b"\n" + installer.END):
            content = self.original + suffix
            self.profile.write_bytes(content)
            with self.assertRaises(ValueError):
                self.run_install()
            self.assertEqual(self.profile.read_bytes(), content)

    def test_install_profile_write_failure_rolls_back_skill_and_profile(self):
        self.installed_skill.mkdir(parents=True)
        (self.installed_skill / "SKILL.md").write_text("old", encoding="utf-8")
        before_skill = installer._inventory(self.installed_skill)
        original_write = installer._atomic_write
        def fail_profile(path, data, *, expected):
            if path == self.profile:
                raise OSError("injected profile write failure")
            return original_write(path, data, expected=expected)
        with patch.object(installer, "_atomic_write", side_effect=fail_profile):
            with self.assertRaisesRegex(OSError, "injected"):
                self.run_install()
        self.assertEqual(self.profile.read_bytes(), self.original)
        self.assertEqual(installer._inventory(self.installed_skill), before_skill)
        self.assertFalse((self.home / ".fish-proteus817/install.lock").exists())

    def test_install_manifest_write_failure_rolls_back_profile_and_new_skill(self):
        original_write = installer._atomic_write
        def fail_manifest(path, data, *, expected):
            if path.name == "install.json":
                raise OSError("injected manifest write failure")
            return original_write(path, data, expected=expected)
        with patch.object(installer, "_atomic_write", side_effect=fail_manifest):
            with self.assertRaisesRegex(OSError, "injected"):
                self.run_install()
        self.assertEqual(self.profile.read_bytes(), self.original)
        self.assertFalse(self.installed_skill.exists())

    def test_uninstall_write_failure_restores_installed_state(self):
        self.installed_skill.mkdir(parents=True)
        (self.installed_skill / "SKILL.md").write_text("original", encoding="utf-8")
        first = self.run_install()
        before = self.profile.read_bytes()
        before_skill = installer._inventory(self.installed_skill)
        with patch.object(installer, "_atomic_write", side_effect=OSError("injected uninstall failure")):
            with self.assertRaisesRegex(OSError, "injected"):
                self.run_install(uninstall=True)
        self.assertEqual(self.profile.read_bytes(), before)
        self.assertEqual(installer._inventory(self.installed_skill), before_skill)
        self.assertTrue(Path(first["manifest"]).is_file())

    def test_atomic_write_refuses_concurrent_change(self):
        with self.assertRaisesRegex(ValueError, "File changed"):
            installer._atomic_write(self.profile, b"replacement", expected=b"stale")
        self.assertEqual(self.profile.read_bytes(), self.original)

    def test_missing_runtime_dependency_reports_once_install_command(self):
        with patch.object(installer, "_runtime_diagnostics", return_value={
            "python": "fixture", "pyyaml": False, "proteus": None,
            "errors": ['Install this interpreter dependency once: python -m pip install "PyYAML>=6,<7"']}):
            result = self.run_install(dry_run=True)
            self.assertEqual(result["status"], "not_ready")
            self.assertIn("pip install", result["errors"][0])
            with self.assertRaisesRegex(ValueError, "dependency once"):
                self.run_install()
        self.assertEqual(self.profile.read_bytes(), self.original)

    def test_missing_desktop_profile_is_not_silently_created(self):
        (self.profile.parent / "package.json").unlink()
        result = self.run_install(dry_run=True)
        self.assertEqual(result["status"], "not_ready")
        self.assertTrue(any("desktop profile" in error for error in result["errors"]))

    def test_source_update_changes_config_identity_and_reconciles_same_paths(self):
        first = self.run_install()
        before = self.profile.read_bytes()
        first_identity = first["plugin"]["sourceIdentity"]
        first_module = first["plugin"]["implementationModule"]
        first_id = first["plugin_id"]
        old_cache = Path(first["plugin_cache"]["directory"])
        original_js = (old_cache / "dsh_desktop_tool.mjs").read_bytes()
        self.assertEqual(self.run_install()["status"], "unchanged")
        (self.repo / "tools/dsh_desktop_tool.mjs").write_text("export const name='updated';", encoding="utf-8")
        second = self.run_install()
        self.assertEqual(second["status"], "updated")
        self.assertNotEqual(second["plugin"]["sourceIdentity"], first_identity)
        self.assertNotEqual(second["plugin"]["implementationModule"], first_module)
        self.assertEqual(second["plugin"]["plugin"], first["plugin"]["plugin"])
        self.assertEqual(second["plugin_id"], first_id)
        self.assertIn(("id: " + first_id).encode(), self.profile.read_bytes())
        self.assertEqual((old_cache / "dsh_desktop_tool.mjs").read_bytes(), original_js)
        self.assertEqual((Path(second["plugin_cache"]["directory"]) / "dsh_desktop_tool.mjs").read_bytes(),
                         (self.repo / "tools/dsh_desktop_tool.mjs").read_bytes())
        self.assertNotEqual(self.profile.read_bytes(), before)
        self.assertTrue(self.profile.read_bytes().startswith(self.original))
        self.assertEqual(self.run_install()["status"], "unchanged")

    def test_source_identity_includes_reviewed_backend_and_excludes_private_data(self):
        core = self.repo / "fish_proteus/core.py"
        core.parent.mkdir()
        core.write_text("# first backend", encoding="utf-8")
        runtime = self.repo / "runtime_adaptation/native.py"
        runtime.parent.mkdir()
        runtime.write_text("# first runtime", encoding="utf-8")
        private = self.repo / ".work/private.log"
        private.parent.mkdir()
        private.write_text("private raw data", encoding="utf-8")
        (self.repo / "public-release.json").write_text(json.dumps({"files": [
            "fish_proteus/core.py", "runtime_adaptation/native.py", ".work/private.log",
            "skills/fish-proteus817/SKILL.md", "skills/fish-proteus817/references/api.md"]}), encoding="utf-8")
        first = self.run_install()
        self.assertIn("fish_proteus/core.py", first["source_identity"]["files"])
        self.assertIn("runtime_adaptation/native.py", first["source_identity"]["files"])
        self.assertNotIn(".work/private.log", first["source_identity"]["files"])
        private.write_text("changed private raw data", encoding="utf-8")
        self.assertEqual(self.run_install()["status"], "unchanged")
        core.write_text("# second backend", encoding="utf-8")
        second = self.run_install()
        self.assertNotEqual(first["plugin"]["sourceIdentity"], second["plugin"]["sourceIdentity"])
        runtime.write_text("# second runtime", encoding="utf-8")
        third = self.run_install()
        self.assertNotEqual(second["plugin"]["sourceIdentity"], third["plugin"]["sourceIdentity"])

    def test_project_skill_shadow_is_diagnosed_without_modifying_it(self):
        local = self.repo / ".dsh/skills/fish-proteus817"
        local.mkdir(parents=True)
        (local / "SKILL.md").write_bytes(b"older project skill")
        before = installer._inventory(local)
        result = self.run_install()
        self.assertTrue(result["project_skill_update_required"])
        self.assertFalse(result["project_skill"]["matches_source"])
        self.assertIn("dsh_install_skill.py", result["project_skill"]["update_command"])
        self.assertTrue(result["warnings"])
        self.assertEqual(installer._inventory(local), before)
        import shutil
        shutil.copytree(self.skill_source, local, dirs_exist_ok=True)
        self.assertFalse(self.run_install()["project_skill_update_required"])

    def test_source_allowlist_escape_is_rejected_without_profile_mutation(self):
        (self.repo / "public-release.json").write_text(json.dumps({"files": [
            "fish_proteus/../../../outside.py"]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.run_install()
        self.assertEqual(self.profile.read_bytes(), self.original)

    def test_successful_dry_run_does_not_materialize_plugin_cache(self):
        result = self.run_install(dry_run=True)
        self.assertEqual(result["status"], "ready")
        self.assertFalse(Path(result["plugin_cache"]["directory"]).exists())
        self.assertFalse((self.home / ".fish-proteus817").exists())
        self.assertEqual(self.profile.read_bytes(), self.original)

    def test_plugin_cache_failure_leaves_profile_and_global_skill_unchanged(self):
        self.installed_skill.mkdir(parents=True)
        (self.installed_skill / "SKILL.md").write_text("preexisting", encoding="utf-8")
        before_skill = installer._inventory(self.installed_skill)
        original_write = installer._atomic_write
        def fail_module(path, data, *, expected):
            if path.name == "dsh_design_tool.mjs":
                raise OSError("injected module staging failure")
            return original_write(path, data, expected=expected)
        with patch.object(installer, "_atomic_write", side_effect=fail_module):
            with self.assertRaisesRegex(OSError, "staging failure"):
                self.run_install()
        self.assertEqual(self.profile.read_bytes(), self.original)
        self.assertEqual(installer._inventory(self.installed_skill), before_skill)
        self.assertFalse((self.home / ".fish-proteus817/install.json").exists())
        self.assertFalse(any((self.repo / ".work/desktop/plugins").glob(".stage-*")))

    def test_modified_cache_is_never_overwritten_and_uninstall_keeps_old_caches(self):
        first = self.run_install()
        cache = Path(first["plugin_cache"]["directory"])
        before_profile = self.profile.read_bytes()
        module = cache / "dsh_desktop_tool.mjs"
        original = module.read_bytes()
        module.write_bytes(b"unexpected cache alteration")
        with self.assertRaisesRegex(ValueError, "cache differs"):
            self.run_install()
        self.assertEqual(module.read_bytes(), b"unexpected cache alteration")
        self.assertEqual(self.profile.read_bytes(), before_profile)
        module.write_bytes(original)
        self.run_install(uninstall=True)
        self.assertEqual(module.read_bytes(), original)
        self.assertEqual((cache / "dsh_design_tool.mjs").read_bytes(),
                         (self.repo / "tools/dsh_design_tool.mjs").read_bytes())

    def test_direct_owned_entry_requires_unload_before_bootstrap_install(self):
        first = self.run_install()
        current = self.profile.read_bytes()
        legacy = current.replace(("id: " + first["plugin_id"]).encode(), ("id: " + installer.PLUGIN_ID).encode())
        self.profile.write_bytes(legacy)
        manifest_path = Path(first["manifest"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        bounds = installer._bounds(legacy)
        import hashlib
        manifest["block_sha256"] = hashlib.sha256(legacy[bounds[0]:bounds[1]]).hexdigest()
        manifest.pop("plugin_id")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        diagnosis = self.run_install(dry_run=True)
        self.assertEqual(diagnosis["status"], "not_ready")
        self.assertTrue(diagnosis["bootstrap_migration_required"])
        with self.assertRaisesRegex(ValueError, "uninstall"):
            self.run_install()
        self.assertEqual(self.profile.read_bytes(), legacy)
        self.run_install(uninstall=True)
        self.assertEqual(self.profile.read_bytes(), self.original)
        result = self.run_install()
        self.assertEqual(result["status"], "installed")
        self.assertEqual(result["plugin_id"], installer.BOOTSTRAP_ID)
        self.assertEqual(self.run_install()["status"], "unchanged")

    def test_bootstrap_source_change_requires_protocol_upgrade(self):
        first = self.run_install()
        before = self.profile.read_bytes()
        (self.repo / "tools/dsh_desktop_bootstrap.mjs").write_text("export const apply=async()=>{ /* protocol changed */ };", encoding="utf-8")
        diagnosis = self.run_install(dry_run=True)
        self.assertEqual(diagnosis["status"], "not_ready")
        self.assertTrue(diagnosis["bootstrap_protocol_update_required"])
        self.assertNotEqual(diagnosis["bootstrap_sha256"], first["bootstrap_sha256"])
        self.assertEqual(diagnosis["source_identity"], first["source_identity"])
        with self.assertRaisesRegex(ValueError, "bootstrap protocol"):
            self.run_install()
        self.assertEqual(self.profile.read_bytes(), before)

    def test_other_content_addressed_registration_outside_marker_is_rejected(self):
        conflict = self.original + ("- id: " + installer.PLUGIN_ID + "-0123456789abcdef\n").encode()
        self.profile.write_bytes(conflict)
        with self.assertRaisesRegex(ValueError, "separate desktop registration"):
            self.run_install()
        self.assertEqual(self.profile.read_bytes(), conflict)

    @unittest.skipUnless(HAS_YAML, "DSH desktop setup uses the optional PyYAML dependency")
    def test_empty_flow_profile_is_valid_idempotent_and_uninstalls_exactly(self):
        import yaml
        for original in (b"[]\n", b"[]", b"# empty desktop\r\n[ ] # keep this comment\r\n# footer\r\n",
                         b"\xef\xbb\xbf# BOM and comments\r\n[]\r\n",
                         b"%YAML 1.1\n---\n[\n# inside flow list\n]\n...\n"):
            with self.subTest(original=original):
                self.profile.write_bytes(original)
                installed = self.run_install()
                self.assertTrue(installed["empty_flow_profile_converted"])
                value = yaml.safe_load(self.profile.read_bytes())
                self.assertEqual(len(value), 1)
                self.assertEqual(value[0]["insert"][0]["id"], installer.BOOTSTRAP_ID)
                self.assertEqual(self.run_install()["status"], "unchanged")
                self.run_install(uninstall=True)
                self.assertEqual(self.profile.read_bytes(), original)

    @unittest.skipUnless(HAS_YAML, "DSH desktop setup uses the optional PyYAML dependency")
    def test_empty_flow_profile_uninstall_keeps_later_user_entries_and_comments(self):
        import yaml
        original = b"# header\r\n[] # original empty marker comment\r\n# footer\r\n"
        self.profile.write_bytes(original)
        self.run_install()
        later = b"- id: user-added-later\r\n  config: {enabled: true}\r\n"
        self.profile.write_bytes(self.profile.read_bytes() + later)
        self.run_install(uninstall=True)
        remaining = self.profile.read_bytes()
        self.assertEqual(yaml.safe_load(remaining), [{"id": "user-added-later", "config": {"enabled": True}}])
        self.assertIn(b"# header\r\n", remaining)
        self.assertIn(b"# original empty marker comment\r\n", remaining)
        self.assertIn(b"# footer\r\n", remaining)
        self.assertTrue(remaining.endswith(later))

    @unittest.skipUnless(HAS_YAML, "DSH desktop setup uses the optional PyYAML dependency")
    def test_empty_flow_original_survives_an_implementation_upgrade(self):
        original = b"# initial flow profile\r\n[]\r\n"
        self.profile.write_bytes(original)
        self.run_install()
        (self.repo / "tools/dsh_desktop_tool.mjs").write_text("export const name='later';", encoding="utf-8")
        self.assertEqual(self.run_install()["status"], "updated")
        self.run_install(uninstall=True)
        self.assertEqual(self.profile.read_bytes(), original)

    @unittest.skipUnless(HAS_YAML, "DSH desktop setup uses the optional PyYAML dependency")
    def test_changed_empty_flow_backup_refuses_uninstall_without_mutation(self):
        self.profile.write_bytes(b"[]\n")
        installed = self.run_install()
        before = self.profile.read_bytes()
        manifest = json.loads(Path(installed["manifest"]).read_text(encoding="utf-8"))
        Path(manifest["empty_flow_profile"]["original_profile"]).write_bytes(b"tampered backup")
        with self.assertRaisesRegex(ValueError, "backup changed"):
            self.run_install(uninstall=True)
        self.assertEqual(self.profile.read_bytes(), before)
        self.assertTrue(self.installed_skill.is_dir())


if __name__ == "__main__":
    unittest.main()
