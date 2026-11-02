"""Plain-language launch failures. No Win32 imports, so tests can run anywhere."""
from __future__ import annotations


def window_titles(rows) -> list[str]:
    """Visible-or-not titles for one process, parents before their children."""
    found: list[str] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if title and title not in found:
            found.append(title)
        for child in row.get("children") or []:
            if not isinstance(child, dict):
                continue
            child_title = str(child.get("title") or "").strip()
            if child_title and child_title not in found:
                found.append(child_title)
    return found


def launch_blocked_message(*, pid: int, project_stem: str, windows, budget_seconds: float) -> str:
    """Explain a hidden Proteus process that never reached its main window."""
    titles = window_titles(windows)
    listed = "; ".join(titles) if titles else "(no window titles)"
    return (
        f"Proteus PID {pid} did not open a main window titled '{project_stem} - ...' "
        f"within {budget_seconds:g}s. Proteus is started hidden, so a license, update, "
        "or first-run dialog can block startup with nothing on screen. Open Proteus once "
        "by hand, dismiss every dialog, and use the English Proteus 8.17 SP2 interface. "
        "On a slow PC set FISH_PROTEUS_TIMEOUT_SCALE (for example 3). "
        "If C: is frozen, set FISH_PROTEUS_WORKDIR to a writable drive and set TEMP and TMP. "
        f"Window titles still open: {listed}"
    )
