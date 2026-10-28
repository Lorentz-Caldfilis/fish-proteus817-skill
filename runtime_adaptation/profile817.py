"""Build-specific, independently inspected read-only ABI for Proteus 8.17 SP2.

The profile is selected only for the exact local PDS/module bytes. It does not
authorize arbitrary offsets or mutate Proteus. RVAs below were derived from the
8.17 PE export tables, MSVC RTTI and constructor/getter instructions, separately
from the upstream 8.16 layout. Live readers additionally validate ownership,
loaded image headers and object identity before each bounded snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType
from typing import Mapping


class CompatibilityError(RuntimeError):
    """The requested native ABI has not been established for this installation."""


@dataclass(frozen=True)
class NativeProfile:
    identifier: str
    pds_sha256: str
    hashes: Mapping[str,str]
    layout: Mapping[str,int]

    def describe(self):
        return {'id':self.identifier,'product':'Proteus 8.17 SP2',
                'pds_file_version':'8.17.37159','machine':'x86',
                'pds_sha256':self.pds_sha256,'module_sha256':dict(self.hashes),
                'reader':'bounded-read-only-owned-PID','layout':dict(self.layout)}


PROFILE817=NativeProfile(
    'proteus-8.17-sp2-37159',
    '0c867df27ff9f472290ae7a0441650ce2b3608988e5f05884241e89b824e561e',
    MappingProxyType({
        'ISIS.DLL':'9f063e377c882aa8a9e7b26436ccdd2e01c581dbaa1c12b3a76e7cbac285a319',
        'NETLIST.DLL':'2e260e0a60e49875bdb6ce76b655337e89ef94f069d8f2e9f0531a3a037fc224',
        'PRIMS.DLL':'7b37fd3b5dbe4432c4c47ca8de9e9ae43a9e5ac76c1e4337369fa5b3816f03b8',
        'VSMDEBUG.DLL':'e14cd7a67ddaff61212b09da34b0f6282bf7b9806b4003909beebdeba5d5560c',
    }),
    MappingProxyType({
        'isis_view_vtable':0xA0D24,'isis_editor_vtable':0xA0B70,
        'editor_view_offset':0x5C8,'editor_simctrl_offset':0x1BCC,
        'debug_ctrl_vtable':0x3EBA8,'debug_module_vtable':0x3EAF0,
        'debug_ctrl_offset':0x5D8,'debug_module_view_offset':0x180C,
        'timer_state_offset':0x1254,'timer_engine_offset':0x998,
        'timer_remaining_offset':0x1278,'timer_current_offset':0x1280,
        'net_getcdb_rva':0x4250,'net_cdb_global':0x492F0,
        'cdb_count_offset':0x28C,'element_icdb_offset':0x9C,
        'component_icdb_offset':0x38,'isis_active_vtable':0x9AB1C,
        'isis_active_icdb_vtable':0x9AC84,'isis_passive_icdb_vtable':0xA201C,
        'prims_property_vtable':0x11B00,
    }))


def _rva_bytes(data,rva,length):
    if data[:2]!=b'MZ':raise CompatibilityError('Expected a PE image')
    pe=struct.unpack_from('<I',data,60)[0]
    if data[pe:pe+4]!=b'PE\0\0':raise CompatibilityError('Invalid PE signature')
    machine,sections=struct.unpack_from('<HH',data,pe+4)
    optional_size=struct.unpack_from('<H',data,pe+20)[0]
    if machine!=0x14c or struct.unpack_from('<H',data,pe+24)[0]!=0x10b:
        raise CompatibilityError('This native profile requires x86 PE32 images')
    for index in range(sections):
        entry=pe+24+optional_size+40*index
        virtual_size,virtual,raw_size,raw=struct.unpack_from('<IIII',data,entry+8)
        if virtual<=rva and rva+length<=virtual+raw_size:
            return data[raw+rva-virtual:raw+rva-virtual+length]
    raise CompatibilityError(f'RVA {rva:#x} is outside image file sections')


def profile_for(executable: str | Path) -> NativeProfile:
    """Verify the executable, modules and ABI evidence before using the profile."""
    path=Path(executable).resolve(strict=True)
    if path.name.upper()!='PDS.EXE':raise CompatibilityError('Expected PDS.EXE')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=PROFILE817.pds_sha256:
        raise CompatibilityError('Unsupported PDS executable build for native 8.17 observation')
    contents={}
    for name,expected in PROFILE817.hashes.items():
        file=path.parent/name
        if not file.is_file():raise CompatibilityError(f'Missing native module {name}')
        data=file.read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:
            raise CompatibilityError(f'Unsupported {name} build for native 8.17 observation')
        contents[name]=data
    # The actual 8.17 getters expose the timer state and double clock. These
    # checks substantiate the field offsets in addition to exact file hashes.
    signatures=(
        ('VSMDEBUG.DLL',0x60F0,bytes.fromhex('83b95412000004740f83b99809000000')),
        ('VSMDEBUG.DLL',0x6160,bytes.fromhex('dd8180120000c3')),
        ('NETLIST.DLL',0x4250,bytes.fromhex('a1f0920410c3')),
        ('NETLIST.DLL',0x13E1,bytes.fromhex('3b818c020000')),
    )
    for module,rva,expected in signatures:
        if _rva_bytes(contents[module],rva,len(expected))!=expected:
            raise CompatibilityError(f'{module} ABI getter evidence mismatch at {rva:#x}')
    return PROFILE817
