---
name: fish-proteus817
description: Design, edit and test supported Proteus 8.17 SP2 circuits from natural-language requests in DeepSeek Harness. Discover local devices and projects, build new schematics or modify copies, load firmware, run simulations and verify measured results. Includes optional 8086 course examples.
license: MIT
compatibility: DeepSeek Harness desktop with the companion desktop tool installed once, Windows with Proteus 8.17 SP2, and Python 3.10+. Local device definitions, models and firmware depend on the task. Model access may require network access.
metadata:
  author: "Fish for Proteus contributors"
  version: "0.3.0"
  source: "https://github.com/Lorentz-Caldfilis/fish-proteus817-skill"
---

# Proteus design and simulation

Use `fish_proteus_design` to turn the user's circuit goal into an editable project and appropriate checks. Work from actual local devices, pins and models. Choose the design and verification method for the request; the course examples are optional recipes, not the available task set.

The [companion repository](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill) supplies the Python/native backend and a desktop installer. Copying this Skill alone does not register its tool. If `fish_proteus_design` is absent, report the missing desktop integration; do not simulate tool results. See [setup](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill/blob/main/README.md). The Skill is [MIT](LICENSE.txt); installed Proteus resources remain separate.

## Work from the user's goal

Check `capabilities` when starting or diagnosing the environment. The desktop adapter automatically manages session-scoped tasks, revisions and storage. Use `task_create` for a distinct new design, `task_list`/`task_select` to resume another design, and `resource_register` when the user supplies a project or firmware. Do not ask the user to prepare internal IDs, job directories or launch arguments. Read [desktop workflow](references/desktop-workflow.md), or `help` topic `desktop`, when using these operations.

Clarify material design choices that cannot be inferred from the request or available resources. Otherwise discover the installed libraries and relevant local samples, inspect definitions and choose a workable approach. Sample projects may supply a format container, device definition or an analysis instrument; distinguish these from the new circuit you design.

Use `create` for new topology, `open` for a recognized existing project, or explicit `stage` for supported native operations on an opaque project. An unsupported open is a reason to explain the limitation, not to replace the original with a blank design. Edits affect managed copies. Use `project_export` when the user wants a deliverable outside managed storage; report the actual generated project location.

## Compose and check

Read the relevant [API contract](references/generic-api.md), also available as `help` topics `actions`, `edits`, `steps` and `assertions`, before unfamiliar calls. Inspect actual device pins and models before connecting; duplicate names can belong to different libraries. Coordinates are native integers: **100000 = 1 mm**.

Submit related edits atomically, then inspect the saved result. Desktop calls may omit `expected_revision`; explicit stale revisions are still rejected. Register firmware and use its returned ID for assignment. Bind interactive controls before opening the native session. Automatic wire routing connects pins but does not guarantee good visible layout.

## Simulate and evaluate

Choose measurements that establish the requested behavior. Read [workflow and evidence](references/workflows-and-evidence.md) for native sequences, power/model setup, timing, GPIO and existing graph CSV. For CM3 GPIO, configure the processor's supported trace property before opening the native session; the reference records the tested STM32 setting. Keep continuous stimulus/response steps in one `run_sequence`; separate calls start separate native sessions. Supported formats, devices and measurements must be checked for the task. Arbitrary Proteus versions, PCB routing and new graph/probe creation are not established capabilities.

Verify against expectations chosen before measurement. Saved structure, native SDF, runtime observations and passed behavioral assertions are different results. A successful command or opened window does not prove circuit behavior; unavailable measurements stay unverified. Report actual results, project location and useful limits without making the user manage internal evidence plumbing.

For the optional 8086 divider, cascade and 8255 examples, read [course recipes](references/cases-and-evidence.md). Existing specialized headless deployments retain their host-selected operations and input registration; those setup rules do not apply to normal desktop use.
