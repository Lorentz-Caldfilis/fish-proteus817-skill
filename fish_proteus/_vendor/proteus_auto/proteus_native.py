"""Shared Win32 window/menu helpers for PID-scoped Proteus sessions."""
import argparse
import ctypes as c
import json
import os
from ctypes import wintypes as w

if os.name == 'nt':
    # Reuse the verified 8.17 PID-scoped Windows boundary. Unlike the reference
    # enumeration it retains hidden main windows and explicitly marks visibility.
    from runtime_adaptation.native import u,k,CALLBACK
else:
    u=k=CALLBACK=None


def windows(pid):
    if os.name!='nt':raise OSError('Proteus desktop sessions require Windows')
    from runtime_adaptation.native import windows as owned_windows
    return owned_windows(pid)


def menus(menu, prefix=""):
    rows = []
    for index in range(u.GetMenuItemCount(menu)):
        text = c.create_unicode_buffer(512)
        u.GetMenuStringW(menu, index, text, len(text), 0x400)
        label = text.value.replace("&", "").split("\t")[0].strip()
        if not label:
            continue
        path = f"{prefix}/{label}" if prefix else label
        sub = u.GetSubMenu(menu, index)
        if sub:
            rows.extend(menus(sub, path))
        else:
            rows.append(dict(path=path, command_id=u.GetMenuItemID(menu, index),
                             enabled=not bool(u.GetMenuState(menu, index, 0x400) & 3)))
    return rows


def refreshed_menus(hwnd):
    if os.name!='nt':raise OSError('Proteus desktop sessions require Windows')
    from runtime_adaptation.native import refreshed_menus as refresh
    return refresh(hwnd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    # ponytail: labels follow this installation's language; rediscover paths on other versions/locales.
    parser.add_argument("--menu", help="Exact discovered menu path to invoke; default is read-only.")
    args = parser.parse_args()
    process = k.OpenProcess(0x1000, False, args.pid)
    if not process:
        raise c.WinError(c.get_last_error())
    try:
        path = c.create_unicode_buffer(32768)
        size = w.DWORD(len(path))
        if not k.QueryFullProcessImageNameW(process, 0, path, c.byref(size)):
            raise c.WinError(c.get_last_error())
        if path.value.lower().rsplit("\\", 1)[-1] != "pds.exe":
            raise ValueError("The PID must belong to PDS.EXE.")
    finally:
        k.CloseHandle(process)
    rows = windows(args.pid)
    main_windows = [row for row in rows if u.GetMenu(row["hwnd"])]
    if len(main_windows) != 1:
        raise RuntimeError("Expected exactly one Proteus window with a menu.")
    window = main_windows[0]
    entries = menus(u.GetMenu(window["hwnd"]))
    if args.menu:
        matches = [entry for entry in entries if entry["path"] == args.menu]
        if len(matches) != 1 or not matches[0]["enabled"] or not window["enabled"]:
            raise ValueError("Menu is missing, ambiguous, disabled, or blocked by a dialog.")
        if not u.PostMessageW(window["hwnd"], 0x111, matches[0]["command_id"], 0):
            raise c.WinError(c.get_last_error())
        print(json.dumps({"sent": matches[0], "pid": args.pid}))
    else:
        print(json.dumps({"pid": args.pid, "windows": rows, "menus": entries}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

