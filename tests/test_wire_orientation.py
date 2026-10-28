"""Original synthetic records for a native-confirmed 8.17 wire contract.

Native two-pin wires start with the earlier component's endpoint; pins of the
same component use pin-table order. Reversing a connection must reverse its
entire path, preserving bends and labels. No licensed project is used here.
"""
import copy
import struct
import unittest

from fish_proteus._vendor.proteus_auto.net_objects import read_wire
from fish_proteus._vendor.proteus_auto.proteus_project import UnsupportedFormat
from fish_proteus._vendor.proteus_auto.wire_codec import encode_connected_body


BODY_OFFSET = 4096
FORWARD_POINTS = [(0, 0), (1000000, 0), (1000000, 2000000), (3000000, 2000000)]


def two_component_model():
    """The first component sorts last lexically, and the object sizes differ."""
    prefixes = [b"ORIGINAL_SYNTHETIC_OLDER_OBJECT", b"SYNTHETIC_NEWER"]
    objects = [prefix + bytes(4) for prefix in prefixes]
    parts = [dict(ref="Z_OLDER1", device="SYNTH_OUTPUT", x=0, y=0),
             dict(ref="A_NEWER2", device="SYNTH_INPUT", x=3000000, y=2000000)]
    templates = {
        "SYNTH_OUTPUT": {"pins": [("OUT", "1")], "pin_offsets": {"OUT": (0, 0)},
                         "pin_directions": {"OUT": (1, 0)}},
        "SYNTH_INPUT": {"pins": [("IN", "1")], "pin_offsets": {"IN": (0, 0)},
                        "pin_directions": {"IN": (-1, 0)}},
    }
    return prefixes, objects, parts, templates


def encoded_wire(objects, parts, templates, connections, prefix):
    """Read the emitted record through its actual first pin reference."""
    body = encode_connected_body(objects, parts, templates, connections, BODY_OFFSET)
    object_start = body.index(prefix)
    pointer = struct.unpack_from("<I", body, object_start + len(prefix))[0]
    # read_wire accepts a complete DSN member and native absolute offsets.
    decoded = read_wire(bytes(BODY_OFFSET) + body, pointer)
    return body, pointer, decoded


class WireOrientationTests(unittest.TestCase):
    def test_reversed_explicit_connection_keeps_the_complete_older_first_path(self):
        prefixes, objects, parts, templates = two_component_model()
        forward = [dict(first=("Z_OLDER1", "OUT"), second=("A_NEWER2", "IN"),
                        points=list(FORWARD_POINTS))]
        reverse = [dict(first=("A_NEWER2", "IN"), second=("Z_OLDER1", "OUT"),
                        points=list(reversed(FORWARD_POINTS)))]
        expected_offset = BODY_OFFSET + sum(map(len, objects))
        bodies = []
        for connection in (forward, reverse):
            with self.subTest(first=connection[0]["first"]):
                body, pointer, wire = encoded_wire(objects, parts, templates, connection, prefixes[0])
                self.assertEqual(wire["points"], FORWARD_POINTS)
                self.assertEqual(pointer, expected_offset, "Wire belongs after the later component's pin table")
                bodies.append(body)
        self.assertEqual(bodies[0], bodies[1], "Equivalent endpoint ordering must not change emitted geometry")

    def test_automatic_connection_uses_component_order_not_reference_sorting(self):
        prefixes, objects, parts, templates = two_component_model()
        for first, second in ((("Z_OLDER1", "OUT"), ("A_NEWER2", "IN")),
                              (("A_NEWER2", "IN"), ("Z_OLDER1", "OUT"))):
            with self.subTest(first=first):
                connection = [dict(first=first, second=second, points=None)]
                _, _, wire = encoded_wire(objects, parts, templates, connection, prefixes[0])
                self.assertEqual(wire["points"][0], FORWARD_POINTS[0])
                self.assertEqual(wire["points"][-1], FORWARD_POINTS[-1])

    def test_same_component_uses_pin_table_order_not_pin_name_sorting(self):
        prefix = b"ORIGINAL_TWO_PIN_SYNTHETIC"
        objects = [prefix + bytes(8)]
        parts = [dict(ref="X1", device="SYNTHETIC", x=0, y=0)]
        templates = {"SYNTHETIC": {"pins": [("Z_FIRST", "9"), ("A_SECOND", "2")],
                                   "pin_offsets": {"Z_FIRST": (0, 0), "A_SECOND": (3000000, 2000000)},
                                   "pin_directions": {"Z_FIRST": (1, 0), "A_SECOND": (-1, 0)}}}
        for first, second, points in (("Z_FIRST", "A_SECOND", FORWARD_POINTS),
                                      ("A_SECOND", "Z_FIRST", list(reversed(FORWARD_POINTS)))):
            with self.subTest(first=first):
                connection = [dict(first=("X1", first), second=("X1", second), points=points)]
                _, _, wire = encoded_wire(objects, parts, templates, connection, prefix)
                self.assertEqual(wire["points"], FORWARD_POINTS)

    def test_reversal_retains_positioned_labels_and_does_not_mutate_input(self):
        prefixes, objects, parts, templates = two_component_model()
        labels = [{"text": "ORIGINAL_BEND_LABEL", "position": (1000000, 1000000),
                   "auto_position": False}]
        connection = [dict(first=("A_NEWER2", "IN"), second=("Z_OLDER1", "OUT"),
                           points=list(reversed(FORWARD_POINTS)), labels=labels)]
        untouched = copy.deepcopy((objects, parts, templates, connection))
        _, _, wire = encoded_wire(objects, parts, templates, connection, prefixes[0])
        self.assertEqual(wire["points"], FORWARD_POINTS)
        self.assertEqual([(row["text"], row["position"]) for row in wire["labels"]],
                         [("ORIGINAL_BEND_LABEL", (1000000, 1000000))])
        self.assertEqual((objects, parts, templates, connection), untouched)

    def test_new_diagonal_or_zero_length_routes_still_refuse(self):
        _, objects, parts, templates = two_component_model()
        invalid = [[FORWARD_POINTS[0], FORWARD_POINTS[-1]],
                   [FORWARD_POINTS[0], FORWARD_POINTS[0], *FORWARD_POINTS[1:]]]
        for points in invalid:
            with self.subTest(points=points), self.assertRaises(UnsupportedFormat):
                encode_connected_body(objects, parts, templates,
                                      [dict(first=("Z_OLDER1", "OUT"), second=("A_NEWER2", "IN"),
                                            points=points)], BODY_OFFSET)


if __name__ == "__main__":
    unittest.main()
