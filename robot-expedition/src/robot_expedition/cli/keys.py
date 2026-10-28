"""Lectura de una tecla sin esperar Enter (macOS/Linux con termios, Windows con msvcrt)."""

from __future__ import annotations

import sys


def read_key() -> str:
    try:
        import msvcrt  # type: ignore[import-not-found]
    except ImportError:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    key = msvcrt.getwch()
    if key in ("\x00", "\xe0"):  # teclas especiales: se descarta el segundo código
        msvcrt.getwch()
        return ""
    return key
