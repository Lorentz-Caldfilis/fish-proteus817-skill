# Composable tool contract

Use `fish_proteus_design`; it calls the companion `fish_proteus.design_cli` module. Unknown fields are rejected at every action/operation/step/assertion boundary. Host paths, shell and arbitrary code are not arguments.

In the normal desktop integration, [desktop task and resource actions](desktop-workflow.md)
manage session identity, storage and input registration automatically. Desktop calls
may omit `expected_revision`; an explicitly supplied stale value is still rejected.
`resource_register.path` and `project_export.destination` are selected local files
and output locations, not shell commands. The contracts below describe the shared
design actions; fixed input manifests and operation allowlists under Host/CLI setup
apply to the specialized standalone launcher.

## Identity and results

Every request has `action` and optional `request_id`. Identical request-ID/payload replays return the recorded result; a changed payload with that ID is rejected. Responses contain request/task/circuit/session IDs, `status`, `current`, `data`, `side_effects`, and hashed `evidence_refs`. Copy `current.revision` into `expected_revision` for mutations, running and verification. Use returned artifact IDs and host-registered input IDs; do not invent paths.

`prepared`, `file_verified`, `native_verified`, `runtime_observed`, and `runtime_verified` are distinct levels. File parsing does not establish native or behavioral success. Errors remain `blocked`, `unsupported`, or `failed`. A mixed verification report retains its weakest basis and per-assertion evidence.

## Actions

| action | Required fields | Optional fields / result |
| --- | --- | --- |
| `capabilities` | none | Service/protocol, resources, native profile probe, enabled actions, registered IDs. No GUI starts. |
| `help` | none | `topic`: actions/edits/steps/assertions/workflow. Read fixed reference sections without arbitrary file access. |
| `library_search` | none | `query`, `limit` (1..1000, default 30); actual installed matches. |
| `library_get` | `name` | `library`: exact enumerated library name; definition, pins, defaults, models and hash. |
| `create` | none | `template_input`, `title`; new topology in a format container. One project per task. |
| `open` | `input_id` | Copy a fully recognized existing project, preserving its structure. |
| `stage` | `input_id` | Explicit opaque copy for native/bounded generator operations; no structural reconstruction. |
| `inspect` | none | `ref`, `sections`: components/pins/connections/nets/terminals/wire_labels/power_rails. Structural mode only. |
| `edit` | `expected_revision`, `operations` | `title`; 1..2000 operations, saved as a new revision only after batch success. |
| `generators` | none | Actual existing generator names/properties. |
| `generator_update` | `expected_revision`, `name`, `properties` | Same-width generator values; preserves unknown objects. |
| `firmware_info` | `firmware_id` | Actual ELF/HEX identity/checksums/bounds; not CPU-compatibility proof. |
| `extract_firmware` | none | `member`: exact relative FIRMWARE member, required if ambiguous; returns firmware ID. |
| `graph_sample` | `artifact_id`, `trace`, `x` | `occurrence=0`; interpolate actual CSV within axis bounds. |
| `run_sequence` | `expected_revision`, `steps` | `save_project=true`; 1..128 native steps in one Session/PID. |
| `verify` | `expected_revision`, `assertions` | 1..128 independent declarative checks. |

Native text/titles use printable ASCII in this codec. Query/import/edit/simulation support are separate facts. Unknown single-sheet objects block whole-sheet reconstruction; `stage` is not a fallback blank constructor.

## Edit operations

Each item has `op`. Coordinates are int32 native integers: **100000 = 1 mm**. Angles are degrees, with orthogonal rotations. Logical endpoints use `REF.PIN` obtained from inspection.

