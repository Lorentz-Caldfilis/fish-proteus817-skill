# Cases and evidence

These are optional 8086 course recipes, not the generic API's capability ceiling. Use the legacy `fish_proteus` tool or `python -m fish_proteus` for them; use `fish_proteus_design` for new circuit composition.

## Recipe commands

Start with `python -m fish_proteus doctor`. Import references using `import-course --source '<originals>' --destination '<unused-library>'`. Prepare with `prepare --library '<library>' --case divider --divisor N --output '<new-job>'`; alternatively use `--case cascade --divisor0 N0 --divisor1 N1` or `--case switch --on-value V --off-value W [--invert]`. Then use `build`, `run --seconds N`, and `verify`, each with the returned `--manifest '<job.json>'`.

The legacy tool uses `operation` doctor/prepare/build/run/verify, `case` divider/cascade/switch and numerical divisor/divisor0/divisor1/on_value/off_value/invert fields. Its library/job paths are host-fixed. Enable runtime operations explicitly; choose an observation interval appropriate to the expected period.

The original examples are supplied locally by the course. Import them using the companion repository's Python CLI; the skill package alone does not include that backend. This skill does not distribute Proteus, device models, teacher projects or the MASM tools. The local course-import manifest identifies the supplied inputs by hash.

## Numerical expectations

- `divider`: the supplied source configures CNT0 with mode-3 control word `36h`. For the provided 1 MHz input and divisor 5, the expected steady-state output frequency is 200,000 Hz and the period is 5 microseconds. The odd-divisor high/low durations need not be equal. Confirm observations at the counter output used by the actual circuit.
- `cascade`: the supplied program uses control words `36h` and `76h`, with two initial values of 1000. With the provided 1 MHz input and actual CNT0-to-CNT1 connection, expected frequencies are 1000 Hz after CNT0 and 1 Hz after CNT1. The formula is `f_out = f_in / (N0 * N1)`; verify the actual input frequency and connection before treating that as the measured result.
- `switch`: the supplied program configures the 8255 with `90h`, reads bit 0 at I/O address `280h`, and writes the selected byte at `282h`. Its unmodified branch writes `FFh` for input bit 0 and `00h` for input bit 1. The runtime observes the D0..D7 LED display; `led_mask` is the illumination mask, not a direct reading of the PB register or an arbitrary electrical-level probe. Mechanical switch position, independently observed PA0, the intended output byte and visible LED state remain distinct facts.

Counter values and 8255 output bytes have different ranges. The supported mode-3 counter domain is 2 through 65536; 65536 is intentionally encoded as the hardware's 16-bit zero count. Output bytes range from 0 through 255. Do not silently change a requested value to fit the representation.

## Evidence required for a behavioral claim

Retain the selected natural-language request and the actual DSH skill/tool calls. The job should bind its source, build output and project copy to the original inputs through hashes and explicit paths. The runtime evidence should identify the installed Proteus build, the fresh process/run, the loaded executable and the observed signal values or transitions.

Compare observations against a precomputed numerical expectation or truth table. A screenshot can help explain the run, but it cannot establish a precise frequency or the complete switch truth table on its own. An existing teacher screenshot is reference material, not evidence from the current run.

For counters, the documented pixel reader estimates frequency from same-direction edges, actual grid spacing and the read-back oscilloscope timebase. Retain the screenshot, OCR, parser details and hashes, and report its image-resolution limits. The result is independent of whether the timer's requested duration was verified.

## Switch-display evidence

Before accepting a switch observation, export the actual native SDF and check the supplied circuit's D0..D7 device identities, polarity and PB0..PB7-to-LED connections. Retain the SDF-derived mapping and its file identity. This wiring evidence supports the interpretation of the LED display; it does not turn the image reader into a PB-register API.

Read PA0 separately from the actual labelled input-pin image. Loaded PB pin markers can be grey: grey or otherwise ambiguous colours are unknown and must not be interpreted as bit 1 or silently filled from the expected byte. The supported LED reader uses complete D0..D7 labels and distinguishes green illuminated interiors from black unlit interiors; an ambiguous display blocks the observation.

Collect actual PA0 transitions `1 -> 0 -> 1` in the same simulation/PID, without restarting between states. Each phase needs two consecutive matching input/display observations. Compare the resulting independently acquired `led_mask` against the requested program's truth table only after acquisition. A single screenshot or a commanded switch position cannot replace these observations.

## Requested versus observed simulation time

`--seconds` is a request submitted through the native timed-run command. Native command acknowledgement and a paused menu state do not prove a particular elapsed simulation time. Only independently read numerical native clocks can verify that duration; when OCR cannot resolve it, retain `actual_time_verified=false` and `simulation_seconds=null`. Never substitute wall time, a sleep delay or the requested number as measured simulation time.

The switch branch is event-driven and records stable same-simulation responses; it does not claim that each state ran for exactly the requested duration. Counter functionality is evaluated from actual waveform observations independently of an unverified timing claim.

## Failures and support boundary

Use these operations only with the supported supplied templates and a compatible local runtime. A valid numerical parameter does not guarantee a readable capture. Missing waveform edges, ambiguous LED states, an unsupported Proteus version or an unavailable desktop route must remain an unsuccessful observation. Do not generalize template-specific operation to arbitrary circuits or register access.

For an error or unsupported route, retain `blocked`, `not_run` or the equivalent unsuccessful status. A DSH `final` event reporting completed only proves the agent turn ended; it does not override a failed build, missing observation or failed `verify` command.
