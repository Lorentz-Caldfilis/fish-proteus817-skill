"""Shared Win32 window/menu helpers for PID-scoped Proteus sessions."""
import argparse
import ctypes as c
import json
from ctypes import wintypes as w

u = c.WinDLL("user32", use_last_error=True)
k = c.WinDLL("kernel32", use_last_error=True)
CALLBACK = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
u.GetWindowThreadProcessId.argtypes = (w.HWND, c.POINTER(w.DWORD))
u.GetWindowTextLengthW.argtypes = (w.HWND,)
u.GetWindowTextW.argtypes = (w.HWND, w.LPWSTR, c.c_int)
u.GetClassNameW.argtypes = (w.HWND, w.LPWSTR, c.c_int)
u.GetDlgCtrlID.argtypes = (w.HWND,)
u.IsWindowVisible.argtypes = (w.HWND,)
u.IsWindowEnabled.argtypes = (w.HWND,)
u.GetMenu.argtypes = (w.HWND,)
u.GetMenu.restype = w.HMENU
u.GetSubMenu.argtypes = (w.HMENU, c.c_int)
u.GetSubMenu.restype = w.HMENU
u.GetMenuItemCount.argtypes = (w.HMENU,)
u.GetMenuItemID.argtypes = (w.HMENU, c.c_int)
u.GetMenuItemID.restype = w.UINT
u.GetMenuStringW.argtypes = (w.HMENU, w.UINT, w.LPWSTR, c.c_int, w.UINT)
u.GetMenuState.argtypes = (w.HMENU, w.UINT, w.UINT)
u.PostMessageW.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
k.OpenProcess.argtypes = (w.DWORD, w.BOOL, w.DWORD)
k.OpenProcess.restype = w.HANDLE
k.QueryFullProcessImageNameW.argtypes = (w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD))
k.CloseHandle.argtypes = (w.HANDLE,)


def enable_dpi_awareness():
    """Use physical pixels on this automation thread, without display changes."""
    if hasattr(u,'SetThreadDpiAwarenessContext'):
        u.SetThreadDpiAwarenessContext.argtypes=(c.c_void_p,)
        u.SetThreadDpiAwarenessContext.restype=c.c_void_p
        return bool(u.SetThreadDpiAwarenessContext(c.c_void_p(-4)))
    return False


def windows(pid):
    rows = []

    def describe(hwnd):
        text = c.create_unicode_buffer(u.GetWindowTextLengthW(hwnd) + 1)
        cls = c.create_unicode_buffer(256)
        u.GetWindowTextW(hwnd, text, len(text))
        u.GetClassNameW(hwnd, cls, len(cls))
        return dict(hwnd=hwnd, title=text.value, cls=cls.value, visible=bool(u.IsWindowVisible(hwnd)),
                    control_id=u.GetDlgCtrlID(hwnd), enabled=bool(u.IsWindowEnabled(hwnd)))

    @CALLBACK
    def visit(hwnd, _):
        owner = w.DWORD()
        u.GetWindowThreadProcessId(hwnd, c.byref(owner))
        if owner.value == pid:
            row = describe(hwnd)
            children = []

            @CALLBACK
            def child(handle, _):
                children.append(describe(handle))
                return True

            u.EnumChildWindows(hwnd, child, 0)
            row["children"] = children
            rows.append(row)
        return True

    u.EnumWindows(visit, 0)
    return rows


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



def message(hwnd, code, wp=0, lp=0):
    result = c.c_size_t()
    u.SendMessageTimeoutW.argtypes = (w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,c.POINTER(c.c_size_t))
    u.SendMessageTimeoutW.restype = w.LPARAM
    if not u.SendMessageTimeoutW(hwnd,code,wp,lp,2,3000,c.byref(result)):
        raise RuntimeError("PID-scoped Proteus message timed out")
    return result.value


def refreshed_menus(hwnd):
    """Ask the native owner to refresh command UI; static menu bits are stale."""
    menu=u.GetMenu(hwnd)
    for index in range(u.GetMenuItemCount(menu)):
        sub=u.GetSubMenu(menu,index)
        if sub:
            message(hwnd,0x117,sub,index)  # WM_INITMENUPOPUP
    return menus(menu)
