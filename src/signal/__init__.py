"""Signal generation layer.

This package intentionally keeps the project-facing `signal.*` imports. Because
the name overlaps Python's stdlib `signal` module, expose common stdlib symbols
so third-party libraries that import `signal` continue to work in local runs.
"""

from __future__ import annotations

import _signal as _stdlib_signal
from enum import IntEnum


for _name in dir(_stdlib_signal):
    if _name.startswith("__"):
        continue
    globals().setdefault(_name, getattr(_stdlib_signal, _name))


_signal_members = {
    name: getattr(_stdlib_signal, name)
    for name in dir(_stdlib_signal)
    if name.startswith("SIG")
    and name.isupper()
    and name not in {"SIG_DFL", "SIG_IGN"}
    and isinstance(getattr(_stdlib_signal, name), int)
    and getattr(_stdlib_signal, name) > 0
}
Signals = IntEnum("Signals", _signal_members) if _signal_members else IntEnum("Signals", {})
Handlers = IntEnum(
    "Handlers",
    {
        "SIG_DFL": int(getattr(_stdlib_signal, "SIG_DFL", 0)),
        "SIG_IGN": int(getattr(_stdlib_signal, "SIG_IGN", 1)),
    },
)


def __getattr__(name: str):
    """Fallback to the stdlib signal extension module for unknown attributes."""
    return getattr(_stdlib_signal, name)
