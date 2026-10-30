---
name: fish-proteus817
description: "Designs, edits, and checks Proteus 8.17 SP2 schematics from a natural-language request in DeepSeek Harness. Use when the user mentions Proteus, a .pdsprj file, drawing or wiring a schematic, an 8086, 8253, or 8255 course circuit, STM32 GPIO simulation, loading firmware onto a Proteus CPU, or asks to simulate or measure a circuit. Discovers installed devices, creates or edits a project, assigns firmware, runs one owned native session, and reports a saved file separately from a measured result."
license: MIT
compatibility: DeepSeek Harness desktop with the companion desktop tool installed once, Windows with Proteus 8.17 SP2, and Python 3.10+. Local device definitions, models, and firmware depend on the task. Model access may require network access.
metadata:
  author: "Fish for Proteus contributors"
  version: "0.3.0"
  source: "https://github.com/Lorentz-Caldfilis/fish-proteus817-skill"
---

# Proteus 8.17 circuit design

Use `fish_proteus_design` for the user's circuit. Work from the devices, pins, and models on this machine. Answer in the user's language.

The companion repository supplies the backend. Copying this folder does not register the tool. If `fish_proteus_design` is missing, say the desktop integration is not installed and point to the repository setup. Do not invent tool results. The skill is [MIT](LICENSE.txt). Proteus itself is separate.

## When to use it

Use it for a Proteus schematic, an edit to one, firmware on a Proteus CPU, a simulation, or a measurement. Also use it for the optional 8086 divider, cascaded 8253 counters, and 8255 LED switch. Those course cases are recipes, not the whole job.

Do not use it for PCB layout, an unsupported Proteus version, or a graph or probe that has to be created from scratch.

## Steps

1. Call `capabilities` when you are starting or the machine looks wrong.
2. Ask only when a design choice cannot be inferred. Otherwise search the installed libraries and inspect the real pins before you connect anything. The same name can exist in two libraries.
3. Use `create` for a new sheet, `open` for a layout this tool recognizes, and `stage` when a native run must keep an opaque project. A failed open is a limitation. Do not replace the original with a blank sheet.
4. The desktop adapter owns task ids, revisions, and storage. Use `task_create` for another circuit, `task_list` and `task_select` to return to one, and `resource_register` when the user gives you a project or a firmware file. Do not ask the user for internal ids or a job directory.
5. Submit related edits together, then read the saved file. Coordinates are native integers: **100000 = 1 mm**. Automatic routing does not promise a tidy drawing.
6. Bind interactive controls before the native session. For CM3 GPIO, set the processor's trace property before that session too. Keep one stimulus and its response inside one `run_sequence`.
7. Report the project path the tool returned. Say which of these you actually have: a saved file, a native structural read, an observation, or a check that passed. A command that returned, or a window that opened, is not a measurement.

Read [desktop workflow](references/desktop-workflow.md) before the task and resource calls. Read [the tool contract](references/generic-api.md) before an unfamiliar action. Read [workflow and evidence](references/workflows-and-evidence.md) before a native sequence. Read [course recipes](references/cases-and-evidence.md) only for the 8086 examples.

## Examples

User: "Make an RC low-pass, R = 2.2k, C = 100n. Label input and output. Check the saved wiring and values, and tell me where the project is. Do not claim a simulation."

- Search the resistor and capacitor that are installed, place them, connect them, add labels and ground, save, then inspect the saved values.
- Report `file_verified` if that check passed. Do not start the simulator.

User: "PA0 is an input. Make PA5 follow it on an STM32F103R6, load this ELF, and show the GPIO edges you recorded."

- Register the ELF. Inspect the CPU pins. Configure the tested trace property before the session.
- Keep the input change and the output edge in one `run_sequence`.
- Report the recorded edges and the project path. If the trace was not configured, say the GPIO result is missing.

User: "Open this project, change the resistor to 4.7k, save a copy, and do not simulate."

- Register the path, `open` a working copy, edit, export if the user wants a file outside managed storage.
- If `open` is unsupported, explain that. Do not create a blank design in its place.

## Rules

- Desktop calls may omit `expected_revision`. A revision you do supply is still rejected when it is stale.
- Edits touch managed copies. Originals stay as they were. `project_export` is how a deliverable leaves managed storage.
- Sample projects may donate a format container, a device definition, or an instrument. Say so. Do not present a copied sample as a circuit you designed.
- Verify against a check chosen before the measurement. Unavailable measurements stay unverified.
- Headless deployments that already pin their own operations are a separate setup. Do not apply those launch rules to a normal desktop chat.
