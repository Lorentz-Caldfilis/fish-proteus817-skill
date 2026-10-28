# Runtime adaptation sources

`native.py` and `session.py` adapt the PID-scoped Win32 menu, ADI and SDF helpers from
`kudoumakoto6523-design/Proteus_automatic_package`, upstream commit
`7439819a7ea4cff47fb9b321d8b0e97ac74fafb2` (MIT; see LICENSE.upstream).

The 8.17 adaptation enumerates hidden owned windows and refreshes native command UI
with `WM_INITMENUPOPUP` before interpreting menu state. The upstream 8.16 private
memory offsets and DLL allowlists are not used or bypassed.

The capture timebase is configured in the disposable DSN instance property
HORIZVAL using an equal-length numeric replacement. The actual displayed value
is then read independently with Windows OCR before pixel measurements. No
physical mouse, global keyboard input, private process memory or focus-policy
changes are needed.

The switch adapter assigns two unused native actuator key slots through ADI,
checks the logical SDF read-back, saves only the disposable project, and reopens
it before simulation. It then sends PID-scoped native commands while paused.
Input pin colors and the D0..D7 LED display are sampled independently; grey
loaded PB pins are never interpreted as digital high values.

Proteus executables, models, component libraries and teacher course files are not
distributed by this adaptation. `upstream/`, `baseline_timer/`, probes and probe
outputs are development material rather than package dependencies.