| op | Arguments |
| --- | --- |
| `import_device` | `name`; optional `library`, `donor_input` (definitions only) |
| `import_from_project` | `input_id`, `device` |
| `add` | `device`, `ref`, `value`, `x`, `y`; optional `rotation=0`, `mirror_x=false`, `mirror_y=false`, `properties` |
| `update` | `ref`, `changes`: only value/x/y/rotation/mirror_x/mirror_y/properties/label_offsets |
| `move` | `ref`, absolute `x`, `y` |
| `rotate` | `ref`, optional relative `degrees=90` |
| `mirror` | `ref`, optional `axis="x"` (`x` or `y`) |
| `set_properties` | `ref`, `properties` |
| `assign_firmware` | `ref`, `firmware_id`; optional `clock` |
| `bind_controls` | `refs`: 1..5 binary controls, with native ten-slot collision checks |
| `rename` | `ref`, `new_ref` |
| `copy_component` | `ref`, `new_ref`, `x`, `y` |
| `delete_component` | `ref` |
| `connect` | `first`, `second`; optional `points` |
| `disconnect` | `first`; optional `second` (omitted detaches that pin) |
| `set_route` | `first`, `second`, `points`; null restores automatic routing |
| `add_wire_label` | `first`, `second`, `text`; optional `position=[x,y]` |
| `remove_wire_label` | `first`, `second`, `text`; removal scope is the physical net |
| `add_terminal` | `kind`, `name`; optional `pin`, `position`, `rotation` |
| `update_terminal` | `terminal_id`, `changes`: only kind/name/pin/position/rotation |
| `delete_terminal` | `terminal_id` |
| `configure_power` | `rails`; optional `bindings` |

Explicit routes include both actual pin locations and satisfy orthogonal-wire validation. `label_offsets` maps reference/value/device/properties to `[x,y]`. Terminal kinds: label/input/output/bidir/power/ground; isolated terminals need a position. API kind `label` creates a generic terminal ($TERDEFAULT/type 9, native SDF `GT`). Actual wire labels use `add_wire_label` and native SDF `LBL`. Use returned terminal IDs.

`rails` is `{name:voltage}` or `{name:{voltage:number,flags:"POWER"}}`; flags may also be empty. `bindings` maps power names to existing rails. Property keys are uppercase native names; values are printable strings/finite numbers. Literal PROGRAM/file/script paths are disabled: use firmware IDs. Model-file properties may name installed resources only.

## Native steps

Each `steps` item has `op`. A sequence always attempts stop/close and saves its task copy by default. If `save_project=false`, native property/firmware changes require an explicit later save. Total requested run_for time is at most 120 seconds.

| op | Arguments / observation |
| --- | --- |
| `status`, `start`, `pause`, `stop`, `reset` | None; native acknowledgements/state/time. |
| `run_for` | `seconds` (>0..60); optional `timeout` (wall budget 1..120), `tolerance_seconds` (0..1, default .003). |
| `controls` | Actual supported binary controls/positions/bindings. |
| `control_state`, `press`, `release` | `ref`; mechanical state, not downstream response. |
| `set_switch` | `ref`, `closed` boolean. |
| `set_firmware` | `ref`, `firmware_id`; optional `clock`. Stopped state required. |
| `log`, `errors` | Record the request clock; return complete final native LOGFILE text/diagnostics after normal process close, without clipboard operations. |
| `gpio_events` | Optional `ref`, `port`, `pin`; requires model GPIO tracing configured before session open (tested STM32F103R6: `TRACE_GPIO="3"`). Record an active native request clock, then return final-log `events` whose timestamps are at most that clock, not voltages. |
| `netlist` | Actual SDF and parsed tables; stop before compiling. |
| `set_properties` | `ref`, `properties`; stopped state and native read-back. |
| `save` | Native save; stopped state required. |
| `graphs` | Existing graph names/indices. |
| `export_graph` | `graph` name/index; optional `simulate=true`, `timeout=60`; clears/recalculates and returns CSV artifact ID. |

