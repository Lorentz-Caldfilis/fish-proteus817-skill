"""Capture a single PID-owned window via Win32 PrintWindow, no desktop input."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import struct, zlib

def capture_window(hwnd, destination):
    u,g=c.WinDLL('user32',use_last_error=True),c.WinDLL('gdi32',use_last_error=True)
    u.GetWindowRect.argtypes=(w.HWND,c.POINTER(w.RECT))
    u.GetDC.argtypes=(w.HWND,);u.GetDC.restype=w.HDC
    u.ReleaseDC.argtypes=(w.HWND,w.HDC)
    u.PrintWindow.argtypes=(w.HWND,w.HDC,w.UINT)
    g.CreateCompatibleDC.argtypes=(w.HDC,);g.CreateCompatibleDC.restype=w.HDC
    g.CreateCompatibleBitmap.argtypes=(w.HDC,c.c_int,c.c_int);g.CreateCompatibleBitmap.restype=w.HBITMAP
    g.SelectObject.argtypes=(w.HDC,w.HGDIOBJ);g.SelectObject.restype=w.HGDIOBJ
    g.DeleteObject.argtypes=(w.HGDIOBJ,);g.DeleteDC.argtypes=(w.HDC,)
    g.GetDIBits.argtypes=(w.HDC,w.HBITMAP,w.UINT,w.UINT,c.c_void_p,c.c_void_p,w.UINT)
    rect=w.RECT()
    if not u.GetWindowRect(hwnd,c.byref(rect)):raise c.WinError(c.get_last_error())
    width,height=rect.right-rect.left,rect.bottom-rect.top
    if not 0<width<=10000 or not 0<height<=10000:raise RuntimeError('Invalid window dimensions')
    hdc=u.GetDC(hwnd);mem=g.CreateCompatibleDC(hdc);bmp=g.CreateCompatibleBitmap(hdc,width,height)
    old=g.SelectObject(mem,bmp)
    try:
        if not u.PrintWindow(hwnd,mem,2):raise RuntimeError('PrintWindow failed')
        header=struct.pack('<IiiHHIIIIII',40,width,-height,1,32,0,width*height*4,0,0,0,0)
        info=c.create_string_buffer(header+bytes(1024));data=c.create_string_buffer(width*height*4)
        if g.GetDIBits(mem,bmp,0,height,data,info,0)!=height:raise RuntimeError('GetDIBits failed')
        # Encode true PNG in the standard library; discard BGRX padding.
        raw=data.raw;rows=[]
        for y in range(height):
            row=raw[y*width*4:(y+1)*width*4]
            rgb=bytearray(width*3)
            rgb[0::3]=row[2::4];rgb[1::3]=row[1::4];rgb[2::3]=row[0::4]
            rows.append(b'\0'+rgb)
        def chunk(kind,payload):return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b'')
        destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(png)
        return str(destination)
    finally:
        g.SelectObject(mem,old);g.DeleteObject(bmp);g.DeleteDC(mem);u.ReleaseDC(hwnd,hdc)
