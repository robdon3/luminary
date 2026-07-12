"""Non-blocking single-key input for interactive missions (Unix TTY)."""

from __future__ import annotations

import select
import sys
import termios
import tty
from contextlib import contextmanager
from typing import Iterator, Optional


@contextmanager
def raw_terminal(enabled: bool = True) -> Iterator[None]:
    """Put stdin in cbreak mode so we can read keys without Enter."""
    if not enabled or not sys.stdin.isatty():
        yield
        return
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def poll_key(timeout: float = 0.0) -> Optional[str]:
    """
    Return one character if available, else None.
    timeout: seconds to wait (0 = non-blocking).
    """
    if not sys.stdin.isatty():
        return None
    r, _, _ = select.select([sys.stdin], [], [], timeout)
    if not r:
        return None
    ch = sys.stdin.read(1)
    if ch == "\x1b":
        # swallow short escape sequences (arrows)
        r2, _, _ = select.select([sys.stdin], [], [], 0.01)
        if r2:
            sys.stdin.read(1)
            r3, _, _ = select.select([sys.stdin], [], [], 0.01)
            if r3:
                seq = sys.stdin.read(1)
                if seq == "A":
                    return "UP"
                if seq == "B":
                    return "DOWN"
                if seq == "C":
                    return "RIGHT"
                if seq == "D":
                    return "LEFT"
        return "ESC"
    return ch


def drain_keys() -> list[str]:
    keys: list[str] = []
    while True:
        k = poll_key(0.0)
        if k is None:
            break
        keys.append(k)
    return keys
