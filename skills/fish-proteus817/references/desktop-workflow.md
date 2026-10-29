# Desktop tasks and resources

The desktop installer registers `fish_proteus_design` in the ordinary DSH desktop profile. It uses the real calling agent's session and working directory. No headless launcher or per-task command line is needed. It leaves other DSH tools and the selected tool mode available.

## Task management

A first design call creates an isolated task automatically. `task_current` reports its current project, `task_list` lists this session's tasks, and `task_select` with an actual `task_id` restores another. `task_create` with an optional `label` starts a distinct task without modifying the earlier one. A task holds one current circuit; use a new task for another circuit. Tasks persist across app restarts. Another DSH conversation has its own task selection.

`expected_revision` is optional in desktop calls: the adapter fills the current revision immediately before execution. If you deliberately supply it, stale values are rejected. File changes outside the managed task are still detected. Automatic task management does not bypass validation or fabricate missing inputs.

## Local resources

Proteus executable, libraries, samples and format template are discovered from the installation. `resources` shows the configuration and currently registered inputs.

| action | Arguments | Use |
| --- | --- | --- |
| `resource_find` | optional `query`, `kind` (`project` or `firmware`), `scope` (`workspace` or `samples`), `limit` | Bounded search in the current DSH directory or installed samples. Returns actual `candidate_id` values. |
| `resource_register` | `kind`, either `path` or `candidate_id`, optional `name` | Register a selected existing `.pdsprj`, ELF or HEX without changing it. Returns an `input_id` and identity. |
| `project_export` | `destination` | Copy the current project and its relative dependencies to a new, non-existing destination directory. |

Use a user-provided local path directly when registering it. Relative paths are relative to the calling conversation's working directory. For discovered files use `candidate_id`; displayed virtual path labels are not filesystem paths. Register project/firmware inputs whenever needed during a task. Use returned IDs for `open`, `stage`, `import_from_project`, `create.template_input` and firmware operations. Do not invent IDs or require the user to restart with a resource manifest.

For an existing project, registration plus `open` creates a managed working copy. For new topology, `create` can use the discovered format template. When a desired device definition is unavailable in a library, a relevant installed or user-provided project can be registered as a definition donor; do not silently present a copied finished sample as a newly designed circuit.

`delivery.project_path` is the actual generated project location. `project_export` preserves firmware already registered or extracted into the task's `inputs`/`firmware` directories and reports the exported location. Opening an existing project does not automatically collect arbitrary files beside its original location: inspect its firmware references, register and assign needed external firmware, or report missing dependencies before claiming a portable export. Keep input originals unchanged, and do not overwrite an existing destination. Raw native evidence is retained locally while the model receives engineering results and evidence identities.

## Design workflow

Interpret the user's functional requirements, inspect local resources, compose or edit the circuit, check saved structure, and choose native measurements where they are needed. These are decisions, not a fixed script. Use the tools already available in DSH for supporting work such as authoring and compiling original firmware when appropriate; the Proteus desktop plugin does not restrict unrelated tools.

Use the generic API help for actual fields. Supply registered firmware IDs rather than literal PROGRAM paths. Controls must be bound in the saved project before the native session starts. Choose expected timing, tolerances and input/output behavior before collecting measurements. The installed models and backend decide actual compatibility; the three course recipes do not limit the design goal.

If the tool is missing, distinguish missing registration from backend execution failure. If an action is unavailable or a specific file/model is unsupported, report that stage. Do not claim simulation success from file edits or a model response.
