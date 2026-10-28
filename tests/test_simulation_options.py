"""Bounded EOF option edits and archive/script integrity; no GUI in tests."""
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from fish_proteus.simulation_options import decode_options, rewrite_options, set_simulation_options
from fish_proteus.automation import Circuit, ProteusConfig, UnsupportedFormat


def fixture(rows=None):
    rows = rows or [('ABSTOL', '1e-12'), ('LOGSTART', '0'), ('LOGTIME', '0')]
    data = b'original synthetic prefix\0' + struct.pack('<I', len(rows))
    for key, value in rows:
        field = key.encode() + b'\0' + value.encode() + b'\0'
        data += struct.pack('<I', len(field)) + field
    return data


class SimulationOptionTests(unittest.TestCase):
    def test_add_remove_roundtrip_preserves_every_unrelated_byte(self):
        original = fixture()
        offset, values = decode_options(original)
        changed = rewrite_options(original, {'LOGFILE': r'C:\owned\trace.log'})
        self.assertEqual(changed[:offset], original[:offset])
        self.assertEqual(decode_options(changed)[1], dict(values, LOGFILE=r'C:\owned\trace.log'))
        self.assertEqual(rewrite_options(changed, {'LOGFILE': None}), original)

    def test_count_order_duplicate_and_trailing_data_are_rejected(self):
        bad = [fixture([('ABSTOL', '1'), ('LOGTIME', '0'), ('LOGSTART', '0')]),
               fixture([('ABSTOL', '1'), ('ABSTOL', '2'), ('LOGSTART', '0'), ('LOGTIME', '0')]),
               fixture() + b'unrecognized suffix']
        corrupt = bytearray(fixture())
        struct.pack_into('<I', corrupt, len(b'original synthetic prefix\0'), 4)
        for data in [*bad, bytes(corrupt)]:
            with self.subTest(data=data), self.assertRaises(UnsupportedFormat):
                decode_options(data)

    def test_unknown_keys_nonfinite_values_and_unsafe_log_strings_are_rejected(self):
        original = fixture()
        for changes in ({'COMMAND': 'run'}, {'LOGTIME': float('nan')}, {'LOGSTART': None},
                        {'LOGFILE': 'relative.log'}, {'LOGFILE': 'C:\\owned\ntrace.log'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                rewrite_options(original, changes)
        self.assertEqual(original, fixture())


@unittest.skipUnless(os.environ.get('FISH_GENERIC_TEST_LOCAL') == '1', 'Needs licensed local installation')
class LocalProjectOptionTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / '.work' / 'options-tests'
        root.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temporary.cleanup)
        self.root, self.config = Path(temporary.name), ProteusConfig.discover()

    def test_atomic_project_option_update_preserves_comment_and_other_members(self):
        c = Circuit(config=self.config)
        c.add('RESISTOR', 'R1', '10k', 0, 0)
        source = c.save(self.root / 'source.pdsprj')
        with ZipFile(source, 'a') as archive:
            archive.comment = b'original-comment'
        original = source.read_bytes()
        output = self.root / 'configured.pdsprj'
        set_simulation_options(source, output, {'LOGFILE': r'C:\owned\trace.log'}, config=self.config)
        self.assertEqual(source.read_bytes(), original)
        with ZipFile(source) as a, ZipFile(output) as b:
            self.assertEqual(a.comment, b.comment)
            self.assertEqual(a.namelist(), b.namelist())
            for name in a.namelist():
                if name != 'ROOT.DSN':
                    self.assertEqual(a.read(name), b.read(name))
        before = output.read_bytes()
        with self.assertRaises(FileExistsError):
            set_simulation_options(source, output, {'LOGFILE': r'C:\owned\other.log'}, config=self.config)
        self.assertEqual(output.read_bytes(), before)
        set_simulation_options(output, output, {'LOGFILE': None}, config=self.config, overwrite=True)
        self.assertNotIn('LOGFILE', Circuit.open(output, config=self.config).simulation_options())

    def test_power_registry_is_persistent_idempotent_and_preserves_other_entries(self):
        c = Circuit(config=self.config)
        metadata = ET.fromstring(c._members['PROJECT.XML'])
        scripts = metadata.find('SCRIPTS')
        if scripts is None:
            scripts = ET.SubElement(metadata, 'SCRIPTS')
        ET.SubElement(scripts, 'STRING').text = 'EXISTING.DAT'
        c._members['PROJECT.XML'] = ET.tostring(metadata)
        rails, bindings = {'GND': 0, 'VCC': 3.3}, {'VDD': 'VCC', 'VSS': 'GND'}
        c.configure_power(rails, bindings).configure_power(rails, bindings)
        output = c.save(self.root / 'power.pdsprj')
        with ZipFile(output) as archive:
            metadata = ET.fromstring(archive.read('PROJECT.XML'))
            names = [entry.text for entry in metadata.find('SCRIPTS').findall('STRING')]
        self.assertEqual(names.count('PWRRAILS.DAT'), 1)
        self.assertIn('EXISTING.DAT', names)
        self.assertEqual(Circuit.open(output, config=self.config).power_rails()['bindings'], bindings)


if __name__ == '__main__':
    unittest.main()
