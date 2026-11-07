"""Fail closed for the single reviewed pixel/OCR oscilloscope layout."""


def validate_scope_layout(rect, work_area, dpi, visible):
    left, top, right, bottom = rect
    wl, wt, wr, wb = work_area
    if (not visible or dpi != 96 or (right-left, bottom-top) != (1380, 900)
            or not (wl <= left < right <= wr and wt <= top < bottom <= wb)):
        raise ValueError("Unsupported oscilloscope layout: requires a fully visible 1380x900 window at 96 DPI "
                         "inside the monitor work area; no OCR measurement was accepted")


def fit_scope(native, hwnd):
    import ctypes as c
    from ctypes import wintypes as w

    class MonitorInfo(c.Structure):
        _fields_ = [('size', w.DWORD), ('monitor', w.RECT), ('work', w.RECT), ('flags', w.DWORD)]

    u = native.u
    u.MonitorFromWindow.argtypes = (w.HWND, w.DWORD)
    u.MonitorFromWindow.restype = w.HANDLE
    u.GetMonitorInfoW.argtypes = (w.HANDLE, c.POINTER(MonitorInfo))
    info = MonitorInfo(); info.size = c.sizeof(info)
    if not u.GetMonitorInfoW(u.MonitorFromWindow(hwnd, 2), c.byref(info)):
        raise c.WinError(c.get_last_error())
    if not hasattr(u, 'GetDpiForWindow'):
        raise ValueError('Cannot establish scope DPI; fixed-pixel OCR is blocked')
    u.GetDpiForWindow.argtypes = (w.HWND,); u.GetDpiForWindow.restype = w.UINT
    dpi = u.GetDpiForWindow(hwnd)
    area = (info.work.left, info.work.top, info.work.right, info.work.bottom)
    desired = (area[0], area[1], area[0]+1380, area[1]+900)
    validate_scope_layout(desired, area, dpi, True)
    u.SetWindowPos.argtypes = (w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT)
    # NOZORDER | NOACTIVATE, deliberately permit both movement and sizing.
    if not u.SetWindowPos(hwnd, None, area[0], area[1], 1380, 900, 0x14):
        raise c.WinError(c.get_last_error())
    u.GetWindowRect.argtypes = (w.HWND, c.POINTER(w.RECT))
    u.IsWindowVisible.argtypes = (w.HWND,)
    rect = w.RECT()
    if not u.GetWindowRect(hwnd, c.byref(rect)):
        raise c.WinError(c.get_last_error())
    validate_scope_layout((rect.left, rect.top, rect.right, rect.bottom), area,
                          u.GetDpiForWindow(hwnd), bool(u.IsWindowVisible(hwnd)))
