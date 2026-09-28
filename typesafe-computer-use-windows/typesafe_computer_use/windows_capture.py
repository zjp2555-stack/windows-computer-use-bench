"""Render one HWND with PrintWindow; for GPU-rendered windows, fall back to the screen DC.

PrintWindow on DirectComposition surfaces (QQ NT and other Electron/GPU-rendered apps) returns
a washed-out uniform image even with PW_RENDERFULLCONTENT. A washed capture is detected by edge
strength and, ONLY when the target is the foreground window, redone from the screen DC with the
fallback announced on stdout. Background windows are never screen-captured: without activation
the screen may hold pixels of something else, which is exactly what upstream refuses to risk.
"""

import ctypes
import time
from ctypes import wintypes

from PIL import Image, ImageFilter

gdi = ctypes.WinDLL("gdi32", use_last_error=True)
ui = ctypes.WinDLL("user32", use_last_error=True)
ui.GetWindowDC.argtypes = [wintypes.HWND]
ui.GetWindowDC.restype = wintypes.HDC
ui.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
ui.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
ui.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
ui.GetWindowDpiAwarenessContext.argtypes = [wintypes.HWND]
ui.GetWindowDpiAwarenessContext.restype = ctypes.c_void_p
ui.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
ui.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
ui.GetForegroundWindow.restype = wintypes.HWND
gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi.CreateCompatibleDC.restype = wintypes.HDC
gdi.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi.SelectObject.restype = wintypes.HANDLE
gdi.DeleteObject.argtypes = [wintypes.HANDLE]
gdi.DeleteDC.argtypes = [wintypes.HDC]
gdi.BitBlt.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.DWORD,
]
gdi.GetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.UINT,
]

WASHED_EDGE_MEAN = 2.5  # smoke-bisected 2026-09-27: QQ NT washed capture 0.54, healthy UI 6.6+


def _edge_mean(image: Image.Image) -> float:
    """Text-bearing UI has strong edges; a washed DirectComposition capture has almost none."""
    hist = image.convert("L").filter(ImageFilter.FIND_EDGES).histogram()
    total = sum(hist)
    if not total:
        return 0.0
    return sum(value * count for value, count in enumerate(hist)) / total


def _logical_rect(hwnd: wintypes.HWND) -> tuple[wintypes.RECT, int, int]:
    previous = ui.SetThreadDpiAwarenessContext(ui.GetWindowDpiAwarenessContext(hwnd))
    try:
        logical = wintypes.RECT()
        if not ui.GetWindowRect(hwnd, ctypes.byref(logical)):
            raise OSError("Cannot read target DPI geometry")
        return logical, logical.right - logical.left, logical.bottom - logical.top
    finally:
        ui.SetThreadDpiAwarenessContext(previous)


def _pull_bitmap(dc, bitmap, width, height) -> Image.Image:
    info = BitmapInfo(ctypes.sizeof(BitmapInfo), width, -height, 1, 32, 0, width * height * 4, 0, 0, 0, 0)
    data = ctypes.create_string_buffer(width * height * 4)
    if gdi.GetDIBits(dc, bitmap, 0, height, data, ctypes.byref(info), 0) != height:
        raise OSError("Cannot read capture pixels")
    return Image.frombytes("RGB", (width, height), data.raw, "raw", "BGRX")


class BitmapInfo(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("width", wintypes.LONG),
        ("height", wintypes.LONG),
        ("planes", wintypes.WORD),
        ("bits", wintypes.WORD),
        ("compression", wintypes.DWORD),
        ("imageSize", wintypes.DWORD),
        ("xppm", wintypes.LONG),
        ("yppm", wintypes.LONG),
        ("used", wintypes.DWORD),
        ("important", wintypes.DWORD),
    ]


def capture_window(hwnd, width, height):
    physical_size = (width, height)
    _, width, height = _logical_rect(hwnd)
    dc = ui.GetWindowDC(hwnd)
    memory = gdi.CreateCompatibleDC(dc)
    bitmap = gdi.CreateCompatibleBitmap(dc, width, height)
    old = gdi.SelectObject(memory, bitmap)
    try:
        if not dc or not memory or not bitmap or not ui.PrintWindow(hwnd, memory, 2):
            raise OSError("The application did not render its window. No desktop fallback was used.")
        gdi.SelectObject(memory, old)
        image = _pull_bitmap(dc, bitmap, width, height)
        return image.resize(physical_size) if image.size != physical_size else image
    finally:
        gdi.SelectObject(memory, old)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory)
        ui.ReleaseDC(hwnd, dc)


def _screen_dc_window(hwnd, physical_size):
    """The composited screen content over the window's own rect. Foreground-only by contract."""
    logical, width, height = _logical_rect(hwnd)
    screen = ui.GetDC(None)
    memory = gdi.CreateCompatibleDC(screen)
    bitmap = gdi.CreateCompatibleBitmap(screen, width, height)
    old = gdi.SelectObject(memory, bitmap)
    try:
        if (
            not screen
            or not memory
            or not bitmap
            or not gdi.BitBlt(memory, 0, 0, width, height, screen, logical.left, logical.top, 0x00CC0020 | 0x40000000)
        ):
            raise OSError("Screen DC capture failed")
        gdi.SelectObject(memory, old)
        image = _pull_bitmap(screen, bitmap, width, height)
        return image.resize(physical_size) if image.size != physical_size else image
    finally:
        gdi.SelectObject(memory, old)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory)
        ui.ReleaseDC(None, screen)


def capture_window_with_fallback(hwnd, width, height):
    """PrintWindow first; a washed GPU-rendered capture is redone from the screen DC, foreground only."""
    physical_size = (width, height)
    image = capture_window(hwnd, width, height)
    if _edge_mean(image) >= WASHED_EDGE_MEAN:
        return image
    if ui.GetForegroundWindow() != hwnd:
        return image  # background windows are never screen-captured
    print("capture: PrintWindow produced a washed image (GPU-rendered window); falling back to the screen DC")
    time.sleep(0.4)  # let the activation animation settle, or the frame comes out skewed
    image = _screen_dc_window(hwnd, physical_size)
    return image.resize(physical_size) if image.size != physical_size else image
