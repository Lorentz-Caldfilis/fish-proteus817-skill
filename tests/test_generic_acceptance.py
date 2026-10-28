"""Intent checks are original synthetic data; real local library tests are opt-in."""
import copy
import os
from pathlib import Path
import tempfile
import unittest

from tools.generic_structure_acceptance import (assert_partition, canonical_groups,
                                               compare_native_graph, run_acceptance, sha256,
                                               vendor_dependency_audit)


class IndependentIntentTests(unittest.TestCase):
    def graph(self):
        return {"parts": {"C1": {"device": "CAPACITOR", "value": "100n"},
                          "C2": {"device": "CAPACITOR", "value": "220n"},
                          "C3": {"device": "CAPACITOR", "value": "330n"}},
                "nets": [{"name": "arbitrary", "pins": [{"ref": "C1", "pin": "1"},
                                                          {"ref": "C2", "pin": "1"},
                                                          {"ref": "C3", "pin": "1"}]},
                         *[{"name": str(i), "pins": [{"ref": f"C{i}", "pin": "2"}]}
                           for i in range(1, 4)]]}

    def expected(self):
        return {"parts": {"C1": {"device": "CAPACITOR", "value": "100n"},
                          "C2": {"device": "CAPACITOR", "value": "220n"},
                          "C3": {"device": "CAPACITOR", "value": "330n"}},
                "net_groups": [["C1.1", "C2.1", "C3.1"], ["C1.2"], ["C2.2"], ["C3.2"]]}

    def test_order_and_net_names_are_immaterial(self):
        graph = self.graph()
        graph["nets"].reverse()
        graph["nets"][-1]["pins"].reverse()
        result = compare_native_graph(graph, self.expected())
        self.assertEqual(result["pins_checked"], 6)
        self.assertFalse(result["provenance_verified"])
        self.assertEqual(result["runtime_status"], "not_run")

    def test_unexpected_bridge_is_rejected(self):
        graph = self.graph()
        graph["nets"][0]["pins"] += graph["nets"].pop()["pins"]
        with self.assertRaisesRegex(AssertionError, "partition"):
            compare_native_graph(graph, self.expected())

    def test_missing_surviving_branch_is_rejected(self):
        graph = self.graph()
        graph["nets"][0]["pins"].pop()
        with self.assertRaisesRegex(AssertionError, "partition"):
            compare_native_graph(graph, self.expected())

    def test_wrong_value_and_unexpected_component_are_rejected(self):
        for field in ("value", "extra_part"):
            graph = self.graph()
            if field == "value":
                graph["parts"]["C2"]["value"] = "221n"
            else:
                graph["parts"]["UNEXPECTED1"] = {"device": "RESISTOR", "value": "1k"}
            with self.subTest(field=field), self.assertRaises(AssertionError):
                compare_native_graph(graph, self.expected())

    def test_duplicate_endpoint_is_not_hidden_by_set_conversion(self):
        for groups in ([["R1.1", "R1.1"]], [["R1.1"], ["R1.1"]], [[]]):
            with self.subTest(groups=groups), self.assertRaises(AssertionError):
                canonical_groups(groups)

    def test_three_four_and_six_way_topologies(self):
        for size in (3, 4, 6):
            groups = [[f"C{i}.1" for i in range(1, size + 1)],
                      [f"C{i}.2" for i in range(1, size + 1)]]
            actual = copy.deepcopy(groups)
            actual.reverse()
            self.assertEqual(assert_partition(actual, groups), 2 * size)
            actual[0].append(actual[1].pop())
            with self.assertRaises(AssertionError):
                assert_partition(actual, groups)

    def test_vendor_dependency_closure_and_source_identity(self):
        self.assertEqual(vendor_dependency_audit()["status"], "passed")


@unittest.skipUnless(os.environ.get("FISH_GENERIC_TEST_LOCAL") == "1",
                     "Requires the licensed local Proteus library; no GUI is launched")
class LocalFileAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(__file__).resolve().parents[1] / ".work" / "generic-structure-review-tests"
        base.mkdir(parents=True, exist_ok=True)
        # Keep evidence for inspection; every invocation gets an unused output path.
        folder = Path(tempfile.mkdtemp(prefix="run-", dir=base))
        cls.report_path = folder / "matrix" / "acceptance.json"
        cls.report = run_acceptance(folder / "matrix")

    def verify_case(self, name):
        row = next(row for row in self.report["results"] if row["name"] == name)
        self.assertEqual(row["status"], "file_verified", row)
        self.assertEqual(row["native_status"], "not_run")
        self.assertEqual(row["runtime_status"], "not_run")

    def test_catalogue_and_nine_definition_instances(self):
        self.verify_case("catalogue-imports")

    def test_six_way_bus_anchor_deletion_and_six_terminal_kinds(self):
        self.verify_case("six-way-buses")

    def test_wire_labels_join_disjoint_nets_and_preserve_geometry(self):
        self.verify_case("wire-labels")

    def test_variable_fields_geometry_and_atomic_rejection(self):
        self.verify_case("component-edits")

    def test_empty_saved_file_uses_configured_fallback(self):
        self.verify_case("empty-fallback")

    def test_stale_save_as_and_unknown_version_rejection(self):
        self.verify_case("stale-and-unknown")

    def test_power_revision_reversible_and_installation_protected(self):
        self.verify_case("revision-protection")

    def test_all_loaded_official_inputs_remain_unchanged(self):
        self.assertTrue(self.report["sources_unchanged"], str(self.report_path))
        self.assertEqual(self.report["native_status"], "not_run")
        self.assertEqual(self.report["runtime_status"], "not_run")

    def test_acceptance_refuses_reusing_its_existing_evidence_directory(self):
        before = sha256(self.report_path)
        with self.assertRaisesRegex(ValueError, "unused"):
            run_acceptance(self.report_path.parent)
        self.assertEqual(sha256(self.report_path), before)


if __name__ == "__main__":
    unittest.main()
