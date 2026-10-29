# Planning and evidence

## New topology

1. Read capabilities, search/get installed devices and derive independent electrical/logic expectations. Select a library explicitly if names are ambiguous.
2. Create, import actual definitions and add components; inspect pins/locations before connecting. Use fresh expected revisions for edits, labels, terminals and power configuration. A format template is a container, not a finished answer.
3. Inspect saved files and check intended connectivity/isolation/properties. Inspect visible placement when relevant; automatic connectivity routing is not a general obstacle-avoidance engine.
4. When enabled, open an owned native sequence, export SDF and compare actual structure against intent. An opened window alone is insufficient.
5. Measure behavior through supported existing graphs, firmware events or explicitly supported readers. Missing models, graphs or trustworthy observations remain blocked/unsupported.

Compose the requested topology from generic operations instead of copying a complete fixed answer. Device/pin names and model support come from the actual installation.

When setting power rails, distinguish rail definitions from the named-net
bindings. In the validated STM32/LOGICSTATE design, defining `VCC=3.3` and
`GND=0` did not by itself bind the nets named VCC and GND. Include `VCC -> VCC`
and `GND -> GND` as well as the processor supply-pin bindings (for example
`VDD` and `VDDA` to VCC, `VSS` and `VSSA` to GND). An actual generated-circuit
comparison failed native compilation without the two self-bindings and produced
GPIO 010 after adding them. Inspect the actual nets for other devices rather
than assuming their power names or voltages.

## Existing graph analysis

Open preserves a fully recognized existing sheet. Unknown objects block reconstruction. Explicit stage copies an opaque graph-based input for native/bounded generator operations without granting whole-sheet rewriting.

Inspect actual generators/graphs; do not invent graph/probe creation APIs. Derive an expected response independently, export with simulate=true, and preserve raw CSV. Repeated columns require occurrence; sampling cannot extrapolate. Recalculate after changing amplitude; an old graph cache is not new evidence. Keep parameter revision, graph identity and units from actual axis/trace labels.

## Firmware and controls

Register firmware with the host or select an exact embedded member. Firmware inspection checks actual ELF/HEX bytes, checksums/bounds and hash; format validity is not CPU compatibility or execution. Assign the ID to the actual processor and check native PROGRAM/model clock.

Bind controls in a structural edit, save, then open a new session. Supported binary controls are build/profile dependent and key collisions are rejected. Read controls/control_state separately from downstream GPIO. A complete input-response test uses one run_sequence, with time advancing after changes and native outputs acquired in all phases. Separate sequences do not share a PID.

CM3 GPIO events are digital drives, not arbitrary pin voltages. Their timestamps are simulation events, not the current clock. A key command or mechanical position is not firmware-response proof.

GPIO logging also needs model-side trace configuration. For the tested
STM32F103R6 CM3 model, set the processor property `TRACE_GPIO="3"` in the saved
circuit before opening the native session, then confirm it in the native SDF.
This is the trace setting used by the validated PA0/PA5 path, not a GPIO pin
number or an electrical input. A complete LOGFILE with no GPIO events does not
prove a constant output; inspect trace configuration, firmware identity and
model support before repeating the same sequence. Do not assume the same
property or encoding exists on every microcontroller model.

Mixed verification reports take the weakest evidence basis. A report combining
SDF and successful time/GPIO checks can therefore be `native_verified`; inspect
the individual checks and levels. Do not repeat a simulation merely to obtain a
different aggregate label.

The native engine buffers LOGFILE until normal process exit. Log/GPIO/error steps capture actual request clocks and are resolved after stop/save/close. GPIO data is a prefix of the final raw log through its recorded clock, with complete/hash metadata; log/errors are final-run diagnostics, not an invented live view. Request GPIO while the clock is active and use a single engine epoch. Run reset and stop/restart tests separately so a reopened/truncated log cannot masquerade as earlier-phase output. No clipboard operation is needed for this route.

## Time, identity and cleanup

Define duration, tolerance/resolution and overshoot criteria before executing. Retain native start/end/actual_elapsed_seconds and completion from run_for. Unverified time remains actual_time_verified=false and simulation_seconds=null; never fill from wall time, sleep or a request. The course timer may use OCR and retains the same uncertainty boundary.

Keep owned session/PID/creation identity, input project snapshot and before/after hashes. A sequence attempts stop/save/close after a failed step; report cleanup errors. A model final does not prove a process closed. The tool cannot attach to or close an unrelated user instance.

Distinguish prepared inputs, parsed files, native SDF, observed runtime and passed assertions. Verify fresh artifacts against their matching revision/hash. Preserve failures and capability limits; selected successful cases do not establish every device/format or arbitrary register access.