Raw step files, run report, input snapshot, SDF/CSV/logs and hashes remain under the task root. `run_sequence.data.run_artifact_id` identifies the native run; steps/evidence_refs identify other observations. A later project edit makes earlier evidence stale. Check cleanup failures as well as steps.

## Assertions

The host supplies an ASCII temporary LOGFILE, restores the source option at close, copies complete raw bytes into the run directory and removes only its own temporary directory. Model properties cannot select LOGFILE/LOGFILENAME. Deferred data carries `collected_after_close`, `log_complete`, `raw_log_artifact_id`, `raw_log_sha256`, and `through_simulation_seconds`. GPIO uses an `event_timestamp_prefix`; log/errors describe the `complete_final_run`, with original request time recorded separately. No live-window log/clipboard route is used. Request GPIO before stop while its native clock is initialized. A traced sequence rejects reset and stop/restart; independent reset tests may use a sequence without log/GPIO/error observations.

| type | Fields |
| --- | --- |
| `connected` | `pins` (2+ endpoints); optional actual native-netlist `artifact_id` |
| `isolated` | `first`, `second`; optional native-netlist artifact; both pins must exist |
| `component` | `ref`, `fields` subset of device/value/properties; optional native-netlist artifact |
| `csv_range` | Fresh re-simulated CSV `artifact_id`, `trace`, `x`, `minimum`, `maximum`; optional `occurrence=0` |
| `gpio_sequence` | Native GPIO `artifact_id`, `ref`, `port`, `pin`, ordered binary `values` |
| `simulation_time` | Native-run `artifact_id`, zero-based index `step` into its complete `steps` array (the entry must have `op=run_for`), independent `seconds`, `tolerance_seconds` |
| `no_errors` | Actual errors-step `artifact_id` |

Only verified native elapsed time satisfies a time assertion. False/null remains unavailable. GPIO and error verification require successful single-epoch execution, normal-close complete raw logging and matching hashes; GPIO values are reparsed from those raw bytes and must have finite monotonic timestamps. Cached simulate=false CSV, failed native sequences, stale revisions, modified raw data and missing timestamps cannot establish a fresh runtime pass. File assertions do not produce runtime_verified.

Read the saved run's full step indices before asserting time. For a sequence
`[netlist, start, run_for, controls, run_for]`, the eligible `step` indices are
`2` and `4`, not `0` and `1`. The verifier rejects an index that selects another
operation; an incorrect index is not a missing simulation clock.

## Host/CLI setup

Send the same JSON request on stdin to `python -m fish_proteus.design_cli --task-root <task> --inputs-file <host-inputs.json> --allow <actions...>`. Only the host writes that input manifest: `projects`/`firmware` map IDs to read-only originals; `config` contains executable/library_root/samples_root/template_project resource paths.

The DSH launcher uses `--workflow design`, new output/job directories, repeated `--input-project ID=PATH` / `--input-firmware ID=PATH` and optional `--design-config`. Explicitly enable run_sequence through `--allowed-operations`; the default design allowlist is file-only. `--workflow course` retains the legacy tool. Model credentials are not inherited by the Python tool child, and saved global DSH profiles are unchanged.


## Model-only presentation

The DSH model receives a minimized presentation: raw logs, library raw-definition text, binary fields and credentials are omitted; machine paths become virtual resource/input/artifact references. GPIO, native time, engineering values, IDs and source/evidence hashes retain their actual values. Virtual path labels are display-only: use typed input/artifact IDs for calls and firmware identity hashes for path-independent checks. Full CLI reports and raw files remain local; each model presentation links to a hashed local-report reference. This presentation does not grant permission for external model use or assert that unrelated DSH framework context is sanitized.

Pure JSON integers outside JavaScript's safe range (`-9007199254740991` through `9007199254740991`) use their original decimal strings on the tool wire, including 64-bit process creation identities; ordinary numbers and simulation times retain their numeric types. Complete stdout bytes and their hash remain in the local wrapper and are omitted from the model presentation.
