# Agent instructions for DeepSeek Harness desktop setup

When a user asks you to install this repository's Proteus skill in DeepSeek Harness desktop, use this workflow. Reading the repository or requesting a circuit alone is not permission to install. Obtain the user's authorization before changing their desktop profile or installing dependencies. If permission or a shell/filesystem capability is unavailable, explain the blocker and give the commands below; do not claim installation succeeded.

1. Work on the same Windows machine as the user's existing DeepSeek Harness and licensed Proteus 8.17 SP2. Keep this repository in a persistent location: the installed tool uses its paths. Open Harness once to create its profile. Never ask for or handle account credentials.
2. From the repository root, use Python 3.10 or newer and a repository-local virtual environment. In PowerShell:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dsh]"
   .\.venv\Scripts\python.exe tools/dsh_install_desktop.py --dry-run
   ```

   If `.venv` already exists, reuse it only if it is this repository's intended environment and is usable; do not delete or replace an existing environment. Dependency installation needs network access or locally available packages. Read the dry-run JSON, especially `status`, `errors`, and `warnings`.
3. Resolve missing prerequisites using the reported diagnostics. `--dsh-executable` selects the installed desktop executable; `--dsh-home` selects a home only when it is actually the home used by Harness. `FISH_PROTEUS_EXE` selects an installed `PDS.EXE`; other paths are documented in `docs/configuration.md`. Do not invent paths, change unrelated profile settings, download Proteus, or bypass version checks. If a required path or authorization is unavailable, stop and report it.
4. Once dry-run reports `ready` and the user has authorized installation, run the same installer without `--dry-run`, keeping any verified path options. It installs the skill and registers the companion desktop tool together, with backups. Do not use `dsh_install_skill.py` as a substitute for desktop tool registration. If it reports an existing project-level skill that shadows the global one, inspect the reported warning and update it only with the user's authorization and the documented backup-preserving `--update` command.
5. Read the actual result. Report installation only for `installed` or `unchanged`, then check whether `fish_proteus_design` appears in the desktop session and call `capabilities` if available. The installer requests hot reload; if the tool is not available yet, say it is unverified and follow the host's reload instructions. Do not claim a native simulation or a successful model/tool call unless it actually ran. `--uninstall` is available for the managed installation.

For ordinary circuit tasks after installation, follow `skills/fish-proteus817/SKILL.md`. If this agent cannot execute local commands or access the desktop profile, the user must provide an environment with those capabilities.
