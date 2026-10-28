"""File-only split-import regressions; installed licensed inputs stay local."""
import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fish_proteus.automation import Circuit, ProteusConfig, UnsupportedFormat


@unittest.skipUnless(os.environ.get("FISH_GENERIC_TEST_LOCAL") == "1",
                     "Requires licensed local definitions; no GUI is launched")
class SplitImportFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = ProteusConfig.discover()
        cls.donor = cls.config.samples_root / (
            "VSM for Cortex M3/STM32/STMCubeMX LED Blink/STMCubeMX LED Blink.pdsprj")

    def setUp(self):
        base = Path(__file__).resolve().parents[1] / ".work" / "split-import-tests"
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="run-", dir=base)
        self.folder = Path(temporary.name).resolve()
        self.assertTrue(self.folder.is_relative_to(base.resolve()))
        self.addCleanup(temporary.cleanup)
        self.counter = 0
        self.protected = {p: hashlib.sha256(p.read_bytes()).digest()
                          for p in (self.donor, self.config.template_project)}
        self.addCleanup(self.check_protected_inputs)

    def check_protected_inputs(self):
        self.assertEqual(self.protected, {
            p: hashlib.sha256(p.read_bytes()).digest() for p in self.protected})

    def reopen(self, circuit):
        self.counter += 1
        path = circuit.save(self.folder / f"revision-{self.counter}.pdsprj")
        return Circuit.open(path, config=self.config)

    def imported(self, device):
        circuit = Circuit(config=self.config)
        if device == "STM32F103R6":
            circuit.import_from_project(self.donor, device)
        else:
            circuit.import_device(device, library="ACTIVE")
        return self.reopen(circuit)

    def test_logic_definition_survives_two_empty_saves_before_add(self):
        circuit = self.reopen(self.imported("LOGICSTATE"))
        self.assertEqual(circuit.components(), [])
        circuit.add("LOGICSTATE", "SW1", "0", 0, 0)
        circuit = self.reopen(circuit)
        self.assertEqual(circuit.components()[0]["device"], "LOGICSTATE")
        self.assertEqual([p["name"] for p in circuit.pins("SW1")], ["Q0"])

    def test_mcu_donor_definition_survives_empty_save_before_add(self):
        circuit = self.reopen(self.imported("STM32F103R6"))
        circuit.add("STM32F103R6", "U1", "STM32F103R6", 0, 0)
        circuit = self.reopen(circuit)
        self.assertEqual(circuit.components()[0]["device"], "STM32F103R6")
        self.assertIn("PA0-WKUP", {p["name"] for p in circuit.pins("U1")})
        self.assertIn("PA5", {p["name"] for p in circuit.pins("U1")})

    def test_independent_import_add_and_connect_revisions(self):
        circuit = self.imported("STM32F103R6")
        circuit.import_device("LOGICSTATE", library="ACTIVE")
        circuit = self.reopen(circuit)
        circuit.add("STM32F103R6", "U1", "STM32F103R6", 0, 0)
        circuit = self.reopen(circuit)
        circuit.add("LOGICSTATE", "SW1", "0", -7000000, -5000000)
        circuit = self.reopen(circuit)
        circuit.connect("U1.PA0-WKUP", "SW1.Q0")
        circuit = self.reopen(circuit)
        self.assertEqual({p["ref"] for p in circuit.components()}, {"U1", "SW1"})
        self.assertEqual(len(circuit.connections()), 1)
        endpoints = circuit.connections()[0]
        self.assertEqual({tuple(endpoints["first"]), tuple(endpoints["second"])},
                         {("U1", "PA0-WKUP"), ("SW1", "Q0")})

    def test_recovery_with_an_existing_component_preserves_it(self):
        circuit = Circuit(config=self.config)
        circuit.add("RESISTOR", "R1", "10k", 5000000, 0)
        circuit.import_device("LOGICSTATE", library="ACTIVE")
        circuit = self.reopen(circuit)
        before = circuit.components()
        circuit.add("LOGICSTATE", "SW1", "0", 0, 0)
        circuit = self.reopen(circuit)
        self.assertEqual(next(p for p in circuit.components() if p["ref"] == "R1"), before[0])

    def test_duplicate_import_still_refuses_without_replacing_definition(self):
        circuit = self.imported("STM32F103R6")
        before = circuit.revision, circuit._dsn, copy.deepcopy(circuit._members)
        with self.assertRaisesRegex(UnsupportedFormat, "already exists"):
            circuit.import_from_project(self.donor, "STM32F103R6")
        self.assertEqual((circuit.revision, circuit._dsn, circuit._members), before)
        circuit.add("STM32F103R6", "U1", "STM32F103R6", 0, 0)
        self.assertEqual(len(self.reopen(circuit).components()), 1)

    def test_invalid_add_changes_neither_cache_nor_saved_state(self):
        circuit = self.imported("LOGICSTATE")
        before = circuit.revision, copy.deepcopy(circuit.templates), circuit._dsn
        with self.assertRaises(UnsupportedFormat):
            circuit.add("LOGICSTATE", "SW1", "0", 0, 0, rotation=45)
        self.assertEqual((circuit.revision, circuit.templates, circuit._dsn), before)
        self.assertEqual(circuit.components(), [])
        circuit.add("LOGICSTATE", "SW1", "0", 0, 0)
        self.assertEqual(len(self.reopen(circuit).components()), 1)

    def test_unused_embedded_devices_are_not_eagerly_parsed(self):
        from fish_proteus._vendor.proteus_auto.device_library import describe_definition

        circuit = self.imported("STM32F103R6")
        circuit.import_device("LOGICSTATE", library="ACTIVE")
        self.counter += 1
        path = circuit.save(self.folder / f"revision-{self.counter}.pdsprj")
        target = "fish_proteus._vendor.proteus_auto.device_library.describe_definition"
        with patch(target, side_effect=AssertionError("Unused metadata was parsed")):
            circuit = Circuit.open(path, config=self.config)
        with patch(target, wraps=describe_definition) as parser:
            circuit.add("LOGICSTATE", "SW1", "0", 0, 0)
        self.assertEqual([call.args[0]["name"] for call in parser.call_args_list], ["LOGICSTATE"])

    def test_definition_remains_placeable_after_last_instance_is_deleted(self):
        circuit = self.imported("LOGICSTATE")
        circuit.add("LOGICSTATE", "SW1", "0", 0, 0)
        circuit = self.reopen(circuit)
        circuit.delete_component("SW1")
        circuit = self.reopen(circuit)
        self.assertEqual(circuit.components(), [])
        circuit.add("LOGICSTATE", "SW2", "1", 0, 0)
        self.assertEqual(self.reopen(circuit).components()[0]["ref"], "SW2")


if __name__ == "__main__":
    unittest.main()
