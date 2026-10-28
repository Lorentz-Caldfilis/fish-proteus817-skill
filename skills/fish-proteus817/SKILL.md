---
name: fish-proteus817
description: Create, inspect and edit supported Proteus 8.17 SP2 schematics from natural-language requests, using installed device definitions, pin connections, labels, terminals, power rails and firmware. Use the companion Python backend and typed DSH tool for owned native sessions, simulation sequences, binary controls, GPIO logs and existing graph CSV measurements. Includes 8086 course recipes.
license: MIT
compatibility: DeepSeek Harness, an interactive Windows desktop with Proteus 8.17 SP2, Python 3.10+, and the full companion repository with its dependencies. Device definitions, project templates and firmware are local user-supplied inputs. Model access may require network access.
metadata:
  author: "Fish for Proteus contributors"
  version: "0.2.2"
  source: "https://github.com/Lorentz-Caldfilis/fish-proteus817-skill"
---

# Proteus 8.17 SP2 design and simulation

Compose circuits from actual device definitions, components, pins and nets. The three 8086 course cases are optional recipes. Supported file layouts, device definitions and native capabilities must be checked for the current task; this skill does not promise arbitrary Proteus formats, all devices, PCB routing or new graph/probe creation.

Clone the [companion repository](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill) and follow its [setup instructions](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill/blob/main/README.md). Copying this skill alone does not provide its Python CLI, native adapter or DSH launcher. Keep DSH, Python, project files and Proteus on the same Windows desktop. The skill license is [MIT](LICENSE.txt); proprietary installed resources remain separate.

## Select the workflow

- For composable designs, use `fish_proteus_design`. Read [generic API](references/generic-api.md) for exact fields and [workflow and evidence](references/workflows-and-evidence.md) for planning and native verification.
- For the supplied 8086 divider, cascade or K0-controlled 8255 examples, the legacy `fish_proteus` tool/CLI remains available. Read [course recipes](references/cases-and-evidence.md).

The host fixes the task root, original input IDs, configuration and enabled actions. Use only those actions. Neither tool accepts arbitrary code, commands, executables or host paths. Do not broaden permissions, change directory ACLs, replace Proteus DLLs or modify global configuration to bypass a blocked route.

In a bounded DSH deployment without file-reading tools, load those references through `fish_proteus_design` with `action="help"` and `topic="actions"`, `"edits"`, `"steps"`, `"assertions"` or `"workflow"`. Read the relevant topic before using its signatures.

## Compose and inspect

Start with `action="capabilities"`. Check the service/protocol, registered input IDs, allowed actions, installed resources and native profile probe. An implemented API or matching fingerprint is not a completed native/runtime test.

Search the installed library, then inspect the exact device with its enumerated library selector. Duplicate device names can exist in different libraries. Read actual pins, properties and model requirements before importing or connecting; do not infer pin names from screen positions. Coordinates are signed native integers: **100000 = 1 mm**. Read the exact method contract before choosing angles, labels or property values.

Use `create` to construct a new topology in a format template, `open` to preserve a recognized registered project, or explicit `stage` for an opaque existing project that needs native or bounded generator-property operations. A failed `open` must not be replaced silently with a blank circuit. Originals, donors, installed libraries and samples remain unchanged.

Read the returned `current.revision`. Submit structured `edit.operations` with that `expected_revision`. Edits save a new managed project only after the entire batch succeeds. After changes, inspect the saved project and use the fresh revision. Resolve ambiguous devices, unknown objects or stale revisions instead of guessing. Automatic connectivity routing is not a general obstacle-avoidance layout engine; inspect visible layout when it matters.

Assign firmware through registered/extracted firmware IDs. Literal PROGRAM/file/script paths are disabled in the typed tool. Before interactive input, bind controls in the file layer, save, and open a new native session so the bindings actually load.

## Run and verify

Use an enabled `run_sequence` to keep ordered steps in one Session/PID. It always attempts to stop and close its owned process, and saves the task copy by default. Native property changes and explicit saves require a stopped simulation. Do not edit the same project concurrently in another process. Separate sequences create separate sessions; collect a complete input/output response sequence in one call when continuity matters.

The sequence can read native SDF, current simulation time, binary control position, CM3 GPIO events and existing graph CSV. Choose only a supported measurement method. A button/switch command or its mechanical position is not downstream GPIO, voltage or LED response. For graph-based analysis, use `export_graph` with `simulate=true` to clear/recalculate old data; preserve duplicate trace names with `occurrence` and reject out-of-range samples.

Native LOGFILE is host-controlled and buffered until normal process close. Log/GPIO/error steps record their actual request clocks, then acquire final raw data after cleanup. Request GPIO while running/paused, before stopping; its returned `events` include only timestamps through that recorded clock. Keep each traced sequence in one engine epoch: test reset or stop/restart separately. Verification requires the complete final raw-log artifact and its hash, not a partial live file or clipboard view.

Keep requested duration, measured native elapsed time, tolerance, overshoot and completion separate. If actual time is unavailable, retain `actual_time_verified=false` and `simulation_seconds=null`; never substitute wall time, sleep or the requested number. The course timer uses a native request and may lack OCR clock evidence; its counter behavior is independently checked from an actual scope trace.

Verify against an independent design specification, truth table or numerical model. File structure, actual native SDF and measured behavior yield different evidence levels. A completed agent turn, schema check, file save, opened window or command acknowledgement does not establish the circuit behavior. Fresh artifact hashes and revision identity must match before verification.

For the 8255 course recipe, output observation is D0..D7 LED illumination, not direct PB-register access. Require actual SDF wiring, independently read PA0 and same-simulation `1 -> 0 -> 1` with two stable frames per phase. Grey or ambiguous pin markers remain unknown.

Report the task/circuit/session identity, project revision, input/firmware identity, parameters, actual observations, verification level, evidence references and any blocked stage. Do not turn missing evidence or unsupported capability into a pass.
