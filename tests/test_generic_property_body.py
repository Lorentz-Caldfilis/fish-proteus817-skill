"""Native property-body and safe-display rules using original synthetic records.

The byte-layout assertions are independent of the production decoder, so an
encoder/decoder pair cannot agree on the former missing-body representation.
No installed library, private project, filesystem fixture or GUI is required.
"""
import struct
import unittest

from fish_proteus._vendor.proteus_auto.component_codec import _render_component
from fish_proteus._vendor.proteus_auto.proteus_project import _dsn_component, UnsupportedFormat


def synthetic_tail(role, style):
    """Author the minimal typed-text attributes, not bytes from a real project."""
    attributes = bytearray(34)
    struct.pack_into("<ii", attributes, 0, 100, 200)
    attributes[13] = 0x10
    struct.pack_into("<I", attributes, 14, role)
    attributes[31:33] = b"\x20\xff"
    return bytes(attributes) + b"UnitTestFont\0" + style.encode("ascii") + b"\0" + bytes(4)


def synthetic_template(length, show):
    properties = "K=" + "A" * (length - 3) + "\n"
    return {
        "x": 100, "y": 200, "device": "SYNTHETIC", "symbol": "SYNTHSYM",
        "package": "", "pins": [("A", "1"), ("B", "2")],
        "instance": bytes(33), "properties": properties, "show_properties": show,
        "text_tails": [synthetic_tail(role, style) for role, style in (
            (50, "COMPONENT ID"), (53, "COMPONENT VALUE"),
            (53, "COMPONENT VALUE"), (48, "PROPERTIES"))],
    }


def independent_layout(record):
    """Walk known text headers and C strings without the codec's parsing helpers."""
    cursor, texts, prefixes = 1, [], []  # leading byte: component record tag
    for _ in range(4):
        if record[cursor] != 0xFF:
            raise AssertionError("Synthetic typed text marker was lost")
        prefixes.append(cursor)
        size = record[cursor + 1]
        start = cursor + 2
        texts.append(record[start:start + size].decode("ascii"))
        attributes = start + size
        font_end = record.index(b"\0", attributes + 34)
        style_end = record.index(b"\0", font_end + 1)
        cursor = style_end + 1 + 4  # four-byte text-record terminator
    length = int.from_bytes(record[cursor:cursor + 4], "little")
    return texts, length, cursor + 4, prefixes[3]


def legacy_display_input(record, display):
    """Manually build a reader-only input; the writer must never emit this form.

    A legacy/foreign long display can load, but native Save corrupts that inline
    buffer. Test reader compatibility without asking the encoder to recreate it.
    """
    _texts, _length, _body_start, prefix = independent_layout(record)
    old_length = record[prefix + 1]
    raw = display.encode("ascii")
    if len(raw) >= 255:
        raise AssertionError("The synthetic legacy input uses a short text length")
    return record[:prefix + 1] + bytes([len(raw)]) + raw + record[prefix + 2 + old_length:]


class GenericPropertyBodyTests(unittest.TestCase):
    def render(self, length, show):
        template = synthetic_template(length, show)
        record, _entity, _cdb = _render_component(template, "R1", "2k", 100, 200, 7)
        return template, record

    def test_50_and_51_byte_boundaries_with_visible_and_hidden_preferences(self):
        # 53 also represents the native-save failure that motivated the safe
        # display rule; the 50/51 pair checks its exact format boundary.
        for length in (50, 51, 53):
            for show in (False, True):
                with self.subTest(length=length, show_properties=show):
                    template, record = self.render(length, show)
                    texts, declared, body_start, _prefix = independent_layout(record)
                    self.assertEqual(declared, length)
                    self.assertEqual(texts[:3], ["R1", "2k", "SYNTHETIC"])
                    properties = template["properties"]
                    # Long inline displays can load but corrupt on native Save.
                    # Both show preferences must therefore produce an empty
                    # display above 50, while retaining the independent body.
                    visible = properties if length == 50 else ""
                    self.assertEqual(texts[3], visible)
                    if length > 50:
                        self.assertEqual(record[body_start:body_start + length], properties.encode("ascii"))
                        pin_start = body_start + length
                    else:
                        pin_start = body_start
                    # This independently proves whether bytes were added before
                    # the pin-count/symbol/instance suffix, not just a roundtrip.
                    self.assertEqual(record[pin_start:pin_start + 2], b"\x02\x00")
                    symbol_size = record[pin_start + 2]
                    self.assertEqual(record[pin_start + 3:pin_start + 3 + symbol_size], b"SYNTHSYM")
                    self.assertEqual(len(record), pin_start + 3 + symbol_size + 33)
                    parsed = _dsn_component(record, 1)
                    self.assertEqual(parsed["fields"][3]["text"], properties)
                    self.assertEqual(parsed["pin_count"], 2)
                    self.assertEqual(parsed["instance_id"], 7)
                    if length > 50:
                        self.assertEqual(parsed["fields"][3]["display_text"], visible)

    def test_long_body_is_authoritative_when_display_has_same_length_other_text(self):
        template, record = self.render(51, True)
        self.assertEqual(independent_layout(record)[0][3], "")
        record = legacy_display_input(record, template["properties"])
        _texts, length, body_start, _prefix = independent_layout(record)
        actual_body = b"K=" + b"B" * 48 + b"\n"
        self.assertEqual(len(actual_body), length)
        modified = record[:body_start] + actual_body + record[body_start + length:]
        parsed = _dsn_component(modified, 1)
        self.assertEqual(parsed["fields"][3]["display_text"], template["properties"])
        self.assertEqual(parsed["fields"][3]["text"], actual_body.decode("ascii"))
        self.assertEqual(parsed["symbol"], "SYNTHSYM")

    def test_missing_long_body_is_rejected_even_with_full_visible_text(self):
        for visible in (False, True):
            with self.subTest(legacy_full_display=visible):
                template, record = self.render(51, True)
                if visible:
                    record = legacy_display_input(record, template["properties"])
                _texts, length, body_start, _prefix = independent_layout(record)
                # Retain a well-formed pin/instance suffix. The old decoder
                # incorrectly accepted this when display_text held all 51 bytes.
                missing = record[:body_start] + record[body_start + length:]
                with self.assertRaises(UnsupportedFormat):
                    _dsn_component(missing, 1)


if __name__ == "__main__":
    unittest.main()
