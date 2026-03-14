import ctypes
from ctypes import wintypes
import ctypes.wintypes

# Windows AppBar constants
ABM_NEW          = 0x00000000
ABM_REMOVE       = 0x00000001
ABM_QUERYPOS     = 0x00000002
ABM_SETPOS       = 0x00000003
ABM_GETSTATE     = 0x00000004
ABM_GETTASKBARPOS = 0x00000005
ABM_ACTIVATE     = 0x00000006
ABM_GETAUTOHIDEBAR = 0x00000007
ABM_SETAUTOHIDEBAR = 0x00000008
ABM_WINDOWPOSCHANGED = 0x00000009
ABM_SETSTATE     = 0x0000000A

ABE_LEFT   = 0
ABE_TOP    = 1
ABE_RIGHT  = 2
ABE_BOTTOM = 3

EDGE_MAP = {
    'left':   ABE_LEFT,
    'top':    ABE_TOP,
    'right':  ABE_RIGHT,
    'bottom': ABE_BOTTOM,
}

class APPBARDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize",            wintypes.DWORD),
        ("hWnd",              wintypes.HWND),
        ("uCallbackMessage",  wintypes.UINT),
        ("uEdge",             wintypes.UINT),
        ("rc",                wintypes.RECT),
        ("lParam",            ctypes.c_long),
    ]

shell32 = ctypes.windll.shell32

class AppBar:
    def __init__(self, hwnd: int, thickness: int = 64):
        self._hwnd = hwnd
        self._thickness = thickness
        self._edge = ABE_RIGHT
        self._registered = False
        self._cb_msg = ctypes.windll.user32.RegisterWindowMessageW("AppBarMessage")

    def register(self, edge: str = 'right', screen=None):
        self._edge = EDGE_MAP.get(edge, ABE_RIGHT)

        # Use provided screen geometry or fall back to primary monitor
        if screen:
            self._screen_rect = screen
        else:
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            self._screen_rect = type('R', (), {
                'left':   lambda s: 0,
                'top':    lambda s: 0,
                'width':  lambda s: w,
                'height': lambda s: h,
                'right':  lambda s: w,
                'bottom': lambda s: h,
            })()

        abd = APPBARDATA()
        abd.cbSize = ctypes.sizeof(APPBARDATA)
        abd.hWnd = self._hwnd
        abd.uCallbackMessage = self._cb_msg
        shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(abd))
        self._registered = True
        self._set_pos()

    def unregister(self):
        if not self._registered:
            return
        abd = APPBARDATA()
        abd.cbSize = ctypes.sizeof(APPBARDATA)
        abd.hWnd = self._hwnd
        shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(abd))
        self._registered = False

    def set_edge(self, edge: str):
        saved_screen = getattr(self, '_screen_rect', None)
        self.unregister()
        self.register(edge, screen=saved_screen)

    def _set_pos(self):
        r = self._screen_rect
        sl = r.left()
        st = r.top()
        sw = r.width()
        sh = r.height()

        abd = APPBARDATA()
        abd.cbSize = ctypes.sizeof(APPBARDATA)
        abd.hWnd = self._hwnd
        abd.uEdge = self._edge

        if self._edge == ABE_RIGHT:
            abd.rc.left   = sl + sw - self._thickness
            abd.rc.top    = st
            abd.rc.right  = sl + sw
            abd.rc.bottom = st + sh
        elif self._edge == ABE_LEFT:
            abd.rc.left   = sl
            abd.rc.top    = st
            abd.rc.right  = sl + self._thickness
            abd.rc.bottom = st + sh
        elif self._edge == ABE_TOP:
            abd.rc.left   = sl
            abd.rc.top    = st
            abd.rc.right  = sl + sw
            abd.rc.bottom = st + self._thickness
        elif self._edge == ABE_BOTTOM:
            abd.rc.left   = sl
            abd.rc.top    = st + sh - self._thickness
            abd.rc.right  = sl + sw
            abd.rc.bottom = st + sh

        shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(abd))
        shell32.SHAppBarMessage(ABM_SETPOS,   ctypes.byref(abd))

        ctypes.windll.user32.MoveWindow(
            self._hwnd,
            abd.rc.left, abd.rc.top,
            abd.rc.right  - abd.rc.left,
            abd.rc.bottom - abd.rc.top,
            True
        )